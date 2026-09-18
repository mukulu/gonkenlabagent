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


def status(config) -> dict[str, object]:
    selection = selection_status(config.llm.model)
    record = _bounded_json(ROSTER_RECORD_PATH)
    inventory: list[dict[str, object]] = []
    inventory_error = None
    try:
        inventory = _inventory(config)
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
        "status": "READY" if selection.get("governed_roster_active") and all(row["installed"] for row in roster_rows) else "DEGRADED",
        "selection": selection,
        "roster": roster_rows,
        "policy": {"max_loaded_models": 1, "num_parallel": 1, "thinking_default": False},
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


def benchmark(config, model: str, iterations: int = 3) -> dict[str, object]:
    admitted_model(model)
    if not 1 <= iterations <= 5:
        raise ValueError("iterations must be between 1 and 5")
    samples: list[dict[str, int]] = []
    client = _client(config, model, timeout=90)
    stop = threading.Event()
    try:
        for _ in range(iterations):
            started = time.monotonic_ns()
            response = client.chat_message(
                [{"role": "user", "content": "Reply with the single word ready."}],
                stop,
                think=False,
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
        "thinking": False,
        "keep_alive": 0,
        "content_logged": False,
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
