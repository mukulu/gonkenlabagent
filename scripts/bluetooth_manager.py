#!/usr/bin/env python3
"""Provision optional headless Bluetooth audio without weakening the USB core path.

The manager deliberately separates three concerns:
* BlueZ pairing/trust is system state and is performed as root.
* PipeWire/WirePlumber runs as the dedicated ``gonken-agent`` audio user with
  lingering enabled, so Bluetooth nodes exist without an interactive login.
* a small system service only reconnects the one explicitly paired/trusted MAC.

No Bluetooth device is selected automatically unless discovery finds exactly
one unpaired audio-capable candidate.  Ambiguity fails closed and asks the
operator to rerun with an explicit name/MAC selector.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


MAC_RE = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")
SAFE_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,120}$")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
KNOWN_PREVIOUS_AUTOCONNECT_SHA256 = {
    # Checkpoint-32 autoconnect unit before explicit bytecode suppression.
    "6e2e426fac110bab9476ceefbe5947feae829773d5e325c75d23ddea2eeb73ce",
    "60f406dd6acd24c3213a430aa0c6b196f4e764de6d603b430229ab17055f492b",
}
AUTOCONNECT_UNIT = Path("/etc/systemd/system/gonken-bluetooth-autoconnect.service")

RECORD_FIELDS = {
    "format",
    "address",
    "name",
    "audio_user",
    "paired_epoch",
    "output_capable",
    "headset_capable",
}
WIREPLUMBER_FRAGMENT = """# Managed by GonKenLab Agent Bluetooth extension.
# Headless appliance ownership: allow the dedicated audio user to expose
# Bluetooth nodes even when there is no active graphical/logind seat.
wireplumber.profiles = {
  main = {
    monitor.bluez.seat-monitoring = disabled
  }
}
"""


class BluetoothError(RuntimeError):
    def __init__(self, code: str, message: str, remediation: str, status: int = 74):
        super().__init__(message)
        self.code = code
        self.remediation = remediation
        self.status = status


def fail(code: str, message: str, remediation: str, status: int = 74) -> None:
    raise BluetoothError(code, message, remediation, status)


def emit_error(error: BluetoothError) -> None:
    print(
        f"[ERROR] code={error.code} message={error} remediation={error.remediation}",
        file=sys.stderr,
    )


def run(
    args: list[str],
    *,
    timeout: int = 30,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            fail(
                "BLUETOOTH_COMMAND",
                f"command could not complete: {args[0]} ({type(exc).__name__})",
                "inspect BlueZ/PipeWire service state and rerun",
                69,
            )
        return subprocess.CompletedProcess(args, 127, "", str(exc))
    if check and result.returncode != 0:
        detail = clean_text(result.stderr or result.stdout).replace("\n", " ")[:800]
        fail(
            "BLUETOOTH_COMMAND",
            f"command failed ({result.returncode}): {detail or args[0]}",
            "inspect Bluetooth/PipeWire state and rerun",
            result.returncode if 1 <= result.returncode <= 125 else 74,
        )
    return result


def clean_text(value: str) -> str:
    return ANSI_RE.sub("", value).replace("\r", "")


def parse_devices(output: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for raw in clean_text(output).splitlines():
        match = re.search(r"(?:^|\s)Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", raw.strip())
        if not match:
            continue
        address = match.group(1).upper()
        name = match.group(2).strip()
        if MAC_RE.fullmatch(address) and SAFE_NAME_RE.fullmatch(name):
            devices[address] = name
    return devices


def parse_info(output: str) -> dict[str, object]:
    text = clean_text(output)
    values: dict[str, object] = {
        "paired": False,
        "trusted": False,
        "connected": False,
        "output_capable": False,
        "headset_capable": False,
        "name": "",
    }
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Name:"):
            values["name"] = line.partition(":")[2].strip()
        elif line.startswith("Alias:") and not values["name"]:
            values["name"] = line.partition(":")[2].strip()
        elif line.startswith("Paired:"):
            values["paired"] = line.lower().endswith("yes")
        elif line.startswith("Trusted:"):
            values["trusted"] = line.lower().endswith("yes")
        elif line.startswith("Connected:"):
            values["connected"] = line.lower().endswith("yes")
    lowered = text.casefold()
    values["output_capable"] = any(
        token in lowered for token in ("audio sink", "icon: audio-card", "advanced audio")
    )
    values["headset_capable"] = any(
        token in lowered for token in ("handsfree", "hands-free", "headset", "head unit")
    )
    return values


def controller_status() -> dict[str, object]:
    rfkill = run(["rfkill", "list", "bluetooth"], timeout=5, check=False)
    rfkill_text = clean_text(rfkill.stdout + rfkill.stderr)
    if "Hard blocked: yes" in rfkill_text:
        fail(
            "BLUETOOTH_BLOCKED",
            "Bluetooth controller is hard-blocked",
            "remove the hardware/radio block before Bluetooth setup",
            78,
        )
    listed = run(["bluetoothctl", "list"], timeout=8, check=False)
    controllers = [
        line.strip()
        for line in clean_text(listed.stdout).splitlines()
        if line.strip().startswith("Controller ")
    ]
    if not controllers:
        fail(
            "BLUETOOTH_CONTROLLER",
            "no BlueZ Bluetooth controller is available",
            "use onboard Pi Bluetooth or repair the controller before enabling the extension",
            78,
        )
    return {
        "controllers": len(controllers),
        "soft_blocked": "Soft blocked: yes" in rfkill_text,
    }


def controller_powered() -> bool:
    shown = run(["bluetoothctl", "show"], timeout=8, check=False)
    return any(line.strip() == "Powered: yes" for line in clean_text(shown.stdout).splitlines())


def ensure_controller_ready(*, repair: bool) -> None:
    state = controller_status()
    active = run(["systemctl", "is-active", "--quiet", "bluetooth.service"], timeout=5, check=False)
    if repair and os.geteuid() == 0:
        if active.returncode != 0:
            run(["systemctl", "start", "bluetooth.service"], timeout=20, check=False)
        if state["soft_blocked"]:
            run(["rfkill", "unblock", "bluetooth"], timeout=8, check=False)
        if not controller_powered():
            run(["bluetoothctl", "power", "on"], timeout=10, check=False)
        state = controller_status()
        active = run(["systemctl", "is-active", "--quiet", "bluetooth.service"], timeout=5, check=False)
    if active.returncode != 0 or state["soft_blocked"] or not controller_powered():
        fail(
            "BLUETOOTH_STACK",
            "Bluetooth controller is not active, unblocked, and powered",
            "enable bluetooth.service, unblock the radio, and power on the controller",
            1,
        )


def user_context(user: str) -> tuple[pwd.struct_passwd, dict[str, str]]:
    try:
        account = pwd.getpwnam(user)
    except KeyError:
        fail("BLUETOOTH_USER", f"audio user does not exist: {user}", "repair the runtime account and rerun", 65)
    runtime = f"/run/user/{account.pw_uid}"
    env = os.environ.copy()
    env.update(
        {
            "HOME": account.pw_dir,
            "USER": user,
            "LOGNAME": user,
            "XDG_RUNTIME_DIR": runtime,
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
        }
    )
    return account, env


def run_as_user(user: str, args: list[str], *, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess[str]:
    account, env = user_context(user)
    command = ["runuser", "-u", user, "--", "env"]
    for key in ("HOME", "USER", "LOGNAME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
        command.append(f"{key}={env[key]}")
    command.extend(args)
    return run(command, timeout=timeout, check=check)


def ensure_dir(path: Path, mode: int, uid: int, gid: int) -> None:
    if path.is_symlink():
        fail("BLUETOOTH_LAYOUT", f"unsafe symlink directory: {path}", "remove the conflicting path after inspection", 73)
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink():
        fail("BLUETOOTH_LAYOUT", f"not a real directory: {path}", "repair the managed audio-user layout", 73)
    os.chown(path, uid, gid)
    path.chmod(mode)


def atomic_text(path: Path, text: str, *, mode: int, uid: int = 0, gid: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail("BLUETOOTH_LAYOUT", f"unsafe symlink destination: {path}", "remove the conflicting path after inspection", 73)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(mode)
        os.chown(path, uid, gid)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def stack_status(audio_user: str) -> None:
    ensure_controller_ready(repair=False)
    missing_audio_tools = [name for name in ("pactl", "parecord", "paplay") if shutil.which(name) is None]
    if missing_audio_tools:
        fail(
            "BLUETOOTH_AUDIO_TOOLS",
            f"headless Bluetooth audio tools are missing: {','.join(missing_audio_tools)}",
            "install pulseaudio-utils and rerun Bluetooth stack preparation",
            1,
        )
    package = run(
        ["dpkg-query", "-W", "-f=${Status}", "libspa-0.2-bluetooth"],
        timeout=8,
        check=False,
    )
    if package.returncode != 0 or "install ok installed" not in clean_text(package.stdout).casefold():
        fail(
            "BLUETOOTH_PIPEWIRE_PLUGIN",
            "PipeWire Bluetooth SPA plugin package is not installed",
            "install libspa-0.2-bluetooth through the governed Bluetooth stack step and rerun",
            1,
        )
    _account, _env = user_context(audio_user)
    pipewire = run_as_user(audio_user, ["systemctl", "--user", "is-active", "--quiet", "pipewire.service"], timeout=8, check=False)
    wireplumber = run_as_user(audio_user, ["systemctl", "--user", "is-active", "--quiet", "wireplumber.service"], timeout=8, check=False)
    pactl = run_as_user(audio_user, ["pactl", "info"], timeout=8, check=False)
    if pipewire.returncode != 0 or wireplumber.returncode != 0 or pactl.returncode != 0:
        fail(
            "BLUETOOTH_STACK",
            "dedicated headless PipeWire/WirePlumber session is not ready",
            "rerun Bluetooth stack preparation and inspect user service logs",
            1,
        )
    print(f"[OK] code=BLUETOOTH_STACK_READY audio_user={audio_user}")


def prepare(audio_user: str) -> None:
    if os.geteuid() != 0:
        fail("BLUETOOTH_PRIVILEGE", "Bluetooth stack preparation requires root", "run through bootstrap or sudo", 77)
    account, _env = user_context(audio_user)
    run(["systemctl", "enable", "--now", "bluetooth.service"], timeout=30)
    run(["rfkill", "unblock", "bluetooth"], timeout=8)
    run(["bluetoothctl", "power", "on"], timeout=10)
    ensure_controller_ready(repair=True)

    home = Path(account.pw_dir)
    config_dir = home / ".config" / "wireplumber" / "wireplumber.conf.d"
    config_dir.mkdir(parents=True, exist_ok=True)
    # Configuration is administrator-owned/read-only; state is isolated below
    # directories writable by the dedicated service account.
    for path in (home / ".config", home / ".config" / "wireplumber", config_dir):
        if path.is_symlink():
            fail("BLUETOOTH_LAYOUT", f"unsafe WirePlumber config path: {path}", "remove the symlink after inspection", 73)
        path.chmod(0o755)
        os.chown(path, 0, 0)
    atomic_text(config_dir / "51-gonken-headless-bluetooth.conf", WIREPLUMBER_FRAGMENT, mode=0o644)

    stable = Path("/usr/local/bin/gonken-bluetooth")
    expected = "../lib/gonken-agent/current/maintenance/bluetooth_manager.py"
    if stable.exists() and not stable.is_symlink():
        fail("BLUETOOTH_LAYOUT", f"stable helper path is occupied: {stable}", "move the conflicting administrator file", 75)
    if stable.is_symlink() and os.readlink(stable) != expected:
        fail("BLUETOOTH_LAYOUT", f"stable helper link differs: {stable}", "review the conflicting symlink", 75)
    if not stable.is_symlink():
        stable.symlink_to(expected)

    ensure_dir(home / ".local", 0o755, 0, 0)
    ensure_dir(home / ".local" / "state", 0o755, 0, 0)
    ensure_dir(home / ".local" / "state" / "wireplumber", 0o700, account.pw_uid, account.pw_gid)
    ensure_dir(Path("/var/cache/gonken-agent/pipewire"), 0o700, account.pw_uid, account.pw_gid)

    run(["loginctl", "enable-linger", audio_user], timeout=15)
    run(["systemctl", "start", f"user@{account.pw_uid}.service"], timeout=20)
    # Debian/Raspberry Pi OS ships these user units with PipeWire/WirePlumber.
    run_as_user(audio_user, ["systemctl", "--user", "daemon-reload"], timeout=15)
    # Package presets already enable the user units globally.  The dedicated
    # service home is administrator-owned, so do not attempt per-user enablement
    # symlinks there; start the globally enabled units in the lingering manager.
    run_as_user(
        audio_user,
        [
            "systemctl",
            "--user",
            "start",
            "pipewire.socket",
            "pipewire-pulse.socket",
            "wireplumber.service",
        ],
        timeout=30,
    )
    # Trigger socket activation and wait for the Pulse compatibility endpoint.
    for _ in range(20):
        result = run_as_user(audio_user, ["pactl", "info"], timeout=5, check=False)
        if result.returncode == 0:
            break
        time.sleep(0.5)
    else:
        fail(
            "BLUETOOTH_PIPEWIRE",
            "PipeWire Pulse endpoint did not become ready",
            f"inspect journalctl --user for {audio_user} PipeWire/WirePlumber",
            69,
        )
    print(f"[OK] code=BLUETOOTH_STACK_PREPARED audio_user={audio_user}")


def bluetooth_info(address: str) -> tuple[dict[str, object], str]:
    result = run(["bluetoothctl", "info", address], timeout=8, check=False)
    if result.returncode != 0:
        return parse_info(result.stdout + result.stderr), clean_text(result.stdout + result.stderr)
    return parse_info(result.stdout), clean_text(result.stdout)


def scan_once(seconds: int) -> dict[str, str]:
    run(["bluetoothctl", "--timeout", str(seconds), "scan", "on"], timeout=seconds + 5, check=False)
    devices = run(["bluetoothctl", "devices"], timeout=8, check=False)
    return parse_devices(devices.stdout)


def audio_candidates(devices: dict[str, str]) -> dict[str, tuple[str, dict[str, object]]]:
    result: dict[str, tuple[str, dict[str, object]]] = {}
    for address, name in devices.items():
        info, _raw = bluetooth_info(address)
        if bool(info["output_capable"]) or bool(info["headset_capable"]):
            result[address] = (str(info.get("name") or name), info)
    return result


def resolve_candidate(selector: str, timeout: int) -> tuple[str, str, dict[str, object]]:
    normalized = selector.strip()
    target_mac = normalized.upper() if MAC_RE.fullmatch(normalized.upper()) else None
    # An explicit MAC is the strongest selector.  BlueZ retains known paired
    # devices even when they are no longer discoverable, so try that identity
    # directly before asking the operator to enter pairing mode.
    if target_mac:
        known, _raw = bluetooth_info(target_mac)
        if bool(known["output_capable"]) or bool(known["headset_capable"]):
            name = str(known.get("name") or target_mac)
            print(
                f"[FOUND] code=BLUETOOTH_DEVICE_KNOWN address={target_mac} "
                f"name={safe_record_name(name)} paired={str(bool(known['paired'])).lower()}",
                flush=True,
            )
            return target_mac, name, known
    deadline = time.monotonic() + timeout
    last_candidates: dict[str, tuple[str, dict[str, object]]] = {}
    selector_kind = "mac" if target_mac else "name" if normalized else "auto"
    print(
        f"[ACTION] code=BLUETOOTH_PAIRING_READY timeout={timeout} selector={selector_kind} "
        "message=put_the_desired_audio_device_in_pairing_mode_now",
        flush=True,
    )
    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        devices = scan_once(min(5, remaining))
        candidates = audio_candidates(devices)
        last_candidates = candidates
        if target_mac:
            if target_mac in candidates:
                name, info = candidates[target_mac]
                return target_mac, name, info
        elif normalized:
            matches = [
                (address, name, info)
                for address, (name, info) in candidates.items()
                if normalized.casefold() in name.casefold()
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                names = ",".join(name for _address, name, _info in matches)
                fail(
                    "BLUETOOTH_AMBIGUOUS",
                    f"selector matches multiple audio devices: {names[:240]}",
                    "rerun with the exact Bluetooth MAC address",
                    65,
                )
        else:
            unpaired = [
                (address, name, info)
                for address, (name, info) in candidates.items()
                if not bool(info["paired"])
            ]
            if len(unpaired) == 1:
                return unpaired[0]
            if len(unpaired) > 1:
                names = ",".join(name for _address, name, _info in unpaired)
                fail(
                    "BLUETOOTH_AMBIGUOUS",
                    f"multiple unpaired audio devices are visible: {names[:240]}",
                    "turn off other pairing devices or rerun with --bluetooth-device NAME_OR_MAC",
                    65,
                )
        time.sleep(0.5)
    visible = ",".join(name for name, _info in last_candidates.values()) or "none"
    fail(
        "BLUETOOTH_PAIRING_TIMEOUT",
        f"no unique requested Bluetooth audio device appeared; visible_audio={visible[:240]}",
        "put the desired device in pairing mode and rerun bootstrap with --bluetooth-audio",
        75,
    )


def pipewire_nodes(audio_user: str, address: str) -> tuple[list[str], list[str]]:
    token = address.replace(":", "_").casefold()
    sinks_result = run_as_user(audio_user, ["pactl", "list", "sinks", "short"], timeout=8, check=False)
    sources_result = run_as_user(audio_user, ["pactl", "list", "sources", "short"], timeout=8, check=False)

    def names(output: str, prefix: str) -> list[str]:
        found: list[str] = []
        for line in clean_text(output).splitlines():
            fields = line.split()
            if len(fields) >= 2:
                name = fields[1]
                if prefix in name.casefold() and token in name.casefold():
                    found.append(name)
        return found

    return names(sinks_result.stdout, "bluez_output"), names(sources_result.stdout, "bluez_input")


def _parse_capture_cards(output: str) -> list[tuple[str, str, str]]:
    """Parse ``arecord -l`` into stable direct-ALSA capture candidates.

    Keep this helper self-contained because Bluetooth provisioning runs before
    the application service is considered ready.  The selection semantics
    intentionally mirror ``voice_runtime.AudioBackend``: one USB capture card
    is preferred; otherwise exactly one non-HDMI capture card is acceptable.
    """
    rows: list[tuple[str, str, str]] = []
    pattern = re.compile(
        r"^card\s+(\d+):\s*([^\[]+)\[([^\]]+)\],\s*device\s+(\d+):\s*(.*)$",
        re.I,
    )
    for raw in clean_text(output).splitlines():
        match = pattern.match(raw.strip())
        if not match:
            continue
        card, short, long_name, device, tail = match.groups()
        card_id = short.strip()
        locator = card_id if re.fullmatch(r"[A-Za-z0-9_]+", card_id) else card
        text = " ".join((short.strip(), long_name.strip(), tail.strip()))
        rows.append((f"plughw:CARD={locator},DEV={device}", text, device))
    return rows


def _one_capture_card(rows: list[tuple[str, str, str]]) -> str | None:
    if not rows:
        return None
    cards: dict[str, list[tuple[str, str, str]]] = {}
    for row in rows:
        cards.setdefault(row[0].split(",", 1)[0], []).append(row)
    if len(cards) != 1:
        return None
    choices = next(iter(cards.values()))
    zero = [row for row in choices if row[2] == "0"]
    return (zero[0] if zero else choices[0])[0]


def direct_capture_fallback(audio_user: str) -> str | None:
    """Return the one deterministic direct capture route available to GonKen.

    This is an enumeration/preflight only; it never records audio.  Ambiguous
    capture hardware fails closed so appliance readiness cannot silently pick a
    different microphone than the operator expects.
    """
    result = run_as_user(audio_user, ["arecord", "-l"], timeout=8, check=False)
    rows = _parse_capture_cards(result.stdout + result.stderr)
    usb = [row for row in rows if "usb" in row[1].casefold()]
    selected = _one_capture_card(usb)
    if selected:
        return selected
    usb_cards = {row[0].split(",", 1)[0] for row in usb}
    if len(usb_cards) > 1:
        fail(
            "AUDIO_INPUT_AMBIGUOUS",
            "multiple direct USB capture cards are available",
            "disconnect extra microphones or set one explicit audio input selector before rerunning",
            65,
        )
    non_hdmi = [
        row
        for row in rows
        if not any(token in row[1].casefold() for token in ("hdmi", "displayport", "vc4"))
    ]
    selected = _one_capture_card(non_hdmi)
    if selected:
        return selected
    non_hdmi_cards = {row[0].split(",", 1)[0] for row in non_hdmi}
    if len(non_hdmi_cards) > 1:
        fail(
            "AUDIO_INPUT_AMBIGUOUS",
            "multiple direct capture cards are available",
            "disconnect extra microphones or set one explicit audio input selector before rerunning",
            65,
        )
    return None


def direct_playback_fallback(audio_user: str) -> str | None:
    """Return one deterministic direct playback route without playing audio."""
    result = run_as_user(audio_user, ["aplay", "-l"], timeout=8, check=False)
    rows = _parse_capture_cards(result.stdout + result.stderr)
    usb = [row for row in rows if "usb" in row[1].casefold()]
    selected = _one_capture_card(usb)
    if selected:
        return selected
    usb_cards = {row[0].split(",", 1)[0] for row in usb}
    if len(usb_cards) > 1:
        fail(
            "AUDIO_OUTPUT_AMBIGUOUS",
            "multiple direct USB playback cards are available",
            "disconnect extra speakers or set one explicit audio output selector before rerunning",
            65,
        )
    non_hdmi = [
        row
        for row in rows
        if not any(token in row[1].casefold() for token in ("hdmi", "displayport", "vc4"))
    ]
    selected = _one_capture_card(non_hdmi)
    if selected:
        return selected
    non_hdmi_cards = {row[0].split(",", 1)[0] for row in non_hdmi}
    if len(non_hdmi_cards) > 1:
        fail(
            "AUDIO_OUTPUT_AMBIGUOUS",
            "multiple direct playback cards are available",
            "disconnect extra playback devices or set one explicit audio output selector before rerunning",
            65,
        )
    return None


def direct_audio_fallback(audio_user: str) -> tuple[str, str] | None:
    """Return deterministic direct capture+playback routes for USB/wired fallback."""
    capture = direct_capture_fallback(audio_user)
    playback = direct_playback_fallback(audio_user)
    if capture is None or playback is None:
        return None
    return capture, playback


def _headset_profile(audio_user: str, address: str) -> tuple[str, str] | None:
    """Return one available Bluetooth profile that exposes a capture source."""
    token = address.replace(":", "_").casefold()
    result = run_as_user(audio_user, ["pactl", "list", "cards"], timeout=10, check=False)
    text = clean_text(result.stdout)
    sections = re.split(r"(?m)^Card #[^\n]*\n", text)
    for section in sections:
        name_match = re.search(r"(?m)^\s*Name:\s*(\S+)\s*$", section)
        if not name_match:
            continue
        card = name_match.group(1)
        if "bluez_card" not in card.casefold() or token not in card.casefold():
            continue
        candidates: list[tuple[int, str]] = []
        for raw in section.splitlines():
            line = raw.strip()
            match = re.match(r"^([A-Za-z0-9_.+-]+):\s+.*sources:\s*([0-9]+).*available:\s*(yes|unknown)", line, re.I)
            if not match or int(match.group(2)) < 1:
                continue
            profile = match.group(1)
            lowered = profile.casefold()
            priority = 0
            if "msbc" in lowered:
                priority = 30
            elif "headset-head-unit" in lowered or "handsfree" in lowered:
                priority = 20
            elif "headset" in lowered or "hfp" in lowered or "hsp" in lowered:
                priority = 10
            candidates.append((priority, profile))
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return card, candidates[0][1]
    return None


def route_defaults(
    audio_user: str,
    address: str,
    *,
    wait_seconds: int = 20,
    require_input: bool = False,
) -> tuple[list[str], list[str]]:
    deadline = time.monotonic() + wait_seconds
    sinks: list[str] = []
    sources: list[str] = []
    while time.monotonic() < deadline:
        sinks, sources = pipewire_nodes(audio_user, address)
        if sinks and (sources or not require_input):
            break
        time.sleep(0.5)
    if require_input and not sources:
        selected = _headset_profile(audio_user, address)
        if selected:
            card, profile = selected
            print(
                f"[RUNNING] code=BLUETOOTH_HEADSET_PROFILE card={card} profile={profile}",
                flush=True,
            )
            run_as_user(audio_user, ["pactl", "set-card-profile", card, profile], timeout=12, check=False)
            # Give WirePlumber/BlueZ a bounded settle window after a profile
            # change.  Headless target enumeration can lag card-profile change.
            profile_deadline = time.monotonic() + max(12, min(wait_seconds, 30))
            while time.monotonic() < profile_deadline:
                sinks, sources = pipewire_nodes(audio_user, address)
                if sources:
                    break
                time.sleep(0.5)
    if sinks:
        run_as_user(audio_user, ["pactl", "set-default-sink", sinks[0]], timeout=8, check=False)
    if sources:
        run_as_user(audio_user, ["pactl", "set-default-source", sources[0]], timeout=8, check=False)
    return sinks, sources


def safe_record_name(name: str) -> str:
    value = clean_text(name).strip()
    if not SAFE_NAME_RE.fullmatch(value) or "=" in value:
        return "bluetooth-audio-device"
    return value


def write_device_record(path: Path, *, address: str, name: str, audio_user: str, info: dict[str, object]) -> None:
    if not path.is_absolute():
        fail("BLUETOOTH_RECORD", "record path must be absolute", "use the managed /etc record path", 64)
    account, _env = user_context(audio_user)
    payload = "".join(
        f"{key}={value}\n"
        for key, value in (
            ("format", "gonken-bluetooth-audio-v1"),
            ("address", address),
            ("name", safe_record_name(name)),
            ("audio_user", audio_user),
            ("paired_epoch", str(int(time.time()))),
            ("output_capable", "yes" if info["output_capable"] else "no"),
            ("headset_capable", "yes" if info["headset_capable"] else "no"),
        )
    )
    atomic_text(path, payload, mode=0o640, uid=0, gid=account.pw_gid)


def read_device_record(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 8192:
        fail("BLUETOOTH_RECORD", "Bluetooth device record is missing or unsafe", "rerun Bluetooth pairing", 1)
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if not sep or key not in RECORD_FIELDS or key in values or "\r" in value:
            fail("BLUETOOTH_RECORD", "Bluetooth device record is malformed", "rerun Bluetooth pairing", 65)
        values[key] = value
    if set(values) != RECORD_FIELDS or values.get("format") != "gonken-bluetooth-audio-v1":
        fail("BLUETOOTH_RECORD", "Bluetooth device record schema is incomplete", "rerun Bluetooth pairing", 65)
    if not MAC_RE.fullmatch(values["address"]):
        fail("BLUETOOTH_RECORD", "recorded Bluetooth address is invalid", "rerun Bluetooth pairing", 65)
    if values["output_capable"] not in {"yes", "no"} or values["headset_capable"] not in {"yes", "no"}:
        fail("BLUETOOTH_RECORD", "recorded Bluetooth capabilities are invalid", "rerun Bluetooth pairing", 65)
    return values


def pair(selector: str, audio_user: str, record: Path, timeout: int) -> None:
    if os.geteuid() != 0:
        fail("BLUETOOTH_PRIVILEGE", "Bluetooth pairing requires root", "run through bootstrap or sudo", 77)
    stack_status(audio_user)
    run(["bluetoothctl", "power", "on"], timeout=10)
    run(["bluetoothctl", "pairable", "on"], timeout=10, check=False)
    address, name, _initial = resolve_candidate(selector, timeout)
    print(f"[RUNNING] code=BLUETOOTH_PAIR address={address} name={safe_record_name(name)}", flush=True)
    info, _raw = bluetooth_info(address)
    if not info["paired"]:
        run(["bluetoothctl", "--timeout", "45", "--agent", "NoInputNoOutput", "pair", address], timeout=50)
    run(["bluetoothctl", "trust", address], timeout=10)
    run(["bluetoothctl", "connect", address], timeout=25, check=False)
    for _ in range(20):
        info, _raw = bluetooth_info(address)
        if info["paired"] and info["trusted"] and info["connected"]:
            break
        time.sleep(0.5)
    if not (info["paired"] and info["trusted"]):
        fail("BLUETOOTH_PAIR", "device did not reach paired+trusted state", "return the device to pairing mode and rerun", 75)

    # Bluetooth is a preferred optional route, never a dependency of the wired
    # USB core.  A headset can legitimately be busy with another host.  In that
    # case installation may continue only after proving one deterministic direct
    # capture route and one deterministic direct playback route for gonken-agent.
    if not info["connected"]:
        fallback = direct_audio_fallback(audio_user)
        if fallback is None:
            fail(
                "BLUETOOTH_CONNECT",
                "paired device did not connect and no deterministic direct audio fallback is available",
                "free/power the Bluetooth device or connect one unambiguous USB microphone and playback device, then rerun",
                75,
            )
        write_device_record(record, address=address, name=name, audio_user=audio_user, info=info)
        print(
            f"[WARN] code=BLUETOOTH_OPTIONAL_UNAVAILABLE address={address} "
            f"fallback_input={fallback[0]} fallback_output={fallback[1]} remediation=autoconnect_will_retry_later",
            flush=True,
        )
        print(
            f"[OK] code=AUDIO_DIRECT_FALLBACK_READY input={fallback[0]} output={fallback[1]}",
            flush=True,
        )
        return

    sinks, sources = route_defaults(audio_user, address, require_input=True)
    fallback_capture = None
    fallback_duplex = None
    if not sinks:
        fallback_duplex = direct_audio_fallback(audio_user)
        if fallback_duplex is None:
            fail(
                "BLUETOOTH_AUDIO_ROUTE",
                "device connected but no PipeWire Bluetooth output node and no direct audio fallback appeared",
                f"inspect WirePlumber for user {audio_user} or connect one deterministic USB audio device",
                69,
            )
    if not sources:
        fallback_capture = direct_capture_fallback(audio_user)
        if fallback_capture is None:
            fail(
                "BLUETOOTH_INPUT_UNAVAILABLE",
                "Bluetooth playback is available but no Bluetooth or direct capture input is available",
                "expose an HFP/HSP microphone profile or connect exactly one USB microphone, then rerun",
                69,
            )
    write_device_record(record, address=address, name=name, audio_user=audio_user, info=info)
    output_state = "bluetooth_ready" if sinks else f"direct_ready:{fallback_duplex[1]}"
    source_state = "bluetooth_ready" if sources else f"direct_ready:{fallback_capture}"
    print(
        f"[OK] code=BLUETOOTH_AUDIO_PAIRED address={address} name={safe_record_name(name)} "
        f"output={output_state} microphone={source_state}",
        flush=True,
    )


def connect_record(record: Path, audio_user: str, *, strict: bool) -> bool:
    try:
        ensure_controller_ready(repair=True)
    except BluetoothError:
        if strict:
            raise
        return False
    values = read_device_record(record)
    if values["audio_user"] != audio_user:
        fail("BLUETOOTH_RECORD", "recorded audio user differs from requested user", "rerun Bluetooth pairing", 65)
    address = values["address"]
    info, _raw = bluetooth_info(address)
    if not info["connected"]:
        result = run(["bluetoothctl", "connect", address], timeout=20, check=False)
        if result.returncode != 0:
            if strict:
                fail("BLUETOOTH_CONNECT", "trusted Bluetooth device is currently unavailable", "power on the paired device and retry", 75)
            return False
        time.sleep(1)
    info, _raw = bluetooth_info(address)
    if not info["connected"]:
        if strict:
            fail("BLUETOOTH_CONNECT", "Bluetooth connection did not become active", "power on the paired device and retry", 75)
        return False
    route_defaults(
        audio_user,
        address,
        wait_seconds=10,
        require_input=values.get("headset_capable") == "yes",
    )
    return True


def device_status(
    record: Path,
    audio_user: str,
    *,
    require_connected: bool,
    allow_direct_fallback: bool = False,
) -> None:
    values = read_device_record(record)
    if values["audio_user"] != audio_user:
        fail("BLUETOOTH_RECORD", "recorded audio user differs from configured audio user", "rerun Bluetooth pairing", 65)
    info, _raw = bluetooth_info(values["address"])
    if not info["paired"] or not info["trusted"]:
        fail("BLUETOOTH_PAIR", "recorded device is no longer paired/trusted", "rerun Bluetooth pairing", 1)
    direct_fallback = None
    if require_connected and not info["connected"]:
        if allow_direct_fallback:
            direct_fallback = direct_audio_fallback(audio_user)
        if direct_fallback is None:
            fail("BLUETOOTH_CONNECT", "recorded device is not connected", "power on the device or let autoconnect retry", 1)
    sinks, sources = pipewire_nodes(audio_user, values["address"]) if info["connected"] else ([], [])
    if require_connected and values.get("output_capable") == "yes" and not sinks:
        if allow_direct_fallback and direct_fallback is None:
            direct_fallback = direct_audio_fallback(audio_user)
        if direct_fallback is None:
            fail(
                "BLUETOOTH_AUDIO_ROUTE",
                "recorded Bluetooth device has no usable output route",
                "reconnect Bluetooth or expose one deterministic direct capture+playback fallback",
                1,
            )
    # The pairing postcondition must not claim a usable headset deployment when
    # no input route can even be enumerated.  This remains non-actuating: the
    # later appliance-readiness gate is still the authority for real capture.
    if require_connected and not sources:
        fallback_capture = direct_capture_fallback(audio_user)
        if fallback_capture is None:
            fail(
                "BLUETOOTH_INPUT_UNAVAILABLE",
                "recorded Bluetooth preference has no Bluetooth or direct capture input route",
                "expose the headset microphone or connect exactly one USB microphone, then rerun",
                1,
            )
    state = "connected" if info["connected"] else "paired_offline_direct_fallback"
    fallback_state = "yes" if direct_fallback is not None else "no"
    print(
        f"[OK] code=BLUETOOTH_AUDIO_STATUS state={state} output_nodes={len(sinks)} "
        f"input_nodes={len(sources)} direct_fallback={fallback_state}"
    )


def _autoconnect_payload(unit_template: Path) -> str:
    if not unit_template.is_file() or unit_template.is_symlink():
        fail("BLUETOOTH_SERVICE", "autoconnect unit template is missing or unsafe", "restore the immutable release", 65)
    payload = unit_template.read_text(encoding="utf-8")
    required = (
        "bluetooth_manager.py watch",
        "Environment=PYTHONDONTWRITEBYTECODE=1",
        "Environment=PYTHONNOUSERSITE=1",
    )
    if "\r" in payload or any(value not in payload for value in required):
        fail("BLUETOOTH_SERVICE", "autoconnect unit template is malformed", "restore the immutable release", 65)
    return payload


def install_autoconnect(unit_template: Path, record: Path) -> None:
    if os.geteuid() != 0:
        fail("BLUETOOTH_PRIVILEGE", "autoconnect installation requires root", "run through bootstrap or sudo", 77)
    read_device_record(record)
    destination = AUTOCONNECT_UNIT
    payload = _autoconnect_payload(unit_template)
    if destination.exists() and (destination.is_symlink() or not destination.is_file()):
        fail("BLUETOOTH_SERVICE", "autoconnect unit destination is unsafe", "remove the conflicting administrator path", 75)
    if destination.exists():
        current = destination.read_text(encoding="utf-8")
        if current != payload:
            import hashlib
            digest = hashlib.sha256(current.encode()).hexdigest()
            if digest not in KNOWN_PREVIOUS_AUTOCONNECT_SHA256:
                fail("BLUETOOTH_SERVICE", "existing autoconnect unit differs", "review/remove the conflicting unit before enabling Bluetooth", 75)
            atomic_text(destination, payload, mode=0o644)
            print(f"[OK] code=BLUETOOTH_AUTOCONNECT_MANAGED_UPGRADE path={destination}")
    else:
        atomic_text(destination, payload, mode=0o644)
    run(["systemctl", "daemon-reload"], timeout=20)
    run(["systemctl", "enable", "--now", "gonken-bluetooth-autoconnect.service"], timeout=30)
    print("[OK] code=BLUETOOTH_AUTOCONNECT_INSTALLED")


def autoconnect_status(record: Path, unit_template: Path) -> None:
    read_device_record(record)
    destination = AUTOCONNECT_UNIT
    expected = _autoconnect_payload(unit_template)
    if not destination.is_file() or destination.is_symlink():
        fail("BLUETOOTH_SERVICE", "autoconnect service is not installed", "rerun Bluetooth setup", 1)
    try:
        installed = destination.read_text(encoding="utf-8")
    except OSError:
        fail("BLUETOOTH_SERVICE", "autoconnect service cannot be read", "rerun Bluetooth setup", 1)
    if installed != expected:
        fail("BLUETOOTH_SERVICE", "autoconnect service requires managed upgrade", "rerun Bluetooth setup", 1)
    enabled = run(["systemctl", "is-enabled", "--quiet", "gonken-bluetooth-autoconnect.service"], timeout=8, check=False)
    active = run(["systemctl", "is-active", "--quiet", "gonken-bluetooth-autoconnect.service"], timeout=8, check=False)
    if enabled.returncode != 0 or active.returncode != 0:
        fail("BLUETOOTH_SERVICE", "autoconnect service is not enabled and active", "rerun Bluetooth setup", 1)
    print("[OK] code=BLUETOOTH_AUTOCONNECT_HEALTHY")


def watch(record: Path, audio_user: str, interval: int) -> None:
    stop = False

    def handle(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)
    last: bool | None = None
    failures = 0
    while not stop:
        try:
            connected = connect_record(record, audio_user, strict=False)
        except BluetoothError as error:
            emit_error(error)
            connected = False
        if connected != last:
            code = "BLUETOOTH_RECONNECTED" if connected else "BLUETOOTH_WAITING"
            print(f"[{'OK' if connected else 'RUNNING'}] code={code}", flush=True)
            last = connected
        failures = 0 if connected else failures + 1
        delay = interval if connected else min(60, interval * (2 ** min(failures - 1, 3)))
        for _ in range(delay * 2):
            if stop:
                break
            time.sleep(0.5)


def direct_status(audio_user: str) -> tuple[str, str]:
    routes = direct_audio_fallback(audio_user)
    if routes is None:
        fail(
            "AUDIO_DIRECT_UNAVAILABLE",
            "no single deterministic direct capture+playback route is available",
            "connect exactly one supported USB/wired microphone and playback device or restore Bluetooth",
            75,
        )
    print(f"[OK] code=AUDIO_DIRECT_FALLBACK_READY input={routes[0]} output={routes[1]}")
    return routes


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    for name in ("stack-status", "prepare", "direct-status"):
        item = commands.add_parser(name)
        item.add_argument("--audio-user", default="gonken-agent")

    pair_cmd = commands.add_parser("pair")
    pair_cmd.add_argument("--audio-user", default="gonken-agent")
    pair_cmd.add_argument("--selector", default="")
    pair_cmd.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")
    pair_cmd.add_argument("--timeout", type=int, default=120)

    status_cmd = commands.add_parser("status")
    status_cmd.add_argument("--audio-user", default="gonken-agent")
    status_cmd.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")
    status_cmd.add_argument("--require-connected", action="store_true")
    status_cmd.add_argument("--allow-direct-fallback", action="store_true")

    connect_cmd = commands.add_parser("connect")
    connect_cmd.add_argument("--audio-user", default="gonken-agent")
    connect_cmd.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")

    install_cmd = commands.add_parser("install-autoconnect")
    install_cmd.add_argument("--unit-template", required=True)
    install_cmd.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")

    service_status = commands.add_parser("autoconnect-status")
    service_status.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")
    service_status.add_argument("--unit-template", required=True)

    watch_cmd = commands.add_parser("watch")
    watch_cmd.add_argument("--audio-user", default="gonken-agent")
    watch_cmd.add_argument("--record", default="/etc/gonken-agent/bluetooth-device.record")
    watch_cmd.add_argument("--interval", type=int, default=10)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if getattr(args, "timeout", 120) < 15 or getattr(args, "timeout", 120) > 600:
            fail("BLUETOOTH_USAGE", "pairing timeout must be 15..600 seconds", "use a bounded pairing window", 64)
        if getattr(args, "interval", 10) < 2 or getattr(args, "interval", 10) > 60:
            fail("BLUETOOTH_USAGE", "watch interval must be 2..60 seconds", "use a bounded reconnect interval", 64)
        if args.command == "stack-status":
            stack_status(args.audio_user)
        elif args.command == "prepare":
            prepare(args.audio_user)
        elif args.command == "direct-status":
            direct_status(args.audio_user)
        elif args.command == "pair":
            pair(args.selector, args.audio_user, Path(args.record), args.timeout)
        elif args.command == "status":
            device_status(
                Path(args.record),
                args.audio_user,
                require_connected=args.require_connected,
                allow_direct_fallback=args.allow_direct_fallback,
            )
        elif args.command == "connect":
            if connect_record(Path(args.record), args.audio_user, strict=True):
                print("[OK] code=BLUETOOTH_CONNECTED")
        elif args.command == "install-autoconnect":
            install_autoconnect(Path(args.unit_template), Path(args.record))
        elif args.command == "autoconnect-status":
            autoconnect_status(Path(args.record), Path(args.unit_template))
        elif args.command == "watch":
            watch(Path(args.record), args.audio_user, args.interval)
        else:  # pragma: no cover
            raise AssertionError(args.command)
    except BluetoothError as error:
        emit_error(error)
        return error.status
    except (OSError, ValueError) as error:
        emit_error(BluetoothError("BLUETOOTH_IO", str(error), "inspect local Bluetooth/audio state", 74))
        return 74
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
