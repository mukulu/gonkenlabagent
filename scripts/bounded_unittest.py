#!/usr/bin/env python3
"""Run unittest modules as bounded, observable subprocesses.

This runner exists for CI evidence quality.  It does not select a smaller test
set than the matching files under the requested suite directory; it executes the
same unittest modules in separate subprocesses so the active module, timeout,
output log and duration are always explicit when a broad run fails or stalls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import select
import sys
import time
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


DEFAULT_PATTERN = "test_*.py"
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str
    returncode: int | None
    duration_seconds: float
    log_file: str
    timed_out: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "status": self.status,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "log_file": self.log_file,
            "timed_out": self.timed_out,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def module_name(root: Path, test_file: Path) -> str:
    relative = test_file.resolve().relative_to(root.resolve()).with_suffix("")
    module = ".".join(relative.parts)
    if not MODULE_RE.fullmatch(module):
        raise ValueError(f"unsafe module name derived from {test_file}: {module}")
    return module


def discover_modules(root: Path, suite_dir: Path, pattern: str) -> list[str]:
    directory = (root / suite_dir).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"suite directory does not exist: {directory}")
    modules = [module_name(root, path) for path in sorted(directory.glob(pattern)) if path.is_file()]
    return [module for module in modules if not module.endswith(".__init__")]


def _iter_suite_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_suite_tests(item)
        else:
            yield item


def discover_test_cases(root: Path, modules: Sequence[str]) -> list[str]:
    src_path = str(root / "src")
    root_path = str(root)
    for candidate in (src_path, root_path):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    loader = unittest.TestLoader()
    test_ids: list[str] = []
    for module in modules:
        suite = loader.loadTestsFromName(module)
        discovered = [test.id() for test in _iter_suite_tests(suite)]
        if not discovered:
            raise ValueError(f"no unittest cases discovered in {module}")
        test_ids.extend(discovered)
    return test_ids


def safe_log_name(module: str) -> str:
    return module.replace(".", "_") + ".log"


def _terminate_process(process: subprocess.Popen[str], kill_after_seconds: float) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + max(0.1, kill_after_seconds)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_module(
    *,
    module: str,
    root: Path,
    log_dir: Path,
    timeout_seconds: float,
    kill_after_seconds: float,
    heartbeat_seconds: float,
    python_bin: str,
    extra_env: dict[str, str],
) -> ModuleResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / safe_log_name(module)
    env = os.environ.copy()
    env.update(extra_env)
    src_path = str(root / "src")
    root_path = str(root)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(item for item in (src_path, root_path, existing) if item)
    command = [python_bin, "-m", "unittest", "-v", module]
    started = time.monotonic()
    print(f"[RUN] module={module} timeout={timeout_seconds:g}s log={log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# command: {' '.join(command)}\n# started_utc: {utc_now()}\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            start_new_session=True,
        )
        assert process.stdout is not None
        fd = process.stdout.fileno()
        os.set_blocking(fd, False)
        next_heartbeat = time.monotonic() + heartbeat_seconds
        output_tail: list[str] = []
        partial = ""
        timed_out = False
        while True:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(fd, 8192)
                except BlockingIOError:
                    chunk = b""
                if chunk:
                    text = chunk.decode("utf-8", errors="replace")
                    log.write(text)
                    log.flush()
                    partial += text
                    while "\n" in partial:
                        line, partial = partial.split("\n", 1)
                        output_tail.append(line)
                        output_tail = output_tail[-3:]
                elif process.poll() is not None:
                    break
            if process.poll() is not None:
                while True:
                    try:
                        chunk = os.read(fd, 8192)
                    except BlockingIOError:
                        break
                    if not chunk:
                        break
                    text = chunk.decode("utf-8", errors="replace")
                    log.write(text)
                    log.flush()
                    partial += text
                if partial:
                    output_tail.append(partial.rstrip("\n"))
                    output_tail = output_tail[-3:]
                break
            now = time.monotonic()
            elapsed = now - started
            if elapsed >= timeout_seconds:
                timed_out = True
                log.write(f"\n# timeout after {elapsed:.3f}s\n")
                log.flush()
                _terminate_process(process, kill_after_seconds)
                break
            if now >= next_heartbeat:
                tail = " | ".join(output_tail[-2:]) if output_tail else "no output yet"
                print(f"[WAIT] module={module} elapsed={elapsed:.1f}s tail={tail}", flush=True)
                next_heartbeat = now + heartbeat_seconds
        returncode = process.poll()
        duration = time.monotonic() - started
        log.write(f"# finished_utc: {utc_now()}\n# duration_seconds: {duration:.3f}\n# returncode: {returncode}\n")
    if timed_out:
        print(f"[TIMEOUT] module={module} seconds={duration:.1f} log={log_path}", flush=True)
        return ModuleResult(module, "TIMEOUT", returncode, duration, str(log_path), True)
    if returncode == 0:
        print(f"[PASS] module={module} seconds={duration:.1f}", flush=True)
        return ModuleResult(module, "PASS", returncode, duration, str(log_path))
    print(f"[FAIL] module={module} returncode={returncode} seconds={duration:.1f} log={log_path}", flush=True)
    return ModuleResult(module, "FAIL", returncode, duration, str(log_path))


def write_manifest(path: Path, *, label: str, granularity: str, results: list[ModuleResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    statuses = [result.status for result in results]
    payload = {
        "schema": "gonken-bounded-unittest-v1",
        "label": label,
        "created_utc": utc_now(),
        "granularity": granularity,
        "result": "PASS" if statuses and all(status == "PASS" for status in statuses) else "FAIL",
        "module_count": len(results),
        "status_counts": {status: statuses.count(status) for status in sorted(set(statuses))},
        "modules": [result.as_dict() for result in results],
    }
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_env(values: Sequence[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(f"expected NAME=VALUE, got {value!r}")
        name, _, content = value.partition("=")
        if not name or "\x00" in name or "\x00" in content:
            raise argparse.ArgumentTypeError(f"invalid environment assignment {value!r}")
        parsed[name] = content
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--suite-dir", type=Path, required=True, help="suite directory relative to --root, e.g. tests/unit")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--module", action="append", default=[], help="explicit module to run; bypasses discovery when supplied")
    parser.add_argument("--exclude-module", action="append", default=[], help="test module to omit from discovery; useful when a long module is run in finer granularity")
    parser.add_argument("--granularity", choices=("module", "case"), default="module", help="run whole modules or individual unittest case IDs as bounded subprocesses")
    parser.add_argument("--label", required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--kill-after-seconds", type=float, default=5.0)
    parser.add_argument("--heartbeat-seconds", type=float, default=15.0)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--env", action="append", default=[], help="extra environment assignment NAME=VALUE")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0 or args.kill_after_seconds <= 0 or args.heartbeat_seconds <= 0:
        parser.error("timeouts and heartbeat must be positive")
    root = args.root.resolve()
    explicit = args.module or []
    modules = explicit if explicit else discover_modules(root, args.suite_dir, args.pattern)
    excluded = set(args.exclude_module or [])
    modules = [module for module in modules if module not in excluded]
    if not modules:
        parser.error("no test modules selected")
    for module in modules:
        if not MODULE_RE.fullmatch(module):
            parser.error(f"unsafe module name: {module}")
    if args.granularity == "case":
        try:
            selected = discover_test_cases(root, modules)
        except Exception as exc:  # pragma: no cover - argparse renders this branch.
            parser.error(str(exc))
    else:
        selected = modules
    for test_name in selected:
        if not MODULE_RE.fullmatch(test_name):
            parser.error(f"unsafe test identifier: {test_name}")
    extra_env = parse_env(args.env)
    results: list[ModuleResult] = []
    for module in selected:
        results.append(
            run_module(
                module=module,
                root=root,
                log_dir=args.log_dir,
                timeout_seconds=args.timeout_seconds,
                kill_after_seconds=args.kill_after_seconds,
                heartbeat_seconds=args.heartbeat_seconds,
                python_bin=args.python,
                extra_env=extra_env,
            )
        )
        if results[-1].status != "PASS":
            # Continue to the next independent module/case so the manifest identifies all
            # immediate failures, but never return success once one item fails.
            pass
    write_manifest(args.manifest, label=args.label, granularity=args.granularity, results=results)
    failures = [result for result in results if result.status != "PASS"]
    if failures:
        print(f"[SUMMARY] label={args.label} result=FAIL modules={len(results)} failures={len(failures)} manifest={args.manifest}", flush=True)
        return 1
    print(f"[SUMMARY] label={args.label} result=PASS modules={len(results)} manifest={args.manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
