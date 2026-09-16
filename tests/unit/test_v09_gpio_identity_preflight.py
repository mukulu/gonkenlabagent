from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gpio_identity_preflight", ROOT / "scripts" / "gpio_identity_preflight.py")
mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)


class FakeChip:
    def __init__(self, lines, label=""):
        self.lines=list(lines); self.label=label
    def get_info(self): return SimpleNamespace(num_lines=len(self.lines), label=self.label, name="")
    def get_line_info(self, offset): return SimpleNamespace(name=self.lines[offset])
    def close(self): pass


class FakeGpiod:
    def __init__(self, chips, labels=None): self.chips=chips; self.labels=labels or {}
    def Chip(self, path): return FakeChip(self.chips[path], self.labels.get(path,""))


class GpioIdentityPreflightTests(unittest.TestCase):
    def test_probe_resolves_pi5_header_without_requesting_lines(self):
        rp1=[None]*54
        for bcm in (2,3,17,22,23,27): rp1[bcm]=f"GPIO{bcm}"
        other=[None]*32; other[5]="GPIO17"; other[7]="GPIO22"; other[9]="GPIO27"; other[4]="GPIO23"
        module=FakeGpiod({"/dev/gpiochip0":rp1,"/dev/gpiochip10":other})
        payload=mod.probe((17,22,23,27), gpiod_module=module, chip_paths=("/dev/gpiochip0","/dev/gpiochip10"))
        self.assertEqual(payload["status"],"PASS")
        self.assertEqual(payload["chip_path"],"/dev/gpiochip0")
        self.assertFalse(payload["physical_acceptance_claimed"])
        self.assertEqual(payload["lines"]["GPIO22"]["line_offset"],22)

    def test_probe_fails_closed_when_header_identity_remains_ambiguous(self):
        a=[None]*54; b=[None]*54
        for lines in (a,b):
            for bcm in (2,3,17,22,23,27): lines[bcm]=f"GPIO{bcm}"
        module=FakeGpiod({"/dev/gpiochip0":a,"/dev/gpiochip10":b})
        payload=mod.probe((17,22,23,27), gpiod_module=module, chip_paths=("/dev/gpiochip0","/dev/gpiochip10"))
        self.assertEqual(payload["status"],"FAIL")
        self.assertEqual(payload["code"],"GPIO_HEADER_UNRESOLVED")


if __name__ == "__main__": unittest.main()
