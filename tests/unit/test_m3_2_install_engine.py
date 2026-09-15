from __future__ import annotations

import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "scripts" / "lib" / "common.sh"
ENGINE = ROOT / "scripts" / "lib" / "install_engine.sh"


def run_engine(body: str) -> subprocess.CompletedProcess[str]:
    script = (
        "set -Euo pipefail\n"
        f"source {shlex.quote(str(COMMON))}\n"
        f"source {shlex.quote(str(ENGINE))}\n"
        f"{body}\n"
    )
    return subprocess.run(
        ["/bin/bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


class StepDefinitionTests(unittest.TestCase):
    def test_complete_step_contract_is_required_and_duplicate_ids_fail(self) -> None:
        body = """
pre() { return 0; }
action() { return 0; }
post() { return 0; }
gonken_register_step alpha 1 pre action post mutations rerun rollback
gonken_register_step alpha 1 pre action post mutations rerun rollback
"""
        result = run_engine(body)
        self.assertEqual(result.returncode, 64)
        self.assertIn("code=INSTALL_STEP_DEFINITION", result.stderr)
        self.assertIn("duplicate step ID", result.stderr)

    def test_invalid_id_version_function_and_metadata_fail_closed(self) -> None:
        bodies = (
            "gonken_register_step 'Bad.ID' 1 missing missing missing x y z",
            "gonken_register_step alpha 0 missing missing missing x y z",
            "gonken_register_step alpha 1 missing missing missing x y z",
            "pre(){ :; }; action(){ :; }; post(){ :; }; "
            "gonken_register_step alpha 1 pre action post '' rerun rollback",
        )
        for body in bodies:
            with self.subTest(body=body):
                result = run_engine(body)
                self.assertEqual(result.returncode, 64)
                self.assertIn("INSTALL_STEP_DEFINITION", result.stderr)


class AtomicRecordTests(unittest.TestCase):
    def test_run_id_collision_gets_a_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            events = Path(temporary)
            result = run_engine(
                f"GONKEN_ENGINE_EVENTS_DIR={shlex.quote(str(events))}; "
                "date(){ printf '123\\n'; }; "
                f"touch {shlex.quote(str(events))}/123.$BASHPID.000001.event; "
                "gonken_allocate_run_id; printf '%s\\n' \"$GONKEN_ENGINE_RUN_ID\""
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^123\.[0-9]+\.1$")

    def test_atomic_record_is_private_and_leaves_no_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            destination = root / "state.record"
            result = run_engine(
                f"gonken_atomic_record {shlex.quote(str(destination))} 0600 "
                "format=test-v1 status=complete"
            )
            mode = stat.S_IMODE(destination.stat().st_mode)
            leftovers = list(root.glob(".gonken-tmp.*"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mode, 0o600)
        self.assertEqual(leftovers, [])

    def test_atomic_record_preserves_callers_umask(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            destination = root / "state.record"
            result = run_engine(
                "umask 0022; before=$(umask); "
                f"gonken_atomic_record {shlex.quote(str(destination))} 0600 format=test-v1; "
                "after=$(umask); printf '%s|%s\\n' \"$before\" \"$after\""
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        before, after = result.stdout.strip().split("|")
        self.assertEqual(after, before)

    def test_private_directory_keeps_parent_traversable_and_preserves_umask(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "service-home"
            private = root / "install"
            result = run_engine(
                "umask 0022; before=$(umask); "
                f"gonken_prepare_private_directory {shlex.quote(str(private))} state; "
                "after=$(umask); printf '%s|%s\\n' \"$before\" \"$after\""
            )
            parent_mode = stat.S_IMODE(root.stat().st_mode)
            private_mode = stat.S_IMODE(private.stat().st_mode)
        self.assertEqual(result.returncode, 0, result.stderr)
        before, after = result.stdout.strip().split("|")
        self.assertEqual(after, before)
        self.assertEqual(parent_mode, 0o755)
        self.assertEqual(private_mode, 0o700)

    def test_known_owned_0755_private_state_can_be_repaired_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / "install"
            private.mkdir()
            private.chmod(0o755)
            result = run_engine(
                f"gonken_prepare_private_directory {shlex.quote(str(private))} "
                "state repair-owned-0755"
            )
            mode = stat.S_IMODE(private.stat().st_mode)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mode, 0o700)
        self.assertIn("code=INSTALL_STATE_REPAIRED", result.stdout)

    def test_private_state_0755_still_fails_without_explicit_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / "install"
            private.mkdir()
            private.chmod(0o755)
            result = run_engine(
                f"gonken_prepare_private_directory {shlex.quote(str(private))} state"
            )
        self.assertEqual(result.returncode, 73)
        self.assertIn("uid=", result.stderr)
        self.assertIn("mode=755", result.stderr)

    def test_known_migration_refuses_group_writable_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary) / "install"
            private.mkdir()
            private.chmod(0o775)
            result = run_engine(
                f"gonken_prepare_private_directory {shlex.quote(str(private))} "
                "state repair-owned-0755"
            )
            mode = stat.S_IMODE(private.stat().st_mode)
        self.assertEqual(result.returncode, 73)
        self.assertEqual(mode, 0o775)

    def test_atomic_record_rejects_symlink_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            target = root / "target"
            target.write_text("unchanged\n", encoding="utf-8")
            destination = root / "state.record"
            destination.symlink_to(target)
            result = run_engine(
                f"gonken_atomic_record {shlex.quote(str(destination))} 0600 format=test-v1"
            )
            content = target.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 73)
        self.assertIn("code=INSTALL_STATE", result.stderr)
        self.assertEqual(content, "unchanged\n")

    def test_record_parser_rejects_unknown_duplicate_and_malformed_lines(self) -> None:
        cases = {
            "unknown": "format=test-v1\nother=value\n",
            "duplicate": "format=test-v1\nformat=again\n",
            "malformed": "format=test-v1\nnot-a-field\n",
        }
        for name, content in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "record"
                path.write_text(content, encoding="utf-8")
                result = run_engine(
                    "allowed=(format); declare -A parsed=(); "
                    f"gonken_read_record {shlex.quote(str(path))} allowed parsed"
                )
                self.assertEqual(result.returncode, 65)
                self.assertIn("code=INSTALL_RECORD", result.stderr)


class EngineFailureTests(unittest.TestCase):
    def run_one_step(self, definitions: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            logs = root / "logs"
            body = f"""
{definitions}
gonken_engine_initialize {shlex.quote(str(state))} {shlex.quote(str(logs))}
gonken_register_step alpha 1 pre action post mutations rerun rollback
gonken_run_registered_steps
"""
            return run_engine(body)

    def test_precondition_exit_code_is_preserved(self) -> None:
        result = self.run_one_step(
            "pre(){ return 43; }; action(){ :; }; post(){ return 1; }"
        )
        self.assertEqual(result.returncode, 43)
        self.assertIn("code=INSTALL_PRECONDITION", result.stderr)

    def test_action_exit_code_is_preserved(self) -> None:
        result = self.run_one_step(
            "pre(){ :; }; action(){ return 42; }; post(){ return 1; }"
        )
        self.assertEqual(result.returncode, 42)
        self.assertIn("code=INSTALL_ACTION", result.stderr)


    def test_action_exit_78_is_recorded_as_planned_pause_not_failure(self) -> None:
        result = self.run_one_step(
            "pre(){ :; }; action(){ return 78; }; post(){ return 1; }"
        )
        self.assertEqual(result.returncode, 78)
        self.assertIn("code=INSTALL_PAUSED", result.stdout)
        self.assertNotIn("code=INSTALL_ACTION", result.stderr)

    def test_planned_pause_state_converges_on_rerun_after_external_condition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            logs = root / "logs"
            ready = root / "ready"
            body = f"""
pre(){{ :; }}
action(){{ [[ -f {shlex.quote(str(ready))} ]] && return 0; return 78; }}
post(){{ [[ -f {shlex.quote(str(ready))} ]]; }}
gonken_engine_initialize {shlex.quote(str(state))} {shlex.quote(str(logs))}
gonken_register_step alpha 1 pre action post mutations rerun rollback
gonken_run_registered_steps
"""
            first = run_engine(body)
            self.assertEqual(first.returncode, 78, first.stderr)
            paused = (state / "steps" / "alpha.record").read_text(encoding="utf-8")
            self.assertIn("status=paused", paused)
            self.assertNotIn("INSTALL_ACTION", first.stderr)

            ready.write_text("ready\n", encoding="utf-8")
            second = run_engine(body)
            self.assertEqual(second.returncode, 0, second.stderr)
            completed = (state / "steps" / "alpha.record").read_text(encoding="utf-8")
            self.assertIn("status=complete", completed)
            self.assertIn("INSTALL_STEP_SATISFIED step=alpha", second.stdout)

    def test_failed_postcondition_has_stable_io_exit_code(self) -> None:
        result = self.run_one_step(
            "pre(){ :; }; action(){ :; }; post(){ return 1; }"
        )
        self.assertEqual(result.returncode, 74)
        self.assertIn("code=INSTALL_POSTCONDITION", result.stderr)

    def test_live_lock_is_not_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            logs = root / "logs"
            lock = state / "engine.lock"
            lock.mkdir(parents=True)
            state.chmod(0o700)
            lock.chmod(0o700)
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="utf-8"
            ).strip()
            stat_tail = Path("/proc/1/stat").read_text(encoding="utf-8").rsplit(
                ") ", 1
            )[1]
            start_ticks = stat_tail.split()[19]
            (lock / "owner.record").write_text(
                "format=gonken-install-lock-v1\n"
                "pid=1\n"
                f"boot_id={boot_id}\n"
                f"process_start_ticks={start_ticks}\n",
                encoding="utf-8",
            )
            (lock / "owner.record").chmod(0o600)
            result = run_engine(
                f"gonken_engine_initialize {shlex.quote(str(state))} {shlex.quote(str(logs))}"
            )
            remains = lock.exists()
        self.assertEqual(result.returncode, 75)
        self.assertIn("code=INSTALL_BUSY", result.stderr)
        self.assertTrue(remains)

    def test_reused_live_pid_with_wrong_start_identity_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            logs = root / "logs"
            lock = state / "engine.lock"
            lock.mkdir(parents=True)
            state.chmod(0o700)
            lock.chmod(0o700)
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="utf-8"
            ).strip()
            (lock / "owner.record").write_text(
                "format=gonken-install-lock-v1\n"
                "pid=1\n"
                f"boot_id={boot_id}\n"
                "process_start_ticks=1\n",
                encoding="utf-8",
            )
            (lock / "owner.record").chmod(0o600)
            result = run_engine(
                f"gonken_engine_initialize {shlex.quote(str(state))} {shlex.quote(str(logs))}"
            )
            remains = lock.exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(remains)


if __name__ == "__main__":
    unittest.main()
