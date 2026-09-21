"""Capability-derived resource claims; pure data, never hardware acquisition.

Configured inactive compatibility fields remain visible but reserve nothing.
Only explicitly enabled physical capabilities participate in collision checks.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

STATES = frozenset({"ACTIVE_REQUIRED", "ACTIVE_OPTIONAL", "INACTIVE_CONFIGURED", "RESERVED_FUTURE_PROFILE", "UNRESOLVED_TARGET_RESOURCE"})
ACTIVE = frozenset({"ACTIVE_REQUIRED", "ACTIVE_OPTIONAL", "UNRESOLVED_TARGET_RESOURCE"})
DISPLAY_PROFILES = frozenset({"none", "osoyoo35-drm", "osoyoo35-fbdev-console", "osoyoo35-fbdev-x11"})


@dataclass(frozen=True, slots=True)
class ResourceClaim:
    resource: str
    kind: str
    owner: str
    consumer: str
    state: str
    reason: str
    actuating: bool = False
    sharing: str | None = None
    physical_evidence: str = "NONE"

    def __post_init__(self):
        if self.state not in STATES or self.kind not in {"gpio", "i2c", "spi", "audio", "tty", "framebuffer"}:
            raise ValueError("invalid resource claim")
        if not all(isinstance(x, str) and x for x in (self.resource, self.owner, self.consumer, self.reason)):
            raise ValueError("claim provenance is required")
        if self.kind == "gpio":
            if not self.resource.startswith("GPIO") or not self.resource[4:].isdigit() or not 0 <= int(self.resource[4:]) <= 53:
                raise ValueError("invalid GPIO claim")
        if self.physical_evidence != "NONE":
            raise ValueError("configured claims cannot establish physical evidence")


class ResourceConflict(ValueError):
    pass


def claims_for_config(config: Config, *, display_profile: str = "none", touch: bool = False,
                      backlight_managed: bool = False, backlight_gpio_verified: bool = False) -> tuple[ResourceClaim, ...]:
    if display_profile not in DISPLAY_PROFILES or type(touch) is not bool or type(backlight_managed) is not bool or type(backlight_gpio_verified) is not bool:
        raise ValueError("invalid display capability settings")
    if display_profile == "none" and (touch or backlight_managed):
        raise ValueError("touch/backlight requires a selected display profile")
    rows: list[ResourceClaim] = []
    def gpio(pin, owner, consumer, enabled, reason, *, actuating=False, sharing=None):
        if type(pin) is not int or not 0 <= pin <= 53: raise ValueError("invalid GPIO number")
        rows.append(ResourceClaim(f"GPIO{pin}","gpio",owner,consumer,"ACTIVE_REQUIRED" if enabled else "INACTIVE_CONFIGURED",reason,actuating,sharing))
    ptt = config.runtime.interaction_mode == "push_to_talk"
    wake = config.runtime.interaction_mode == "wake_word" and config.extensions.wake_word.enabled
    gpio(config.interaction.push_to_talk_gpio,"ptt","gonken-agent",ptt,"push_to_talk_input")
    gpio(config.interaction.recording_led_gpio,"ptt_recording_indicator","gonken-agent",ptt,"ptt_recording_indicator",actuating=True)
    # GPIO22 is not dormant PTT; current wake code actually opens this indicator.
    gpio(config.extensions.wake_word.monitoring_led_gpio,"wake_indicator","gonken-agent",wake,"wake_privacy_indicator",actuating=True)
    env = config.extensions.environment
    sensor = env.enabled and env.sensor_backend == "sht31"
    relay = env.enabled and env.relay_backend == "libgpiod"
    gpio(env.relay_bcm,"room_fan","gonken-env",relay,"room_fan_relay",actuating=True)
    rows.append(ResourceClaim(f"I2C{env.i2c_bus}","i2c","environment_sensor","gonken-env","ACTIVE_REQUIRED" if sensor else "INACTIVE_CONFIGURED","sht31_sensor",False,f"I2C{env.i2c_bus}"))
    if env.i2c_bus == 1:
        for pin, reason in ((2,"sht31_sda"),(3,"sht31_scl")):
            gpio(pin,"environment_sensor","kernel-i2c/gonken-env",sensor,reason,sharing="I2C1")
    if display_profile != "none":
        rows.append(ResourceClaim("SPI0","spi","osoyoo_display","kernel-spi","ACTIVE_REQUIRED","display_transport",False,"SPI0"))
        for pin in (9,10,11): gpio(pin,"osoyoo_display","kernel-spi",True,"spi_bus",sharing="SPI0")
        for pin, reason in ((8,"display_chip_select"),(24,"display_dc"),(25,"display_reset")):
            gpio(pin,"osoyoo_display","kernel-display",True,reason)
        if touch:
            rows.append(ResourceClaim("SPI0","spi","osoyoo_touch","kernel-spi","ACTIVE_REQUIRED","touch_transport",False,"SPI0"))
            for pin, reason in ((7,"touch_chip_select"),(17,"touch_irq")):
                gpio(pin,"osoyoo_touch","kernel-input",True,reason)
        # Board documentation disagrees about GPIO18. Do not allocate it elsewhere
        # while the physical profile is selected, even with management disabled.
        state = "ACTIVE_REQUIRED" if backlight_managed and backlight_gpio_verified else "UNRESOLVED_TARGET_RESOURCE"
        rows.append(ResourceClaim("GPIO18","gpio","osoyoo_backlight","kernel-display",state,"exact_board_backlight_wiring_unverified" if state.startswith("UNRESOLVED") else "backlight_control",backlight_managed))
        if backlight_managed and not backlight_gpio_verified:
            raise ResourceConflict("GPIO18 backlight management requires exact-board verification")
    validate_claims(rows)
    return tuple(rows)


def validate_claims(claims) -> None:
    grouped: dict[str,list[ResourceClaim]] = {}
    for claim in claims:
        if claim.state in ACTIVE: grouped.setdefault(claim.resource,[]).append(claim)
    for resource, rows in grouped.items():
        owners = {r.owner for r in rows}
        if len(owners) < 2: continue
        shares = {r.sharing for r in rows}
        if len(shares) == 1 and None not in shares and all(not r.actuating for r in rows):
            continue
        raise ResourceConflict(f"{resource} conflict between {','.join(sorted(owners))}")


def gpio_lines(claims) -> tuple[int, ...]:
    return tuple(sorted({int(r.resource[4:]) for r in claims if r.kind == "gpio" and r.state in {"ACTIVE_REQUIRED","ACTIVE_OPTIONAL"}}))


def resource_document(config: Config, **kwargs) -> dict:
    claims = claims_for_config(config, **kwargs)
    rows = [asdict(r) for r in claims]
    fingerprint = hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"format":"gonken-resource-claims-v1","claims":rows,"required_gpio_lines":list(gpio_lines(claims)),
            "claims_sha256":fingerprint,"physical_acceptance_claimed":False}
