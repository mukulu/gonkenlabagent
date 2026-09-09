"""Stable audio selection and capped recovery scheduling."""
from dataclasses import dataclass


class DeviceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Device:
    stable_id: str
    name: str
    input_channels: int
    output_channels: int
    rates: tuple[int, ...]


def select(devices, selector, direction, rate):
    if direction not in {'input', 'output'} or not selector:
        raise ValueError('explicit direction and selector required')
    eligible = [d for d in devices if getattr(d, direction + '_channels') > 0]
    exact = [d for d in eligible if d.stable_id == selector]
    matches = exact or [d for d in eligible if selector.casefold() in d.name.casefold()]
    if not matches:
        raise DeviceUnavailable('AUDIO_NOT_FOUND')
    if len(matches) != 1:
        raise DeviceUnavailable('AUDIO_AMBIGUOUS')
    if rate not in matches[0].rates:
        raise DeviceUnavailable('AUDIO_UNSUPPORTED_RATE')
    return matches[0]


class Recovery:
    def __init__(self, enumerate_devices, open_device, selector, direction, rate):
        self.enumerate = enumerate_devices
        self.open = open_device
        self.selector, self.direction, self.rate = selector, direction, rate
        self.failures = 0
        self.next_attempt = 0.0

    def attempt(self, now):
        if now < self.next_attempt:
            return None
        try:
            # Always re-enumerate; never cache a numeric device index.
            device = select(self.enumerate(), self.selector, self.direction, self.rate)
            stream = self.open(device)
        except (DeviceUnavailable, OSError):
            self.failures += 1
            self.next_attempt = now + min(30.0, 0.25 * 2 ** min(self.failures - 1, 7))
            return None
        self.failures = 0
        self.next_attempt = now
        return stream
