"""Export only newly constructed allow-listed diagnostic data, never raw files."""
from __future__ import annotations

import json
import os
import grp
import pwd
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from . import __version__
from .health import COMPONENTS
from .telemetry import validate_event
from .diagnostics import load_snapshot, collect_environment_diagnostics


SAFE_CODE_RE = re.compile(r"^[A-Z0-9_]{1,64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
RELEASE_ROOT = Path("/usr/local/lib/gonken-agent")
INSTALL_EVENTS_DIR = Path("/var/lib/gonken-agent/install/logs/events")
SERVICE_UNITS = ("gonken-agent.service", "gonken-environment.service")
BINDING_PACKAGES = ("python3-libgpiod",)
BINDING_MANIFEST = Path(sys.prefix).parent / "share/gonken-agent/hardware-bindings.json"


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
    if level not in {"info", "error"} or not SAFE_CODE_RE.fullmatch(code):
        return None
    if not re.fullmatch(r"[a-z0-9_.-]{1,64}|none", step):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", message):
        return None
    return {"level": level, "code": code, "step_id": step, "message": message}


def _install_events(limit: int = 40) -> dict[str, object]:
    if not INSTALL_EVENTS_DIR.is_dir() or INSTALL_EVENTS_DIR.is_symlink():
        return {"status": "UNAVAILABLE", "events": []}
    events = []
    for path in sorted(INSTALL_EVENTS_DIR.glob("*.event"))[-limit:]:
        event = _read_event(path)
        if event is not None:
            events.append(event)
    return {"status": "READY", "events": events}


def _service_event_codes(limit: int = 200) -> dict[str, object]:
    journalctl = shutil.which("journalctl")
    if not journalctl:
        return {"status": "UNAVAILABLE", "units": {}}
    units: dict[str, object] = {}
    for unit in SERVICE_UNITS:
        try:
            result = subprocess.run(
                [journalctl, "-u", unit, "-b", "--no-pager", "-n", str(limit), "-o", "cat"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            units[unit] = {"status": "UNAVAILABLE", "codes": {}}
            continue
        counts = Counter()
        for match in re.finditer(r"(?:^|\s)code=([A-Z0-9_]{1,64})(?:\s|$)", result.stdout):
            counts[match.group(1)] += 1
        units[unit] = {
            "status": "READY" if result.returncode == 0 else "DEGRADED",
            "codes": dict(sorted(counts.items())),
        }
    return {"status": "READY", "units": units}


def create_bundle(output, effective_config, health, telemetry_path=None, allowed_source_ids=(), startup_snapshot=None):
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
        'install_events.json': _install_events(),
        'service_events.json': _service_event_codes(),
    }
    environment_health = health.get('environment')
    if isinstance(environment_health, dict):
        files['environment_health.json'] = environment_health
    if startup_snapshot is not None:
        files['startup_snapshot.json']=load_snapshot(startup_snapshot)
    fd,temporary=tempfile.mkstemp(prefix='.support-',dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,value in sorted(files.items()):
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.external_attr=0o100600<<16
                entry.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(entry,json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
        with open(temporary,'rb') as stream:os.fsync(stream.fileno())
        # Hard link is atomic and fails if another writer created output meanwhile.
        os.link(temporary,output,follow_symlinks=False)
    finally:Path(temporary).unlink(missing_ok=True)
    return {'status':'CREATED','members':sorted(files),'content_logging':False}
