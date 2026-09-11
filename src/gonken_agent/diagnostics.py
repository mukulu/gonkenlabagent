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
)
SERVICES = (
    "gonken-agent.service",
    "ollama.service",
    "bluetooth.service",
    "gonken-bluetooth-autoconnect.service",
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
