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
    "audio_runtime": False,
    "service_identity": False,
    "release_state": False,
    "i2c_sht31": False,
    "environment_profile": False,
    "operator_identity": False,
    "systemd_runtime": False,
    "release_lifecycle": False,
    "resource_capacity": False,
    "model_finalization": False,
    "readiness_identity": False,
}
SERVICE_IDENTITY_REQUIREMENTS = {
    "gonken-agent": frozenset({"audio", "gpio"}),
    "gonken-env": frozenset({"gpio", "i2c"}),
}
RELEASE_ROOT = "/usr/local/lib/gonken-agent/releases/"
SHT31_READY_STATUSES = frozenset({"available", "ready", "observed", "present", "crc_valid", "diagnostic_pass"})
SHT31_REBOOT_STATUSES = frozenset({"reboot_required", "i2c_reboot_required", "enabled_reboot_required"})
SHT31_UNREADY_STATUSES = frozenset({
    "",
    "absent",
    "disabled",
    "missing",
    "not_found",
    "not_probed",
    "not_probed_non_actuating_manifest",
    "sensor_address_ambiguous",
    "sensor_not_found",
    "unavailable",
})
ENVIRONMENT_PROFILE_SPECS = {
    "full-simulation": {
        "enabled": True,
        "sensor_backend": "simulated",
        "relay_backend": "simulated",
        "relay_bcm": 23,
        "safe_state": "off",
    },
    "sensor-deferred-relay": {
        "enabled": True,
        "sensor_backend": "simulated",
        "relay_backend": "libgpiod",
        "relay_bcm": 23,
        "safe_state": "off",
    },
    "real-sensor-simulated-actuator": {
        "enabled": True,
        "sensor_backend": "sht31",
        "relay_backend": "simulated",
        "relay_bcm": 23,
        "safe_state": "off",
    },
    "full-real": {
        "enabled": True,
        "sensor_backend": "sht31",
        "relay_backend": "libgpiod",
        "relay_bcm": 23,
        "safe_state": "off",
    },
}
REAL_SENSOR_PROFILES = frozenset({"real-sensor-simulated-actuator", "full-real"})
REAL_RELAY_PROFILES = frozenset({"sensor-deferred-relay", "full-real"})
REQUIRED_RUNTIME_UNITS = ("gonken-agent.service", "gonken-environment.service", "ollama.service")
SYSTEMD_TEMPLATE_OK = frozenset({"current", "compatible", "upgraded", "not-managed"})
SYSTEMD_RESTART_OK = frozenset({"ok", "not-run", "not-required", "none"})
RELEASE_HISTORY_BLOCKING_ROLES = frozenset({"current", "previous", "rollback_target", "selected_previous"})
RELEASE_HISTORY_OK = frozenset({"verified", "stale_nonblocking", "pruned", "none"})
PYTHON_CACHE_SUFFIXES = (".pyc", ".pyo")
MIN_TARGET_FREE_KIB = 4_194_304


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


def _resource_inventory() -> dict[str, object]:
    root = shutil.disk_usage("/")
    var = shutil.disk_usage("/var") if Path("/var").exists() else root
    return {
        "root_free_kib": root.free // 1024,
        "var_free_kib": var.free // 1024,
        "minimum_required_free_kib": MIN_TARGET_FREE_KIB,
    }


def _effective_resource_claims(site=None) -> dict:
    try:
        from gonken_agent.config import load_config, DEFAULT_SITE_PATH
        from gonken_agent.resources import resource_document
        path = Path(site) if site else DEFAULT_SITE_PATH
        if not path.is_file() or path.is_symlink():
            return {"status":"INVALID","code":"TARGET_CONFIG_UNAVAILABLE"}
        return resource_document(load_config(site_path=path, environ={}).config)
    except (ImportError, OSError, ValueError):
        return {"status":"INVALID","code":"TARGET_CONFIG_INVALID"}


def collect_manifest(*, gpiod_module=None, chip_paths: Iterable[str] | None = None, stat_func=os.stat) -> dict[str, object]:
    return {
        "format": FORMAT,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _git_commit(),
        "raspberry_pi": _pi_model(),
        "python": _python_info(),
        "resource_claims": _effective_resource_claims(),
        "gpiochips": _collect_gpiochips(gpiod_module=gpiod_module, chip_paths=chip_paths, stat_func=stat_func),
        "i2c": _i2c_inventory(),
        "audio": _audio_inventory(),
        "bluetooth": _bluetooth_inventory(),
        "systemd": {"version": _systemd_version(), "units": {name: _unit_state(name) for name in SERVICE_UNITS}},
        "identity": _identity(),
        "release": _release_state(),
        "resources": _resource_inventory(),
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


def replay_gpio_identity(manifest: dict[str, object], required_gpios: Iterable[int] | None = None) -> dict[str, object]:
    if required_gpios is None:
        claims = manifest.get("resource_claims")
        if not isinstance(claims, dict) or claims.get("format") != "gonken-resource-claims-v1" or not isinstance(claims.get("required_gpio_lines"), list):
            return {"status":"FAIL","code":"GPIO_REQUIREMENTS_MISSING","lines":{}}
        required_gpios = claims["required_gpio_lines"]
    required_gpios = tuple(required_gpios)
    if any(type(n) is not int or not 0 <= n <= 53 for n in required_gpios) or len(set(required_gpios)) != len(required_gpios):
        return {"status":"FAIL","code":"GPIO_REQUIREMENTS_INVALID","lines":{}}
    if not required_gpios:
        return {"status":"PASS","code":"GPIO_HEADER_NOT_REQUIRED","lines":{},"physical_acceptance_claimed":False}
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


def replay_audio_runtime(manifest: dict[str, object]) -> dict[str, object]:
    """Replay service-context audio evidence, not just device inventory.

    Structural enumeration can look healthy while the dedicated service user
    still cannot record.  This gate therefore requires an explicit bounded
    functional capture result when a fixture opts into ``audio_runtime``.
    """
    audio = manifest.get("audio")
    if not isinstance(audio, dict):
        return {"status": "FAIL", "code": "AUDIO_RUNTIME_UNDECLARED", "detail": "audio"}
    runtime = audio.get("runtime")
    if not isinstance(runtime, dict):
        return {"status": "FAIL", "code": "AUDIO_RUNTIME_UNDECLARED", "detail": "audio.runtime"}
    problems: list[str] = []
    if runtime.get("service_user") != "gonken-agent":
        problems.append("service_user")
    if runtime.get("runtime_dir_ready") is not True:
        problems.append("runtime_dir")
    if runtime.get("pipewire_socket_exists") is not True and runtime.get("pulse_socket_exists") is not True:
        problems.append("audio_socket")
    capture = runtime.get("capture_probe")
    if not isinstance(capture, dict):
        problems.append("capture_probe")
    else:
        if str(capture.get("status", "")).casefold() not in {"ready", "pass", "ok"}:
            problems.append("capture")
        if capture.get("content_persisted") is not False:
            problems.append("capture_privacy")
    if problems:
        detail = ",".join(sorted(set(problems)))
        observed_code = ""
        if isinstance(capture, dict):
            observed_code = str(capture.get("code", ""))[:64]
        result: dict[str, object] = {
            "status": "FAIL",
            "code": "AUDIO_CAPTURE_RUNTIME_UNREADY",
            "detail": detail,
        }
        if observed_code:
            result["observed_code"] = observed_code
        return result
    return {
        "status": "PASS",
        "code": "AUDIO_CAPTURE_RUNTIME_READY",
        "backend": str(capture.get("backend", "")) if isinstance(capture, dict) else "",
        "service_user": "gonken-agent",
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


def replay_operator_identity(manifest: dict[str, object]) -> dict[str, object]:
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        return {"status": "FAIL", "code": "OPERATOR_IDENTITY_UNDECLARED", "detail": "identity"}
    groups = {str(group) for group in identity.get("operator_groups", []) if isinstance(group, str)}
    if "gonken-envctl" not in groups:
        return {"status": "FAIL", "code": "OPERATOR_IDENTITY_UNREADY", "detail": "gonken-envctl"}
    raw_groups = sorted(groups & {"gpio", "i2c"})
    return {"status": "PASS", "code": "OPERATOR_IDENTITY_READY", "groups": sorted(groups), "raw_hardware_groups": raw_groups}


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


def replay_readiness_identity(manifest: dict[str, object]) -> dict[str, object]:
    release = manifest.get("release")
    readiness = manifest.get("voice_readiness")
    if not isinstance(release, dict) or not isinstance(readiness, dict):
        return {"status": "FAIL", "code": "READINESS_IDENTITY_UNDECLARED", "detail": "release,voice_readiness"}
    current = str(release.get("current", ""))
    current_commit = str(release.get("current_commit") or _release_commit_from_current(current))
    current_profile = str(release.get("profile") or release.get("release_profile") or "")
    ready_commit = str(readiness.get("release_commit") or "")
    ready_profile = str(readiness.get("release_profile") or "")
    status = str(readiness.get("status") or "").upper()
    problems = []
    if status != "READY":
        problems.append(f"status={status or 'missing'}")
    if not current_commit or ready_commit != current_commit:
        problems.append(f"commit={ready_commit or 'missing'}!={current_commit or 'missing'}")
    if not current_profile or ready_profile != current_profile:
        problems.append(f"profile={ready_profile or 'missing'}!={current_profile or 'missing'}")
    if problems:
        return {"status": "FAIL", "code": "READINESS_IDENTITY_MISMATCH", "detail": ";".join(problems)}
    return {
        "status": "PASS",
        "code": "READINESS_IDENTITY_MATCH",
        "release_commit": current_commit,
        "release_profile": current_profile,
    }


def replay_systemd_runtime(manifest: dict[str, object]) -> dict[str, object]:
    systemd = manifest.get("systemd")
    if not isinstance(systemd, dict):
        return {"status": "FAIL", "code": "SYSTEMD_RUNTIME_UNDECLARED", "detail": "systemd"}
    units = systemd.get("units")
    if not isinstance(units, dict):
        return {"status": "FAIL", "code": "SYSTEMD_RUNTIME_UNDECLARED", "detail": "units"}
    problems = []
    for unit_name in REQUIRED_RUNTIME_UNITS:
        unit = units.get(unit_name)
        if not isinstance(unit, dict):
            problems.append(f"{unit_name}:missing")
            continue
        active = str(unit.get("active", "")).casefold()
        enabled = str(unit.get("enabled", "")).casefold()
        if active != "active":
            problems.append(f"{unit_name}:active={active or 'missing'}")
        if enabled not in {"enabled", "static"}:
            problems.append(f"{unit_name}:enabled={enabled or 'missing'}")
        template = str(unit.get("managed_template_status", "current")).casefold()
        if template not in SYSTEMD_TEMPLATE_OK:
            problems.append(f"{unit_name}:template={template}")
        restart = str(unit.get("restart_status", "ok")).casefold()
        if restart not in SYSTEMD_RESTART_OK:
            problems.append(f"{unit_name}:restart={restart}")
    if problems:
        return {"status": "FAIL", "code": "SYSTEMD_RUNTIME_UNREADY", "detail": ";".join(sorted(problems))}
    return {"status": "PASS", "code": "SYSTEMD_RUNTIME_READY", "units": list(REQUIRED_RUNTIME_UNITS)}


def _release_commit_from_current(current: str) -> str:
    path = Path(current)
    if str(current).startswith(RELEASE_ROOT) and path.name:
        return path.name
    return ""


def _is_python_cache_artifact(path: object) -> bool:
    text = str(path or "")
    parts = Path(text).parts
    return "__pycache__" in parts or text.endswith(PYTHON_CACHE_SUFFIXES)


def replay_release_lifecycle(manifest: dict[str, object]) -> dict[str, object]:
    release = manifest.get("release")
    if not isinstance(release, dict):
        return {"status": "FAIL", "code": "RELEASE_LIFECYCLE_UNDECLARED", "detail": "release"}
    current = str(release.get("current", ""))
    current_commit = str(release.get("current_commit") or _release_commit_from_current(current))
    expected_commit = str(release.get("expected_commit") or manifest.get("commit") or current_commit)
    problems = []
    if expected_commit and current_commit != expected_commit:
        problems.append("current_commit")
    if release.get("install_complete") is not True:
        problems.append("install_complete")
    symlink = str(release.get("current_symlink_state", "valid")).casefold()
    if symlink not in {"valid", "none"}:
        problems.append("current_symlink_state")
    temp_artifacts = release.get("temp_artifacts")
    if isinstance(temp_artifacts, list) and temp_artifacts:
        problems.append("temp_artifacts")
    runtime_derivatives = release.get("runtime_derivatives")
    if isinstance(runtime_derivatives, list):
        for item in runtime_derivatives:
            path = item.get("path") if isinstance(item, dict) else item
            kind = str(item.get("kind", "") if isinstance(item, dict) else "").casefold()
            if kind in {"authoritative_drift", "source_drift", "manifest_drift"} or not _is_python_cache_artifact(path):
                problems.append("runtime_mutation")
                break
    support = release.get("support_collection")
    if isinstance(support, dict):
        if str(support.get("source_release_commit") or current_commit) != current_commit:
            problems.append("support_wrong_release")
        if support.get("release_mutated") is True:
            problems.append("support_mutated_release")
    history = release.get("history")
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).casefold()
            status = str(item.get("status", "")).casefold()
            if role in RELEASE_HISTORY_BLOCKING_ROLES and status not in RELEASE_HISTORY_OK:
                problems.append(f"history:{role}")
    if problems:
        return {"status": "FAIL", "code": "RELEASE_LIFECYCLE_UNSAFE", "detail": ",".join(sorted(set(problems)))}
    return {"status": "PASS", "code": "RELEASE_LIFECYCLE_READY", "current_commit": current_commit}


def replay_resource_capacity(manifest: dict[str, object]) -> dict[str, object]:
    resources = manifest.get("resources")
    if not isinstance(resources, dict):
        return {"status": "FAIL", "code": "RESOURCE_CAPACITY_UNDECLARED", "detail": "resources"}
    minimum = resources.get("minimum_required_free_kib", MIN_TARGET_FREE_KIB)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < MIN_TARGET_FREE_KIB:
        minimum = MIN_TARGET_FREE_KIB
    failures = []
    for field in ("root_free_kib", "var_free_kib"):
        value = resources.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            failures.append(field)
        elif value < minimum:
            failures.append(f"{field}={value}")
    if failures:
        return {"status": "FAIL", "code": "RESOURCE_CAPACITY_LOW", "detail": ",".join(failures), "minimum_required_free_kib": minimum}
    return {"status": "PASS", "code": "RESOURCE_CAPACITY_READY", "minimum_required_free_kib": minimum}


def replay_model_finalization(manifest: dict[str, object]) -> dict[str, object]:
    model = manifest.get("model_finalization")
    if not isinstance(model, dict):
        model = manifest.get("ollama_model") if isinstance(manifest.get("ollama_model"), dict) else None
    if not isinstance(model, dict):
        return {"status": "FAIL", "code": "MODEL_FINALIZATION_UNDECLARED", "detail": "model_finalization"}
    problems = []
    status = str(model.get("status", "")).casefold()
    if status not in {"ready", "validated", "complete"}:
        problems.append("status")
    for field in ("install_record_valid", "digest_match", "smoke_passed"):
        if model.get(field) is not True:
            problems.append(field)
    if model.get("partial_artifacts"):
        problems.append("partial_artifacts")
    digest = str(model.get("model_digest", ""))
    prefix = str(model.get("model_digest_prefix", ""))
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        problems.append("model_digest")
    elif prefix and not digest.startswith(prefix):
        problems.append("model_digest_prefix")
    quantization = str(model.get("quantization", "")).upper()
    if quantization and quantization != "Q4_K_M":
        problems.append("quantization")
    if problems:
        return {"status": "FAIL", "code": "MODEL_FINALIZATION_UNREADY", "detail": ",".join(sorted(set(problems)))}
    return {"status": "PASS", "code": "MODEL_FINALIZATION_READY", "model": model.get("model", "")}


def _i2c_device_names(i2c: dict[str, object]) -> set[str]:
    devices = i2c.get("devices")
    if not isinstance(devices, list):
        return set()
    names = set()
    for item in devices:
        if not isinstance(item, str):
            continue
        names.add(item)
        names.add(Path(item).name)
    return names


def _normalize_i2c_address(value: object) -> str:
    if isinstance(value, int):
        return f"0x{value:02x}"
    text = str(value or "").strip().casefold()
    if text in {"44", "0x44"}:
        return "0x44"
    if text in {"45", "0x45"}:
        return "0x45"
    return text


def replay_i2c_sht31(manifest: dict[str, object]) -> dict[str, object]:
    i2c = manifest.get("i2c")
    if not isinstance(i2c, dict):
        return {"status": "FAIL", "code": "I2C_SHT31_UNDECLARED", "detail": "i2c"}
    probe = i2c.get("sht31_targeted_probe")
    if not isinstance(probe, dict):
        return {"status": "FAIL", "code": "I2C_SHT31_UNDECLARED", "detail": "sht31_targeted_probe"}
    bus = str(probe.get("bus") or "/dev/i2c-1")
    status = str(probe.get("status", "")).casefold()
    if i2c.get("reboot_required") is True or status in SHT31_REBOOT_STATUSES:
        return {"status": "FAIL", "code": "I2C_REBOOT_REQUIRED", "detail": "reboot_then_resume_same_installer"}
    if Path(bus).name not in _i2c_device_names(i2c):
        return {"status": "FAIL", "code": "I2C_BUS_UNREADY", "detail": bus}
    address = _normalize_i2c_address(probe.get("address"))
    if address not in {"0x44", "0x45"}:
        return {"status": "FAIL", "code": "I2C_SHT31_UNRESOLVED", "detail": "address"}
    if probe.get("heater_enabled") is True:
        return {"status": "FAIL", "code": "I2C_SHT31_UNRESOLVED", "detail": "heater_enabled"}
    if status in SHT31_READY_STATUSES:
        result = {"status": "PASS", "code": "I2C_SHT31_READY", "bus": bus, "address": address, "probe_status": status}
        if isinstance(probe.get("valid_reads"), int):
            result["valid_reads"] = probe["valid_reads"]
        return result
    detail = status if status in SHT31_UNREADY_STATUSES else f"unsupported_status:{status}"
    return {"status": "FAIL", "code": "I2C_SHT31_UNRESOLVED", "detail": detail}


def _environment_payload(manifest: dict[str, object]) -> dict[str, object] | None:
    profile = manifest.get("environment_profile")
    if isinstance(profile, dict):
        return profile
    environment = manifest.get("environment")
    if isinstance(environment, dict):
        nested = environment.get("profile")
        if isinstance(nested, dict):
            return nested
    return None


def replay_environment_profile(manifest: dict[str, object], *, gpio: dict[str, object], i2c_sht31: dict[str, object]) -> dict[str, object]:
    profile = _environment_payload(manifest)
    if not isinstance(profile, dict):
        return {"status": "FAIL", "code": "ENVIRONMENT_PROFILE_UNDECLARED", "detail": "environment_profile"}
    name = str(profile.get("name") or profile.get("profile") or "")
    expected = ENVIRONMENT_PROFILE_SPECS.get(name)
    if expected is None:
        return {"status": "FAIL", "code": "ENVIRONMENT_PROFILE_UNKNOWN", "detail": name}
    problems = []
    for key, expected_value in expected.items():
        if profile.get(key) != expected_value:
            problems.append(key)
    if name in REAL_SENSOR_PROFILES:
        if i2c_sht31.get("status") != "PASS":
            problems.append("sht31")
        address = _normalize_i2c_address(profile.get("i2c_address"))
        if address not in {"0x44", "0x45"}:
            problems.append("i2c_address")
        if profile.get("i2c_bus") != 1:
            problems.append("i2c_bus")
    if name in REAL_RELAY_PROFILES:
        lines = gpio.get("lines") if isinstance(gpio.get("lines"), dict) else {}
        if not isinstance(lines, dict) or "GPIO23" not in lines:
            problems.append("relay_gpio23")
    if name == "full-real" and profile.get("simulation_runtime_control_enabled") is not False:
        problems.append("simulation_runtime_control_enabled")
    if problems:
        return {"status": "FAIL", "code": "ENVIRONMENT_PROFILE_UNREADY", "detail": ",".join(sorted(problems))}
    return {"status": "PASS", "code": "ENVIRONMENT_PROFILE_READY", "profile": name}


def _first_failed_code(checks: Iterable[dict[str, object]]) -> str:
    for check in checks:
        if check.get("status") != "PASS":
            return str(check.get("code") or "TARGET_SHADOW_FAILED")
    return "TARGET_SHADOW_READY"


def replay_manifest(manifest: dict[str, object], required_gpios: Iterable[int] | None = None) -> dict[str, object]:
    requirements = _manifest_requirements(manifest)
    gpio = replay_gpio_identity(manifest, required_gpios)
    format_check = {
        "status": "PASS" if manifest.get("format") == FORMAT else "FAIL",
        "code": "MANIFEST_FORMAT_VALID" if manifest.get("format") == FORMAT else "MANIFEST_FORMAT_INVALID",
    }
    privacy = replay_privacy_boundary(manifest)
    audio = replay_audio_duplex(manifest)
    audio_runtime = replay_audio_runtime(manifest)
    identity = replay_service_identity(manifest)
    release = replay_release_state(manifest)
    i2c_sht31 = replay_i2c_sht31(manifest)
    environment = replay_environment_profile(manifest, gpio=gpio, i2c_sht31=i2c_sht31)
    operator = replay_operator_identity(manifest)
    systemd = replay_systemd_runtime(manifest)
    lifecycle = replay_release_lifecycle(manifest)
    resources = replay_resource_capacity(manifest)
    model = replay_model_finalization(manifest)
    readiness_identity = replay_readiness_identity(manifest)
    required_checks = [format_check]
    if requirements["privacy_boundary"]:
        required_checks.append(privacy)
    if requirements["gpio_identity"]:
        required_checks.append(gpio)
    if requirements["audio_duplex"]:
        required_checks.append(audio)
    if requirements["audio_runtime"]:
        required_checks.append(audio_runtime)
    if requirements["service_identity"]:
        required_checks.append(identity)
    if requirements["release_state"]:
        required_checks.append(release)
    if requirements["i2c_sht31"]:
        required_checks.append(i2c_sht31)
    if requirements["environment_profile"]:
        required_checks.append(environment)
    if requirements["operator_identity"]:
        required_checks.append(operator)
    if requirements["systemd_runtime"]:
        required_checks.append(systemd)
    if requirements["release_lifecycle"]:
        required_checks.append(lifecycle)
    if requirements["resource_capacity"]:
        required_checks.append(resources)
    if requirements["model_finalization"]:
        required_checks.append(model)
    if requirements["readiness_identity"]:
        required_checks.append(readiness_identity)
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
        "audio_runtime": audio_runtime,
        "service_identity": identity,
        "release_state": release,
        "i2c_sht31": i2c_sht31,
        "environment_profile": environment,
        "operator_identity": operator,
        "systemd_runtime": systemd,
        "readiness_identity": readiness_identity,
        "release_lifecycle": lifecycle,
        "resource_capacity": resources,
        "model_finalization": model,
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


def _parse_lines(values: list[int] | None) -> tuple[int, ...] | None:
    if values is None:
        return None
    lines = tuple(values)
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
