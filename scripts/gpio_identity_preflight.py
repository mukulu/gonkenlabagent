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
import time
import re
from pathlib import Path

from gonken_agent.gpio_resolver import GpioResolveError, resolve_named_gpio_line

FORMAT = "gonken-gpio-identity-preflight-v1"
from gonken_agent.config import ConfigError, DEFAULT_SITE_PATH, load_config
from gonken_agent.resources import resource_document



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
    if any(type(v) is not int or not 0 <= v <= 53 for v in lines) or len(set(lines)) != len(lines):
        return {"format": FORMAT, "status": "FAIL", "code": "GPIO_PREFLIGHT_INPUT", "lines": {}, "physical_acceptance_claimed": False}
    if not lines:
        return {"format": FORMAT, "status": "PASS", "code": "GPIO_HEADER_NOT_REQUIRED", "lines": {}, "physical_acceptance_claimed": False}
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


def configured_requirements(site: Path) -> dict:
    if not site.is_file() or site.is_symlink():
        raise ConfigError("preflight requires the installed regular site configuration")
    # The system service consumes packaged defaults + installed site config;
    # caller-only shell overrides must not silently change its claims.
    return resource_document(load_config(site_path=site, environ={}).config)


def boot_id() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return value if re.fullmatch(r"[0-9a-f-]{36}", value) else ""
    except OSError:
        return ""


def record_matches(payload: object, requirements: dict, fresh: object | None = None) -> bool:
    expected = {f"GPIO{n}" for n in requirements["required_gpio_lines"]}
    valid = (isinstance(payload, dict) and payload.get("format") == FORMAT
            and payload.get("status") == "PASS" and payload.get("physical_acceptance_claimed") is False
            and payload.get("code") == ("GPIO_HEADER_RESOLVED" if expected else "GPIO_HEADER_NOT_REQUIRED")
            and bool(boot_id()) and payload.get("boot_id") == boot_id()
            and payload.get("claims_sha256") == requirements["claims_sha256"]
            and payload.get("required_claims") == requirements["claims"]
            and isinstance(payload.get("lines"),dict) and set(payload["lines"]) == expected)
    if not valid: return False
    if fresh is not None:
        return record_matches(fresh, requirements) and payload["lines"] == fresh["lines"]
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--line", action="append", type=int, dest="lines", help="Explicit diagnostic line set; not an installer profile")
    parser.add_argument("--config", type=Path, default=DEFAULT_SITE_PATH)
    parser.add_argument("--validate-record", type=Path, help="Validate saved claim/config binding only; does not probe devices")
    parser.add_argument("--fresh-json", help="Fresh service-context metadata for record comparison")
    parser.add_argument("--output")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    requirements = None
    try:
        if args.lines is not None:
            if args.validate_record: raise ValueError("record validation requires a configured profile")
            lines = tuple(args.lines)
        else:
            requirements = configured_requirements(args.config)
            lines = tuple(requirements["required_gpio_lines"])
        if any(type(value) is not int or value < 0 or value > 53 for value in lines) or len(set(lines)) != len(lines):
            raise ValueError("lines must be unique BCM 0..53")
        if args.validate_record:
            path = args.validate_record
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
                raise ValueError("unsafe GPIO evidence record")
            payload = json.loads(path.read_text(encoding="utf-8"))
            fresh = json.loads(args.fresh_json) if args.fresh_json else None
            if not record_matches(payload, requirements, fresh):
                print("[ERROR] code=GPIO_EVIDENCE_STALE_OR_INVALID", file=sys.stderr); return 75
            if args.json: print(json.dumps({"status":"PASS","code":"GPIO_RECORD_CURRENT","physical_acceptance_claimed":False}))
            return 0
    except (ConfigError, OSError, ValueError) as exc:
        print(f"[ERROR] code=GPIO_PREFLIGHT_INPUT type={type(exc).__name__}", file=sys.stderr)
        return 64
    payload = probe(lines)
    payload["requested_lines"] = list(lines)
    payload["boot_id"] = boot_id()
    payload["observed_epoch"] = int(time.time())
    payload["physical_acceptance_claimed"] = False
    if requirements:
        payload["claims_sha256"] = requirements["claims_sha256"]
        payload["required_claims"] = requirements["claims"]
    if args.output:
        _atomic_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    if payload["status"] != "PASS":
        print(f"[ERROR] code={payload['code']} message={payload.get('detail','')} remediation=inspect selected-capability GPIO metadata", file=sys.stderr)
        return 75
    if not args.json:
        print(f"[OK] code={payload['code']} chip={payload.get('chip_path','not-required')} lines={','.join(map(str, lines))} physical_acceptance_claimed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
