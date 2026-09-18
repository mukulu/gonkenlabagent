"""Operator-safe local-model administration for the governed V04 roster."""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .models import (
    DEFAULT_SELECTION_PATH,
    MODEL_ROSTER,
    active_model,
    admitted_model,
    roster_manifest,
    selection_status,
    write_selection,
)
from .ollama import OllamaClient, OllamaError
from ..tool_broker import TOOL_SCHEMAS, parse_tool_call, ToolBrokerError

ROSTER_RECORD_PATH = Path("/var/lib/gonken-agent/ollama/roster.json")
READY_FILE = Path("/run/gonken-agent/ready.json")
_CAPABILITY_TOOL = ({
    "type": "function",
    "function": {
        "name": "readiness_probe",
        "description": "Return readiness using this read-only capability probe.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
},)


class ModelAdminError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _bounded_json(path: Path, max_bytes: int = 256 * 1024) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _client(config, model: str, *, timeout: int = 30) -> OllamaClient:
    return OllamaClient(config.llm, timeout=timeout, model=model)


def _inventory(config) -> list[dict[str, object]]:
    probe = _client(config, active_model(config.llm.model), timeout=5)
    try:
        return probe.model_inventory(threading.Event())
    finally:
        probe.close()


def _loaded_models(config) -> list[str]:
    probe = _client(config, active_model(config.llm.model), timeout=5)
    try:
        return probe.loaded_models(threading.Event())
    finally:
        probe.close()


def _resource_snapshot() -> dict[str, object]:
    memory: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, remainder = line.partition(":")
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                value = remainder.strip().split()[0]
                if value.isdigit():
                    memory[f"{key.lower()}_kib"] = int(value)
    except OSError:
        pass
    temperature_c = None
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="ascii").strip()
        if raw.lstrip("-").isdigit():
            temperature_c = round(int(raw) / 1000.0, 1)
    except (OSError, ValueError):
        pass
    return {"memory": memory, "soc_temperature_c": temperature_c}


def status(config) -> dict[str, object]:
    selection = selection_status(config.llm.model)
    record = _bounded_json(ROSTER_RECORD_PATH)
    inventory: list[dict[str, object]] = []
    loaded: list[str] = []
    inventory_error = None
    try:
        inventory = _inventory(config)
        loaded = _loaded_models(config)
    except (OSError, ValueError, RuntimeError, OllamaError) as exc:
        inventory_error = type(exc).__name__
    installed = {str(item.get("name")) for item in inventory}
    roster_rows = []
    recorded_rows = {}
    if isinstance(record, dict) and isinstance(record.get("models"), list):
        recorded_rows = {
            str(item.get("tag")): item
            for item in record["models"]
            if isinstance(item, dict) and isinstance(item.get("tag"), str)
        }
    for spec in MODEL_ROSTER:
        recorded = recorded_rows.get(spec.tag, {})
        roster_rows.append({
            "tag": spec.tag,
            "role": spec.role,
            "installed": spec.tag in installed,
            "selected": selection.get("model") == spec.tag,
            "catalog_tools": spec.tools,
            "catalog_thinking": spec.thinking,
            "tool_call_smoke": recorded.get("tool_call_smoke", "NOT_TESTED"),
            "inference_total_ns": recorded.get("inference_total_ns"),
            "tool_total_ns": recorded.get("tool_total_ns"),
        })
    return {
        "status": "READY" if selection.get("governed_roster_active") and all(row["installed"] for row in roster_rows) and len(loaded) <= 1 else "DEGRADED",
        "selection": selection,
        "roster": roster_rows,
        "policy": {"max_loaded_models": 1, "num_parallel": 1, "thinking_default": False},
        "loaded_models": loaded,
        "one_loaded_model_invariant": len(loaded) <= 1,
        "resources": _resource_snapshot(),
        "inventory_error": inventory_error,
        "physical_acceptance": False,
    }


def capability_smoke(config, model: str) -> dict[str, object]:
    admitted_model(model)
    client = _client(config, model, timeout=60)
    stop = threading.Event()
    started = time.monotonic_ns()
    try:
        response = client.chat_message(
            [{"role": "user", "content": "Use the readiness probe tool exactly once."}],
            stop,
            tools=_CAPABILITY_TOOL,
            think=False,
            keep_alive=0,
        )
    finally:
        client.close()
    calls = response.get("tool_calls", [])
    passed = (
        isinstance(calls, list)
        and len(calls) == 1
        and isinstance(calls[0], dict)
        and calls[0].get("function", {}).get("name") == "readiness_probe"
        and calls[0].get("function", {}).get("arguments") == {}
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "model": model,
        "thinking": False,
        "tool": "readiness_probe",
        "wall_ns": time.monotonic_ns() - started,
        "ollama_total_ns": response.get("total_duration"),
        "content_logged": False,
    }


def semantic_tool_quality(config, model: str, *, thinking: bool = False) -> dict[str, object]:
    """Verify semantic tool selection without executing any proposed tool."""
    admitted_model(model)
    cases = (
        ("clock", "What time is it right now?", "system_get_local_datetime", {}),
        ("temperature", "Could you check how warm the room is?", "environment_read_sensor", {}),
        ("fan_status", "Is the room fan powered on?", "environment_get_status", {}),
        ("fan_on_proposal", "Please turn the room fan on.", "environment_set_fan_power", {"power": "on"}),
    )
    client = _client(config, model, timeout=90)
    stop = threading.Event()
    rows: list[dict[str, object]] = []
    try:
        for case_id, prompt, expected_name, expected_args in cases:
            started = time.monotonic_ns()
            response = client.chat_message(
                [{"role": "user", "content": prompt}],
                stop, tools=TOOL_SCHEMAS, think=thinking, keep_alive=0,
            )
            calls = response.get("tool_calls", [])
            observed_name = None
            observed_args: dict[str, object] | None = None
            valid = False
            if isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], dict):
                try:
                    proposal = parse_tool_call(calls[0])
                except ToolBrokerError:
                    pass
                else:
                    observed_name = proposal.name
                    observed_args = dict(proposal.arguments)
                    valid = proposal.name == expected_name and observed_args == expected_args
            rows.append({
                "case": case_id, "status": "PASS" if valid else "FAIL",
                "expected_tool": expected_name, "observed_tool": observed_name,
                "arguments_match": observed_args == expected_args,
                "wall_ns": time.monotonic_ns() - started,
                "ollama_total_ns": response.get("total_duration"),
            })
    finally:
        client.close()
    passed = sum(1 for row in rows if row["status"] == "PASS")
    return {
        "status": "PASS" if passed == len(rows) else "FAIL",
        "model": model, "thinking": bool(thinking),
        "passed": passed, "total": len(rows), "cases": rows,
        "tools_executed": False, "content_logged": False,
        "physical_acceptance": False,
    }


def capability_report(config, model: str, *, thinking: bool = False) -> dict[str, object]:
    provider = capability_smoke(config, model)
    semantic = semantic_tool_quality(config, model, thinking=thinking)
    return {
        "status": "PASS" if provider["status"] == "PASS" and semantic["status"] == "PASS" else "FAIL",
        "model": model, "provider_tool_api": provider, "semantic_tool_quality": semantic,
        "thinking": bool(thinking), "tools_executed": False, "content_logged": False,
    }


def all_model_capabilities(config, *, thinking: bool = False) -> dict[str, object]:
    rows = [capability_report(config, spec.tag, thinking=thinking) for spec in MODEL_ROSTER]
    return {
        "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "DEGRADED",
        "thinking": bool(thinking), "models": rows,
        "tools_executed": False, "content_logged": False, "physical_acceptance": False,
    }


def benchmark(config, model: str, iterations: int = 3, *, thinking: bool = False) -> dict[str, object]:
    admitted_model(model)
    if not 1 <= iterations <= 5:
        raise ValueError("iterations must be between 1 and 5")
    samples: list[dict[str, int]] = []
    resources_before = _resource_snapshot()
    client = _client(config, model, timeout=90)
    stop = threading.Event()
    try:
        for _ in range(iterations):
            started = time.monotonic_ns()
            response = client.chat_message(
                [{"role": "user", "content": "Reply with the single word ready."}],
                stop,
                think=thinking,
                keep_alive=0,
            )
            row = {"wall_ns": time.monotonic_ns() - started}
            for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
                value = response.get(key)
                if isinstance(value, int) and value >= 0:
                    row[key] = value
            samples.append(row)
    finally:
        client.close()
    wall = [row["wall_ns"] for row in samples]
    return {
        "status": "PASS",
        "model": model,
        "iterations": iterations,
        "wall_ns": {"min": min(wall), "median": int(statistics.median(wall)), "max": max(wall)},
        "samples": samples,
        "thinking": bool(thinking),
        "keep_alive": 0,
        "content_logged": False,
        "resources_before": resources_before,
        "resources_after": _resource_snapshot(),
        "physical_acceptance": False,
    }


def _ready_model(path: Path, model: str) -> bool:
    value = _bounded_json(path, 8192)
    return bool(value and value.get("status") == "READY" and value.get("code") == "VOICE_RUNTIME_READY" and value.get("model") == model)


def _restart_and_wait(model: str, *, ready_file: Path = READY_FILE, timeout_seconds: int = 120) -> None:
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "restart", "gonken-agent.service"],
            check=False, capture_output=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ModelAdminError("MODEL_SWITCH_RESTART_FAILED", type(exc).__name__) from exc
    if result.returncode != 0:
        raise ModelAdminError("MODEL_SWITCH_RESTART_FAILED", "voice service restart failed")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _ready_model(ready_file, model):
            return
        time.sleep(1)
    raise ModelAdminError("MODEL_SWITCH_NOT_READY", "voice service did not publish READY for selected model")


def switch(config, model: str, *, selection_path: Path = DEFAULT_SELECTION_PATH, ready_file: Path = READY_FILE) -> dict[str, object]:
    if os.geteuid() != 0:
        raise ModelAdminError("MODEL_SWITCH_ROOT_REQUIRED", "model switching requires root")
    admitted_model(model)
    state = selection_status(config.llm.model, path=selection_path)
    if not state.get("governed_roster_active"):
        raise ModelAdminError("MODEL_ROSTER_NOT_COMMISSIONED", "three-model roster must be commissioned before switching")
    previous = str(state["model"])
    if previous == model:
        return {"status": "READY", "model": model, "previous_model": previous, "changed": False}
    smoke = capability_smoke(config, model)
    if smoke["status"] != "PASS":
        raise ModelAdminError("MODEL_TOOL_CAPABILITY_FAILED", "selected model failed the typed tool capability smoke")
    write_selection(model, path=selection_path, previous_model=previous)
    try:
        _restart_and_wait(model, ready_file=ready_file)
    except ModelAdminError as exc:
        # Roll selection back before retrying the prior known-good voice model.
        write_selection(previous, path=selection_path, previous_model=model)
        try:
            _restart_and_wait(previous, ready_file=ready_file)
        except ModelAdminError as rollback_exc:
            raise ModelAdminError("MODEL_SWITCH_AND_ROLLBACK_FAILED", f"{exc.code}; rollback={rollback_exc.code}") from rollback_exc
        raise
    return {
        "status": "READY",
        "model": model,
        "previous_model": previous,
        "changed": True,
        "generation": selection_status(config.llm.model, path=selection_path).get("generation"),
        "tool_capability": smoke,
    }


def manifest() -> list[dict[str, object]]:
    return roster_manifest()
