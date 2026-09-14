import inspect
import os
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path

from gonken_agent.environment import (
    EnvironmentClient,
    EnvironmentClientError,
    EnvironmentController,
    EnvironmentMode,
    EnvironmentPolicy,
    EnvironmentServiceCore,
    EnvironmentUnixServer,
    FanPower,
    PolicyBounds,
    ProtocolError,
    ScriptedSensorSource,
    SensorQuality,
    SensorReading,
)
from gonken_agent.environment.protocol import (
    MAX_REQUEST_BYTES,
    encode_request,
    make_request,
    parse_request_mapping,
    parse_response_bytes,
)
from gonken_agent.environment.service import ServiceIdentity


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


class EnvironmentProtocolTests(unittest.TestCase):
    def test_protocol_rejects_unsafe_or_unknown_shapes(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "UNSUPPORTED_PROTOCOL"):
            parse_request_mapping({"protocol_version": 999, "request_id": "r1", "operation": "status.get", "params": {}})
        with self.assertRaisesRegex(ProtocolError, "UNKNOWN_OPERATION"):
            parse_request_mapping({"protocol_version": 1, "request_id": "r1", "operation": "gpio.set", "params": {}})
        with self.assertRaisesRegex(ProtocolError, "unknown request field"):
            parse_request_mapping({"protocol_version": 1, "request_id": "r1", "operation": "status.get", "params": {}, "shell": "rm -rf /"})
        with self.assertRaisesRegex(ProtocolError, "params must be an object"):
            parse_request_mapping({"protocol_version": 1, "request_id": "r1", "operation": "status.get", "params": []})

    def test_request_encoding_is_bounded(self) -> None:
        request = make_request("status.get", request_id="abc")
        encoded = encode_request(request)
        self.assertLess(len(encoded), MAX_REQUEST_BYTES)
        with self.assertRaisesRegex(ProtocolError, "exceeds maximum size"):
            parse_response_bytes(b"{" + b"x" * (64 * 1024 + 10) + b"}")

    def test_ipc_modules_do_not_import_hardware_or_shell_surfaces(self) -> None:
        import gonken_agent.environment.client as client
        import gonken_agent.environment.protocol as protocol
        import gonken_agent.environment.server as server
        import gonken_agent.environment.service as service

        combined = "\n".join(inspect.getsource(module) for module in (client, protocol, server, service))
        self.assertNotIn("smbus", combined)
        self.assertNotIn("gpiod", combined)
        self.assertNotIn("subprocess", combined)
        self.assertNotIn("set_gpio", combined)
        self.assertNotIn("/bin/sh", combined)


class EnvironmentServiceCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bounds = PolicyBounds()
        self.clock = ManualClock(0.0)
        policy = EnvironmentPolicy.default().updated(bounds=self.bounds, mode=EnvironmentMode.AUTOMATIC, minimum_on_seconds=5, minimum_off_seconds=5)
        self.controller = EnvironmentController(policy=policy, bounds=self.bounds, now_monotonic=self.clock())

    def reading(self, temp: float, rh: float = 60.0) -> SensorReading:
        return SensorReading(
            temperature_c=temp,
            relative_humidity_pct=rh,
            observed_monotonic=self.clock(),
            sensor_address=0x44,
        )

    def test_service_core_exposes_status_health_and_sensor_read_without_physical_claims(self) -> None:
        source = ScriptedSensorSource([self.reading(29.0), self.reading(29.0), self.reading(29.0)])
        core = EnvironmentServiceCore(
            controller=self.controller,
            bounds=self.bounds,
            sensor_read=source.read,
            now=self.clock,
            identity=ServiceIdentity(hardware_backend="host_fake", physical_evidence=False),
        )
        status = core.handle(make_request("status.get"))
        self.assertEqual(status["service"], "READY")
        self.assertEqual(status["physical_evidence"], False)
        self.assertEqual(status["capabilities"]["software_speed_control"], False)

        for now in (1.0, 2.0, 6.0):
            self.clock.set(now)
            observed = core.handle(make_request("sensor.read"))
        self.assertEqual(observed["reading"]["valid"], True)
        self.assertEqual(observed["state"]["sensor_quality"], SensorQuality.READY.value)
        self.assertEqual(observed["state"]["fan_power"], FanPower.ON.value)
        self.assertEqual(observed["physical_evidence"], False)

        health = core.handle(make_request("health.get"))
        self.assertEqual(health["process_alive"], True)
        self.assertEqual(health["ipc_ready"], True)
        self.assertIn(health["overall"], {"READY", "STARTING", "DEGRADED"})

    def test_service_mutations_validate_policy_generation_and_disabled_mode(self) -> None:
        core = EnvironmentServiceCore(controller=self.controller, bounds=self.bounds, now=self.clock)
        policy_result = core.handle(make_request("policy.get"))
        generation = policy_result["policy"]["generation"]
        with self.assertRaisesRegex(Exception, "POLICY_GENERATION_CONFLICT"):
            core.handle(make_request("policy.update", {"expected_generation": generation + 99, "start_c": 30.0}))

        updated = core.handle(make_request("mode.set", {"mode": "disabled"}))
        self.assertEqual(updated["state"]["mode"], EnvironmentMode.DISABLED.value)
        self.assertEqual(updated["state"]["fan_power"], FanPower.OFF.value)
        with self.assertRaisesRegex(Exception, "ENV_DISABLED"):
            core.handle(make_request("fan.set", {"power": "on"}))

    def test_service_rejects_bad_operation_parameters(self) -> None:
        core = EnvironmentServiceCore(controller=self.controller, bounds=self.bounds, now=self.clock)
        with self.assertRaisesRegex(Exception, "power must be a string"):
            core.handle(make_request("fan.set", {"power": True}))
        with self.assertRaisesRegex(Exception, "start_c must be a number"):
            core.handle(make_request("policy.update", {"start_c": "hot"}))
        with self.assertRaisesRegex(Exception, "unknown parameter"):
            core.handle(make_request("policy.update", {"raw_gpio": 23}))
        with self.assertRaisesRegex(Exception, "unknown parameter"):
            core.handle(make_request("status.get", {"verbose_shell": True}))


class EnvironmentUnixIpcTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.socket_path = Path(self.tempdir.name) / "control.sock"
        self.clock = ManualClock(0.0)
        self.bounds = PolicyBounds()
        policy = EnvironmentPolicy.default().updated(bounds=self.bounds, mode=EnvironmentMode.AUTOMATIC, minimum_on_seconds=5, minimum_off_seconds=5)
        controller = EnvironmentController(policy=policy, bounds=self.bounds, now_monotonic=self.clock())
        source = ScriptedSensorSource([
            SensorReading(31.0, 60.0, observed_monotonic=0.0, sensor_address=0x44),
            SensorReading(31.0, 60.0, observed_monotonic=0.0, sensor_address=0x44),
            SensorReading(31.0, 60.0, observed_monotonic=0.0, sensor_address=0x44),
        ])
        core = EnvironmentServiceCore(controller=controller, bounds=self.bounds, sensor_read=source.read, now=self.clock)
        self.server = EnvironmentUnixServer(self.socket_path, core)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.client = EnvironmentClient(self.socket_path, timeout_seconds=2.0)

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)

    def test_unix_socket_contract_status_sensor_fan_mode_policy(self) -> None:
        mode = stat.S_IMODE(os.stat(self.socket_path).st_mode)
        self.assertEqual(mode, 0o660)
        status = self.client.status()
        self.assertEqual(status["service"], "READY")
        self.assertEqual(status["physical_evidence"], False)

        for now in (1.0, 2.0, 6.0):
            self.clock.set(now)
            sensor = self.client.read_sensor()
        self.assertEqual(sensor["state"]["sensor_quality"], SensorQuality.READY.value)
        self.assertEqual(sensor["state"]["fan_power"], FanPower.ON.value)

        manual = self.client.fan_set("off")
        self.assertEqual(manual["state"]["mode"], EnvironmentMode.MANUAL.value)
        self.assertEqual(manual["state"]["fan_power"], FanPower.OFF.value)

        policy = self.client.policy_get()["policy"]
        changed = self.client.policy_update(expected_generation=policy["generation"], mode="semi-automatic", start_c=29.0, stop_c=27.0)
        self.assertEqual(changed["state"]["mode"], EnvironmentMode.SEMI_AUTOMATIC.value)
        self.assertEqual(changed["state"]["policy"]["start_c"], 29.0)
        self.assertEqual(changed["physical_evidence"], False)

    def test_client_surfaces_daemon_rejections_without_fake_success(self) -> None:
        self.client.mode_set("disabled")
        with self.assertRaises(EnvironmentClientError) as caught:
            self.client.fan_set("on")
        self.assertEqual(caught.exception.code, "ENV_DISABLED")

    def test_server_rejects_non_socket_path_and_removes_socket_on_close(self) -> None:
        self.assertTrue(self.socket_path.exists())
        self._stop_server()
        self.assertFalse(self.socket_path.exists())
        blocker = self.socket_path
        blocker.write_text("not a socket", encoding="utf-8")
        with self.assertRaises(OSError):
            EnvironmentUnixServer(blocker, EnvironmentServiceCore.with_defaults(now=self.clock))


if __name__ == "__main__":
    unittest.main()
