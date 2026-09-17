"""Target-safe Raspberry Pi GPIO line discovery for libgpiod v2.

The public project configuration uses logical BCM GPIO identities.  Raspberry
Pi 5 exposes the 40-pin header through RP1, but the kernel may expose several
``gpiochip`` devices and line names are not globally unique.  This module
resolves a named header GPIO without assuming a fixed ``/dev/gpiochipN``.

Resolution order is deliberately fail-closed:
1. a globally unique line-name match;
2. a unique match whose chip metadata identifies the RP1 pin controller;
3. a unique chip whose line-name topology contains the project's complete
   Raspberry Pi header signature.

No GPIO line is requested or written during discovery.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HEADER_SIGNATURE = frozenset({"GPIO2", "GPIO3", "GPIO17", "GPIO22", "GPIO23", "GPIO27"})


class GpioResolveError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = " ".join(str(detail).replace("\r", " ").replace("\n", " ").split())[:480]


@dataclass(frozen=True, slots=True)
class GpioLineResolution:
    logical_bcm: int
    chip_path: str
    line_offset: int
    line_name: str
    chip_name: str = ""
    chip_label: str = ""
    resolution_basis: str = "unique-line-name"
    canonical_chip_id: str = ""
    alias_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ChipSnapshot:
    chip_path: str
    chip_name: str
    chip_label: str
    line_names: tuple[str | None, ...]
    canonical_chip_id: str = ""
    alias_paths: tuple[str, ...] = ()

    @property
    def named_set(self) -> frozenset[str]:
        return frozenset(name for name in self.line_names if isinstance(name, str) and name)


def _clean_metadata(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())[:160]


def _sysfs_label(chip_path: str) -> str:
    """Best-effort read-only controller label fallback.

    Raspberry Pi OS normally exposes gpiochip metadata through libgpiod.  Some
    Python binding/kernel combinations have returned incomplete ``ChipInfo``
    metadata, while the kernel sysfs view still contains the controller label.
    This helper never writes and failure simply returns an empty string.
    """
    name = Path(chip_path).name
    if not name.startswith("gpiochip"):
        return ""
    candidates = (
        Path("/sys/bus/gpio/devices") / name / "label",
        Path("/sys/class/gpio") / name / "label",
    )
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if value:
            return _clean_metadata(value)
    return ""


def _device_identity(chip_path: str) -> str:
    """Return a canonical read-only identity for a gpiochip device node.

    The path under ``/dev`` is not a stable Raspberry Pi 5 hardware identity.
    When the node can be inspected, prefer character-device major/minor plus
    the kernel's ``/sys/dev/char`` realpath.  If inspection fails, return an
    empty identity and let the resolver fall back to metadata/topology without
    deduplicating paths that may be distinct hardware.
    """
    try:
        info = os.stat(chip_path)
    except OSError:
        return ""
    mode = getattr(info, "st_mode", 0)
    if not stat.S_ISCHR(mode):
        return ""
    rdev = getattr(info, "st_rdev", 0)
    major = os.major(rdev)
    minor = os.minor(rdev)
    sysfs = Path("/sys/dev/char") / f"{major}:{minor}"
    try:
        sysfs_real = str(sysfs.resolve(strict=True))
    except OSError:
        sysfs_real = ""
    return f"char:{major}:{minor}:{sysfs_real}"


def _deduplicate_aliases(snapshots: list[_ChipSnapshot]) -> list[_ChipSnapshot]:
    by_identity: dict[str, list[_ChipSnapshot]] = {}
    output: list[_ChipSnapshot] = []
    for snapshot in snapshots:
        if snapshot.canonical_chip_id:
            by_identity.setdefault(snapshot.canonical_chip_id, []).append(snapshot)
        else:
            output.append(snapshot)
    for identity, group in by_identity.items():
        if len(group) == 1:
            output.append(group[0])
            continue
        paths = tuple(sorted(item.chip_path for item in group))
        primary = sorted(group, key=lambda item: item.chip_path)[0]
        output.append(
            _ChipSnapshot(
                chip_path=primary.chip_path,
                chip_name=primary.chip_name,
                chip_label=primary.chip_label,
                line_names=primary.line_names,
                canonical_chip_id=identity,
                alias_paths=paths,
            )
        )
    return sorted(output, key=lambda item: item.chip_path)


def _scan(gpiod: Any, chip_paths: Iterable[str]) -> list[_ChipSnapshot]:
    snapshots: list[_ChipSnapshot] = []
    for chip_path in chip_paths:
        if not isinstance(chip_path, str) or not chip_path.startswith("/dev/gpiochip"):
            continue
        try:
            chip = gpiod.Chip(chip_path)
        except Exception:
            continue
        try:
            info = chip.get_info()
            count = int(getattr(info, "num_lines"))
            if count < 1 or count > 4096:
                continue
            chip_name = _clean_metadata(getattr(info, "name", ""))
            chip_label = _clean_metadata(getattr(info, "label", "")) or _sysfs_label(chip_path)
            canonical_chip_id = _device_identity(chip_path)
            names: list[str | None] = []
            for offset in range(count):
                try:
                    line_info = chip.get_line_info(offset)
                    value = getattr(line_info, "name", None)
                except Exception:
                    value = None
                names.append(value if isinstance(value, str) and value else None)
            snapshots.append(
                _ChipSnapshot(
                    chip_path,
                    chip_name,
                    chip_label,
                    tuple(names),
                    canonical_chip_id=canonical_chip_id,
                    alias_paths=(chip_path,),
                )
            )
        finally:
            close = getattr(chip, "close", None)
            if callable(close):
                close()
    return _deduplicate_aliases(snapshots)


def _rp1_metadata(snapshot: _ChipSnapshot) -> bool:
    combined = f"{snapshot.chip_name} {snapshot.chip_label}".casefold()
    return "pinctrl-rp1" in combined or ("rp1" in combined and "gpio" not in combined)


def _candidate_detail(rows: list[tuple[_ChipSnapshot, int]]) -> str:
    parts = []
    for chip, offset in rows:
        parts.append(
            f"{chip.chip_path}:{offset}[name={chip.chip_name or '-'},label={chip.chip_label or '-'}]"
        )
    return ",".join(parts)[:420]


def resolve_named_gpio_line(
    *,
    gpiod: Any,
    logical_bcm: int,
    chip_paths: Iterable[str],
) -> GpioLineResolution:
    if isinstance(logical_bcm, bool) or not isinstance(logical_bcm, int) or not 0 <= logical_bcm <= 53:
        raise GpioResolveError("config", "logical BCM must be 0..53")
    expected = f"GPIO{logical_bcm}"
    snapshots = _scan(gpiod, chip_paths)
    matches: list[tuple[_ChipSnapshot, int]] = []
    for chip in snapshots:
        for offset, name in enumerate(chip.line_names):
            if name == expected:
                matches.append((chip, offset))
    if not matches:
        raise GpioResolveError("not_found", expected)

    def result(row: tuple[_ChipSnapshot, int], basis: str) -> GpioLineResolution:
        chip, offset = row
        return GpioLineResolution(
            logical_bcm=logical_bcm,
            chip_path=chip.chip_path,
            line_offset=offset,
            line_name=expected,
            chip_name=chip.chip_name,
            chip_label=chip.chip_label,
            resolution_basis=basis,
            canonical_chip_id=chip.canonical_chip_id,
            alias_paths=chip.alias_paths or (chip.chip_path,),
        )

    if len(matches) == 1:
        return result(matches[0], "unique-line-name")

    rp1 = [row for row in matches if _rp1_metadata(row[0])]
    if len(rp1) == 1:
        return result(rp1[0], "rp1-metadata")

    # Real Pi 5 fallback: identify the unique chip carrying the coherent set of
    # project header GPIO line names.  This deliberately does not use gpiochip
    # numbering or assume BCM == offset.
    topology_chips = [chip for chip in snapshots if HEADER_SIGNATURE.issubset(chip.named_set)]
    topology_matches = [row for row in matches if row[0] in topology_chips]
    if len(topology_chips) == 1 and len(topology_matches) == 1:
        return result(topology_matches[0], "header-topology")

    raise GpioResolveError("ambiguous", f"{expected} candidates={_candidate_detail(matches)}")
