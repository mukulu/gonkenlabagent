#!/usr/bin/env python3
"""Bounded SHT31 production-adapter probe using exact GonKen wire semantics."""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

# Maintenance copies live one level below the release root.  Re-exec with the
# immutable release interpreter so diagnostics exercise the exact production package.
if __name__ == "__main__" and os.environ.get("GONKEN_SHT31_DIAGNOSTIC_REEXEC") != "1":
    here=Path(__file__).resolve()
    release=here.parent.parent
    candidate=release/".venv/bin/python"
    if candidate.is_file() and Path(sys.executable).resolve()!=candidate.resolve():
        env=os.environ.copy(); env["GONKEN_SHT31_DIAGNOSTIC_REEXEC"]="1"
        os.execve(candidate, [str(candidate), str(here), *sys.argv[1:]], env)

from gonken_agent.environment.sensors.sht31 import SHT31Sensor
from gonken_agent.environment.sensors.base import SensorAdapterError

ADDRESSES=(0x44,0x45)


def _prepare_sensor(sensor: SHT31Sensor) -> tuple[bool, bool]:
    """Verify the status register and force the SHT31 plausibility heater off."""
    initially_enabled = sensor.heater_enabled()
    if initially_enabled:
        sensor.disable_heater()
    heater_off_verified = not sensor.heater_enabled()
    if not heater_off_verified:
        raise SensorAdapterError("SENSOR_HEATER_STATE", "SHT31 heater remained enabled")
    return initially_enabled, heater_off_verified


def one(address: int, *, bus: int, sensor_factory: Callable[..., SHT31Sensor]=SHT31Sensor):
    sensor=sensor_factory(bus_number=bus,address=address,repeatability="high")
    try:
        _prepare_sensor(sensor)
        return sensor.read(now_monotonic=time.monotonic())
    finally:
        sensor.close()


def discover(*, bus: int, sensor_factory: Callable[..., SHT31Sensor]=SHT31Sensor) -> tuple[int, dict[int, str]]:
    valid=[]; errors={}
    for address in ADDRESSES:
        try:
            reading=one(address,bus=bus,sensor_factory=sensor_factory)
        except SensorAdapterError as exc:
            errors[address]=exc.code
            continue
        if reading.is_valid(): valid.append(address)
        else: errors[address]=str(reading.error_code or "SENSOR_UNAVAILABLE")
    if len(valid)==1: return valid[0], errors
    if not valid: raise RuntimeError("SHT31_ADDRESS_NOT_FOUND:"+",".join(f"0x{k:02x}={v}" for k,v in errors.items()))
    raise RuntimeError("SHT31_ADDRESS_AMBIGUOUS:"+",".join(f"0x{v:02x}" for v in valid))


def campaign(address: int, *, bus: int, reads: int, sensor_factory: Callable[..., SHT31Sensor]=SHT31Sensor) -> dict[str, object]:
    sensor=sensor_factory(bus_number=bus,address=address,repeatability="high")
    temperatures=[]; humidities=[]; errors={}
    heater_initially_enabled=False; heater_off_verified=False
    try:
        heater_initially_enabled, heater_off_verified = _prepare_sensor(sensor)
        for _ in range(reads):
            reading=sensor.read(now_monotonic=time.monotonic())
            if reading.is_valid():
                temperatures.append(float(reading.temperature_c)); humidities.append(float(reading.relative_humidity_pct))
            else:
                code=str(reading.error_code or "SENSOR_UNAVAILABLE"); errors[code]=errors.get(code,0)+1
    finally:
        sensor.close()
    valid=len(temperatures)
    def summary(values):
        return None if not values else {"min":min(values),"max":max(values),"mean":statistics.fmean(values)}
    return {
        "reads_requested": reads, "valid_reads": valid, "invalid_reads": reads-valid,
        "error_counts": dict(sorted(errors.items())), "temperature_c": summary(temperatures),
        "relative_humidity_pct": summary(humidities), "all_valid": valid==reads,
        "heater_initially_enabled": heater_initially_enabled, "heater_off_verified": heater_off_verified,
    }


def parser():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--bus",type=int,default=1); p.add_argument("--address",default="auto"); p.add_argument("--reads",type=int,default=100); p.add_argument("--json",action="store_true"); return p


def main(argv=None):
    args=parser().parse_args(argv)
    if args.bus<0 or not 1<=args.reads<=500:
        print("[ERROR] code=SHT31_DIAGNOSTIC_USAGE message=bus/reads_out_of_range",file=sys.stderr); return 64
    try:
        if args.address=="auto": address,_=discover(bus=args.bus)
        else:
            address=int(args.address,0)
            if address not in ADDRESSES: raise ValueError("address must be 0x44, 0x45, or auto")
        result=campaign(address,bus=args.bus,reads=args.reads)
    except ValueError as exc:
        print(f"[ERROR] code=SHT31_DIAGNOSTIC_USAGE message={exc}",file=sys.stderr); return 64
    except SensorAdapterError as exc:
        print(f"[ERROR] code={exc.code} message=targeted_probe_failed physical_acceptance_claimed=false",file=sys.stderr); return 75
    except RuntimeError as exc:
        code=str(exc).split(":",1)[0]
        print(f"[ERROR] code={code} message=targeted_probe_failed physical_acceptance_claimed=false",file=sys.stderr); return 75
    payload={"status":"PASS" if result["all_valid"] else "DEGRADED","bus":args.bus,"address":f"0x{address:02x}","physical_acceptance_claimed":False,**result}
    if args.json: print(json.dumps(payload,sort_keys=True))
    else: print(f"[OK] code=SHT31_DIAGNOSTIC status={payload['status']} address={payload['address']} valid_reads={payload['valid_reads']}/{payload['reads_requested']} physical_acceptance_claimed=false")
    return 0 if result["all_valid"] else 75


if __name__=="__main__": raise SystemExit(main())
