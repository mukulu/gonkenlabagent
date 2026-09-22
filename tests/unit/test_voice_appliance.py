from __future__ import annotations

import contextlib
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import PropertyMock

from gonken_agent.llm.ollama import OllamaClient
from gonken_agent.audio.process import ProcessFailure
from gonken_agent.voice_runtime import (
    AudioBackend,
    ConversationBrain,
    EnvironmentTransitionAnnouncer,
    ProcessingCuePlan,
    RollingWakeTranscriptMatcher,
    WakeCapturePipeline,
    WakeCaptureWindow,
    VoiceAppliance,
    VoiceRuntimeError,
    WAKE_MATCHER_VERSION,
    _classify_audio_capture_failure,
    _runtime_release_commit,
    _write_pcm16_mono_wav,
    _transition_announcement_text,
    _wake_remainder,
    wake_matcher_aliases,
)


class VoiceWakeTests(unittest.TestCase):
    def test_wake_phrase_matches_punctuation_and_one_edit_for_long_brand_token(self) -> None:
        self.assertEqual(_wake_remainder("Hey, GonKen! What time is it?", "Hey Gonken"), "what time is it")
        self.assertEqual(_wake_remainder("hey gonkin tell me a joke", "Hey Gonken"), "tell me a joke")
        self.assertEqual(_wake_remainder("please hey gonken", "Hey Gonken"), "")
        self.assertIsNone(_wake_remainder("hello assistant", "Hey Gonken"))
        self.assertIsNone(_wake_remainder("hay gonken", "Hey Gonken"))


    def test_gonken_default_aliases_match_split_tokens_errors_and_legacy_hey_form(self) -> None:
        self.assertEqual(_wake_remainder("GonKen what is the temperature", "GonKen"), "what is the temperature")
        self.assertEqual(_wake_remainder("Gon Ken turn fan off", "GonKen"), "turn fan off")
        self.assertEqual(_wake_remainder("Hey GonKen status", "GonKen"), "status")
        self.assertEqual(_wake_remainder("gonkin tell me a joke", "GonKen"), "tell me a joke")
        self.assertIsNone(_wake_remainder("gone camping is relaxing", "GonKen"))
        self.assertIn("Hey GonKen", wake_matcher_aliases("GonKen"))
        self.assertEqual(wake_matcher_aliases("Hey Gonken"), ["Hey Gonken"])

    def test_rolling_wake_matcher_carries_short_tail_across_capture_windows(self) -> None:
        matcher = RollingWakeTranscriptMatcher("GonKen")
        self.assertIsNone(matcher.observe("gon"))
        match = matcher.observe("ken what is the humidity")
        self.assertIsNotNone(match)
        self.assertEqual(match.remainder, "what is the humidity")
        self.assertEqual(match.matcher_version, WAKE_MATCHER_VERSION)

    def test_wake_capture_pipeline_keeps_capturing_and_drops_stale_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calls = []

            def capture(seconds, *, cancel):
                index = len(calls) + 1
                path = root / f"wake-{index}.wav"
                path.write_bytes(b"fixture")
                calls.append((seconds, path))
                cancel.wait(0.03)
                return path

            pipeline = WakeCapturePipeline(capture, window_seconds=2, queue_size=1)
            pipeline.start()
            deadline = threading.Event()
            for _ in range(50):
                if pipeline.captured_windows >= 3:
                    break
                deadline.wait(0.01)
            self.assertGreaterEqual(pipeline.captured_windows, 3)
            self.assertGreaterEqual(pipeline.dropped_windows, 1)
            newest = pipeline.next_window(timeout=0.2)
            self.assertIsNotNone(newest)
            self.assertEqual(newest.sequence, pipeline.captured_windows)
            newest.path.unlink(missing_ok=True)
            pipeline.stop()
            for _seconds, path in calls:
                self.assertFalse(path.exists(), "stale/cancelled wake windows must be deleted")

    def test_cancelled_capture_does_not_fall_through_to_another_audio_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self._backend_fixture()
            backend.runtime_dir = Path(temporary)
            backend._input_candidates = [("alsa-usb", "one"), ("alsa-usb", "two")]
            cancel = threading.Event()
            cancel.set()
            backend._record_to = mock.Mock()
            with self.assertRaises(VoiceRuntimeError) as caught:
                backend.capture(2, cancel=cancel)
            self.assertEqual(caught.exception.code, "AUDIO_CAPTURE_CANCELLED")
            backend._record_to.assert_not_called()
            self.assertEqual(list(Path(temporary).glob("voice-*.wav")), [])

    def test_processing_cue_plan_cancels_unstarted_cues_when_answer_is_ready(self) -> None:
        plan = ProcessingCuePlan()
        self.assertIsNone(plan.due(elapsed_seconds=0.2, final_ready=False))
        first = plan.due(elapsed_seconds=1.0, final_ready=False)
        self.assertIsNotNone(first)
        self.assertEqual(first.text, "Just a second.")
        plan.mark_spoken(first)
        self.assertIsNone(plan.due(elapsed_seconds=4.5, final_ready=True))
        second = plan.due(elapsed_seconds=4.5, final_ready=False)
        self.assertIsNotNone(second)
        self.assertEqual(second.text, "I'm still working on that.")

    def test_transition_announcement_text_preserves_simulation_and_motion_boundary(self) -> None:
        event = {
            "sequence": 1,
            "source": "controller",
            "event_type": "controller.transition",
            "detail": {"reason": "AUTO_START_THRESHOLD", "fan_power": "on"},
            "provenance": {"sensor_is_simulated": True, "actuator_is_simulated": True},
        }
        text = _transition_announcement_text(event)
        self.assertIn("In simulation", text)
        self.assertEqual(text, "In simulation, fan actuator started.")
        self.assertNotIn("evidence", text)
        event["detail"]["reason"] = "USER_MANUAL_ON"
        self.assertIsNone(_transition_announcement_text(event))

    def test_alsa_card_parser_and_unique_selector(self) -> None:
        output = (
            "card 2: AIRHUG [Generic AIRHUG 01], device 0: USB Audio [USB Audio]\n"
            "card 3: HDMI [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]\n"
        )
        parsed = AudioBackend._parse_cards(output)
        self.assertEqual(parsed[0][0], "plughw:CARD=AIRHUG,DEV=0")
        self.assertIn("AIRHUG", parsed[0][1])

    def test_auto_selector_prefers_one_usb_card_over_hdmi(self) -> None:
        output = (
            "card 0: vc4hdmi [vc4-hdmi-0], device 0: HDMI 0 [HDMI 0]\n"
            "card 2: USB [Generic Conference Audio], device 0: USB Audio [USB Audio]\n"
        )
        appliance = AudioBackend.__new__(AudioBackend)
        completed = SimpleNamespace(returncode=0, stdout=output, stderr="")
        with mock.patch("gonken_agent.voice_runtime._safe_run", return_value=completed):
            selected = appliance._select(Path("/usr/bin/arecord"), "auto")
        self.assertEqual(selected, "plughw:CARD=USB,DEV=0")

    def test_auto_selector_fails_closed_for_multiple_usb_cards(self) -> None:
        output = (
            "card 2: USB [Conference Audio], device 0: USB Audio [USB Audio]\n"
            "card 3: USB2 [Second USB Mic], device 0: USB Audio [USB Audio]\n"
        )
        appliance = AudioBackend.__new__(AudioBackend)
        completed = SimpleNamespace(returncode=0, stdout=output, stderr="")
        with mock.patch("gonken_agent.voice_runtime._safe_run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "AUDIO_DEVICE_AMBIGUOUS"):
                appliance._select(Path("/usr/bin/arecord"), "auto")

    def _backend_fixture(self):
        backend = AudioBackend.__new__(AudioBackend)
        backend.config = SimpleNamespace(audio=SimpleNamespace(input_match="auto", output_match="auto"))
        backend.arecord = Path("/usr/bin/arecord")
        backend.aplay = Path("/usr/bin/aplay")
        backend.pactl = Path("/usr/bin/pactl")
        backend.parecord = Path("/usr/bin/parecord")
        backend.paplay = Path("/usr/bin/paplay")
        backend.input_device = backend.output_device = ""
        backend.input_mode = backend.output_mode = backend.mode = ""
        backend._input_candidates = []
        backend._output_candidates = []
        return backend

    def test_raw_pcm_wrapper_produces_canonical_mono_s16_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "capture.pcm"
            wav = root / "capture.wav"
            raw.write_bytes(b"\x01\x00" * 1600)
            result = _write_pcm16_mono_wav(raw, wav, rate=16000)
            self.assertEqual(result["frames"], 1600)
            with wave.open(str(wav), "rb") as source:
                self.assertEqual(source.getnchannels(), 1)
                self.assertEqual(source.getsampwidth(), 2)
                self.assertEqual(source.getframerate(), 16000)
                self.assertEqual(source.getnframes(), 1600)

    def test_audio_failure_classifier_preserves_actionable_reason_classes(self) -> None:
        self.assertEqual(
            _classify_audio_capture_failure("Connection refused", backend="pulse"),
            "AUDIO_SERVER_UNAVAILABLE",
        )
        self.assertEqual(
            _classify_audio_capture_failure("Permission denied", backend="pulse"),
            "AUDIO_CAPTURE_PERMISSION_DENIED",
        )
        self.assertEqual(
            _classify_audio_capture_failure("Device or resource busy", backend="alsa"),
            "AUDIO_CAPTURE_DEVICE_BUSY",
        )

    def test_pulse_capture_uses_raw_pcm_then_owns_wav_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self._backend_fixture()
            backend.runtime_dir = Path(temporary)
            backend.config.audio.processing_rate = 16000
            backend.input_device = "alsa_input.usb-AIRHUG"
            backend.input_mode = "pipewire-usb"
            destination = Path(temporary) / "capture.wav"
            observed_args = []

            class FakeProcess:
                def __init__(self, args, stdout):
                    self.returncode = None
                    self.stderr = None
                    observed_args.extend(args)
                    stdout.write(b"\x01\x00" * 1600)
                    stdout.flush()

                def poll(self):
                    return self.returncode

                def send_signal(self, _signal):
                    self.returncode = 0

                def communicate(self, timeout=None):
                    self.returncode = 0
                    return None, ""

                def kill(self):
                    self.returncode = -9

                def wait(self, timeout=None):
                    return self.returncode

            def fake_popen(args, *, stdout, stderr, text):
                return FakeProcess(args, stdout)

            with mock.patch("gonken_agent.voice_runtime.subprocess.Popen", side_effect=fake_popen), \
                 mock.patch("gonken_agent.voice_runtime.time.monotonic", side_effect=[0.0, 2.0]):
                backend._pulse_record_to(destination, 1)
            self.assertIn("--raw", observed_args)
            self.assertNotIn("--file-format=wav", observed_args)
            with wave.open(str(destination), "rb") as source:
                self.assertEqual(source.getframerate(), 16000)
                self.assertEqual(source.getnchannels(), 1)
                self.assertEqual(source.getsampwidth(), 2)

    def test_wired_routes_outrank_connected_bluetooth_when_both_exist(self) -> None:
        backend = self._backend_fixture()
        with mock.patch.object(AudioBackend, "bluetooth_configured", new_callable=PropertyMock, return_value=True), \
             mock.patch.object(backend, "_alsa_candidate", side_effect=["plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0"]), \
             mock.patch.object(backend, "_pulse_usb_candidate", side_effect=[None, None]), \
             mock.patch.object(backend, "_pulse_bluetooth_candidate", side_effect=["bluez_input.AA_BB", "bluez_output.AA_BB"]):
            backend.refresh()
        self.assertEqual(backend.input_mode, "alsa-usb")
        self.assertEqual(backend.output_mode, "alsa-usb")
        self.assertEqual(backend.input_device, "plughw:CARD=A01,DEV=0")
        self.assertEqual(backend.output_device, "plughw:CARD=A01,DEV=0")
        self.assertEqual(backend._input_candidates[-1], ("pipewire-bluetooth", "bluez_input.AA_BB"))
        self.assertEqual(backend._output_candidates[-1], ("pipewire-bluetooth", "bluez_output.AA_BB"))

    def test_pipewire_usb_outranks_direct_usb_and_bluetooth(self) -> None:
        backend = self._backend_fixture()
        with mock.patch.object(AudioBackend, "bluetooth_configured", new_callable=PropertyMock, return_value=True), \
             mock.patch.object(backend, "_alsa_candidate", side_effect=["plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0"]), \
             mock.patch.object(backend, "_pulse_usb_candidate", side_effect=["alsa_input.usb-AIRHUG", "alsa_output.usb-AIRHUG"]), \
             mock.patch.object(backend, "_pulse_bluetooth_candidate", side_effect=["bluez_input.AA_BB", "bluez_output.AA_BB"]):
            backend.refresh()
        self.assertEqual(backend.input_mode, "pipewire-usb")
        self.assertEqual(backend.output_mode, "pipewire-usb")
        self.assertEqual(backend._input_candidates[1], ("alsa-usb", "plughw:CARD=A01,DEV=0"))
        self.assertEqual(backend._input_candidates[2], ("pipewire-bluetooth", "bluez_input.AA_BB"))

    def test_managed_bluetooth_ignores_unrelated_pipewire_endpoint(self) -> None:
        backend = self._backend_fixture()
        with mock.patch.object(AudioBackend, "bluetooth_configured", new_callable=PropertyMock, return_value=True), \
             mock.patch.object(backend, "_managed_bluetooth_token", return_value="41_42_06_42_05_80"), \
             mock.patch.object(backend, "_pulse_names", return_value=["alsa_output.platform-hdmi.stereo"]):
            self.assertIsNone(backend._pulse_bluetooth_candidate("output"))

    def test_bluetooth_routes_are_used_when_no_wired_route_exists(self) -> None:
        backend = self._backend_fixture()
        with mock.patch.object(AudioBackend, "bluetooth_configured", new_callable=PropertyMock, return_value=True), \
             mock.patch.object(backend, "_alsa_candidate", side_effect=[None, None]), \
             mock.patch.object(backend, "_pulse_usb_candidate", side_effect=[None, None]), \
             mock.patch.object(backend, "_pulse_bluetooth_candidate", side_effect=["bluez_input.AA_BB", "bluez_output.AA_BB"]):
            backend.refresh()
        self.assertEqual(backend.input_mode, "pipewire-bluetooth")
        self.assertEqual(backend.output_mode, "pipewire-bluetooth")
        self.assertEqual(backend.mode, "pipewire-bluetooth")

    def test_capture_falls_through_wired_then_bluetooth_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend = self._backend_fixture()
            backend.runtime_dir = Path(temporary)
            backend._input_candidates = [
                ("pipewire-usb", "alsa_input.usb-AIRHUG"),
                ("alsa-usb", "plughw:CARD=A01,DEV=0"),
                ("pipewire-bluetooth", "bluez_input.AA_BB"),
            ]
            backend._output_candidates = [("pipewire-bluetooth", "bluez_output.AA_BB")]
            backend.output_mode, backend.output_device = backend._output_candidates[0]
            backend._record_to = mock.Mock(side_effect=[
                VoiceRuntimeError("AUDIO_CAPTURE_FAILED"),
                VoiceRuntimeError("AUDIO_CAPTURE_FAILED"),
                None,
            ])
            path = backend.capture(1)
            try:
                self.assertEqual(backend.input_mode, "pipewire-bluetooth")
                self.assertEqual(backend.input_device, "bluez_input.AA_BB")
                self.assertEqual(backend._record_to.call_count, 3)
            finally:
                path.unlink(missing_ok=True)

    def test_audio_constructor_defers_physical_route_resolution_until_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch("gonken_agent.voice_runtime._which", return_value=Path("/bin/true")), \
             mock.patch("gonken_agent.voice_runtime._optional_which", return_value=None), \
             mock.patch.object(AudioBackend, "refresh", side_effect=VoiceRuntimeError("AUDIO_INPUT_NOT_FOUND")) as refresh:
            config = SimpleNamespace(paths=SimpleNamespace(runtime_dir=Path(temporary)), audio=SimpleNamespace())
            backend = AudioBackend(config)
        refresh.assert_not_called()
        self.assertEqual(backend._input_candidates, [])
        self.assertEqual(backend._output_candidates, [])



class _FakeConnection:
    def __init__(self):
        self.payload = None

    def request(self, _method, _path, body=None, headers=None):
        import json
        self.payload = json.loads(body)

    def getresponse(self):
        import json
        payload = {
            "model": "qwen3.5:2b-q4_K_M",
            "done": True,
            "message": {"content": "Hello there."},
        }
        data = json.dumps(payload).encode()
        return SimpleNamespace(
            status=200,
            read=lambda _size: data,
            close=lambda: None,
        )

    def close(self):
        pass


class ConversationContractTests(unittest.TestCase):
    def test_plain_chat_disables_thinking_without_json_format(self) -> None:
        config = SimpleNamespace(
            base_url="http://127.0.0.1:11434",
            model="qwen3.5:2b-q4_K_M",
            keep_alive="5m",
            context_tokens=2048,
            max_output_tokens=160,
        )
        client = OllamaClient(config)
        connection = _FakeConnection()
        with mock.patch.object(client, "_connection", return_value=connection):
            result = client.chat_text([{"role": "user", "content": "hello"}], threading.Event())
        self.assertEqual(result, "Hello there.")
        self.assertIs(connection.payload["think"], False)
        self.assertNotIn("format", connection.payload)

    def test_brain_probe_warms_inference_without_adding_history(self) -> None:
        brain = ConversationBrain.__new__(ConversationBrain)
        brain.history = []
        client = mock.Mock()
        client.model_identity.return_value = {"model": "qwen3.5:2b-q4_K_M", "digest": "a" * 64}
        client.chat_text.return_value = "ready"
        brain.client = client
        stop = threading.Event()
        result = brain.probe(stop)
        self.assertEqual(result["model"], "qwen3.5:2b-q4_K_M")
        client.chat_text.assert_called_once()
        self.assertEqual(brain.history, [])


class VoiceTurnTests(unittest.TestCase):
    def test_one_turn_is_capture_transcribe_generate_speak_without_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "captured.wav"
            source.write_bytes(b"fixture")

            class Audio:
                def capture(self, seconds):
                    self.seconds = seconds
                    return source
                def play(self, wav):
                    self.played = Path(wav)

            class Whisper:
                def transcribe(self, path, stop):
                    self.path = Path(path)
                    return "What is Python?"

            class Piper:
                @contextlib.contextmanager
                def synthesize(self, text, stop):
                    self.text = text
                    wav = root / "answer.wav"
                    wav.write_bytes(b"fixture")
                    yield wav

            class Brain:
                def reply(self, question, stop):
                    self.question = question
                    return "Python is a programming language."
                def close(self):
                    self.closed = True

            appliance = VoiceAppliance.__new__(VoiceAppliance)
            appliance.config = SimpleNamespace()
            appliance.emit = lambda *args, **kwargs: None
            appliance.stop = threading.Event()
            appliance.audio = Audio()
            appliance.whisper = Whisper()
            appliance.piper = Piper()
            appliance.brain = Brain()
            appliance.ready = True
            appliance.publish_ready = False
            appliance._last_wait_code = ""
            answer = appliance.one_turn(seconds=7, foreground=False)
            self.assertEqual(answer, "Python is a programming language.")
            self.assertEqual(appliance.audio.seconds, 7)
            self.assertEqual(appliance.brain.question, "What is Python?")
            self.assertEqual(appliance.piper.text, answer)
            self.assertFalse(source.exists(), "raw capture must be deleted after transcription")

    def test_silence_does_not_drop_wake_runtime_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "silence.wav"
            source.write_bytes(b"fixture")

            class Audio:
                def capture(self, _seconds):
                    return source

            class Whisper:
                def transcribe(self, _path, _stop):
                    raise ProcessFailure("STT_OUTPUT_INVALID")

            appliance = VoiceAppliance.__new__(VoiceAppliance)
            appliance.audio = Audio()
            appliance.whisper = Whisper()
            appliance.stop = threading.Event()
            self.assertEqual(appliance.capture_text(2), "")
            self.assertFalse(source.exists(), "silent capture must still be deleted")

    def test_wake_turn_uses_pipelined_standby_and_separate_question_window(self) -> None:
        appliance = VoiceAppliance.__new__(VoiceAppliance)
        appliance.config = SimpleNamespace(
            extensions=SimpleNamespace(wake_word=SimpleNamespace(enabled=True, phrase="Hey Gonken"))
        )
        appliance.stop = threading.Event()
        appliance.ready = True
        appliance.publish_ready = False
        appliance._last_wait_code = ""
        appliance.emit = lambda *args, **kwargs: None
        appliance.wait_until_ready = lambda: True
        source = Path(tempfile.gettempdir()) / "gonken-wake-fixture.wav"
        source.write_bytes(b"fixture")

        class Pipeline:
            window_seconds = 2
            dropped_windows = 0
            def __init__(self):
                self.calls = 0
                self.stopped = False
            def start(self):
                pass
            def next_window(self, *, timeout=0.25):
                self.calls += 1
                return WakeCaptureWindow(1, source, 0.0)
            def stop(self, *, join_timeout=3.0):
                self.stopped = True
                source.unlink(missing_ok=True)

        pipeline = Pipeline()
        appliance._new_wake_capture_pipeline = lambda: pipeline

        class MonitorLed:
            def __init__(self):
                self.states = []
                self.closed = False
            def open(self):
                pass
            def metadata(self):
                return {"logical_bcm": 22, "chip_path": "/dev/gpiochip-test", "line_offset": 22}
            def set(self, state):
                self.states.append(state)
            def close(self, *, suppress_errors=False):
                self.closed = True

        monitor = MonitorLed()
        appliance._new_wake_monitor_led = lambda: monitor
        appliance._transcribe_captured_audio = lambda _path: "hey gonken what is"
        appliance.capture_text = lambda seconds: "What is Python?"
        appliance.transition_announcer = None
        spoken = []
        appliance.speak = lambda text: spoken.append(text)
        appliance.speak_progress_cue = lambda text: spoken.append(text)

        class Brain:
            def reply(self, question, stop):
                self.question = question
                stop.set()
                return "Python is a programming language."

        appliance.brain = Brain()
        self.assertEqual(appliance.wake_loop(), 0)
        self.assertTrue(pipeline.stopped)
        self.assertEqual(monitor.states[:2], [True, False])
        self.assertTrue(monitor.closed)
        self.assertEqual(appliance.brain.question, "What is Python?")
        self.assertEqual(spoken[0], "Yes?")
        self.assertEqual(spoken[1], "Python is a programming language.")


    def test_transition_announcer_returns_one_priority_message_without_daemon_audio_ownership(self) -> None:
        class Client:
            def __init__(self):
                self.calls = 0
            def events(self, *, limit=None):
                self.calls += 1
                return {
                    "events": [
                        {"sequence": 1, "source": "controller", "event_type": "controller.transition",
                         "detail": {"reason": "AUTO_START_THRESHOLD", "fan_power": "on"},
                         "provenance": {"sensor_is_simulated": False, "actuator_is_simulated": False}},
                    ]
                }
        client = Client()
        announcer = EnvironmentTransitionAnnouncer(lambda: client)
        first = announcer.pending()
        self.assertEqual(first, "Fan actuator started.")
        self.assertNotIn("evidence", first)
        self.assertIsNone(announcer.pending())

    def test_ready_is_published_only_after_real_ready_announcement_playback(self) -> None:
        order = []
        appliance = VoiceAppliance.__new__(VoiceAppliance)
        appliance.config = SimpleNamespace(
            runtime=SimpleNamespace(interaction_mode="wake_word"),
            extensions=SimpleNamespace(wake_word=SimpleNamespace(phrase="Hey Gonken")),
        )
        appliance.stop = threading.Event()
        appliance.ready = False
        appliance.publish_ready = False
        appliance._last_wait_code = ""
        appliance.emit = lambda *args, **kwargs: None
        appliance.probe = lambda: {"audio": {"backend": "fixture"}, "model": {"model": "qwen"}}
        appliance.cue_cache = mock.Mock()
        appliance.piper = mock.Mock()
        appliance.speak = lambda text: order.append(("speak", text))
        appliance._write_ready = lambda probe: order.append(("ready", probe["audio"]["backend"]))
        self.assertTrue(appliance.wait_until_ready())
        self.assertEqual(order[0], ("speak", "GonKen assistant is ready."))
        self.assertEqual(order[1], ("ready", "fixture"))


if __name__ == "__main__":
    unittest.main()
