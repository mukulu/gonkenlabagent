from __future__ import annotations

import importlib.util
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
    @mock.patch.object(bluetooth_manager, "route_defaults", return_value=(["bluez_output.fixture"], []))
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

    def test_stack_status_requires_unblocked_powered_controller(self) -> None:
        with mock.patch.object(bluetooth_manager, "controller_status", return_value={"controllers": 1, "soft_blocked": True}), \
             mock.patch.object(bluetooth_manager, "controller_powered", return_value=False), \
             mock.patch.object(bluetooth_manager, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")):
            with self.assertRaises(bluetooth_manager.BluetoothError):
                bluetooth_manager.stack_status("gonken-agent")


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
