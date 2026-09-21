from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "bluetooth_manager", ROOT / "scripts" / "bluetooth_manager.py"
)
assert SPEC and SPEC.loader
bluetooth_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bluetooth_manager)


class BluetoothManagerTests(unittest.TestCase):
    def test_parse_devices_is_bounded_to_valid_mac_and_single_line_name(self) -> None:
        parsed = bluetooth_manager.parse_devices(
            "Device AA:BB:CC:DD:EE:FF Lab Headset\n"
            "[NEW] Device 11:22:33:44:55:66 Speaker\n"
            "Device invalid nope\n"
        )
        self.assertEqual(
            parsed,
            {
                "AA:BB:CC:DD:EE:FF": "Lab Headset",
                "11:22:33:44:55:66": "Speaker",
            },
        )

    def test_parse_info_distinguishes_output_and_headset_capability(self) -> None:
        info = bluetooth_manager.parse_info(
            "Name: Lab Headset\n"
            "Paired: yes\nTrusted: yes\nConnected: yes\n"
            "UUID: Audio Sink\nUUID: Handsfree\n"
        )
        self.assertTrue(info["paired"])
        self.assertTrue(info["trusted"])
        self.assertTrue(info["connected"])
        self.assertTrue(info["output_capable"])
        self.assertTrue(info["headset_capable"])

    def test_headless_wireplumber_fragment_disables_logind_seat_monitoring(self) -> None:
        fragment = bluetooth_manager.WIREPLUMBER_FRAGMENT
        self.assertIn("monitor.bluez.seat-monitoring = disabled", fragment)
        self.assertNotIn("address", fragment.lower())

    def test_device_record_round_trip_is_closed_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "device.record"
            info = {"output_capable": True, "headset_capable": True}
            bluetooth_manager.write_device_record(
                path,
                address="AA:BB:CC:DD:EE:FF",
                name="Lab Headset",
                audio_user="root",
                info=info,
            )
            parsed = bluetooth_manager.read_device_record(path)
            self.assertEqual(parsed["address"], "AA:BB:CC:DD:EE:FF")
            self.assertEqual(parsed["name"], "Lab Headset")
            self.assertEqual(parsed["output_capable"], "yes")
            self.assertEqual(parsed["headset_capable"], "yes")
            path.write_text(path.read_text() + "unknown=value\n", encoding="utf-8")
            with self.assertRaises(bluetooth_manager.BluetoothError):
                bluetooth_manager.read_device_record(path)

    @mock.patch.object(bluetooth_manager, "write_device_record")
    @mock.patch.object(bluetooth_manager, "route_defaults", return_value=(["bluez_output.fixture"], ["bluez_input.fixture"]))
    @mock.patch.object(bluetooth_manager, "bluetooth_info")
    @mock.patch.object(bluetooth_manager, "resolve_candidate")
    @mock.patch.object(bluetooth_manager, "run")
    @mock.patch.object(bluetooth_manager, "stack_status")
    def test_pairing_requires_verified_paired_trusted_connected_state(
        self,
        stack_status,
        run,
        resolve_candidate,
        bluetooth_info,
        route_defaults,
        write_record,
    ) -> None:
        initial = {
            "paired": False,
            "trusted": False,
            "connected": False,
            "output_capable": True,
            "headset_capable": True,
            "name": "Lab Headset",
        }
        final = dict(initial, paired=True, trusted=True, connected=True)
        resolve_candidate.return_value = (
            "AA:BB:CC:DD:EE:FF",
            "Lab Headset",
            initial,
        )
        bluetooth_info.side_effect = [(initial, ""), (final, "")]
        with mock.patch.object(bluetooth_manager.os, "geteuid", return_value=0):
            bluetooth_manager.pair(
                "Lab Headset",
                "gonken-agent",
                Path("/etc/gonken-agent/bluetooth-device.record"),
                120,
            )
        stack_status.assert_called_once_with("gonken-agent")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any("pair" in command for command in commands))
        self.assertTrue(any("trust" in command for command in commands))
        self.assertTrue(any("connect" in command for command in commands))
        write_record.assert_called_once()


    @mock.patch.object(bluetooth_manager, "bluetooth_info")
    def test_exact_mac_reuses_known_audio_identity_before_scanning(self, bluetooth_info) -> None:
        bluetooth_info.return_value = ({
            "paired": True,
            "trusted": True,
            "connected": False,
            "output_capable": True,
            "headset_capable": True,
            "name": "Known Headset",
        }, "")
        with mock.patch.object(bluetooth_manager, "scan_once") as scan:
            address, name, info = bluetooth_manager.resolve_candidate(
                "AA:BB:CC:DD:EE:FF", 120
            )
        self.assertEqual(address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(name, "Known Headset")
        self.assertTrue(info["paired"])
        scan.assert_not_called()


    def test_parse_capture_cards_matches_voice_runtime_alsa_identity(self) -> None:
        listing = """**** List of CAPTURE Hardware Devices ****
card 2: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
card 3: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
"""
        rows = bluetooth_manager._parse_capture_cards(listing)
        self.assertEqual(rows[0][0], "plughw:CARD=Device,DEV=0")
        self.assertIn("USB", rows[0][1])
        self.assertEqual(rows[0][2], "0")

    def test_direct_capture_fallback_prefers_one_usb_card_and_ignores_hdmi(self) -> None:
        listing = """**** List of CAPTURE Hardware Devices ****
card 2: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
card 3: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
"""
        completed = mock.Mock(returncode=0, stdout=listing, stderr="")
        with mock.patch.object(bluetooth_manager, "run_as_user", return_value=completed):
            selected = bluetooth_manager.direct_capture_fallback("gonken-agent")
        self.assertEqual(selected, "plughw:CARD=Device,DEV=0")

    def test_direct_capture_fallback_refuses_ambiguous_usb_cards(self) -> None:
        listing = """**** List of CAPTURE Hardware Devices ****
card 2: MicA [USB Mic A], device 0: USB Audio [USB Audio]
card 4: MicB [USB Mic B], device 0: USB Audio [USB Audio]
"""
        completed = mock.Mock(returncode=0, stdout=listing, stderr="")
        with mock.patch.object(bluetooth_manager, "run_as_user", return_value=completed):
            with self.assertRaises(bluetooth_manager.BluetoothError) as caught:
                bluetooth_manager.direct_capture_fallback("gonken-agent")
        self.assertEqual(caught.exception.code, "AUDIO_INPUT_AMBIGUOUS")

    def test_headset_profile_prefers_available_msbc_capture_profile(self) -> None:
        listing = """Card #12
	Name: bluez_card.AA_BB_CC_DD_EE_FF
	Profiles:
		a2dp-sink: High Fidelity Playback (A2DP Sink, codec SBC) (sinks: 1, sources: 0, priority: 40, available: yes)
		headset-head-unit-cvsd: Headset Head Unit (HSP/HFP, codec CVSD) (sinks: 1, sources: 1, priority: 30, available: yes)
		headset-head-unit-msbc: Headset Head Unit (HSP/HFP, codec mSBC) (sinks: 1, sources: 1, priority: 35, available: yes)
"""
        completed = mock.Mock(returncode=0, stdout=listing, stderr="")
        with mock.patch.object(bluetooth_manager, "run_as_user", return_value=completed):
            selected = bluetooth_manager._headset_profile("gonken-agent", "AA:BB:CC:DD:EE:FF")
        self.assertEqual(selected, ("bluez_card.AA_BB_CC_DD_EE_FF", "headset-head-unit-msbc"))


    def test_pipewire_nodes_return_each_matching_endpoint_once(self) -> None:
        sink = mock.Mock(returncode=0, stdout="1 bluez_output.AA_BB_CC_DD_EE_FF.1 module s16le\n", stderr="")
        source = mock.Mock(returncode=0, stdout="2 bluez_input.AA_BB_CC_DD_EE_FF.0 module s16le\n", stderr="")
        with mock.patch.object(bluetooth_manager, "run_as_user", side_effect=[sink, source]):
            sinks, sources = bluetooth_manager.pipewire_nodes("gonken-agent", "AA:BB:CC:DD:EE:FF")
        self.assertEqual(sinks, ["bluez_output.AA_BB_CC_DD_EE_FF.1"])
        self.assertEqual(sources, ["bluez_input.AA_BB_CC_DD_EE_FF.0"])

    def test_stack_status_requires_pipewire_bluetooth_plugin_package(self) -> None:
        missing = mock.Mock(returncode=1, stdout="", stderr="no package")
        with mock.patch.object(bluetooth_manager, "ensure_controller_ready"), \
             mock.patch.object(bluetooth_manager.shutil, "which", return_value="/usr/bin/tool"), \
             mock.patch.object(bluetooth_manager, "run", return_value=missing):
            with self.assertRaises(bluetooth_manager.BluetoothError) as caught:
                bluetooth_manager.stack_status("gonken-agent")
        self.assertEqual(caught.exception.code, "BLUETOOTH_PIPEWIRE_PLUGIN")

    def test_stack_status_requires_unblocked_powered_controller(self) -> None:
        with mock.patch.object(bluetooth_manager, "controller_status", return_value={"controllers": 1, "soft_blocked": True}), \
             mock.patch.object(bluetooth_manager, "controller_powered", return_value=False), \
             mock.patch.object(bluetooth_manager, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")):
            with self.assertRaises(bluetooth_manager.BluetoothError):
                bluetooth_manager.stack_status("gonken-agent")



    def test_connected_headset_status_allows_capture_to_be_proven_by_appliance_gate(self) -> None:
        values = {
            "format": "gonken-bluetooth-audio-v1",
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Lab Headset",
            "audio_user": "gonken-agent",
            "paired_epoch": "1",
            "output_capable": "yes",
            "headset_capable": "yes",
        }
        info = {
            "paired": True, "trusted": True, "connected": True,
            "output_capable": True, "headset_capable": True, "name": "Lab Headset",
        }
        with mock.patch.object(bluetooth_manager, "read_device_record", return_value=values), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(info, "")), \
             mock.patch.object(bluetooth_manager, "pipewire_nodes", return_value=(["bluez_output.fixture"], [])), \
             mock.patch.object(bluetooth_manager, "direct_capture_fallback", return_value="plughw:CARD=Mic,DEV=0"):
            bluetooth_manager.device_status(
                Path("/etc/gonken-agent/bluetooth-device.record"),
                "gonken-agent",
                require_connected=True,
            )

    @mock.patch.object(bluetooth_manager, "write_device_record")
    def test_pairing_allows_output_only_headset_for_direct_microphone_fallback(self, write_record) -> None:
        initial = {
            "paired": True, "trusted": True, "connected": True,
            "output_capable": True, "headset_capable": True, "name": "Lab Headset",
        }
        with mock.patch.object(bluetooth_manager, "stack_status"), \
             mock.patch.object(bluetooth_manager, "resolve_candidate", return_value=("AA:BB:CC:DD:EE:FF", "Lab Headset", initial)), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(initial, "")), \
             mock.patch.object(bluetooth_manager, "route_defaults", return_value=(["bluez_output.fixture"], [])), \
             mock.patch.object(bluetooth_manager, "direct_capture_fallback", return_value="plughw:CARD=Mic,DEV=0"), \
             mock.patch.object(bluetooth_manager, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")), \
             mock.patch.object(bluetooth_manager.os, "geteuid", return_value=0):
            bluetooth_manager.pair(
                "AA:BB:CC:DD:EE:FF",
                "gonken-agent",
                Path("/etc/gonken-agent/bluetooth-device.record"),
                120,
            )
        write_record.assert_called_once()

    @mock.patch.object(bluetooth_manager, "write_device_record")
    def test_pairing_busy_bluetooth_continues_with_deterministic_direct_audio(self, write_record) -> None:
        info = {
            "paired": True, "trusted": True, "connected": False,
            "output_capable": True, "headset_capable": True, "name": "AIRHUG 01",
        }
        with mock.patch.object(bluetooth_manager.time, "sleep") as delay, \
             mock.patch.object(bluetooth_manager, "stack_status"), \
             mock.patch.object(bluetooth_manager, "resolve_candidate", return_value=("41:42:06:42:05:80", "AIRHUG 01", info)), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(info, "")), \
             mock.patch.object(bluetooth_manager, "direct_audio_fallback", return_value=("plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0")), \
             mock.patch.object(bluetooth_manager, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            bluetooth_manager.pair(
                "41:42:06:42:05:80", "gonken-agent", Path("/tmp/device.record"), 15
            )
        write_record.assert_called_once()
        self.assertEqual(delay.call_args_list, [mock.call(0.5)] * 20)

    def test_pairing_busy_bluetooth_without_direct_audio_still_fails(self) -> None:
        info = {
            "paired": True, "trusted": True, "connected": False,
            "output_capable": True, "headset_capable": True, "name": "AIRHUG 01",
        }
        with mock.patch.object(bluetooth_manager.time, "sleep") as delay, \
             mock.patch.object(bluetooth_manager, "stack_status"), \
             mock.patch.object(bluetooth_manager, "resolve_candidate", return_value=("41:42:06:42:05:80", "AIRHUG 01", info)), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(info, "")), \
             mock.patch.object(bluetooth_manager, "direct_audio_fallback", return_value=None), \
             mock.patch.object(bluetooth_manager, "run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            with self.assertRaises(bluetooth_manager.BluetoothError) as raised:
                bluetooth_manager.pair(
                    "41:42:06:42:05:80", "gonken-agent", Path("/tmp/device.record"), 15
                )
        self.assertEqual(raised.exception.code, "BLUETOOTH_CONNECT")
        self.assertEqual(delay.call_args_list, [mock.call(0.5)] * 20)

    def test_disconnected_preferred_bluetooth_status_accepts_direct_audio_fallback(self) -> None:
        values = {
            "format": "gonken-bluetooth-audio-v1",
            "address": "41:42:06:42:05:80",
            "name": "AIRHUG 01",
            "audio_user": "gonken-agent",
            "paired_epoch": "1",
            "output_capable": "yes",
            "headset_capable": "yes",
        }
        info = {
            "paired": True, "trusted": True, "connected": False,
            "output_capable": True, "headset_capable": True, "name": "AIRHUG 01",
        }
        with mock.patch.object(bluetooth_manager, "read_device_record", return_value=values), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(info, "")), \
             mock.patch.object(bluetooth_manager, "direct_audio_fallback", return_value=("plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0")), \
             mock.patch.object(bluetooth_manager, "direct_capture_fallback", return_value="plughw:CARD=A01,DEV=0"):
            bluetooth_manager.device_status(
                Path("/tmp/device.record"),
                "gonken-agent",
                require_connected=True,
                allow_direct_fallback=True,
            )

    def test_direct_status_accepts_deterministic_usb_duplex_without_bluetooth(self) -> None:
        with mock.patch.object(bluetooth_manager, "direct_audio_fallback", return_value=("plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0")):
            routes = bluetooth_manager.direct_status("gonken-agent")
        self.assertEqual(routes, ("plughw:CARD=A01,DEV=0", "plughw:CARD=A01,DEV=0"))

    def test_direct_status_refuses_missing_or_ambiguous_direct_audio(self) -> None:
        with mock.patch.object(bluetooth_manager, "direct_audio_fallback", return_value=None):
            with self.assertRaises(bluetooth_manager.BluetoothError) as raised:
                bluetooth_manager.direct_status("gonken-agent")
        self.assertEqual(raised.exception.code, "AUDIO_DIRECT_UNAVAILABLE")

    def test_direct_playback_fallback_prefers_one_usb_card_and_ignores_hdmi(self) -> None:
        output = """**** List of PLAYBACK Hardware Devices ****
card 0: A01 [AIRHUG 01], device 0: USB Audio [USB Audio]
card 1: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM [MAI PCM]
"""
        with mock.patch.object(
            bluetooth_manager,
            "run_as_user",
            return_value=subprocess.CompletedProcess([], 0, output, ""),
        ):
            selected = bluetooth_manager.direct_playback_fallback("gonken-agent")
        self.assertEqual(selected, "plughw:CARD=A01,DEV=0")

    @mock.patch.object(bluetooth_manager, "write_device_record")
    def test_pairing_fails_early_when_headset_has_no_capture_route(self, write_record) -> None:
        initial = {
            "paired": True, "trusted": True, "connected": True,
            "output_capable": True, "headset_capable": True, "name": "Lab Headset",
        }
        with mock.patch.object(bluetooth_manager, "stack_status"), \
             mock.patch.object(bluetooth_manager, "resolve_candidate", return_value=("AA:BB:CC:DD:EE:FF", "Lab Headset", initial)), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(initial, "")), \
             mock.patch.object(bluetooth_manager, "route_defaults", return_value=(["bluez_output.fixture"], [])), \
             mock.patch.object(bluetooth_manager, "direct_capture_fallback", return_value=None), \
             mock.patch.object(bluetooth_manager, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")), \
             mock.patch.object(bluetooth_manager.os, "geteuid", return_value=0):
            with self.assertRaises(bluetooth_manager.BluetoothError) as caught:
                bluetooth_manager.pair(
                    "AA:BB:CC:DD:EE:FF",
                    "gonken-agent",
                    Path("/etc/gonken-agent/bluetooth-device.record"),
                    120,
                )
        self.assertEqual(caught.exception.code, "BLUETOOTH_INPUT_UNAVAILABLE")
        write_record.assert_not_called()

    def test_connected_headset_status_fails_early_without_any_capture_route(self) -> None:
        values = {
            "format": "gonken-bluetooth-audio-v1",
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Lab Headset",
            "audio_user": "gonken-agent",
            "paired_epoch": "1",
            "output_capable": "yes",
            "headset_capable": "yes",
        }
        info = {
            "paired": True, "trusted": True, "connected": True,
            "output_capable": True, "headset_capable": True, "name": "Lab Headset",
        }
        with mock.patch.object(bluetooth_manager, "read_device_record", return_value=values), \
             mock.patch.object(bluetooth_manager, "bluetooth_info", return_value=(info, "")), \
             mock.patch.object(bluetooth_manager, "pipewire_nodes", return_value=(["bluez_output.fixture"], [])), \
             mock.patch.object(bluetooth_manager, "direct_capture_fallback", return_value=None):
            with self.assertRaises(bluetooth_manager.BluetoothError) as caught:
                bluetooth_manager.device_status(
                    Path("/etc/gonken-agent/bluetooth-device.record"),
                    "gonken-agent",
                    require_connected=True,
                )
        self.assertEqual(caught.exception.code, "BLUETOOTH_INPUT_UNAVAILABLE")

    def test_known_fix4_autoconnect_unit_is_upgraded_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "gonken-bluetooth-autoconnect.service"
            previous = ROOT / "tests/fixtures/systemd/gonken-bluetooth-autoconnect-pre-fix5.service"
            current = ROOT / "packaging/systemd/gonken-bluetooth-autoconnect.service"
            destination.write_text(previous.read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(bluetooth_manager, "AUTOCONNECT_UNIT", destination), \
                 mock.patch.object(bluetooth_manager, "read_device_record", return_value={}), \
                 mock.patch.object(bluetooth_manager, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")), \
                 mock.patch.object(bluetooth_manager.os, "geteuid", return_value=0):
                bluetooth_manager.install_autoconnect(current, Path("/etc/gonken-agent/bluetooth-device.record"))
            self.assertEqual(destination.read_text(encoding="utf-8"), current.read_text(encoding="utf-8"))

    def test_autoconnect_status_detects_managed_template_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "gonken-bluetooth-autoconnect.service"
            previous = ROOT / "tests/fixtures/systemd/gonken-bluetooth-autoconnect-pre-fix5.service"
            current = ROOT / "packaging/systemd/gonken-bluetooth-autoconnect.service"
            destination.write_text(previous.read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(bluetooth_manager, "AUTOCONNECT_UNIT", destination), \
                 mock.patch.object(bluetooth_manager, "read_device_record", return_value={}):
                with self.assertRaises(bluetooth_manager.BluetoothError) as caught:
                    bluetooth_manager.autoconnect_status(Path("/etc/gonken-agent/bluetooth-device.record"), current)
            self.assertEqual(caught.exception.status, 1)

    def test_installer_explicitly_provisions_pipewire_bluetooth_plugin(self) -> None:
        install = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn("libspa-0.2-bluetooth", install)

    def test_fix6_pairing_step_revalidates_connected_output_route(self) -> None:
        install = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
        self.assertIn('"bluetooth_audio_pairing" "2"', install)
        self.assertIn('--require-connected', install)

    def test_autoconnect_unit_is_bounded_to_one_managed_record(self) -> None:
        text = (ROOT / "packaging/systemd/gonken-bluetooth-autoconnect.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("ConditionPathExists=/etc/gonken-agent/bluetooth-device.record", text)
        self.assertIn("bluetooth_manager.py watch", text)
        self.assertIn("NoNewPrivileges=true", text)
        self.assertIn("ProtectSystem=strict", text)
        self.assertIn("ProtectHome=read-only", text)
        self.assertIn("CapabilityBoundingSet=CAP_NET_ADMIN CAP_SETUID CAP_SETGID", text)
        self.assertNotIn("scan", text)
        self.assertNotIn("pair", text)


if __name__ == "__main__":
    unittest.main()
