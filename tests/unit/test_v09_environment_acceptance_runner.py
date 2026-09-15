from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/environment_acceptance_runner.py"


class AcceptanceRunnerFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.log = root / "commands.log"
        self.gonken = self._fake("gonken-agent")
        self.systemctl = self._fake("systemctl")
        self.journalctl = self._fake("journalctl")

    def _fake(self, name: str) -> Path:
        path = self.root / name
        path.write_text(
            """#!/usr/bin/env python3
import json
import os
import pathlib
import sys

log = pathlib.Path(os.environ[\"GONKEN_FAKE_COMMAND_LOG\"])
log.parent.mkdir(parents=True, exist_ok=True)
with log.open(\"a\", encoding=\"utf-8\") as handle:
    handle.write(pathlib.Path(sys.argv[0]).name + \" \" + \" \".join(sys.argv[1:]) + \"\\n\")

name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == \"systemctl\":
    if args[:1] == [\"is-active\"]:
        print(\"active\")
        raise SystemExit(0)
    if args[:1] == [\"is-enabled\"]:
        print(\"enabled\")
        raise SystemExit(0)
if name == \"journalctl\":
    print(\"fixture journal line without transcript\")
    raise SystemExit(0)
payload = {
    \"status\": \"PASS\",
    \"command\": args,
    \"physical_evidence\": False,
    \"capabilities\": {
        \"power_control\": True,
        \"software_speed_control\": False,
        \"fan_motion_observed\": False,
    },
    \"reading\": {
        \"temperature_c\": 27.5,
        \"relative_humidity_pct\": 61.0,
        \"quality\": \"VALID\",
    },
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0)
""",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def run(self, *extra: str, output_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
        out = output_dir or (self.root / "out")
        env = os.environ.copy()
        env["GONKEN_FAKE_COMMAND_LOG"] = str(self.log)
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--output-dir",
                str(out),
                "--run-id",
                "fixture-run",
                "--gonken-agent",
                str(self.gonken),
                "--systemctl",
                str(self.systemctl),
                "--journalctl",
                str(self.journalctl),
                *extra,
            ],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )


class EnvironmentAcceptanceRunnerTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], AcceptanceRunnerFixture]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return temporary, AcceptanceRunnerFixture(Path(temporary.name))

    def test_plan_only_writes_private_evidence_without_executing_commands(self) -> None:
        _temporary, fixture = self.fixture()
        result = fixture.run("--plan-only", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((fixture.root / "out/m10_7_evidence_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "gonken-m10.7-environment-evidence-v1")
        self.assertTrue(manifest["plan_only"])
        self.assertFalse(manifest["physical_acceptance_claimed"])
        self.assertFalse(fixture.log.exists(), "plan-only mode must not run target commands")
        blocked = json.loads((fixture.root / "out/private_evidence/m10_7_fan_manual_cycle_blocked.json").read_text(encoding="utf-8"))
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertFalse(blocked["physical_evidence_claimed"])

    def test_default_collection_is_non_destructive_and_blocks_fan_cycle(self) -> None:
        _temporary, fixture = self.fixture()
        result = fixture.run("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = fixture.log.read_text(encoding="utf-8")
        self.assertIn("gonken-agent env status --json", log)
        self.assertIn("gonken-agent env health --json", log)
        self.assertIn("gonken-agent env read --json", log)
        self.assertNotIn("gonken-agent env fan on --json", log)
        self.assertNotIn("gonken-agent env fan off --json", log)
        manifest = json.loads((fixture.root / "out/m10_7_evidence_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["allow_actuation"])
        self.assertFalse(manifest["physical_acceptance_claimed"])
        with (fixture.root / "out/m10_7_private_evidence_ledger.csv").open(encoding="utf-8") as handle:
            ledger_rows = list(csv.DictReader(handle))
        by_id = {row["step_id"]: row for row in ledger_rows}
        self.assertEqual(by_id["m10_7_fan_manual_cycle_blocked"]["status"], "BLOCKED")
        status_step = json.loads((fixture.root / "out/private_evidence/m10_7_env_status_json.json").read_text(encoding="utf-8"))
        self.assertEqual(status_step["status"], "PASS")
        self.assertEqual(status_step["parsed_json"]["capabilities"]["software_speed_control"], False)

    def test_explicit_actuation_runs_fan_cycle_commands_but_still_claims_no_acceptance(self) -> None:
        _temporary, fixture = self.fixture()
        result = fixture.run("--allow-actuation", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = fixture.log.read_text(encoding="utf-8")
        self.assertIn("gonken-agent env fan off --json", log)
        self.assertIn("gonken-agent env fan on --json", log)
        manifest = json.loads((fixture.root / "out/m10_7_evidence_manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["allow_actuation"])
        self.assertFalse(manifest["physical_acceptance_claimed"])
        on_step = json.loads((fixture.root / "out/private_evidence/m10_7_fan_manual_on_cycle.json").read_text(encoding="utf-8"))
        self.assertEqual(on_step["status"], "PASS")
        self.assertEqual(on_step["actuation"], "fan_power_on")
        self.assertFalse(on_step["physical_evidence_claimed"])

    def test_release_payload_includes_environment_acceptance_runner(self) -> None:
        text = (ROOT / "scripts/release_manager.py").read_text(encoding="utf-8")
        self.assertIn("environment_acceptance_runner.py", text)
        self.assertIn("maintenance / \"environment_acceptance_runner.py\"", text)

    def test_target_runbook_references_private_environment_evidence(self) -> None:
        runbook = (ROOT / "docs/RASPBERRY_PI_ACCEPTANCE_RUN.md").read_text(encoding="utf-8")
        self.assertIn("environment_acceptance_runner.py", runbook)
        self.assertIn("--allow-actuation", runbook)
        self.assertIn("physical_acceptance_claimed=false", runbook)


if __name__ == "__main__":
    unittest.main()
