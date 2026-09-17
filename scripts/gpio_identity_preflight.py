#!/usr/bin/env python3
"""Non-actuating Raspberry Pi GPIO header-identity preflight.

This helper opens gpiochip metadata only.  It never requests a GPIO line and
therefore cannot toggle PTT/LED/relay hardware.  It uses the same resolver as
the production PTT/wake/relay adapters so installer readiness cannot be green
while the runtime resolver would later fail.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
from pathlib import Path

from gonken_agent.gpio_resolver import GpioResolveError, resolve_named_gpio_line

FORMAT = "gonken-gpio-identity-preflight-v1"
DEFAULT_LINES = (17, 22, 23, 27)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        try: os.unlink(name)
        except FileNotFoundError: pass


def probe(lines: tuple[int, ...], *, gpiod_module=None, chip_paths: tuple[str, ...] | None = None) -> dict[str, object]:
    if gpiod_module is None:
        try:
            import gpiod as gpiod_module  # type: ignore[import-not-found]
        except Exception as exc:
            return {"format": FORMAT, "status": "FAIL", "code": "GPIO_DEPENDENCY_MISSING", "detail": type(exc).__name__, "lines": {}}
    gpiod = gpiod_module
    if chip_paths is None:
        chip_paths = tuple(sorted(glob.glob("/dev/gpiochip*")))
    if not chip_paths:
        return {"format": FORMAT, "status": "FAIL", "code": "GPIOCHIP_UNAVAILABLE", "detail": "no /dev/gpiochip* devices", "lines": {}}
    resolved: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for bcm in lines:
        try:
            item = resolve_named_gpio_line(gpiod=gpiod, logical_bcm=bcm, chip_paths=chip_paths)
        except GpioResolveError as exc:
            errors.append(f"GPIO{bcm}:{exc.reason}:{exc.detail}")
            continue
        resolved[f"GPIO{bcm}"] = {
            "logical_bcm": bcm,
            "chip_path": item.chip_path,
            "line_offset": item.line_offset,
            "line_name": item.line_name,
            "chip_name": item.chip_name,
            "chip_label": item.chip_label,
            "resolution_basis": item.resolution_basis,
            "canonical_chip_id": item.canonical_chip_id,
            "alias_paths": list(item.alias_paths),
        }
    if errors:
        return {"format": FORMAT, "status": "FAIL", "code": "GPIO_HEADER_UNRESOLVED", "detail": ";".join(errors)[:900], "lines": resolved}
    chips = {str(row["chip_path"]) for row in resolved.values()}
    if len(chips) != 1:
        return {"format": FORMAT, "status": "FAIL", "code": "GPIO_HEADER_CHIP_MISMATCH", "detail": ",".join(sorted(chips)), "lines": resolved}
    return {"format": FORMAT, "status": "PASS", "code": "GPIO_HEADER_RESOLVED", "chip_path": next(iter(chips)), "lines": resolved, "physical_acceptance_claimed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--line", action="append", type=int, dest="lines")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    lines = tuple(args.lines or DEFAULT_LINES)
    if not lines or any(value < 0 or value > 53 for value in lines) or len(set(lines)) != len(lines):
        print("[ERROR] code=GPIO_PREFLIGHT_INPUT message=lines must be unique BCM 0..53", file=sys.stderr)
        return 64
    payload = probe(lines)
    if args.output:
        _atomic_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    if payload["status"] != "PASS":
        print(f"[ERROR] code={payload['code']} message={payload.get('detail','')} remediation=inspect gpiochip metadata and Pi5 RP1 header mapping", file=sys.stderr)
        return 75
    if not args.json:
        print(f"[OK] code=GPIO_HEADER_RESOLVED chip={payload['chip_path']} lines={','.join(map(str, lines))} physical_acceptance_claimed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
