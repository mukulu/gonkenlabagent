from __future__ import annotations

import contextlib
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gonken_agent.llm.ollama import OllamaClient
from gonken_agent.audio.process import ProcessFailure
from gonken_agent.voice_runtime import (
    AudioBackend,
    ConversationBrain,
    VoiceAppliance,
    _wake_remainder,
)


class VoiceWakeTests(unittest.TestCase):
    def test_wake_phrase_matches_punctuation_and_one_edit_for_long_brand_token(self) -> None:
        self.assertEqual(_wake_remainder("Hey, GonKen! What time is it?", "Hey Gonken"), "what time is it")
        self.assertEqual(_wake_remainder("hey gonkin tell me a joke", "Hey Gonken"), "tell me a joke")
        self.assertEqual(_wake_remainder("please hey gonken", "Hey Gonken"), "")
        self.assertIsNone(_wake_remainder("hello assistant", "Hey Gonken"))
        self.assertIsNone(_wake_remainder("hay gonken", "Hey Gonken"))

    def test_alsa_card_parser_and_unique_selector(self) -> None:
        output = (
            "card 2: AIRHUG [Generic AIRHUG 01], device 0: USB Audio [USB Audio]\n"
            "card 3: HDMI [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]\n"
        )
        parsed = AudioBackend._parse_cards(output)
        self.assertEqual(parsed[0][0], "plughw:CARD=2,DEV=0")
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
        self.assertEqual(selected, "plughw:CARD=2,DEV=0")

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

    def test_wake_turn_uses_separate_question_window_even_when_wake_capture_has_remainder(self) -> None:
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
        heard = iter(("hey gonken what is", "What is Python?"))
        appliance.capture_text = lambda seconds: next(heard)
        spoken = []
        appliance.speak = lambda text: spoken.append(text)

        class Brain:
            def reply(self, question, stop):
                self.question = question
                stop.set()
                return "Python is a programming language."

        appliance.brain = Brain()
        self.assertEqual(appliance.wake_loop(), 0)
        self.assertEqual(appliance.brain.question, "What is Python?")
        self.assertEqual(spoken[0], "Yes?")
        self.assertEqual(spoken[1], "Python is a programming language.")

    def test_ready_is_published_only_after_real_ready_announcement_playback(self) -> None:
        order = []
        appliance = VoiceAppliance.__new__(VoiceAppliance)
        appliance.config = SimpleNamespace(
            extensions=SimpleNamespace(wake_word=SimpleNamespace(phrase="Hey Gonken"))
        )
        appliance.stop = threading.Event()
        appliance.ready = False
        appliance.publish_ready = False
        appliance._last_wait_code = ""
        appliance.emit = lambda *args, **kwargs: None
        appliance.probe = lambda: {"audio": {"backend": "fixture"}, "model": {"model": "qwen"}}
        appliance.speak = lambda text: order.append(("speak", text))
        appliance._write_ready = lambda probe: order.append(("ready", probe["audio"]["backend"]))
        self.assertTrue(appliance.wait_until_ready())
        self.assertEqual(order[0], ("speak", "GonKen assistant is ready."))
        self.assertEqual(order[1], ("ready", "fixture"))


if __name__ == "__main__":
    unittest.main()
