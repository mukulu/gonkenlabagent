#!/usr/bin/env python3
"""Provision and validate the V04 three-model Ollama roster.

Online mode uses Ollama's resumable pull API. Offline mode performs no network
activity and accepts only models already present in the local Ollama store.
Every smoke unloads its model (`keep_alive=0`) so validation never attempts to
keep all three resident on a 4GB Pi.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import ollama_manager as om  # noqa: E402

FORMAT = "gonken-ollama-model-roster-v1"
RECORD_FORMAT = "gonken-ollama-roster-record-v1"
SELECTION_FORMAT = "gonken-active-model-v1"
REQUIRED_MODEL_FIELDS = {
    "tag", "digest_prefix", "quantization", "parameter_size", "display_size_mib",
    "license", "source", "tools", "thinking", "role",
}


class RosterError(RuntimeError):
    def __init__(self, code: str, message: str, exit_code: int = 75):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def _fail(code: str, message: str, exit_code: int = 75):
    raise RosterError(code, message, exit_code)


def _mapped(root: Path, absolute: str) -> Path:
    return Path(absolute) if root == Path("/") else root / absolute.lstrip("/")


def read_roster(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        _fail("MODEL_ROSTER_MANIFEST", f"cannot read roster manifest: {type(exc).__name__}", 66)
    if not isinstance(data, dict) or set(data) != {"format", "default_model", "verified_at", "models"}:
        _fail("MODEL_ROSTER_MANIFEST", "roster manifest has unexpected fields", 65)
    if data.get("format") != FORMAT or not isinstance(data.get("models"), list) or len(data["models"]) != 3:
        _fail("MODEL_ROSTER_MANIFEST", "roster manifest schema is invalid", 65)
    tags = set()
    for item in data["models"]:
        if not isinstance(item, dict) or set(item) != REQUIRED_MODEL_FIELDS:
            _fail("MODEL_ROSTER_MANIFEST", "model entry schema is invalid", 65)
        tag = item.get("tag")
        if not isinstance(tag, str) or tag in tags or len(tag) > 96:
            _fail("MODEL_ROSTER_MANIFEST", "model tag is invalid or duplicated", 65)
        tags.add(tag)
        prefix = item.get("digest_prefix")
        if not isinstance(prefix, str) or len(prefix) != 12 or any(c not in "0123456789abcdef" for c in prefix):
            _fail("MODEL_ROSTER_MANIFEST", "digest prefix is invalid", 65)
        if item.get("quantization") not in {"Q4_K_M", "Q8_0"}:
            _fail("MODEL_ROSTER_MANIFEST", "quantization is not admitted", 65)
        if not isinstance(item.get("display_size_mib"), int) or not 128 <= item["display_size_mib"] <= 4096:
            _fail("MODEL_ROSTER_MANIFEST", "display size is invalid", 65)
        source = item.get("source")
        if not isinstance(source, str) or not source.startswith("https://ollama.com/library/"):
            _fail("MODEL_ROSTER_MANIFEST", "model source must be official Ollama catalog", 65)
        if item.get("tools") is not True or item.get("thinking") is not True:
            _fail("MODEL_ROSTER_MANIFEST", "V04 roster entry must declare tools and thinking support", 65)
    if data.get("default_model") not in tags:
        _fail("MODEL_ROSTER_MANIFEST", "default model is outside roster", 65)
    return data


def _tags(endpoint: str) -> list[dict[str, Any]]:
    payload = om._api(endpoint, "/api/tags")
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        _fail("MODEL_ROSTER_API", "Ollama tag list is malformed", 69)
    return [item for item in models if isinstance(item, dict)]


def _model_item(models: list[dict[str, Any]], spec: Mapping[str, Any]) -> dict[str, Any] | None:
    matches = [item for item in models if item.get("name") == spec["tag"]]
    if not matches:
        return None
    if len(matches) != 1:
        _fail("MODEL_ROSTER_DUPLICATE", f"duplicate local tag {spec['tag']}")
    item = matches[0]
    digest = item.get("digest")
    details = item.get("details")
    if not isinstance(digest, str) or len(digest) != 64 or not digest.startswith(str(spec["digest_prefix"])):
        _fail("MODEL_ROSTER_DIGEST", f"digest drift for {spec['tag']}")
    if not isinstance(details, dict) or details.get("quantization_level") != spec["quantization"]:
        _fail("MODEL_ROSTER_QUANTIZATION", f"quantization drift for {spec['tag']}")
    return item


def _tool_smoke(endpoint: str, model: str, context_tokens: int) -> dict[str, int | str]:
    payload = om._api(endpoint, "/api/chat", {
        "model": model,
        "messages": [{"role": "user", "content": "Use the provided readiness tool now."}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "readiness_probe",
                "description": "Return deterministic readiness metadata.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        }],
        "stream": False,
        "think": False,
        "keep_alive": 0,
        "options": {"temperature": 0, "num_ctx": context_tokens, "num_predict": 32, "seed": 0},
    })
    message = payload.get("message") if isinstance(payload, dict) else None
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(calls, list) or len(calls) != 1:
        return {"status": "FAILED", "total_ns": int(payload.get("total_duration", 0)) if isinstance(payload, dict) else 0}
    function = calls[0].get("function") if isinstance(calls[0], dict) else None
    if not isinstance(function, dict) or function.get("name") != "readiness_probe":
        return {"status": "FAILED", "total_ns": int(payload.get("total_duration", 0)) if isinstance(payload, dict) else 0}
    return {"status": "PASS", "total_ns": int(payload.get("total_duration", 0))}


def _record_path(root: Path) -> Path:
    return _mapped(root, "/var/lib/gonken-agent/ollama/roster.json")


def _selection_path(root: Path) -> Path:
    return _mapped(root, "/var/lib/gonken-agent/ollama/active-model.json")


def _atomic_json(path: Path, payload: Mapping[str, Any], mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    if path.parent.is_symlink() or path.is_symlink():
        _fail("MODEL_ROSTER_PATH", "roster state path cannot be a symlink")
    fd, name = tempfile.mkstemp(prefix=".gonken-roster.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(dict(payload), stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
        path.chmod(mode)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, max_bytes: int = 65536) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _selection(root: Path) -> dict[str, Any] | None:
    value = _read_json(_selection_path(root), 4096)
    if not value or value.get("format") != SELECTION_FORMAT:
        return None
    return value


def _write_selection(root: Path, model: str, previous: str | None) -> dict[str, Any]:
    current = _selection(root)
    generation = int(current.get("generation", 0)) + 1 if current and isinstance(current.get("generation"), int) else 1
    payload = {"format": SELECTION_FORMAT, "model": model, "generation": generation, "previous_model": previous}
    _atomic_json(_selection_path(root), payload, 0o644)
    return payload


def status(root: Path, roster: Mapping[str, Any], endpoint: str, *, require_default: bool = False) -> dict[str, Any]:
    models = _tags(endpoint)
    observed = []
    for spec in roster["models"]:
        item = _model_item(models, spec)
        if item is None:
            _fail("MODEL_ROSTER_MISSING", f"missing admitted model {spec['tag']}", 1)
        observed.append({"tag": spec["tag"], "digest": item["digest"], "quantization": spec["quantization"]})
    selection = _selection(root)
    admitted = {str(item["tag"]) for item in roster["models"]}
    if not selection or selection.get("model") not in admitted:
        _fail("MODEL_SELECTION_MISSING", "active model selection is missing or invalid", 1)
    if require_default and selection.get("model") != roster["default_model"]:
        _fail("MODEL_SELECTION_DEFAULT", "active model is not the V04 default", 1)
    record = _read_json(_record_path(root))
    if not record or record.get("format") != RECORD_FORMAT or record.get("status") != "READY":
        _fail("MODEL_ROSTER_RECORD", "validated model roster record is missing", 1)
    return {"status": "READY", "models": observed, "selection": selection, "record": record}


def provision(root: Path, roster: Mapping[str, Any], endpoint: str, context_tokens: int, mode: str) -> dict[str, Any]:
    if mode not in {"online", "preseeded-offline"}:
        _fail("MODEL_ROSTER_MODE", "invalid provisioning mode", 64)
    model_store = _mapped(root, "/var/lib/ollama/models")
    state_dir = _record_path(root).parent
    model_store.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    models = _tags(endpoint)
    missing = [spec for spec in roster["models"] if _model_item(models, spec) is None]
    required = sum(int(spec["display_size_mib"]) for spec in missing) * 1024 * 1024 + 512 * 1024 * 1024
    free = shutil.disk_usage(model_store).free
    if missing and free < required and root == Path("/"):
        _fail("MODEL_ROSTER_SPACE", f"insufficient free model storage: need {required} bytes, have {free}", 78)
    if missing and mode == "preseeded-offline":
        _fail("MODEL_ROSTER_OFFLINE_MISSING", "preseeded-offline mode requires every roster model already present", 78)
    pull_bytes: dict[str, int] = {}
    for spec in missing:
        pull_bytes[str(spec["tag"])] = om.pull_model(endpoint, str(spec["tag"]))
    models = _tags(endpoint)
    rows = []
    for spec in roster["models"]:
        item = _model_item(models, spec)
        if item is None:
            _fail("MODEL_ROSTER_MISSING", f"model absent after provisioning: {spec['tag']}", 69)
        inference = om.smoke_model(endpoint, str(spec["tag"]), context_tokens)
        capability = _tool_smoke(endpoint, str(spec["tag"]), context_tokens)
        rows.append({
            "tag": spec["tag"],
            "digest": item["digest"],
            "digest_prefix": spec["digest_prefix"],
            "quantization": spec["quantization"],
            "role": spec["role"],
            "catalog_tools": bool(spec["tools"]),
            "catalog_thinking": bool(spec["thinking"]),
            "tool_call_smoke": capability["status"],
            "inference_total_ns": int(inference.get("total_ns", 0)),
            "tool_total_ns": int(capability.get("total_ns", 0)),
            "pull_total_bytes": int(pull_bytes.get(str(spec["tag"]), 0)),
        })
    default = str(roster["default_model"])
    # A tool-smoke failure does not destroy installation; it marks that model
    # conversation-only until a later target-qualified selection explicitly admits it.
    default_row = next(row for row in rows if row["tag"] == default)
    if default_row["tool_call_smoke"] != "PASS":
        _fail("MODEL_DEFAULT_TOOL_SMOKE", "default model failed typed tool capability smoke", 69)
    selection = _selection(root)
    admitted = {str(item["tag"]) for item in roster["models"]}
    if selection and isinstance(selection.get("model"), str) and str(selection["model"]) in admitted:
        # Preserve an operator-selected admitted model across idempotent installer reruns.
        # Provisioning validates the whole roster; it does not silently reset user choice.
        selected = selection
    else:
        previous = str(selection["model"]) if selection and isinstance(selection.get("model"), str) else "qwen3.5:2b-q4_K_M"
        selected = _write_selection(root, default, previous)
    record = {
        "format": RECORD_FORMAT,
        "status": "READY",
        "validated_epoch": int(time.time()),
        "provision_mode": mode,
        "default_model": default,
        "active_model": selected["model"],
        "max_loaded_models": 1,
        "num_parallel": 1,
        "context_tokens": context_tokens,
        "models": rows,
        "selection_generation": selected["generation"],
        "legacy_model_retained": True,
        "physical_acceptance_claimed": False,
    }
    _atomic_json(_record_path(root), record, 0o644)
    print(f"[OK] code=MODEL_ROSTER_READY models={len(rows)} default={default} active={selected['model']} mode={mode}")
    return record


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("status", "provision"))
    p.add_argument("--manifest", required=True)
    p.add_argument("--endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--context-tokens", type=int, default=2048)
    p.add_argument("--system-root", default="/")
    p.add_argument("--mode", choices=("online", "preseeded-offline"), default="online")
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        root = Path(args.system_root)
        if not root.is_absolute():
            _fail("MODEL_ROSTER_ROOT", "system root must be absolute", 64)
        if root == Path("/") and args.command == "provision" and os.geteuid() != 0:
            _fail("MODEL_ROSTER_PRIVILEGE", "production roster provisioning requires root", 77)
        endpoint = om.validate_endpoint(args.endpoint)
        roster = read_roster(Path(args.manifest))
        if not 512 <= args.context_tokens <= 8192:
            _fail("MODEL_ROSTER_CONTEXT", "context tokens outside bounded Pi budget", 65)
        if args.command == "status":
            value = status(root, roster, endpoint)
            print(json.dumps({"status": "READY", "default_model": roster["default_model"], "selection": value["selection"]}, sort_keys=True))
        else:
            provision(root, roster, endpoint, args.context_tokens, args.mode)
    except RosterError as exc:
        print(f"[ERROR] code={exc.code} message={str(exc).replace(' ', '_')}", file=sys.stderr)
        return exc.exit_code
    except om.OllamaError as exc:
        om.emit_error(exc)
        return exc.exit_code
    except (OSError, ValueError) as exc:
        print(f"[ERROR] code=MODEL_ROSTER_IO message={type(exc).__name__}", file=sys.stderr)
        return 73
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
