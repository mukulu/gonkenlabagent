"""Content-free target platform snapshots for service startup and support."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__


SNAPSHOT_SCHEMA = 1
COMMANDS = (
    "python3",
    "systemctl",
    "journalctl",
    "arecord",
    "aplay",
    "parecord",
    "paplay",
    "pactl",
    "bluetoothctl",
    "rfkill",
    "wpctl",
    "ollama",
    "whisper-cli",
    "piper",
    "i2cdetect",
    "gpioinfo",
)
SERVICES = (
    "gonken-agent.service",
    "ollama.service",
    "bluetooth.service",
    "gonken-bluetooth-autoconnect.service",
    "gonken-environment.service",
)


def default_snapshot_dir(config) -> Path:
    return Path(config.paths.state_dir) / "runtime" / "startup"


def collect_snapshot(config, *, mode: str = "debug") -> dict[str, object]:
    if mode not in {"debug", "production"}:
        raise ValueError("diagnostic mode must be debug or production")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "timestamp": now,
        "mode": mode,
        "package": {"version": __version__},
        "platform": _platform(),
        "process": _process(),
        "resources": _resources(config),
        "commands": {name: shutil.which(name) is not None for name in COMMANDS},
        "services": _services(),
        "audio": _audio(mode),
        "gpio": _gpio(mode),
        "environment": collect_environment_diagnostics(config, mode=mode),
        "network": {
            "external_probe": False,
            "ollama_host": urlsplit(config.llm.base_url).hostname,
            "ollama_port": urlsplit(config.llm.base_url).port,
        },
        "configuration": {
            "audio_input_match": config.audio.input_match,
            "audio_output_match": config.audio.output_match,
            "capture_rate": config.audio.capture_rate,
            "processing_rate": config.audio.processing_rate,
            "push_to_talk_gpio": config.interaction.push_to_talk_gpio,
            "recording_led_gpio": config.interaction.recording_led_gpio,
            "llm_model": config.llm.model,
            "stt_model": config.stt.model,
            "tts_voice": config.tts.voice,
        },
        "privacy": {
            "content_logging": False,
            "raw_audio_retention": config.privacy.raw_audio_retention,
        },
    }


def collect_environment_diagnostics(config, *, mode: str = "debug", client_factory=None) -> dict[str, object]:
    """Return content-free room-environment diagnostic facts.

    This routine is deliberately non-destructive.  It may inspect local paths,
    command availability, service status and the environment daemon's read-only
    health endpoint, but it never toggles a relay, scans arbitrary I2C devices,
    opens GPIO lines, mutates policy, or claims physical target acceptance.
    """

    if mode not in {"debug", "production"}:
        raise ValueError("diagnostic mode must be debug or production")
    env = config.extensions.environment
    socket_path = Path(env.socket_path)
    policy_path = Path(env.policy_path)
    payload: dict[str, object] = {
        "schema": 1,
        "enabled": env.enabled,
        "target_acceptance": "not_established_by_diagnostics",
        "physical_evidence": False,
        "static": {
            "sensor_backend": env.sensor_backend,
            "i2c_bus": env.i2c_bus,
            "i2c_address_hex": f"0x{env.i2c_address:02x}",
            "sensor_repeatability": env.sensor_repeatability,
            "poll_interval_seconds": env.poll_interval_seconds,
            "stale_after_seconds": env.stale_after_seconds,
            "valid_samples_to_recover": env.valid_samples_to_recover,
            "relay_backend": env.relay_backend,
            "relay_bcm": env.relay_bcm,
            "relay_active_high": env.relay_active_high,
            "safe_state": env.safe_state,
            "temperature_policy_min_c": env.temperature_policy_min_c,
            "temperature_policy_max_c": env.temperature_policy_max_c,
            "minimum_hysteresis_c": env.minimum_hysteresis_c,
            "maximum_hysteresis_c": env.maximum_hysteresis_c,
            "minimum_dwell_seconds": env.minimum_dwell_seconds,
            "maximum_dwell_seconds": env.maximum_dwell_seconds,
        },
        "capabilities": {
            "power_control": True,
            "software_speed_control": False,
            "fan_motion_observed": False,
        },
        "devices": {
            "i2c_device": _device_status(Path(f"/dev/i2c-{env.i2c_bus}")),
            "i2c_device_names": sorted(path.name for path in Path("/dev").glob("i2c-*"))[:16],
            "gpiochip_names": sorted(path.name for path in Path("/dev").glob("gpiochip*"))[:16],
            "i2cdetect_available": shutil.which("i2cdetect") is not None,
            "gpioinfo_available": shutil.which("gpioinfo") is not None,
        },
        "paths": {
            "socket": _path_summary(socket_path, expect_socket=True),
            "policy": _path_summary(policy_path, expect_socket=False),
        },
        "service": _single_service("gonken-environment.service"),
        "ipc": _environment_ipc(socket_path, client_factory=client_factory),
    }
    if mode == "debug":
        payload["debug_note"] = "non_destructive_no_i2c_scan_no_gpio_toggle"
    return payload


def write_startup_snapshot(
    config,
    *,
    directory: Path | str | None = None,
    mode: str = "debug",
    retain: int | None = None,
) -> dict[str, str | int]:
    selected_dir = Path(directory) if directory is not None else default_snapshot_dir(config)
    selected_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    selected_dir.chmod(0o700)
    if selected_dir.is_symlink() or selected_dir.resolve() != selected_dir:
        raise ValueError("unsafe startup snapshot directory")
    selected_retain = 20 if retain is None and mode == "debug" else 0 if retain is None else retain
    if not 0 <= selected_retain <= 200:
        raise ValueError("startup snapshot retention must be between 0 and 200")
    snapshot = collect_snapshot(config, mode=mode)
    raw = json.dumps(snapshot, sort_keys=True, indent=2, allow_nan=False) + "\n"
    latest = selected_dir / "latest.json"
    _atomic_write(latest, raw)
    retained = None
    if selected_retain:
        stamp = snapshot["timestamp"].replace(":", "").replace("-", "")
        retained = selected_dir / f"startup-{stamp}.json"
        _atomic_write(retained, raw)
        _prune(selected_dir, selected_retain)
    return {
        "status": "RECORDED",
        "mode": mode,
        "latest": str(latest),
        "retained": str(retained) if retained else "",
        "retention": selected_retain,
    }


def load_snapshot(path: Path | str) -> dict[str, object]:
    selected = Path(path)
    if selected.is_symlink() or not selected.is_file() or selected.stat().st_size > 1024 * 1024:
        raise ValueError("unsafe startup snapshot input")
    data = json.loads(selected.read_text(encoding="utf-8"))
    _validate_snapshot(data)
    return data


def _validate_snapshot(data: object) -> None:
    if not isinstance(data, dict) or data.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("unsupported startup snapshot")
    if data.get("privacy", {}).get("content_logging") is not False:
        raise ValueError("startup snapshot must be content-free")
    for required in ("platform", "resources", "commands", "audio", "gpio", "services"):
        if required not in data:
            raise ValueError("startup snapshot is incomplete")


def _device_status(path: Path) -> dict[str, object]:
    try:
        return {
            "exists": path.exists(),
            "is_character_device": path.is_char_device() if path.exists() and not path.is_symlink() else False,
            "is_symlink": path.is_symlink(),
        }
    except OSError:
        return {"exists": False, "is_character_device": False, "is_symlink": False}


def _path_summary(path: Path, *, expect_socket: bool) -> dict[str, object]:
    try:
        parent = path.parent
        exists = path.exists()
        return {
            "configured": bool(str(path)),
            "exists": exists,
            "parent_exists": parent.exists(),
            "is_symlink": path.is_symlink(),
            "is_socket": path.is_socket() if exists and not path.is_symlink() else False,
            "is_file": path.is_file() if exists and not path.is_symlink() else False,
            "expected_type": "socket" if expect_socket else "file",
        }
    except OSError:
        return {
            "configured": bool(str(path)),
            "exists": False,
            "parent_exists": False,
            "is_symlink": False,
            "is_socket": False,
            "is_file": False,
            "expected_type": "socket" if expect_socket else "file",
        }


def _environment_ipc(socket_path: Path, *, client_factory=None) -> dict[str, object]:
    try:
        if socket_path.is_symlink():
            return {"status": "UNAVAILABLE", "code": "SOCKET_SYMLINK_REFUSED"}
        if not socket_path.exists():
            return {"status": "UNAVAILABLE", "code": "SOCKET_MISSING"}
        if not socket_path.is_socket():
            return {"status": "UNAVAILABLE", "code": "SOCKET_NOT_UNIX_SOCKET"}
    except OSError:
        return {"status": "UNAVAILABLE", "code": "SOCKET_INSPECTION_FAILED"}
    try:
        if client_factory is None:
            from .environment import EnvironmentClient
            client = EnvironmentClient(socket_path, timeout_seconds=0.5)
        else:
            client = client_factory(socket_path)
        health = client.health()
        simulation = _environment_client_optional(client, "simulation_status")
        snapshot = _environment_client_optional(client, "snapshot")
    except Exception as exc:
        code = getattr(exc, "code", type(exc).__name__)
        return {"status": "UNAVAILABLE", "code": _safe_text(str(code))}
    return {
        "status": "READY",
        "code": "READ_ONLY_HEALTH_OK",
        "overall": health.get("overall", "UNKNOWN") if isinstance(health, dict) else "UNKNOWN",
        "sensor": health.get("sensor", "unknown") if isinstance(health, dict) else "unknown",
        "actuator": health.get("actuator", "unknown") if isinstance(health, dict) else "unknown",
        "controller": health.get("controller", "unknown") if isinstance(health, dict) else "unknown",
        "physical_evidence": bool(health.get("physical_evidence", False)) if isinstance(health, dict) else False,
        "simulation": _environment_simulation_summary(simulation),
        "snapshot": _environment_snapshot_summary(snapshot),
    }


def _environment_client_optional(client, method_name: str) -> object:
    method = getattr(client, method_name, None)
    if not callable(method):
        return {"status": "UNAVAILABLE", "code": "METHOD_UNAVAILABLE"}
    try:
        return method()
    except Exception as exc:
        return {"status": "UNAVAILABLE", "code": _safe_text(str(getattr(exc, "code", type(exc).__name__)))}


def _environment_simulation_summary(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"status": "UNAVAILABLE", "code": "SIMULATION_STATUS_UNAVAILABLE"}
    simulation = payload.get("simulation") if isinstance(payload.get("simulation"), dict) else payload
    sensor = simulation.get("sensor") if isinstance(simulation.get("sensor"), dict) else {}
    actuator = simulation.get("actuator") if isinstance(simulation.get("actuator"), dict) else {}
    return {
        "status": "READY" if simulation.get("active") is True else "UNAVAILABLE",
        "active": bool(simulation.get("active", False)),
        "runtime_control_enabled": bool(simulation.get("runtime_control_enabled", False)),
        "sensor_is_simulated": bool(simulation.get("sensor_is_simulated", False)),
        "actuator_is_simulated": bool(simulation.get("actuator_is_simulated", False)),
        "evidence_mode": _safe_text(str(simulation.get("evidence_mode", "UNKNOWN"))),
        "generation": simulation.get("simulation_generation"),
        "sensor_fault": sensor.get("fault"),
        "actuator_behavior": actuator.get("behavior"),
        "actuator_modeled_power": actuator.get("modeled_power"),
        "physical_evidence": False,
    }


def _environment_snapshot_summary(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"status": "UNAVAILABLE", "code": "SNAPSHOT_UNAVAILABLE"}
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    polling = payload.get("polling") if isinstance(payload.get("polling"), dict) else {}
    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
    return {
        "status": "READY",
        "environment": _safe_text(str(payload.get("environment", "UNKNOWN"))),
        "mode": _safe_text(str(state.get("mode", "unknown"))),
        "fan_power": _safe_text(str(state.get("fan_power", "unknown"))),
        "sensor_quality": _safe_text(str(state.get("sensor_quality", "unknown"))),
        "last_transition_reason": _safe_text(str(state.get("last_transition_reason", "unknown"))),
        "poll_count": polling.get("poll_count"),
        "sensor_backend": _safe_text(str(provenance.get("sensor_backend", "unknown"))),
        "actuator_backend": _safe_text(str(provenance.get("actuator_backend", "unknown"))),
        "physical_evidence": bool(payload.get("physical_evidence", False)),
    }


def _single_service(service: str) -> dict[str, str]:
    if shutil.which("systemctl") is None:
        return {"active": "UNKNOWN_NO_SYSTEMCTL", "enabled": "UNKNOWN_NO_SYSTEMCTL"}
    return {"active": _systemctl("is-active", service), "enabled": _systemctl("is-enabled", service)}


def _platform() -> dict[str, object]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
    }


def _process() -> dict[str, object]:
    return {
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "euid": os.geteuid() if hasattr(os, "geteuid") else None,
        "gid": os.getgid() if hasattr(os, "getgid") else None,
        "groups": list(os.getgroups())[:64] if hasattr(os, "getgroups") else [],
    }


def _resources(config) -> dict[str, object]:
    return {
        "memory": _memory(),
        "thermal": _thermal(),
        "throttled": _read_text(Path("/sys/devices/platform/soc/soc:firmware/get_throttled")),
        "filesystems": {
            role: _filesystem(Path(value))
            for role, value in {
                "state": config.paths.state_dir,
                "cache": config.paths.cache_dir,
                "runtime": config.paths.runtime_dir,
                "corpus": config.paths.corpus_dir,
            }.items()
        },
    }


def _memory() -> dict[str, int | None]:
    values: dict[str, int | None] = {"mem_total_kib": None, "mem_available_kib": None}
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return values
    for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
        name, _, rest = line.partition(":")
        if name == "MemTotal":
            values["mem_total_kib"] = _first_int(rest)
        if name == "MemAvailable":
            values["mem_available_kib"] = _first_int(rest)
    return values


def _thermal() -> dict[str, object]:
    zones = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))[:8]:
        raw = _read_text(path)
        try:
            millidegrees = int(raw) if raw is not None else None
        except ValueError:
            millidegrees = None
        zones.append({"zone": path.parent.name, "temperature_c": millidegrees / 1000 if millidegrees is not None else None})
    return {"zones": zones}


def _filesystem(path: Path) -> dict[str, object]:
    try:
        target = path if path.exists() else path.parent
        stats = os.statvfs(target)
    except OSError:
        return {"exists": path.exists(), "writable": False, "free_bytes": None}
    return {
        "exists": path.exists(),
        "writable": os.access(target, os.W_OK),
        "free_bytes": stats.f_bavail * stats.f_frsize,
    }


def _services() -> dict[str, dict[str, str]]:
    if shutil.which("systemctl") is None:
        return {service: {"active": "UNKNOWN_NO_SYSTEMCTL", "enabled": "UNKNOWN_NO_SYSTEMCTL"} for service in SERVICES}
    return {
        service: {
            "active": _systemctl("is-active", service),
            "enabled": _systemctl("is-enabled", service),
        }
        for service in SERVICES
    }


def _systemctl(action: str, service: str) -> str:
    result = _run(["systemctl", action, service], timeout=3)
    if result["exit_code"] == 0:
        return result["stdout"][0] if result["stdout"] else "OK"
    return "UNKNOWN_OR_NOT_" + action.split("-")[-1].upper()


def _bluetooth_audio_state() -> dict[str, object]:
    state: dict[str, object] = {
        "controller_count": 0,
        "soft_blocked": None,
        "hard_blocked": None,
        "configured": Path("/etc/gonken-agent/bluetooth-device.record").is_file(),
    }
    if shutil.which("rfkill"):
        result = _run(["rfkill", "list", "bluetooth"], timeout=5)
        text = "\n".join(result.get("stdout", []))
        state["soft_blocked"] = "Soft blocked: yes" in text
        state["hard_blocked"] = "Hard blocked: yes" in text
    if shutil.which("bluetoothctl"):
        result = _run(["bluetoothctl", "list"], timeout=5)
        state["controller_count"] = sum(
            1 for line in result.get("stdout", []) if line.strip().startswith("Controller ")
        )
    return state


def _audio(mode: str) -> dict[str, object]:
    cards = _bounded_lines(Path("/proc/asound/cards"), 40 if mode == "debug" else 12)
    data: dict[str, object] = {
        "proc_asound_cards": cards,
        "capture_devices": _run(["arecord", "-l"], timeout=5) if shutil.which("arecord") else {"available": False},
        "playback_devices": _run(["aplay", "-l"], timeout=5) if shutil.which("aplay") else {"available": False},
        "bluetooth": _bluetooth_audio_state(),
    }
    if mode == "debug":
        data["capture_pcms"] = _run(["arecord", "-L"], timeout=5) if shutil.which("arecord") else {"available": False}
        data["playback_pcms"] = _run(["aplay", "-L"], timeout=5) if shutil.which("aplay") else {"available": False}
        if shutil.which("pactl"):
            data["pipewire_pulse_info"] = _run(["pactl", "info"], timeout=5)
            data["pipewire_default_source"] = _run(["pactl", "get-default-source"], timeout=5)
            data["pipewire_default_sink"] = _run(["pactl", "get-default-sink"], timeout=5)
            data["pipewire_sources"] = _run(["pactl", "list", "sources", "short"], timeout=5)
            data["pipewire_sinks"] = _run(["pactl", "list", "sinks", "short"], timeout=5)
        if shutil.which("wpctl"):
            data["wireplumber_status"] = _run(["wpctl", "status", "-n"], timeout=5)
    return data


def _gpio(mode: str) -> dict[str, object]:
    chips = sorted(path.name for path in Path("/dev").glob("gpiochip*"))[:16]
    return {
        "dev_gpiochips": chips,
        "sys_class_gpio": Path("/sys/class/gpio").exists(),
        "details": _run(["gpioinfo"], timeout=5) if mode == "debug" and shutil.which("gpioinfo") else {"available": False},
    }


def _run(command: list[str], *, timeout: int) -> dict[str, object]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "exit_code": None, "stdout": [], "stderr": []}
    return {
        "available": True,
        "exit_code": result.returncode,
        "stdout": _safe_lines(result.stdout, 80),
        "stderr": _safe_lines(result.stderr, 20),
    }


def _safe_lines(value: str, limit: int) -> list[str]:
    return [_safe_text(line) for line in value.splitlines()[:limit]]


def _bounded_lines(path: Path, limit: int) -> list[str]:
    if not path.is_file() or path.is_symlink():
        return []
    return _safe_lines(path.read_text(encoding="utf-8", errors="replace"), limit)


def _safe_text(value: str) -> str:
    return "".join(character if character.isprintable() else "?" for character in value)[:240]


def _read_text(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    return _safe_text(path.read_text(encoding="utf-8", errors="replace").strip())


def _first_int(value: str) -> int | None:
    for token in value.split():
        if token.isdigit():
            return int(token)
    return None


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _prune(directory: Path, retain: int) -> None:
    retained = sorted(directory.glob("startup-*.json"), key=lambda path: path.name, reverse=True)
    for path in retained[retain:]:
        if not path.is_symlink() and path.is_file():
            path.unlink()
