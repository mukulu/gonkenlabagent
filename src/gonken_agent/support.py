"""Export only newly constructed allow-listed diagnostic data, never raw files."""
from __future__ import annotations

import json
import os
import hashlib
import stat
import grp
import pwd
import platform
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .health import COMPONENTS
from .telemetry import validate_event
from .diagnostics import load_snapshot, collect_environment_diagnostics
from .evidence import write_bundle
from .runtime_readiness import read_ready, read_pending
from .component_status import collect as collect_component_status
from .llm.models import active_model, selection_status, roster_manifest
from .tool_broker import TOOL_NAMES
from .environment.journal import parse_event_line


SAFE_CODE_RE = re.compile(r"^[A-Z0-9_]{1,64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
RELEASE_ROOT = Path("/usr/local/lib/gonken-agent")
INSTALL_EVENTS_DIR = Path("/var/lib/gonken-agent/install/logs/events")
SERVICE_UNITS = ("gonken-agent.service", "gonken-environment.service")
BINDING_PACKAGES = ("python3-libgpiod",)
BINDING_MANIFEST = Path(sys.prefix).parent / "share/gonken-agent/hardware-bindings.json"
TARGET_MANIFEST_FORMAT = "gonken-target-hardware-manifest-v1"


def _bounded_json_file(path: Path, *, max_bytes: int = 1024 * 1024) -> object | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _safe_release_identity() -> dict[str, object]:
    current = RELEASE_ROOT / "current"
    result: dict[str, object] = {
        "status": "UNAVAILABLE",
        "commit": None,
        "profile": None,
        "active_release": None,
        "validation": None,
    }
    try:
        if not current.is_symlink():
            return result
        target = os.readlink(current)
        match = re.fullmatch(r"releases/([0-9a-f]{40})", target)
        if not match:
            return result
        commit = match.group(1)
        record = RELEASE_ROOT / target / "release.record"
        if not record.is_file() or record.is_symlink() or record.stat().st_size > 16384:
            return result
        fields: dict[str, str] = {}
        for line in record.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in fields:
                return result
            fields[key] = value
        if fields.get("format") != "gonken-release-v1":
            return result
        if fields.get("commit") != commit or not COMMIT_RE.fullmatch(commit):
            return result
        profile = fields.get("profile", "")
        if not PROFILE_RE.fullmatch(profile):
            return result
        validation = fields.get("validation")
        if validation not in {"passed", "failed"}:
            return result
        return {
            "status": "READY",
            "commit": commit,
            "profile": profile,
            "active_release": target,
            "validation": validation,
        }
    except (OSError, UnicodeError):
        return result


def _venv_policy() -> dict[str, object]:
    config = Path(sys.prefix) / "pyvenv.cfg"
    enabled = None
    try:
        if config.is_file() and not config.is_symlink() and config.stat().st_size <= 16384:
            for line in config.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip().casefold() == "include-system-site-packages":
                    normalized = value.strip().casefold()
                    enabled = normalized == "true" if normalized in {"true", "false"} else None
                    break
    except (OSError, UnicodeError):
        enabled = None
    return {
        "system_site_packages": enabled,
        "interpreter_is_venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
    }


def _module_probe(code: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "UNAVAILABLE", "code": "PROBE_FAILED"}
    return {
        "status": "READY" if result.returncode == 0 else "FAILED",
        "code": "IMPORT_API_OK" if result.returncode == 0 else "IMPORT_API_FAILED",
    }


def _package_versions() -> dict[str, object]:
    command = shutil.which("dpkg-query")
    if not command:
        return {name: {"status": "UNAVAILABLE", "version": None} for name in BINDING_PACKAGES}
    output: dict[str, object] = {}
    for name in BINDING_PACKAGES:
        try:
            result = subprocess.run(
                [command, "-W", "-f=${db:Status-Abbrev}\t${Version}", name],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            output[name] = {"status": "UNAVAILABLE", "version": None}
            continue
        fields = result.stdout.strip().split("\t", 1)
        installed = result.returncode == 0 and len(fields) == 2 and fields[0].startswith("ii")
        version = fields[1] if installed and re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", fields[1]) else None
        output[name] = {"status": "INSTALLED" if version else "NOT_INSTALLED", "version": version}
    return output


def _binding_bridge() -> dict[str, object]:
    path = BINDING_MANIFEST
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            return {"status": "UNAVAILABLE", "format": None, "profile": None, "packages": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "UNAVAILABLE", "format": None, "profile": None, "packages": []}
    if payload.get("format") != "gonken-hardware-binding-bridge-v1":
        return {"status": "INVALID", "format": None, "profile": None, "packages": []}
    packages = []
    for item in payload.get("packages", []):
        if not isinstance(item, dict):
            continue
        name = item.get("package")
        version = item.get("version")
        files = item.get("files")
        if name not in BINDING_PACKAGES or not isinstance(version, str) or not isinstance(files, list):
            continue
        packages.append({"package": name, "version": version, "file_count": len(files)})
    return {
        "status": "READY" if {item["package"] for item in packages} == set(BINDING_PACKAGES) else "DEGRADED",
        "format": payload.get("format"),
        "profile": payload.get("profile"),
        "packages": sorted(packages, key=lambda item: item["package"]),
    }


def _i2c_platform_health() -> dict[str, object]:
    device = Path("/dev/i2c-1")
    device_exists = device.exists() and not device.is_symlink()
    service_user_exists = False
    service_user_i2c_group = False
    try:
        account = pwd.getpwnam("gonken-env")
        service_user_exists = True
        memberships = {grp.getgrgid(account.pw_gid).gr_name}
        memberships.update(entry.gr_name for entry in grp.getgrall() if "gonken-env" in entry.gr_mem)
        service_user_i2c_group = "i2c" in memberships
    except (KeyError, OSError):
        pass
    ready = device_exists and service_user_exists and service_user_i2c_group
    return {
        "status": "READY" if ready else "NOT_READY",
        "device": "/dev/i2c-1",
        "device_exists": device_exists,
        "service_user_exists": service_user_exists,
        "service_user_i2c_group": service_user_i2c_group,
    }



def _gpio_platform_health() -> dict[str, object]:
    """Return bounded, non-actuating GPIO23 discovery evidence."""
    gpiochips = sorted(Path("/dev").glob("gpiochip*"))
    valid_chips = [path.name for path in gpiochips if path.exists() and not path.is_symlink()]
    result: dict[str, object] = {
        "status": "UNAVAILABLE",
        "gpiochip_count": len(valid_chips),
        "gpio23": {"status": "UNRESOLVED", "chip": None, "line_offset": None, "line_name": "GPIO23"},
    }
    tool = shutil.which("gpioinfo")
    if not tool:
        return result
    try:
        completed = subprocess.run(
            [tool, "--strict", "GPIO23"],
            check=False, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return result
    match = re.search(r'^(gpiochip\d+)\s+(\d+)\s+"GPIO23"(?:\s|$)', completed.stdout, re.M)
    if completed.returncode == 0 and match:
        result["status"] = "READY"
        result["gpio23"] = {
            "status": "RESOLVED",
            "chip": match.group(1),
            "line_offset": int(match.group(2)),
            "line_name": "GPIO23",
        }
    else:
        result["status"] = "NOT_READY"
    return result


def _runtime_context_health() -> dict[str, object]:
    """Summarize service-user runtime context without exporting paths or content."""
    result: dict[str, object] = {
        "status": "NOT_READY",
        "audio_user_exists": False,
        "runtime_environment_file_exists": False,
        "runtime_dir_exists": False,
        "runtime_dir_owner_matches": False,
        "pipewire_socket_exists": False,
        "pulse_socket_exists": False,
    }
    try:
        account = pwd.getpwnam("gonken-agent")
    except KeyError:
        return result
    result["audio_user_exists"] = True
    runtime_environment = Path("/etc/gonken-agent/runtime-environment")
    result["runtime_environment_file_exists"] = runtime_environment.is_file() and not runtime_environment.is_symlink()
    runtime_dir = Path("/run/user") / str(account.pw_uid)
    try:
        stat_result = runtime_dir.stat()
        result["runtime_dir_exists"] = runtime_dir.is_dir() and not runtime_dir.is_symlink()
        result["runtime_dir_owner_matches"] = stat_result.st_uid == account.pw_uid
    except OSError:
        return result
    result["pipewire_socket_exists"] = (runtime_dir / "pipewire-0").exists()
    result["pulse_socket_exists"] = (runtime_dir / "pulse/native").exists()
    structural_ready = bool(
        result["runtime_environment_file_exists"]
        and result["runtime_dir_exists"]
        and result["runtime_dir_owner_matches"]
    )
    result["status"] = "READY" if structural_ready else "NOT_READY"
    return result

def _safe_audio_endpoint(value: str) -> str | None:
    """Return bounded endpoint metadata without stable device identifiers."""
    value = re.sub(
        r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}|(?:[0-9a-f]{2}_){5}[0-9a-f]{2}",
        "DEVICE",
        value.strip(),
    )
    value = re.sub(r"[^A-Za-z0-9_.:+/@ -]", "", value)[:160]
    return value or None


def _service_user_audio_context() -> dict[str, object]:
    """Collect metadata-only audio-session evidence in the exact service identity."""
    result: dict[str, object] = {
        "status": "UNAVAILABLE",
        "service_user": "gonken-agent",
        "server_ready": False,
        "default_source": None,
        "default_sink": None,
        "source_count": 0,
        "sink_count": 0,
        "capture_content_collected": False,
    }
    try:
        account = pwd.getpwnam("gonken-agent")
    except KeyError:
        return result
    pactl = shutil.which("pactl")
    if not pactl:
        return result
    current_euid = os.geteuid()
    if current_euid not in {0, account.pw_uid}:
        result["code"] = "SERVICE_IDENTITY_REQUIRED"
        return result
    runtime_dir = f"/run/user/{account.pw_uid}"
    environment = os.environ.copy()
    environment["XDG_RUNTIME_DIR"] = runtime_dir
    environment["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    base: list[str] = []
    if current_euid == 0 and current_euid != account.pw_uid:
        runuser = shutil.which("runuser")
        if not runuser:
            return result
        base = [runuser, "-u", "gonken-agent", "--"]
    def invoke(extra: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                base + [pactl] + extra, check=False, capture_output=True, text=True,
                timeout=5, env=environment,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
    info = invoke(["info"])
    if info is None or info.returncode != 0:
        result["status"] = "NOT_READY"
        return result
    result["server_ready"] = True
    for line in info.stdout.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        normalized = key.strip().casefold()
        safe_value = _safe_audio_endpoint(value)
        if normalized == "default source":
            result["default_source"] = safe_value
        elif normalized == "default sink":
            result["default_sink"] = safe_value
        elif normalized == "server name":
            result["server_name"] = safe_value
    sources = invoke(["list", "short", "sources"])
    sinks = invoke(["list", "short", "sinks"])
    if sources is not None and sources.returncode == 0:
        result["source_count"] = len([line for line in sources.stdout.splitlines() if line.strip()])
    if sinks is not None and sinks.returncode == 0:
        result["sink_count"] = len([line for line in sinks.stdout.splitlines() if line.strip()])
    result["status"] = "READY" if result["source_count"] > 0 and result["sink_count"] > 0 else "DEGRADED"
    return result


def _runtime_readiness_state() -> dict[str, object]:
    path = Path("/run/gonken-agent/readiness.json")
    payload = _bounded_json_file(path, max_bytes=8192)
    if not isinstance(payload, dict) or payload.get("format") != "gonken-voice-readiness-v1":
        return {"status": "UNAVAILABLE", "code": "READINESS_STATE_UNAVAILABLE"}
    code = str(payload.get("code", ""))
    component = str(payload.get("component", ""))
    status = str(payload.get("status", ""))
    if not SAFE_CODE_RE.fullmatch(code) or status not in {"WAITING", "READY"} or not re.fullmatch(r"[a-z0-9_.-]{1,64}", component):
        return {"status": "INVALID", "code": "READINESS_STATE_INVALID"}
    return {
        "status": status,
        "code": code,
        "component": component,
        "recoverable": bool(payload.get("recoverable")),
        "release_commit": payload.get("release_commit") if isinstance(payload.get("release_commit"), str) else None,
        "release_profile": payload.get("release_profile") if isinstance(payload.get("release_profile"), str) else None,
        "service_start_ticks": payload.get("service_start_ticks") if isinstance(payload.get("service_start_ticks"), int) else None,
        "observed_epoch": payload.get("observed_epoch") if isinstance(payload.get("observed_epoch"), int) else None,
    }


def _runtime_binding_health() -> dict[str, object]:
    gpiod = _module_probe(
        "import gpiod; from gpiod.line import Bias,Direction,Value; "
        "assert callable(getattr(gpiod,'Chip',None)); "
        "assert callable(getattr(gpiod,'LineSettings',None)); "
        "assert callable(getattr(gpiod,'request_lines',None)); "
        "assert callable(getattr(gpiod.Chip,'get_info',None)); "
        "assert callable(getattr(gpiod.Chip,'get_line_info',None)); "
        "assert Bias is not None and Direction is not None and Value is not None"
    )
    return {
        "release": _safe_release_identity(),
        "venv": _venv_policy(),
        "binding_bridge": _binding_bridge(),
        "bindings": {"gpiod": gpiod},
        "sensor_transport": {"status": "READY", "type": "linux-i2c-dev-stdlib", "python_smbus_required": False},
        "i2c_platform": _i2c_platform_health(),
        "gpio_platform": _gpio_platform_health(),
        "runtime_context": _runtime_context_health(),
        "audio_session": _service_user_audio_context(),
        "voice_readiness": _runtime_readiness_state(),
        "distro_packages": _package_versions(),
    }


def _read_event(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            return None
        fields: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in fields:
                return None
            fields[key] = value
    except (OSError, UnicodeError):
        return None
    if fields.get("format") != "gonken-install-event-v1":
        return None
    level = fields.get("level", "")
    code = fields.get("code", "")
    step = fields.get("step_id", "")
    message = fields.get("message", "")
    run_id = fields.get("run_id", "")
    sequence = fields.get("sequence", "")
    observed_epoch = fields.get("observed_epoch", "")
    if level not in {"info", "error"} or not SAFE_CODE_RE.fullmatch(code):
        return None
    if not re.fullmatch(r"[a-z0-9_.-]{1,64}|none", step):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", message):
        return None
    if not re.fullmatch(r"[0-9.]{3,64}", run_id) or not sequence.isdigit() or not observed_epoch.isdigit():
        return None
    return {
        "run_id": run_id, "sequence": int(sequence), "observed_epoch": int(observed_epoch),
        "level": level, "code": code, "step_id": step, "message": message,
    }


def _install_events(limit: int = 40) -> dict[str, object]:
    if not INSTALL_EVENTS_DIR.is_dir() or INSTALL_EVENTS_DIR.is_symlink():
        return {"status": "UNAVAILABLE", "events": []}
    events = []
    for path in sorted(INSTALL_EVENTS_DIR.glob("*.event"))[-limit:]:
        event = _read_event(path)
        if event is not None:
            events.append(event)
    latest_run_id = events[-1]["run_id"] if events else None
    latest_run = [event for event in events if event.get("run_id") == latest_run_id] if latest_run_id else []
    return {
        "status": "READY", "events": events, "latest_run_id": latest_run_id,
        "latest_run_event_count": len(latest_run),
        "latest_run_last_code": latest_run[-1]["code"] if latest_run else None,
    }


def _voice_metric_line(line: str) -> dict[str, object] | None:
    """Retain only bounded numeric/boolean timing fields, never spoken content."""
    match = re.search(r"(?:^|\s)code=(WAKE_STREAM_METRICS|VOICE_CAPTURE_METRICS|VOICE_TURN_METRICS|WAKE_DETECTED)(?:\s|$)", line[:4096])
    if not match:
        return None
    result: dict[str, object] = {"code": match.group(1)}
    for key in ("utterance_ms", "keyword_decode_max_ms", "transcription_ms", "capture_ms",
                "recognition_ms", "dropped_windows", "answer_ms", "pending_resolved", "ack_cache_ms"):
        found = re.search(r"(?:^|\s)" + key + r"=([0-9]+(?:\.[0-9]+)?)(?:\s|$)", line[:4096])
        if found:
            value = float(found.group(1))
            if 0 <= value <= 600000:
                result[key] = int(value) if value.is_integer() else value
    for key in ("native_keyword", "fallback", "inline", "heard_new_audio"):
        found = re.search(r"(?:^|\s)" + key + r"=(True|False|true|false)(?:\s|$)", line[:4096])
        if found:
            result[key] = found.group(1).lower() == "true"
    return result if len(result) > 1 else None


def _service_event_codes(limit: int = 200) -> dict[str, object]:
    """Summarize current-boot structured reason codes without exporting journal text."""
    journalctl = shutil.which("journalctl")
    if not journalctl:
        return {"status": "UNAVAILABLE", "scope": "current_boot", "units": {}}
    units: dict[str, object] = {}
    for unit in SERVICE_UNITS:
        try:
            result = subprocess.run(
                [journalctl, "-u", unit, "-b", "--no-pager", "-n", str(limit), "-o", "cat"],
                check=False, capture_output=True, text=True, timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            units[unit] = {"status": "UNAVAILABLE", "codes": {}, "events": []}
            continue
        counts = Counter()
        summaries: dict[str, dict[str, object]] = {}
        actuator_transitions = []
        voice_metrics = []
        for sequence, line in enumerate(result.stdout.splitlines()[-limit:], 1):
            if unit == "gonken-agent.service":
                metric = _voice_metric_line(line)
                if metric is not None:
                    voice_metrics.append({"journal_sequence": sequence, **metric})
            event = parse_event_line(line) if unit == "gonken-environment.service" else None
            if event is not None:
                actuator_transitions.append({"journal_sequence": sequence, **event})
                line = "[INFO] code=" + str(event['code'])
            match = re.search(r"(?:^|\s)code=([A-Z0-9_]{1,64})(?:\s|$)", line)
            if not match:
                continue
            code = match.group(1)
            counts[code] += 1
            level_match = re.match(r"^\[([A-Z]{2,12})\]", line)
            level = level_match.group(1) if level_match else "UNKNOWN"
            row = summaries.setdefault(code, {"code": code, "count": 0, "first_sequence": sequence, "last_sequence": sequence, "last_level": level})
            row["count"] = int(row["count"]) + 1
            row["last_sequence"] = sequence
            row["last_level"] = level
        units[unit] = {
            "status": "READY" if result.returncode == 0 else "DEGRADED",
            "codes": dict(sorted(counts.items())),
            "events": [summaries[key] for key in sorted(summaries)],
            "lines_examined": min(limit, len(result.stdout.splitlines())),
            "raw_text_exported": False,
            "actuator_transitions": actuator_transitions[-40:],
            "voice_metrics": voice_metrics[-20:],
            "event_scope": "current_boot_history_not_current_readiness",
        }
    return {"status": "READY", "scope": "current_boot", "units": units}


def _existing_environment_reconciliation() -> dict[str, object]:
    """Expose the historical installer phase, not a live readiness declaration."""
    path = INSTALL_EVENTS_DIR.parent.parent / "environment-current-reconciliation.json"
    data = _bounded_json_file(path, max_bytes=16384)
    result = {"status": "UNAVAILABLE", "scope": "existing_environment_reconciliation_record",
              "runtime_freshness_claimed": False, "physical_acceptance_claimed": False}
    if not isinstance(data, dict) or data.get('format') != 'gonken-existing-environment-reconciliation-v1':
        return result
    state = data.get('status')
    if state not in {'RUNNING','READY_EXISTING_ENVIRONMENT','DEFERRED_NO_CURRENT','DEGRADED_EXISTING_ENVIRONMENT'}:
        return result
    inputs = data.get('inputs', {})
    if not isinstance(inputs, dict): return result
    clean_inputs = {}
    for key, length in (('candidate_commit',40),('current_commit',40),('configuration_inputs_sha256',64)):
        value = inputs.get(key)
        if value is not None and (not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',value)):
            return result
        clean_inputs[key] = value
    if inputs.get('mode_requested') not in {'preserve','manual','semi_automatic','automatic','disabled'}:
        return result
    clean_inputs['mode_requested'] = inputs['mode_requested']
    result.update(status='READY', recorded_status=state, inputs=clean_inputs,
                  global_activation_changed=False)
    invocation = data.get('invocation_id')
    if isinstance(invocation,str) and re.fullmatch('[0-9a-f]{32}',invocation):result['invocation_id']=invocation
    code = data.get('reason_code')
    if isinstance(code,str) and re.fullmatch('[A-Za-z0-9_]{1,64}',code):result['reason_code']=code
    return result


def _boot_id() -> str | None:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip().lower()
    except (OSError, UnicodeError):
        return None
    return value if re.fullmatch(r"[0-9a-f-]{36}", value) else None


def _evidence_phase_context(install_events: dict[str, object] | None = None) -> dict[str, object]:
    release = _safe_release_identity()
    readiness = read_pending()
    ready = read_ready()
    install_events = install_events if isinstance(install_events, dict) else {}
    return {
        "status": "READY",
        "phase": "runtime_support_collection",
        "install_run_id": install_events.get("latest_run_id"),
        "boot_id": _boot_id(),
        "release": release,
        "voice_readiness": readiness if isinstance(readiness, dict) else {"status": "UNAVAILABLE"},
        "voice_ready": ready if isinstance(ready, dict) else {"status": "UNAVAILABLE"},
        "precedence": "current_runtime_state_over_same_boot_history_over_install_history",
        "physical_acceptance_claimed": False,
    }


def _safe_owner_group(st) -> tuple[str | None, str | None]:
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = None
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = None
    return owner, group


def _path_permission(label: str, path: Path, *, expected_owner: str | None = None, expected_group: str | None = None, expected_mode: int | None = None) -> dict[str, object]:
    row: dict[str, object] = {"label": label, "status": "MISSING", "exists": False}
    try:
        if path.is_symlink():
            row.update({"status": "UNSAFE_SYMLINK", "exists": True})
            return row
        st = path.stat()
    except OSError:
        return row
    owner, group = _safe_owner_group(st)
    mode = stat.S_IMODE(st.st_mode)
    matches = True
    if expected_owner is not None:
        matches = matches and owner == expected_owner
    if expected_group is not None:
        matches = matches and group == expected_group
    if expected_mode is not None:
        matches = matches and mode == expected_mode
    row.update({
        "status": "READY" if matches else "MISMATCH",
        "exists": True,
        "owner": owner,
        "group": group,
        "mode_octal": f"{mode:04o}",
        "expected_owner": expected_owner,
        "expected_group": expected_group,
        "expected_mode_octal": f"{expected_mode:04o}" if expected_mode is not None else None,
    })
    return row


def _permissions_manifest(config) -> dict[str, object]:
    env = config.extensions.environment
    entries = [
        _path_permission("environment_state_dir", Path("/var/lib/gonken-environment"), expected_owner="gonken-env", expected_group="gonken-env", expected_mode=0o750),
        _path_permission("environment_policy", Path(env.policy_path), expected_owner="gonken-env", expected_group="gonken-env", expected_mode=0o640),
        _path_permission("environment_run_dir", Path("/run/gonken-environment"), expected_owner="gonken-env", expected_group="gonken-envctl", expected_mode=0o2770),
        _path_permission("environment_socket", Path(env.socket_path), expected_owner="gonken-env", expected_group="gonken-envctl", expected_mode=0o660),
        _path_permission("ollama_model_store", Path("/var/lib/ollama/models"), expected_owner="ollama", expected_group="ollama"),
        _path_permission("model_selection", Path("/var/lib/gonken-agent/ollama/active-model.json")),
        _path_permission("model_roster_record", Path("/var/lib/gonken-agent/ollama/roster.json")),
        _path_permission("site_config", Path("/etc/gonken-agent/config.toml")),
    ]
    return {
        "status": "READY" if not any(row["status"] in {"MISMATCH", "UNSAFE_SYMLINK"} for row in entries) else "DEGRADED",
        "entries": entries,
        "paths_allowlisted": True,
    }


def _systemd_unit_state(unit: str) -> dict[str, object]:
    tool = shutil.which("systemctl")
    if not tool:
        return {"status": "UNAVAILABLE"}
    properties = ("ActiveState", "SubState", "UnitFileState", "MainPID", "ExecMainStatus", "Result", "InvocationID", "FragmentPath", "DropInPaths")
    command = [tool, "show", unit] + [f"--property={item}" for item in properties]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "UNAVAILABLE"}
    values: dict[str, object] = {}
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep and key in properties:
                if key in {"MainPID", "ExecMainStatus"} and value.isdigit():
                    values[key] = int(value)
                elif len(value) <= 512 and not any(ch in value for ch in "\r\n"):
                    values[key] = value
    return {"status": "READY" if result.returncode == 0 else "DEGRADED", "properties": values}


def _systemd_effective_state() -> dict[str, object]:
    return {"status": "READY", "units": {unit: _systemd_unit_state(unit) for unit in (*SERVICE_UNITS, "ollama.service")}}


def _configuration_provenance(effective_config) -> dict[str, object]:
    sources = effective_config.source_dict()
    counts = Counter(str(value) for value in sources.values())
    return {
        "status": "READY",
        "field_sources": sources,
        "source_counts": dict(sorted(counts.items())),
        "site_config_present": Path("/etc/gonken-agent/config.toml").is_file(),
        "values_exported_here": False,
    }


def _ollama_inventory(config) -> dict[str, object]:
    try:
        from .llm import admin as llm_admin
        return llm_admin.status(config)
    except Exception as exc:
        return {"status": "UNAVAILABLE", "code": type(exc).__name__, "selection": selection_status(config.llm.model), "roster": roster_manifest()}


def _tool_broker_health(config, component_evidence: dict | None = None) -> dict[str, object]:
    # Consume the same component result, not a second unconditional READY rule.
    evidence = component_evidence if isinstance(component_evidence, dict) else {}
    components = evidence.get("components", {})
    broker = components.get("llm_environment_tool_broker", {}) if isinstance(components, dict) else {}
    return {
        "status": broker.get("status", "UNAVAILABLE"),
        "code": broker.get("code", "ACTIVE_MODEL_TOOLS_NOT_QUALIFIED"),
        "active_model": active_model(config.llm.model),
        "implementation_available": broker.get("implementation_available", False),
        "active_model_qualified": broker.get("active_model_qualified", False),
        "tools": sorted(TOOL_NAMES),
        "mutation_policy": "explicit_present_tense_user_authorization_required",
        "raw_shell": False,
        "raw_gpio": False,
        "raw_i2c": False,
        "physical_acceptance_claimed": False,
    }


def _diagnostic_summary(files: dict[str, object]) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    phase = files.get("evidence_phase.json") if isinstance(files.get("evidence_phase.json"), dict) else {}
    ready = phase.get("voice_ready") if isinstance(phase.get("voice_ready"), dict) else {}
    service_events = files.get("service_events.json") if isinstance(files.get("service_events.json"), dict) else {}
    units = service_events.get("units") if isinstance(service_events.get("units"), dict) else {}
    voice_events = units.get("gonken-agent.service") if isinstance(units.get("gonken-agent.service"), dict) else {}
    codes = voice_events.get("codes") if isinstance(voice_events.get("codes"), dict) else {}
    if ready.get("status") != "READY":
        findings.append({"code": "VOICE_RUNTIME_NOT_CURRENT", "severity": "warning"})
    if ready.get("status") == "READY" and any(code in codes for code in ("AUDIO_CAPTURE_FAILED", "VOICE_DEPENDENCY_WAIT")):
        findings.append({"code": "VOICE_READY_WITH_RECOVERED_HISTORY", "severity": "info", "current_state": "READY", "history": "recoverable_errors_present", "interpretation": "historical errors do not override current semantic readiness"})
    permissions = files.get("permissions.json") if isinstance(files.get("permissions.json"), dict) else {}
    for row in permissions.get("entries", []) if isinstance(permissions.get("entries"), list) else []:
        if isinstance(row, dict) and row.get("status") == "MISMATCH":
            findings.append({"code": "PERMISSION_INVARIANT_MISMATCH", "severity": "error", "label": row.get("label")})
    components = files.get("component_readiness.json") if isinstance(files.get("component_readiness.json"), dict) else {}
    comp = components.get("components") if isinstance(components.get("components"), dict) else {}
    fan = comp.get("room_fan_control") if isinstance(comp.get("room_fan_control"), dict) else {}
    sensor = comp.get("temperature_humidity_sensor") if isinstance(comp.get("temperature_humidity_sensor"), dict) else {}
    if fan.get("simulated") is True and sensor.get("simulated") is False and sensor.get("backend") == "sht31":
        findings.append({"code": "REAL_SENSOR_WITH_SIMULATED_ACTUATOR", "severity": "info", "physical_fan_acceptance": False})
    ollama = files.get("ollama_inventory.json") if isinstance(files.get("ollama_inventory.json"), dict) else {}
    if ollama.get("status") != "READY":
        findings.append({"code": "OLLAMA_ROSTER_NOT_READY", "severity": "warning"})
    return {"status": "READY", "collection_status": "READY", "incident_status": "DEGRADED" if any(f.get("severity") in {"error", "warning"} for f in findings) else "NO_CURRENT_FAULT_IDENTIFIED", "findings": findings, "finding_count": len(findings), "causal_precedence": "current_state_then_same_boot_history_then_older_install_history"}


def _memory_inventory() -> dict[str, object]:
    keys = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, remainder = line.partition(":")
            if key in keys:
                number = remainder.strip().split(" ", 1)[0]
                if number.isdigit():
                    values[f"{key.lower()}_kib"] = int(number)
    except OSError:
        pass
    return values


def _command_inventory() -> dict[str, bool]:
    commands = (
        "arecord",
        "aplay",
        "bluetoothctl",
        "gpiodetect",
        "gpioinfo",
        "i2cdetect",
        "journalctl",
        "ollama",
        "systemctl",
        "vcgencmd",
    )
    return {name: shutil.which(name) is not None for name in commands}


def _safe_command_output(command: list[str], *, timeout: float = 3.0, limit: int = 160) -> dict[str, object]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "UNAVAILABLE", "exit": None, "summary": type(exc).__name__}
    text = " ".join((result.stdout or result.stderr or "").replace("\x00", "").split())[:limit]
    return {"status": "READY" if result.returncode == 0 else "DEGRADED", "exit": result.returncode, "summary": text}


def _platform_inventory() -> dict[str, object]:
    root = shutil.disk_usage("/")
    var = shutil.disk_usage("/var") if Path("/var").exists() else root
    payload: dict[str, object] = {
        "schema": 1,
        "content_logging": False,
        "python": platform.python_version(),
        "system": platform.system(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "disk": {
            "root_total_kib": root.total // 1024,
            "root_free_kib": root.free // 1024,
            "var_total_kib": var.total // 1024,
            "var_free_kib": var.free // 1024,
        },
        "memory": _memory_inventory(),
        "commands": _command_inventory(),
        "release": _safe_release_identity(),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else [],
    }
    if shutil.which("vcgencmd"):
        payload["throttled"] = _safe_command_output(["vcgencmd", "get_throttled"], timeout=3, limit=80)
    else:
        payload["throttled"] = {"status": "UNAVAILABLE", "exit": None, "summary": "vcgencmd_missing"}
    return payload


def _target_manifest_member(path: Path | None) -> dict[str, object]:
    if path is None:
        return {
            "status": "UNAVAILABLE",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_manifest_not_supplied",
            "physical_acceptance_claimed": False,
            "privacy": {
                "raw_audio_included": False,
                "transcripts_included": False,
                "prompts_or_model_responses_included": False,
            },
        }
    payload = _bounded_json_file(path)
    if not isinstance(payload, dict) or payload.get("format") != TARGET_MANIFEST_FORMAT:
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_manifest_invalid_or_unreadable",
            "physical_acceptance_claimed": False,
        }
    if payload.get("physical_acceptance_claimed") is not False:
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_manifest_claims_physical_acceptance",
            "physical_acceptance_claimed": False,
        }
    privacy = payload.get("privacy")
    if not isinstance(privacy, dict) or any(
        privacy.get(key) is not False
        for key in ("raw_audio_included", "transcripts_included", "prompts_or_model_responses_included")
    ):
        return {
            "status": "INVALID",
            "format": TARGET_MANIFEST_FORMAT,
            "detail": "target_probe_manifest_privacy_boundary_invalid",
            "physical_acceptance_claimed": False,
        }
    result = dict(payload)
    result["support_member_status"] = "READY"
    return result


def _evidence_index(files: dict[str, object]) -> dict[str, object]:
    return {
        "schema": 1,
        "format": "gonken-support-evidence-index-v1",
        "content_logging": False,
        "physical_acceptance_claimed": False,
        "diagnostic_package_role": (
            "single-upload target evidence bundle for host-side troubleshooting and next-package construction"
        ),
        "members": sorted(files),
        "privacy_exclusions": [
            "raw audio",
            "conversation transcripts",
            "prompts or model responses",
            "credentials",
            "Wi-Fi passphrases",
            "arbitrary raw journal text",
        ],
        "interpretation": (
            "The bundle can establish target topology, runtime state, logs-by-code and failure provenance. "
            "It does not by itself prove physical fan blade motion, acoustic quality or sensor placement."
        ),
    }


def create_bundle(
    output,
    effective_config,
    health,
    telemetry_path=None,
    allowed_source_ids=(),
    startup_snapshot=None,
    target_manifest=None,
):
    output=Path(output).absolute()
    if output.exists() or output.is_symlink() or output.parent.resolve()!=output.parent:
        raise ValueError('support output must be a new file in a safe directory')
    # Caller-supplied health detail is not copied. Only schema-validated categories survive.
    rows=[]
    for row in health.get('components',[]):
        if row.get('component') not in COMPONENTS or row.get('status') not in {'READY','FAILED','DEGRADED','MAINTENANCE'}:
            raise ValueError('invalid support health')
        code = row.get('code')
        if not isinstance(code, str) or not SAFE_CODE_RE.fullmatch(code):
            raise ValueError('invalid support health code')
        rows.append({'component':row['component'],'status':row['status'],'code':code})
    events=[]
    if telemetry_path is not None:
        path=Path(telemetry_path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>8*1024*1024:
            raise ValueError('unsafe support telemetry input')
        with path.open('rb') as stream:
            raw=stream.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('telemetry limit')
        for line in raw.splitlines()[-100:]:
            record=json.loads(line)
            # Drop timestamps rather than treating arbitrary timestamp strings as trusted.
            record.pop('timestamp',None)
            events.append(validate_event(record,allowed_source_ids))
    files={
        'environment.json':{'schema':1,'package_version':__version__,'python':platform.python_version(),
                            'system':platform.system(),'architecture':platform.machine(),
                            'target_acceptance':'not_established_by_support_export'},
        'configuration.json':{'config':effective_config.as_dict(redact=True),'sources':effective_config.source_dict()},
        'health.json':{'components':rows},
        'telemetry.json':{'content_logging':False,'events':events},
        'environment_control.json': collect_environment_diagnostics(effective_config.config, mode='production'),
        'runtime_bindings.json': _runtime_binding_health(),
        'platform_inventory.json': _platform_inventory(),
        'target_manifest.json': _target_manifest_member(Path(target_manifest) if target_manifest is not None else None),
        'install_events.json': _install_events(),
        'service_events.json': _service_event_codes(),
    }
    collection_errors: list[dict[str, str]] = []
    def collect_optional(name: str, producer) -> None:
        try:
            files[name] = producer()
        except Exception as exc:
            code = type(exc).__name__
            files[name] = {'status': 'UNAVAILABLE', 'code': code}
            collection_errors.append({'section': name, 'error_type': code})

    collect_optional('component_readiness.json', lambda: collect_component_status(effective_config.config, environment_evidence=files['environment_control.json']))
    from .resources import resource_document
    collect_optional('resource_claims.json', lambda: resource_document(effective_config.config))
    from .power_diagnostics import collect as collect_power_status
    collect_optional('power_status.json', lambda: collect_power_status(effective_config.config))
    collect_optional('evidence_phase.json', lambda: _evidence_phase_context(files.get('install_events.json') if isinstance(files.get('install_events.json'), dict) else None))
    collect_optional('permissions.json', lambda: _permissions_manifest(effective_config.config))
    collect_optional('systemd_effective.json', _systemd_effective_state)
    collect_optional('environment_current_reconciliation.json', _existing_environment_reconciliation)
    collect_optional('configuration_provenance.json', lambda: _configuration_provenance(effective_config))
    collect_optional('ollama_inventory.json', lambda: _ollama_inventory(effective_config.config))
    collect_optional('tool_broker.json', lambda: _tool_broker_health(effective_config.config, files.get('component_readiness.json')))
    files['collection_errors.json'] = {
        'status': 'READY' if not collection_errors else 'DEGRADED',
        'errors': collection_errors,
        'error_count': len(collection_errors),
    }
    files['diagnostic_summary.json'] = _diagnostic_summary(files)
    environment_health = health.get('environment')
    if isinstance(environment_health, dict):
        files['environment_health.json'] = environment_health
    if startup_snapshot is not None:
        files['startup_snapshot.json']=load_snapshot(startup_snapshot)
    release = files["runtime_bindings.json"].get("release", {}) if isinstance(files["runtime_bindings.json"], dict) else {}
    package_commit = release.get("commit") if isinstance(release, dict) and isinstance(release.get("commit"), str) else None
    producers = {name: "gonken_agent.support" for name in files}
    result = write_bundle(
        output, files, bundle_kind="support", producers=producers, package_commit=package_commit
    )
    return result
