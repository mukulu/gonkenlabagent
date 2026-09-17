#!/usr/bin/env python3
"""Sanitized non-actuating target manifest and target-shadow replay.

This helper records platform facts needed for reliability gating without
requesting GPIO lines, scanning arbitrary I2C addresses, reading audio content,
or inspecting conversation/model data.  It can also replay a saved manifest as
a target-shadow fixture so host tests can exercise real topology classes.
"""
from __future__ import annotations

import argparse
import glob
import grp
import json
import os
import platform
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

FORMAT = "gonken-target-hardware-manifest-v1"
REPLAY_FORMAT = "gonken-target-shadow-replay-v1"
HEADER_SIGNATURE = frozenset({"GPIO2", "GPIO3", "GPIO17", "GPIO22", "GPIO23", "GPIO27"})
DEFAULT_REQUIRED_GPIOS = (17, 22, 23, 27)
SERVICE_UNITS = (
    "gonken-agent.service",
    "gonken-environment.service",
    "ollama.service",
    "bluetooth.service",
    "gonken-bluetooth-autoconnect.service",
)
TARGET_SHADOW_REQUIREMENTS = {
    "gpio_identity": True,
    "privacy_boundary": True,
    "audio_duplex": False,
    "service_identity": False,
    "release_state": False,
}
SERVICE_IDENTITY_REQUIREMENTS = {
    "gonken-agent": frozenset({"audio", "gpio"}),
    "gonken-env": frozenset({"gpio", "i2c"}),
}
RELEASE_ROOT = "/usr/local/lib/gonken-agent/releases/"


def _clean(value: object, limit: int = 240) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.replace("\x00", "").replace("\r", " ").replace("\n", " ").split())[:limit]


def _run(command: list[str], *, timeout: float = 3.0) -> tuple[int | None, str]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__
    return result.returncode, _clean(result.stdout or result.stderr)


def _git_commit() -> str | None:
    code, text = _run(["git", "rev-parse", "HEAD"], timeout=3)
    if code == 0 and len(text) == 40 and all(ch in "0123456789abcdef" for ch in text):
        return text
    return None


def _os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    output: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"}:
                output[key] = _clean(value.strip().strip('"'), 160)
    except OSError:
        pass
    return output


def _pi_model() -> dict[str, str]:
    model = ""
    revision = ""
    try:
        model = _clean(Path("/proc/device-tree/model").read_text(encoding="utf-8", errors="replace"), 160)
    except OSError:
        pass
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().casefold() == "revision":
                revision = _clean(value, 80)
                break
    except OSError:
        pass
    return {"model": model, "revision": revision, "kernel": platform.release(), "os_release": _os_release()}


def _python_info() -> dict[str, object]:
    try:
        import gpiod  # type: ignore[import-not-found]
        libgpiod = _clean(getattr(gpiod, "__version__", "") or getattr(gpiod, "version_string", "") or "available")
    except Exception as exc:
        libgpiod = f"unavailable:{type(exc).__name__}"
    return {"version": platform.python_version(), "executable": sys.executable, "libgpiod": libgpiod}


def _device_identity(chip_path: str, *, stat_func=os.stat) -> tuple[dict[str, object], str]:
    try:
        info = stat_func(chip_path)
    except OSError:
        return {"kind": "missing", "major": None, "minor": None}, ""
    mode = getattr(info, "st_mode", 0)
    if not stat.S_ISCHR(mode):
        return {"kind": "other", "major": None, "minor": None}, ""
    rdev = getattr(info, "st_rdev", 0)
    major = os.major(rdev)
    minor = os.minor(rdev)
    sysfs = Path("/sys/dev/char") / f"{major}:{minor}"
    try:
        sysfs_realpath = str(sysfs.resolve(strict=True))
    except OSError:
        sysfs_realpath = ""
    return {"kind": "char", "major": major, "minor": minor}, f"char:{major}:{minor}:{sysfs_realpath}"


def _collect_gpiochips(*, gpiod_module=None, chip_paths: Iterable[str] | None = None, stat_func=os.stat) -> list[dict[str, object]]:
    if chip_paths is None:
        chip_paths = tuple(sorted(glob.glob("/dev/gpiochip*")))
    if gpiod_module is None:
        try:
            import gpiod as gpiod_module  # type: ignore[import-not-found]
        except Exception:
            gpiod_module = None
    chips: list[dict[str, object]] = []
    for chip_path in chip_paths:
        if not isinstance(chip_path, str) or not chip_path.startswith("/dev/gpiochip"):
            continue
        stat_payload, canonical = _device_identity(chip_path, stat_func=stat_func)
        chip_info: dict[str, object] = {"name": "", "label": "", "num_lines": 0}
        line_names: dict[str, str] = {}
        if gpiod_module is not None:
            try:
                chip = gpiod_module.Chip(chip_path)
            except Exception:
                chip = None
            if chip is not None:
                try:
                    info = chip.get_info()
                    count = int(getattr(info, "num_lines"))
                    if 0 < count <= 4096:
                        chip_info = {
                            "name": _clean(getattr(info, "name", "")),
                            "label": _clean(getattr(info, "label", "")),
                            "num_lines": count,
                        }
                        for offset in range(count):
                            try:
                                line_info = chip.get_line_info(offset)
                                name = getattr(line_info, "name", None)
                            except Exception:
                                name = None
                            if isinstance(name, str) and name:
                                line_names[str(offset)] = _clean(name, 80)
                finally:
                    close = getattr(chip, "close", None)
                    if callable(close):
                        close()
        chips.append({
            "path": chip_path,
            "stat": stat_payload,
            "sysfs_realpath": canonical.rsplit(":", 1)[-1] if canonical else "",
            "chip_info": chip_info,
            "line_names": line_names,
            "canonical_chip_id": canonical,
            "alias_paths": [chip_path],
        })
    aliases: dict[str, list[str]] = {}
    for chip in chips:
        identity = str(chip.get("canonical_chip_id") or "")
        if identity:
            aliases.setdefault(identity, []).append(str(chip["path"]))
    for chip in chips:
        identity = str(chip.get("canonical_chip_id") or "")
        if identity and identity in aliases:
            chip["alias_paths"] = sorted(aliases[identity])
    return chips


def _i2c_inventory() -> dict[str, object]:
    devices = sorted(path.name for path in Path("/dev").glob("i2c-*"))[:16]
    return {
        "devices": devices,
        "sht31_targeted_probe": {
            "bus": "/dev/i2c-1",
            "address": "0x44",
            "status": "not_probed_non_actuating_manifest",
        },
    }


def _audio_inventory() -> dict[str, object]:
    code_capture, capture = _run(["arecord", "-l"], timeout=3) if shutil.which("arecord") else (None, "missing")
    code_playback, playback = _run(["aplay", "-l"], timeout=3) if shutil.which("aplay") else (None, "missing")
    return {
        "capture_routes": [] if code_capture is None else [{"source": "arecord -l", "status": "observed", "summary": capture}],
        "playback_routes": [] if code_playback is None else [{"source": "aplay -l", "status": "observed", "summary": playback}],
        "selected_route": None,
    }


def _bluetooth_inventory() -> dict[str, object]:
    if not shutil.which("bluetoothctl"):
        return {"controller": "", "devices": []}
    _, show = _run(["bluetoothctl", "show"], timeout=3)
    code, devices = _run(["bluetoothctl", "devices"], timeout=3)
    parsed = []
    if code == 0:
        for line in devices.split(" Device "):
            line = _clean(line)
            if line:
                parsed.append(line[:160])
    return {"controller": show, "devices": parsed[:16]}


def _unit_state(name: str) -> dict[str, object]:
    if not shutil.which("systemctl"):
        return {"available": False}
    code, active = _run(["systemctl", "is-active", name], timeout=3)
    _, enabled = _run(["systemctl", "is-enabled", name], timeout=3)
    return {"active": active, "active_exit": code, "enabled": enabled}


def _identity() -> dict[str, object]:
    service_users: dict[str, object] = {}
    for user in ("gonken-agent", "gonken-env", "ollama"):
        try:
            record = pwd.getpwnam(user)
            groups = {grp.getgrgid(record.pw_gid).gr_name}
            groups.update(entry.gr_name for entry in grp.getgrall() if user in entry.gr_mem)
            service_users[user] = {"exists": True, "groups": sorted(groups)}
        except (KeyError, OSError):
            service_users[user] = {"exists": False, "groups": []}
    operator_groups: list[str] = []
    try:
        operator = os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
        record = pwd.getpwnam(operator)
        groups = {grp.getgrgid(record.pw_gid).gr_name}
        groups.update(entry.gr_name for entry in grp.getgrall() if operator in entry.gr_mem)
        operator_groups = sorted(groups)
    except (KeyError, OSError):
        pass
    return {"service_users": service_users, "operator_groups": operator_groups}


def _release_state() -> dict[str, object]:
    current = Path("/usr/local/lib/gonken-agent/current")
    installer_state = Path("/var/lib/gonken-agent/install")
    try:
        current_target = os.readlink(current) if current.is_symlink() else ""
    except OSError:
        current_target = ""
    return {
        "current": _clean(current_target, 160),
        "installer_state": {
            "exists": installer_state.exists(),
            "path": str(installer_state),
        },
    }


def collect_manifest(*, gpiod_module=None, chip_paths: Iterable[str] | None = None, stat_func=os.stat) -> dict[str, object]:
    return {
        "format": FORMAT,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _git_commit(),
        "raspberry_pi": _pi_model(),
        "python": _python_info(),
        "gpiochips": _collect_gpiochips(gpiod_module=gpiod_module, chip_paths=chip_paths, stat_func=stat_func),
        "i2c": _i2c_inventory(),
        "audio": _audio_inventory(),
        "bluetooth": _bluetooth_inventory(),
        "systemd": {"version": _systemd_version(), "units": {name: _unit_state(name) for name in SERVICE_UNITS}},
        "identity": _identity(),
        "release": _release_state(),
        "privacy": {
            "raw_audio_included": False,
            "transcripts_included": False,
            "prompts_or_model_responses_included": False,
        },
        "physical_acceptance_claimed": False,
    }


def _systemd_version() -> str:
    code, text = _run(["systemctl", "--version"], timeout=3) if shutil.which("systemctl") else (None, "")
    if code == 0:
        return text.split(" ", 1)[0] if text else ""
    return ""


def _chip_named_set(chip: dict[str, object]) -> frozenset[str]:
    line_names = chip.get("line_names")
    if not isinstance(line_names, dict):
        return frozenset()
    return frozenset(str(value) for value in line_names.values() if value)


def _dedup_manifest_chips(chips: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    output: list[dict[str, object]] = []
    for chip in chips:
        identity = str(chip.get("canonical_chip_id") or "")
        if identity:
            grouped.setdefault(identity, []).append(chip)
        else:
            output.append(chip)
    for identity, group in grouped.items():
        if len(group) == 1:
            output.append(group[0])
            continue
        primary = sorted(group, key=lambda item: str(item.get("path", "")))[0].copy()
        primary["alias_paths"] = sorted(str(item.get("path", "")) for item in group)
        primary["canonical_chip_id"] = identity
        output.append(primary)
    return sorted(output, key=lambda item: str(item.get("path", "")))


def _chip_info_text(chip: dict[str, object]) -> str:
    info = chip.get("chip_info") if isinstance(chip.get("chip_info"), dict) else {}
    return f"{info.get('name', '')} {info.get('label', '')}".casefold()


def _manifest_line_matches(chips: list[dict[str, object]], logical_bcm: int) -> list[tuple[dict[str, object], str]]:
    expected = f"GPIO{logical_bcm}"
    matches: list[tuple[dict[str, object], str]] = []
    for chip in chips:
        line_names = chip.get("line_names")
        if not isinstance(line_names, dict):
            continue
        for offset, name in line_names.items():
            if name == expected:
                matches.append((chip, str(offset)))
    return matches


def replay_gpio_identity(manifest: dict[str, object], required_gpios: Iterable[int] = DEFAULT_REQUIRED_GPIOS) -> dict[str, object]:
    chips_raw = manifest.get("gpiochips")
    chips = _dedup_manifest_chips(chips_raw if isinstance(chips_raw, list) else [])
    resolved: dict[str, object] = {}
    errors: list[str] = []
    for logical_bcm in required_gpios:
        expected = f"GPIO{logical_bcm}"
        matches = _manifest_line_matches(chips, logical_bcm)
        selected: tuple[dict[str, object], str, str] | None = None
        if len(matches) == 1:
            selected = (matches[0][0], matches[0][1], "unique-line-name")
        else:
            rp1 = [row for row in matches if "pinctrl-rp1" in _chip_info_text(row[0])]
            if len(rp1) == 1:
                selected = (rp1[0][0], rp1[0][1], "rp1-metadata")
            else:
                topology = [chip for chip in chips if HEADER_SIGNATURE.issubset(_chip_named_set(chip))]
                topology_matches = [row for row in matches if row[0] in topology]
                if len(topology) == 1 and len(topology_matches) == 1:
                    selected = (topology_matches[0][0], topology_matches[0][1], "header-topology")
        if selected is None:
            errors.append(expected)
            continue
        chip, offset, basis = selected
        resolved[expected] = {
            "chip_path": chip.get("path"),
            "line_offset": int(offset) if offset.isdigit() else offset,
            "resolution_basis": basis,
            "canonical_chip_id": chip.get("canonical_chip_id") or "",
            "alias_paths": chip.get("alias_paths") or [chip.get("path")],
        }
    chip_paths = {str(item["chip_path"]) for item in resolved.values() if isinstance(item, dict)}
    if errors:
        return {"status": "FAIL", "code": "GPIO_HEADER_UNRESOLVED", "detail": ",".join(errors), "lines": resolved}
    if len(chip_paths) != 1:
        return {"status": "FAIL", "code": "GPIO_HEADER_CHIP_MISMATCH", "detail": ",".join(sorted(chip_paths)), "lines": resolved}
    return {"status": "PASS", "code": "GPIO_HEADER_RESOLVED", "chip_path": next(iter(chip_paths)), "lines": resolved}


def _manifest_requirements(manifest: dict[str, object]) -> dict[str, bool]:
    requirements = dict(TARGET_SHADOW_REQUIREMENTS)
    requested = manifest.get("target_shadow_requirements")
    if isinstance(requested, dict):
        for key in requirements:
            value = requested.get(key)
            if isinstance(value, bool):
                requirements[key] = value
    return requirements


def replay_privacy_boundary(manifest: dict[str, object]) -> dict[str, object]:
    privacy = manifest.get("privacy")
    if not isinstance(privacy, dict):
        return {"status": "FAIL", "code": "PRIVACY_BOUNDARY_UNDECLARED", "detail": "privacy"}
    unsafe = []
    for field in ("raw_audio_included", "transcripts_included", "prompts_or_model_responses_included"):
        if privacy.get(field) is not False:
            unsafe.append(field)
    if manifest.get("physical_acceptance_claimed") is not False:
        unsafe.append("physical_acceptance_claimed")
    if unsafe:
        return {"status": "FAIL", "code": "PRIVACY_BOUNDARY_FAILED", "detail": ",".join(sorted(unsafe))}
    return {"status": "PASS", "code": "PRIVACY_BOUNDARY_CONTENT_FREE"}


def _route_status(route: object) -> str:
    return str(route.get("status", "") if isinstance(route, dict) else "").casefold()


def replay_audio_duplex(manifest: dict[str, object]) -> dict[str, object]:
    audio = manifest.get("audio")
    if not isinstance(audio, dict):
        return {"status": "FAIL", "code": "AUDIO_ROUTE_UNDECLARED", "detail": "audio"}
    selected = audio.get("selected_route")
    if not isinstance(selected, dict):
        return {"status": "FAIL", "code": "AUDIO_ROUTE_UNRESOLVED", "detail": "selected_route"}
    capture = selected.get("capture")
    playback = selected.get("playback")
    problems = []
    if not isinstance(capture, dict) or _route_status(capture) not in {"available", "ready", "observed"}:
        problems.append("capture")
    if not isinstance(playback, dict) or _route_status(playback) not in {"available", "ready", "observed"}:
        problems.append("playback")
    if isinstance(playback, dict) and playback.get("hdmi") is True:
        problems.append("hdmi-playback")
    if selected.get("ambiguous") is True:
        problems.append("ambiguous")
    if problems:
        return {"status": "FAIL", "code": "AUDIO_ROUTE_UNRESOLVED", "detail": ",".join(sorted(problems))}
    return {
        "status": "PASS",
        "code": "AUDIO_DUPLEX_ROUTE_RESOLVED",
        "capture": capture.get("id", "") if isinstance(capture, dict) else "",
        "playback": playback.get("id", "") if isinstance(playback, dict) else "",
        "selection_basis": selected.get("selection_basis", ""),
    }


def replay_service_identity(manifest: dict[str, object]) -> dict[str, object]:
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        return {"status": "FAIL", "code": "SERVICE_IDENTITY_UNDECLARED", "detail": "identity"}
    service_users = identity.get("service_users")
    if not isinstance(service_users, dict):
        return {"status": "FAIL", "code": "SERVICE_IDENTITY_UNDECLARED", "detail": "service_users"}
    missing = []
    for user, required_groups in SERVICE_IDENTITY_REQUIREMENTS.items():
        payload = service_users.get(user)
        if not isinstance(payload, dict) or payload.get("exists") is not True:
            missing.append(user)
            continue
        groups = {str(group) for group in payload.get("groups", []) if isinstance(group, str)}
        missing_groups = sorted(required_groups - groups)
        if missing_groups:
            missing.append(f"{user}:{','.join(missing_groups)}")
    if missing:
        return {"status": "FAIL", "code": "SERVICE_IDENTITY_UNRESOLVED", "detail": ";".join(missing)}
    return {"status": "PASS", "code": "SERVICE_IDENTITY_RESOLVED"}


def replay_release_state(manifest: dict[str, object]) -> dict[str, object]:
    release = manifest.get("release")
    if not isinstance(release, dict):
        return {"status": "FAIL", "code": "RELEASE_STATE_UNDECLARED", "detail": "release"}
    current = str(release.get("current", ""))
    installer = release.get("installer_state")
    problems = []
    if not current.startswith(RELEASE_ROOT) or ".." in Path(current).parts:
        problems.append("current")
    current_status = str(release.get("current_status", "")).casefold()
    if current_status and current_status not in {"verified", "none"}:
        problems.append("current_status")
    if not isinstance(installer, dict):
        problems.append("installer_state")
    else:
        if installer.get("dirty") is True:
            problems.append("installer_dirty")
        status = str(installer.get("status", "")).casefold()
        if status and status not in {"complete", "none"}:
            problems.append("installer_status")
        if str(installer.get("path", "")) != "/var/lib/gonken-agent/install":
            problems.append("installer_path")
    if problems:
        return {"status": "FAIL", "code": "RELEASE_STATE_UNSAFE", "detail": ",".join(sorted(problems))}
    return {"status": "PASS", "code": "RELEASE_STATE_SAFE"}


def _first_failed_code(checks: Iterable[dict[str, object]]) -> str:
    for check in checks:
        if check.get("status") != "PASS":
            return str(check.get("code") or "TARGET_SHADOW_FAILED")
    return "TARGET_SHADOW_READY"


def replay_manifest(manifest: dict[str, object], required_gpios: Iterable[int] = DEFAULT_REQUIRED_GPIOS) -> dict[str, object]:
    requirements = _manifest_requirements(manifest)
    gpio = replay_gpio_identity(manifest, required_gpios)
    format_check = {
        "status": "PASS" if manifest.get("format") == FORMAT else "FAIL",
        "code": "MANIFEST_FORMAT_VALID" if manifest.get("format") == FORMAT else "MANIFEST_FORMAT_INVALID",
    }
    privacy = replay_privacy_boundary(manifest)
    audio = replay_audio_duplex(manifest)
    identity = replay_service_identity(manifest)
    release = replay_release_state(manifest)
    required_checks = [format_check]
    if requirements["privacy_boundary"]:
        required_checks.append(privacy)
    if requirements["gpio_identity"]:
        required_checks.append(gpio)
    if requirements["audio_duplex"]:
        required_checks.append(audio)
    if requirements["service_identity"]:
        required_checks.append(identity)
    if requirements["release_state"]:
        required_checks.append(release)
    status = "PASS" if all(check.get("status") == "PASS" for check in required_checks) else "FAIL"
    return {
        "format": REPLAY_FORMAT,
        "manifest_format": manifest.get("format"),
        "status": status,
        "code": "TARGET_SHADOW_READY" if status == "PASS" else _first_failed_code(required_checks),
        "requirements": requirements,
        "gpio_identity": gpio,
        "privacy_boundary": privacy,
        "audio_duplex": audio,
        "service_identity": identity,
        "release_state": release,
        "physical_acceptance_claimed": False,
    }


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    if not path.is_absolute() or path.is_symlink() or ".." in path.parts:
        raise ValueError("output path must be an absolute non-symlink path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parse_lines(values: list[int] | None) -> tuple[int, ...]:
    lines = tuple(values or DEFAULT_REQUIRED_GPIOS)
    if not lines or any(isinstance(value, bool) or value < 0 or value > 53 for value in lines) or len(set(lines)) != len(lines):
        raise SystemExit("required GPIO lines must be unique BCM values 0..53")
    return lines


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--json", action="store_true")
    result.add_argument("--output")
    result.add_argument("--replay", help="Replay a sanitized manifest fixture instead of collecting live target data")
    result.add_argument("--required-gpio", action="append", type=int, dest="required_gpios")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    required_gpios = _parse_lines(args.required_gpios)
    if args.replay:
        with Path(args.replay).open("r", encoding="utf-8") as handle:
            payload = replay_manifest(json.load(handle), required_gpios)
    else:
        payload = collect_manifest()
    if args.output:
        atomic_json(Path(args.output), payload)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        status = payload.get("status", "PASS")
        code = payload.get("gpio_identity", {}).get("code", "TARGET_MANIFEST_CAPTURED") if isinstance(payload.get("gpio_identity"), dict) else "TARGET_MANIFEST_CAPTURED"
        print(f"[{'OK' if status == 'PASS' or not args.replay else 'ERROR'}] code={code} status={status} physical_acceptance_claimed=false")
    return 0 if (not args.replay or payload.get("status") == "PASS") else 75


if __name__ == "__main__":
    raise SystemExit(main())
