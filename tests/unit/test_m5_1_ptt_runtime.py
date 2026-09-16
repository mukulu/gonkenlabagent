from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gonken_agent.interaction.gpiod_ptt import GpiodPushToTalkHardware, GpiodWakeMonitoringLed, PttHardwareError
from gonken_agent.voice_runtime import PushToTalkVoiceAdapter, run_appliance


class Direction:
    INPUT = "input"
    OUTPUT = "output"


class Bias:
    PULL_UP = "pull_up"


class Value:
    ACTIVE = "active"
    INACTIVE = "inactive"


class FakeLineSettings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeChip:
    def __init__(self, lines, *, label=""):
        self.lines = list(lines)
        self.label = label
        self.closed = False

    def get_info(self):
        return SimpleNamespace(num_lines=len(self.lines), label=self.label)

    def get_line_info(self, offset):
        return SimpleNamespace(name=self.lines[offset])

    def close(self):
        self.closed = True


class FakeRequest:
    def __init__(self):
        self.values = {}
        self.set_calls = []
        self.released = False

    def get_value(self, offset):
        return self.values.get(offset, Value.INACTIVE)

    def set_value(self, offset, value):
        self.values[offset] = value
        self.set_calls.append((offset, value))

    def release(self):
        self.released = True


class FakeGpiod:
    Direction = Direction
    Bias = Bias
    Value = Value
    LineSettings = FakeLineSettings

    def __init__(self, chips, *, labels=None):
        self.chips = {path: list(lines) for path, lines in chips.items()}
        self.labels = dict(labels or {})
        self.requests = []
        self.last_request = None

    def Chip(self, path):
        if path not in self.chips:
            raise OSError("missing")
        return FakeChip(self.chips[path], label=self.labels.get(path, ""))

    def request_lines(self, chip_path, *, consumer, config):
        request = FakeRequest()
        self.requests.append((chip_path, consumer, config))
        self.last_request = request
        return request


class GpiodPttHardwareTests(unittest.TestCase):
    def test_discovers_gpio_by_name_and_requests_pullup_button_and_led_off(self):
        names = [None] * 32
        names[5] = "GPIO17"
        names[9] = "GPIO27"
        gpiod = FakeGpiod({"/dev/gpiochip4": names})
        hardware = GpiodPushToTalkHardware(
            button_bcm=17,
            led_bcm=27,
            gpiod_module=gpiod,
            chip_paths=["/dev/gpiochip4"],
        )
        hardware.open()
        self.assertEqual(len(gpiod.requests), 1)
        chip, consumer, config = gpiod.requests[0]
        self.assertEqual(chip, "/dev/gpiochip4")
        self.assertEqual(consumer, "gonken-agent-ptt")
        self.assertEqual(config[5].kwargs["direction"], Direction.INPUT)
        self.assertEqual(config[5].kwargs["bias"], Bias.PULL_UP)
        self.assertTrue(config[5].kwargs["active_low"])
        self.assertEqual(config[9].kwargs["direction"], Direction.OUTPUT)
        self.assertEqual(config[9].kwargs["output_value"], Value.INACTIVE)
        self.assertEqual(gpiod.last_request.set_calls[-1], (9, Value.INACTIVE))
        identity = hardware.identities()
        self.assertEqual(identity["button_line_offset"], 5)
        self.assertEqual(identity["led_line_offset"], 9)
        self.assertFalse(identity["physical_acceptance_claimed"])

        gpiod.last_request.values[5] = Value.ACTIVE
        self.assertTrue(hardware.pressed())
        hardware.led(True)
        self.assertEqual(gpiod.last_request.set_calls[-1], (9, Value.ACTIVE))
        hardware.close()
        self.assertEqual(gpiod.last_request.set_calls[-1], (9, Value.INACTIVE))
        self.assertTrue(gpiod.last_request.released)

    def test_wake_monitor_led_resolves_by_name_and_is_off_on_close(self):
        names = [None] * 24
        names[7] = "GPIO22"
        gpiod = FakeGpiod({"/dev/gpiochip4": names})
        led = GpiodWakeMonitoringLed(
            logical_bcm=22, gpiod_module=gpiod, chip_paths=["/dev/gpiochip4"]
        )
        led.open()
        metadata = led.metadata()
        self.assertEqual(metadata["line_offset"], 7)
        self.assertFalse(metadata["physical_acceptance_claimed"])
        self.assertEqual(gpiod.last_request.set_calls[-1], (7, Value.INACTIVE))
        led.set(True)
        self.assertEqual(gpiod.last_request.set_calls[-1], (7, Value.ACTIVE))
        led.close()
        self.assertEqual(gpiod.last_request.set_calls[-1], (7, Value.INACTIVE))
        self.assertTrue(gpiod.last_request.released)


    def test_pi5_rp1_label_disambiguates_duplicate_header_gpio_names(self):
        rp1 = [None] * 32
        rp1[17] = "GPIO17"
        rp1[22] = "GPIO22"
        rp1[27] = "GPIO27"
        duplicate = [None] * 24
        duplicate[5] = "GPIO17"
        duplicate[7] = "GPIO22"
        duplicate[9] = "GPIO27"
        module = FakeGpiod(
            {"/dev/gpiochip0": rp1, "/dev/gpiochip4": duplicate},
            labels={"/dev/gpiochip0": "pinctrl-rp1", "/dev/gpiochip4": "other-controller"},
        )

        hardware = GpiodPushToTalkHardware(
            button_bcm=17,
            led_bcm=27,
            gpiod_module=module,
            chip_paths=["/dev/gpiochip0", "/dev/gpiochip4"],
        )
        hardware.open()
        self.assertEqual(hardware.button_identity.chip_path, "/dev/gpiochip0")
        self.assertEqual(hardware.led_identity.chip_path, "/dev/gpiochip0")

        wake = GpiodWakeMonitoringLed(
            logical_bcm=22,
            gpiod_module=module,
            chip_paths=["/dev/gpiochip0", "/dev/gpiochip4"],
        )
        wake.open()
        self.assertEqual(wake.identity.chip_path, "/dev/gpiochip0")
        self.assertEqual(wake.identity.line_offset, 22)

    def test_refuses_missing_ambiguous_or_cross_chip_mappings(self):
        with self.subTest("missing"):
            module = FakeGpiod({"/dev/gpiochip0": ["GPIO27"]})
            hardware = GpiodPushToTalkHardware(
                button_bcm=17, led_bcm=27, gpiod_module=module, chip_paths=["/dev/gpiochip0"]
            )
            with self.assertRaises(PttHardwareError) as ctx:
                hardware.open()
            self.assertEqual(ctx.exception.code, "PTT_GPIO_LINE_NOT_FOUND")
        with self.subTest("ambiguous"):
            module = FakeGpiod({"/dev/gpiochip0": ["GPIO17", "GPIO27"], "/dev/gpiochip4": ["GPIO17"]})
            hardware = GpiodPushToTalkHardware(
                button_bcm=17,
                led_bcm=27,
                gpiod_module=module,
                chip_paths=["/dev/gpiochip0", "/dev/gpiochip4"],
            )
            with self.assertRaises(PttHardwareError) as ctx:
                hardware.open()
            self.assertEqual(ctx.exception.code, "PTT_GPIO_LINE_AMBIGUOUS")
        with self.subTest("cross-chip"):
            module = FakeGpiod({"/dev/gpiochip0": ["GPIO17"], "/dev/gpiochip4": ["GPIO27"]})
            hardware = GpiodPushToTalkHardware(
                button_bcm=17,
                led_bcm=27,
                gpiod_module=module,
                chip_paths=["/dev/gpiochip0", "/dev/gpiochip4"],
            )
            with self.assertRaises(PttHardwareError) as ctx:
                hardware.open()
            self.assertEqual(ctx.exception.code, "PTT_GPIO_CHIP_MISMATCH")


class FakeHardware:
    def __init__(self):
        self.led_calls = []
        self.closed = False

    def led(self, on):
        self.led_calls.append(on)

    def close(self, *, suppress_errors=False):
        self.closed = True


class FakeAudio:
    def __init__(self, root: Path):
        self.root = root
        self.calls = []

    def capture(self, seconds, *, cancel=None, keep_on_cancel=False):
        self.calls.append((seconds, keep_on_cancel))
        deadline = time.monotonic() + 2
        while cancel is not None and not cancel.is_set() and time.monotonic() < deadline:
            time.sleep(0.005)
        path = self.root / "ptt.wav"
        path.write_bytes(b"fixture")
        return path


class FakeAppliance:
    def __init__(self, root: Path):
        self.stop = threading.Event()
        self.audio = FakeAudio(root)
        self.events = []
        self.spoken = []
        self.transcribed = []

    def _event(self, level, code, **fields):
        self.events.append((level, code, fields))

    def _transcribe_captured_audio(self, path):
        self.transcribed.append(Path(path))
        Path(path).unlink(missing_ok=True)
        return "what is the temperature"

    def _answer_question(self, question):
        self.question = question
        return "The room temperature is simulated."

    def speak(self, text):
        self.spoken.append(text)


class PushToTalkVoiceAdapterTests(unittest.TestCase):
    def test_release_preserves_partial_capture_then_processes_and_cleans_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = FakeAppliance(Path(tmp))
            hardware = FakeHardware()
            adapter = PushToTalkVoiceAdapter(app, hardware, max_capture_seconds=30)
            adapter.led(True)
            adapter.start_capture()
            time.sleep(0.03)
            adapter.stop_capture()
            adapter.led(False)
            adapter.submit()
            self.assertEqual(app.audio.calls, [(30, True)])
            self.assertEqual(hardware.led_calls, [True, False])
            self.assertEqual(app.question, "what is the temperature")
            self.assertEqual(app.spoken, ["The room temperature is simulated."])
            self.assertFalse((Path(tmp) / "ptt.wav").exists())
            adapter.close()
            self.assertTrue(hardware.closed)

    def test_discard_removes_max_hold_capture_without_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = FakeAppliance(Path(tmp))
            hardware = FakeHardware()
            adapter = PushToTalkVoiceAdapter(app, hardware)
            adapter.start_capture()
            time.sleep(0.02)
            adapter.stop_capture()
            adapter.discard_capture()
            self.assertFalse((Path(tmp) / "ptt.wav").exists())
            self.assertFalse(app.transcribed)
            adapter.close()


class RunApplianceModeTests(unittest.TestCase):
    def test_push_to_talk_mode_selects_ptt_loop_not_wake_loop(self):
        calls = []

        class FakeVoiceAppliance:
            def __init__(self, config, foreground=False):
                self.stop = threading.Event()

            def request_stop(self, *_args):
                self.stop.set()

            def push_to_talk_loop(self):
                calls.append("ptt")
                return 0

            def wake_loop(self):
                calls.append("wake")
                return 0

            def close(self):
                calls.append("close")

        config = SimpleNamespace(runtime=SimpleNamespace(interaction_mode="push_to_talk"))
        with mock.patch("gonken_agent.voice_runtime.VoiceAppliance", FakeVoiceAppliance):
            self.assertEqual(run_appliance(config), 0)
        self.assertEqual(calls, ["ptt", "close"])


if __name__ == "__main__":
    unittest.main()
