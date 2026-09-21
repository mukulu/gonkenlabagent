from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("environment_readiness", ROOT / "scripts/environment_readiness.py")
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


class EnvironmentReadinessTests(unittest.TestCase):
    def fake_agent(self, root: Path, payload: dict[str, object], *, exit_code: int = 0) -> Path:
        path = root / "gonken-agent"
        serialized = json.dumps(payload)
        path.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' {serialized!r}\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def health(self, *, sensor_backend: str, actuator_backend: str) -> dict[str, object]:
        return {
            "overall": "READY",
            "sensor": "ready",
            "actuator": "READY",
            "physical_evidence": False,
            "provenance": {
                "sensor_backend": sensor_backend,
                "actuator_backend": actuator_backend,
                "physical_evidence": False,
                "sensor_is_simulated": sensor_backend == "simulated",
                "actuator_is_simulated": actuator_backend == "simulated",
            },
        }

    def test_real_sensor_simulated_actuator_requires_semantic_sensor_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            agent = self.fake_agent(root, self.health(sensor_backend="sht31", actuator_backend="simulated"))
            result = readiness.probe(agent, "real-sensor-simulated-actuator", timeout=0.1, interval=0)
        self.assertEqual(result["status"], "READY")

    def test_backend_mismatch_fails_instead_of_accepting_process_liveness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            agent = self.fake_agent(root, self.health(sensor_backend="simulated", actuator_backend="simulated"))
            with self.assertRaises(readiness.ReadinessError) as ctx:
                readiness.probe(agent, "real-sensor-simulated-actuator", timeout=0.01, interval=0)
        self.assertEqual(ctx.exception.code, "ENVIRONMENT_SEMANTIC_NOT_READY")

    def test_physical_evidence_claim_is_rejected(self) -> None:
        payload = self.health(sensor_backend="simulated", actuator_backend="simulated")
        payload["physical_evidence"] = True
        with tempfile.TemporaryDirectory() as temporary:
            agent = self.fake_agent(Path(temporary), payload)
            with self.assertRaises(readiness.ReadinessError) as ctx:
                readiness.probe(agent, "full-simulation", timeout=0.01, interval=0)
        self.assertEqual(ctx.exception.code, "ENVIRONMENT_SEMANTIC_NOT_READY")

    def test_full_real_rejects_a_simulated_actuator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            agent = self.fake_agent(Path(temporary), self.health(sensor_backend="sht31", actuator_backend="simulated"))
            with self.assertRaises(readiness.ReadinessError) as ctx:
                readiness.probe(agent, "full-real", timeout=0.1, interval=0)
        self.assertEqual(ctx.exception.code, "ENVIRONMENT_SEMANTIC_NOT_READY")
        self.assertEqual(ctx.exception.status, 75)


if __name__ == "__main__":
    unittest.main()
