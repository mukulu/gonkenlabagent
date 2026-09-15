from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from gonken_agent.config import ConfigError, load_config
from gonken_agent.environment import (
    EnvironmentClient,
    EnvironmentClientError,
    EnvironmentMode,
    FanPower,
    SensorReading,
    SimulatedEnvironmentSensor,
    SimulatedFanActuator,
    SimulationState,
    build_actuator_adapter,
    build_environment_service_core,
    build_sensor_adapter,
    classify_evidence_mode,
)
from gonken_agent.environment.protocol import make_request
from gonken_agent.environment.server import EnvironmentUnixServer

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _env_config(tempdir: str, *, sensor_backend: str = "simulated", relay_backend: str = "simulated", control: bool = True):
    return load_config(
        defaults_path=DEFAULTS,
        site_path=None,
        environ={},
        cli_overrides={
            "extensions.environment.enabled": True,
            "extensions.environment.sensor_backend": sensor_backend,
            "extensions.environment.relay_backend": relay_backend,
            "extensions.environment.simulation_runtime_control_enabled": control,
            "extensions.environment.socket_path": str(Path(tempdir) / "control.sock"),
            "extensions.environment.policy_path": str(Path(tempdir) / "policy.json"),
            "extensions.environment.valid_samples_to_recover": 1,
            "extensions.environment.minimum_dwell_seconds": 0,
        },
    ).config.extensions.environment


class EnvironmentSimulationConfigTests(unittest.TestCase):
    def test_defaults_keep_simulation_control_disabled(self) -> None:
        effective = load_config(defaults_path=DEFAULTS, site_path=None, environ={})
        env = effective.config.extensions.environment
        self.assertEqual(env.sensor_backend, "sht31")
        self.assertEqual(env.relay_backend, "libgpiod")
        self.assertFalse(env.simulation_runtime_control_enabled)
        self.assertEqual(env.simulation_event_history_limit, 128)

    def test_independent_simulation_backend_axes_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary, sensor_backend="simulated", relay_backend="libgpiod")
            self.assertEqual(env.sensor_backend, "simulated")
            self.assertEqual(env.relay_backend, "libgpiod")
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary, sensor_backend="sht31", relay_backend="simulated")
            self.assertEqual(env.sensor_backend, "sht31")
            self.assertEqual(env.relay_backend, "simulated")

    def test_unknown_simulation_backend_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ConfigError, "sensor_backend"):
                _env_config(temporary, sensor_backend="pretend", relay_backend="simulated")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ConfigError, "relay_backend"):
                _env_config(temporary, sensor_backend="simulated", relay_backend="pretend")

    def test_evidence_mode_classifier_keeps_hybrid_modes_distinct(self) -> None:
        self.assertEqual(classify_evidence_mode(sensor_backend="simulated", actuator_backend="simulated"), "HOST_SIMULATION")
        self.assertEqual(classify_evidence_mode(sensor_backend="simulated", actuator_backend="libgpiod"), "TARGET_HYBRID_SENSOR_SIMULATED")
        self.assertEqual(classify_evidence_mode(sensor_backend="sht31", actuator_backend="simulated"), "TARGET_HYBRID_ACTUATOR_SIMULATED")
        self.assertEqual(classify_evidence_mode(sensor_backend="sht31", actuator_backend="libgpiod"), "TARGET_PHYSICAL")


class SimulatedAdapterTests(unittest.TestCase):
    def test_simulated_sensor_persists_reading_and_faults_truthfully(self) -> None:
        clock = ManualClock(10.0)
        state = SimulationState(now=clock)
        sensor = SimulatedEnvironmentSensor(state)
        reading = sensor.read(now_monotonic=clock())
        self.assertFalse(reading.is_valid())
        self.assertEqual(reading.source_backend, "simulated")
        self.assertIsNone(reading.sensor_address)
        self.assertFalse(reading.physical_evidence)

        state.set_sensor(temperature_c=27.5, relative_humidity_pct=51.0)
        reading = sensor.read(now_monotonic=clock())
        self.assertTrue(reading.is_valid())
        self.assertEqual(reading.temperature_c, 27.5)
        self.assertEqual(reading.relative_humidity_pct, 51.0)
        clock.advance(1.0)
        again = sensor.read(now_monotonic=clock())
        self.assertEqual(again.temperature_c, 27.5)

        state.fault_sensor(fault="crc-error")
        fault = sensor.read(now_monotonic=clock())
        self.assertFalse(fault.is_valid())
        self.assertEqual(fault.error_code, "SENSOR_CRC_FAILED")
        self.assertFalse(fault.crc_valid)

    def test_simulated_sensor_rejects_invalid_operator_values(self) -> None:
        state = SimulationState()
        with self.assertRaisesRegex(Exception, "relative_humidity_pct"):
            state.set_sensor(temperature_c=25.0, relative_humidity_pct=150.0)
        with self.assertRaisesRegex(Exception, "temperature_c"):
            state.set_sensor(temperature_c=float("inf"), relative_humidity_pct=50.0)
        with self.assertRaisesRegex(Exception, "unsupported sensor fault"):
            state.fault_sensor(fault="nonsense")

    def test_simulated_actuator_records_power_and_fault_injection_without_gpiod(self) -> None:
        state = SimulationState()
        actuator = SimulatedFanActuator(state)
        actuator.set_power("on")
        self.assertEqual(actuator.commanded_power, FanPower.ON)
        self.assertEqual(actuator.modeled_power, FanPower.ON)
        self.assertFalse(actuator.capabilities().software_speed_control)
        self.assertFalse(actuator.capabilities().fan_motion_observed)

        state.set_actuator_behavior("fail-next-write")
        with self.assertRaisesRegex(Exception, "ACTUATOR_UNAVAILABLE"):
            actuator.set_power("off")
        self.assertEqual(state.actuator_behavior, "normal")
        actuator.safe_off()
        self.assertEqual(actuator.commanded_power, FanPower.OFF)

    def test_factories_select_simulated_backends_without_physical_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary)
            state = SimulationState()
            sensor = build_sensor_adapter(env, simulation_state=state)
            actuator = build_actuator_adapter(env, simulation_state=state)
        self.assertIsInstance(sensor, SimulatedEnvironmentSensor)
        self.assertIsInstance(actuator, SimulatedFanActuator)


class EnvironmentSimulationProtocolTests(unittest.TestCase):
    def test_service_core_supports_simulation_protocol_and_polling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            clock = ManualClock(100.0)
            env = _env_config(temporary, control=True)
            core = build_environment_service_core(env, now=clock)

            status = core.handle(make_request("simulation.status.get"))
            self.assertTrue(status["simulation"]["active"])
            self.assertTrue(status["simulation"]["runtime_control_enabled"])
            self.assertEqual(status["provenance"]["sensor_backend"], "simulated")
            self.assertEqual(status["provenance"]["actuator_backend"], "simulated")
            self.assertEqual(status["provenance"]["evidence_mode"], "HOST_SIMULATION")
            self.assertFalse(status["physical_evidence"])

            core.handle(make_request("simulation.sensor.set", {"temperature_c": 29.0, "relative_humidity_pct": 52.0}))
            core.handle(make_request("policy.update", {"mode": "automatic", "minimum_on_seconds": 0, "minimum_off_seconds": 0}))
            result = core.poll_once()
            self.assertTrue(result["ok"])
            self.assertEqual(result["reading"]["source_backend"], "simulated")
            self.assertEqual(result["state"]["fan_power"], "on")
            self.assertEqual(result["state"]["last_transition_reason"], "AUTO_START_THRESHOLD")
            self.assertEqual(result["provenance"]["sensor_is_simulated"], True)
            self.assertEqual(result["provenance"]["actuator_is_simulated"], True)

            events = core.handle(make_request("events.get", {"limit": 2}))
            self.assertLessEqual(len(events["events"]), 2)
            snapshot = core.handle(make_request("state.snapshot.get"))
            self.assertIn("polling", snapshot)
            self.assertEqual(snapshot["state"]["fan_power"], "on")

    def test_simulation_runtime_control_is_explicitly_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary, control=False)
            core = build_environment_service_core(env)
            status = core.handle(make_request("simulation.status.get"))
            self.assertTrue(status["simulation"]["active"])
            self.assertFalse(status["simulation"]["runtime_control_enabled"])
            with self.assertRaisesRegex(Exception, "SIMULATION_DISABLED"):
                core.handle(make_request("simulation.sensor.set", {"temperature_c": 26.0, "relative_humidity_pct": 50.0}))

    def test_simulation_operations_reject_wrong_backend_axis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary, sensor_backend="sht31", relay_backend="simulated", control=True)
            core = build_environment_service_core(
                env,
                sensor_factory=lambda _env: lambda *, now_monotonic: SensorReading(25.0, 50.0, now_monotonic, source_backend="fake_sht31"),
            )
            with self.assertRaisesRegex(Exception, "SIMULATION_SENSOR_NOT_ACTIVE"):
                core.handle(make_request("simulation.sensor.set", {"temperature_c": 26.0, "relative_humidity_pct": 50.0}))
            result = core.handle(make_request("simulation.actuator.behavior.set", {"behavior": "unavailable"}))
            self.assertEqual(result["simulation"]["actuator"]["behavior"], "unavailable")

    def test_unix_protocol_accepts_simulation_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = _env_config(temporary, control=True)
            core = build_environment_service_core(env)
            server = EnvironmentUnixServer(env.socket_path, core)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = EnvironmentClient(env.socket_path)
                result = client.simulation_sensor_set(temperature_c=27.0, relative_humidity_pct=50.0)
                self.assertEqual(result["simulation"]["sensor"]["temperature_c"], 27.0)
                status = client.simulation_status()
                self.assertEqual(status["provenance"]["evidence_mode"], "HOST_SIMULATION")
                with self.assertRaises(EnvironmentClientError) as caught:
                    client.simulation_sensor_fault("unknown-fault")
                self.assertEqual(caught.exception.code, "SIMULATION_FAULT_INVALID")
            finally:
                server.shutdown()
                server.server_close()

    def test_simulated_actuator_fail_next_write_surfaces_service_error_and_safe_off(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            clock = ManualClock(20.0)
            env = _env_config(temporary, control=True)
            core = build_environment_service_core(env, now=clock)
            core.handle(make_request("simulation.sensor.set", {"temperature_c": 30.0, "relative_humidity_pct": 50.0}))
            core.handle(make_request("policy.update", {"mode": EnvironmentMode.AUTOMATIC.value, "minimum_on_seconds": 0, "minimum_off_seconds": 0}))
            core.handle(make_request("simulation.actuator.behavior.set", {"behavior": "fail-next-write"}))
            result = core.poll_once()
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["code"], "ACTUATOR_UNAVAILABLE")
            self.assertEqual(result["state"]["fan_power"], "off")
            self.assertEqual(core.handle(make_request("simulation.status.get"))["simulation"]["actuator"]["commanded_power"], "off")


if __name__ == "__main__":
    unittest.main()
