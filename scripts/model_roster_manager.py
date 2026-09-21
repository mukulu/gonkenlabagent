#!/usr/bin/env python3
"""Provision and validate the V04 three-model Ollama roster.

Online mode uses Ollama's resumable pull API. Offline mode performs no network
activity and accepts only models already present in the local Ollama store.
Every smoke unloads its model (`keep_alive=0`) so validation never attempts to
keep all three resident on a 4GB Pi.
"""
from __future__ import annotations

import argparse
import hashlib
import uuid
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
if (SCRIPT_DIR / "model_catalog.py").is_file():
    from model_catalog import DEFAULT_MODEL, roster_manifest
else:
    from gonken_agent.llm.models import DEFAULT_MODEL, roster_manifest
if (SCRIPT_DIR / "model_qualification.py").is_file():
    from model_qualification import RECORD_FORMAT, qualified_rows
else:
    from gonken_agent.llm.qualification import RECORD_FORMAT, qualified_rows

FORMAT = "gonken-ollama-model-roster-v1"
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
    if data["default_model"] != DEFAULT_MODEL or data["models"] != roster_manifest():
        _fail("MODEL_ROSTER_CATALOG_DRIFT", "packaging manifest differs from canonical runtime catalog", 65)
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
    if (not isinstance(function, dict) or function.get("name") != "readiness_probe"
            or function.get("arguments") != {} or payload.get("done") is not True
            or payload.get("model") != model):
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


def _roster_fingerprint(roster: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(roster), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _record_error(exc: Exception) -> dict[str, object]:
    # Messages can contain arbitrary server text. Preserve codes and already
    # allowlisted structured diagnostics only, never exception strings.
    return {"code": getattr(exc, "code", type(exc).__name__),
            "diagnostics": getattr(exc, "diagnostics", {}), "content_logged": False}


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
        _fail("MODEL_ROSTER_RECORD", "current qualification record is missing or failed; rerun provisioning", 1)
    if record.get("roster_sha256") != _roster_fingerprint(roster):
        _fail("MODEL_ROSTER_RECORD_STALE", "qualification belongs to another roster", 1)
    qualified = qualified_rows(record, models)
    if any(item["tag"] not in qualified for item in observed):
        _fail("MODEL_ROSTER_RECORD_STALE", "model bytes lack completed matching qualification", 1)
    if not qualified.get(roster["default_model"], {}).get("tools"):
        _fail("MODEL_DEFAULT_TOOL_SMOKE", "default model has no passing tool qualification", 1)
    if not qualified.get(selection["model"], {}).get("tools"):
        _fail("MODEL_SELECTED_TOOL_SMOKE", "selected model has no passing tool qualification", 1)
    return {"status": "READY", "models": observed, "selection": selection, "record": record}


def provision(root: Path, roster: Mapping[str, Any], endpoint: str, context_tokens: int, mode: str) -> dict[str, Any]:
    if mode not in {"online", "preseeded-offline"}:
        _fail("MODEL_ROSTER_MODE", "invalid provisioning mode", 64)
    previous = _read_json(_record_path(root))
    record: dict[str, Any] = {
        "format": RECORD_FORMAT, "status": "QUALIFYING", "attempt_id": uuid.uuid4().hex,
        "started_epoch": int(time.time()), "roster_sha256": _roster_fingerprint(roster),
        "provision_mode": mode, "default_model": roster["default_model"],
        "context_tokens": context_tokens, "max_loaded_models": 1, "num_parallel": 1,
        "models": [], "stages": [], "current_failure": None, "optional_failures": [],
        "previous_attempt_status": ("INTERRUPTED" if previous and previous.get("status") == "QUALIFYING" else previous.get("status") if previous else None),
        "physical_acceptance_claimed": False, "content_logged": False,
    }
    def persist():
        _atomic_json(_record_path(root), record, 0o644)
    def stage(owner: dict, name: str, action, *, optional_tool: bool = False):
        event = {"stage": name, "status": "RUNNING", "started_epoch": int(time.time())}
        owner.setdefault("stages", []).append(event)
        record["current_stage"] = {"model": owner.get("tag"), "stage": name}
        persist()
        start = time.monotonic_ns()
        print(f"[MODEL] model={owner.get('tag', '-')} stage={name}", flush=True)
        try:
            value = action()
        except (om.OllamaError, RosterError, OSError, ValueError) as exc:
            event.update(status="FAIL", wall_ns=time.monotonic_ns()-start, error=_record_error(exc))
            # A tool-only server rejection for an alternate is an observed
            # capability failure, not proof that the default or fan is unusable.
            # Transport/auth/identity/inference/residency failures remain fatal.
            diagnostics = getattr(exc, "diagnostics", {})
            if (optional_tool and name == "TOOLS" and isinstance(exc, om.OllamaError)
                    and exc.code == "OLLAMA_API_HTTP" and isinstance(diagnostics, dict)
                    and diagnostics.get("http_status") in {400, 422, 500}):
                incident = {"model": owner.get("tag"), "stage": name, **_record_error(exc)}
                record["optional_failures"].append(incident)
                owner["tool_failure"] = incident
                persist()
                print(f"[DEGRADED] code=MODEL_ALTERNATE_TOOL_INCOMPATIBLE model={owner.get('tag')} stage=TOOLS", flush=True)
                return {"status": "FAILED", "total_ns": 0}
            if record["current_failure"] is None:
                record["current_failure"] = {"model": owner.get("tag"), "stage": name, **_record_error(exc)}
            record["status"] = "FAIL"
            persist()
            raise
        event.update(status="PASS", wall_ns=time.monotonic_ns()-start)
        persist()
        return value
    persist()  # invalidate any prior READY before the first new attempt
    model_store = _mapped(root, "/var/lib/ollama/models")
    model_store.mkdir(parents=True, exist_ok=True)
    models = stage(record, "INVENTORY", lambda: _tags(endpoint))
    missing = [spec for spec in roster["models"] if _model_item(models, spec) is None]
    required = sum(int(spec["display_size_mib"]) for spec in missing) * 1024 * 1024 + 512 * 1024 * 1024
    def prerequisites():
        if missing and shutil.disk_usage(model_store).free < required and root == Path("/"):
            _fail("MODEL_ROSTER_SPACE", "insufficient free model storage", 78)
        if missing and mode == "preseeded-offline":
            _fail("MODEL_ROSTER_OFFLINE_MISSING", "preseeded-offline mode requires every roster model already present", 78)
    stage(record, "PREREQUISITES", prerequisites)
    pull_bytes: dict[str, int] = {}
    for spec in missing:
        pull_bytes[str(spec["tag"])] = stage(record, "PULL:" + str(spec["tag"]), lambda spec=spec: om.pull_model(endpoint, str(spec["tag"])))
    models = stage(record, "INVENTORY_AFTER_PULL", lambda: _tags(endpoint))
    initial_selection = _selection(root)
    required_models = {str(roster["default_model"])}
    if initial_selection and initial_selection.get("model") in {s["tag"] for s in roster["models"]}:
        required_models.add(str(initial_selection["model"]))
    for spec in roster["models"]:
        row: dict[str, Any] = {"tag": spec["tag"], "digest_prefix": spec["digest_prefix"],
            "quantization": spec["quantization"], "role": spec["role"],
            "catalog_tools": bool(spec["tools"]), "catalog_thinking": bool(spec["thinking"]),
            "tool_call_smoke": "NOT_TESTED", "inference_status": "NOT_TESTED",
            "pull_total_bytes": int(pull_bytes.get(str(spec["tag"]), 0)), "stages": []}
        record["models"].append(row); persist()
        problem = None
        try:
            def identity():
                item = _model_item(models, spec)
                if item is None:
                    _fail("MODEL_ROSTER_MISSING", "model absent after provisioning", 69)
                return item
            item = stage(row, "IDENTITY", identity)
            row["digest"] = item["digest"]
            inference = stage(row, "INFERENCE", lambda: om.smoke_model(endpoint, str(spec["tag"]), context_tokens))
            row.update(inference_status="PASS", inference_total_ns=int(inference.get("total_ns", 0)))
            persist()
            capability = stage(row, "TOOLS", lambda: _tool_smoke(endpoint, str(spec["tag"]), context_tokens),
                               optional_tool=spec["tag"] not in required_models)
            row.update(tool_call_smoke=capability["status"], tool_total_ns=int(capability.get("total_ns", 0)))
            row["capability_status"] = "READY" if capability["status"] == "PASS" else "TOOL_INCOMPATIBLE"
            if capability["status"] != "PASS":
                row["stages"][-1]["status"] = "FAIL"
                if spec["tag"] not in required_models and "tool_failure" not in row:
                    incident = {"model": row["tag"], "stage": "TOOLS",
                                "code": "MODEL_TOOL_RESULT_INVALID", "content_logged": False}
                    row["tool_failure"] = incident
                    record["optional_failures"].append(incident)
                    print(f"[DEGRADED] code=MODEL_ALTERNATE_TOOL_INCOMPATIBLE model={row['tag']} stage=TOOLS", flush=True)
            persist()
        except (om.OllamaError, RosterError, OSError, ValueError) as exc:
            problem = exc
        finally:
            def unload():
                result = om._api(endpoint, "/api/chat", {"model": str(spec["tag"]), "messages": [], "stream": False, "keep_alive": 0})
                if not isinstance(result, dict) or result.get("done") is not True:
                    _fail("MODEL_UNLOAD_UNCONFIRMED", "unload transaction did not finish", 69)
                loaded = om._api(endpoint, "/api/ps")
                if not isinstance(loaded, dict) or not isinstance(loaded.get("models"), list) or loaded["models"]:
                    _fail("MODEL_UNLOAD_UNCONFIRMED", "model still resident or loaded-model inventory unavailable", 69)
            try:
                stage(row, "UNLOAD", unload)
            except (om.OllamaError, RosterError, OSError, ValueError) as exc:
                if problem is None: problem = exc
        if problem is not None:
            if record["current_failure"] is None:
                record["status"] = "FAIL"; record["current_failure"] = {"model": row["tag"], **_record_error(problem)}; persist()
            raise problem
    default = str(roster["default_model"])
    selection = _selection(root)
    admitted = {str(item["tag"]) for item in roster["models"]}
    selected_tag = str(selection["model"]) if selection and selection.get("model") in admitted else default
    def admission():
        for tag, code in ((default, "MODEL_DEFAULT_TOOL_SMOKE"), (selected_tag, "MODEL_SELECTED_TOOL_SMOKE")):
            row = next(r for r in record["models"] if r["tag"] == tag)
            if row["tool_call_smoke"] != "PASS":
                _fail(code, "required model failed typed tool capability smoke", 69)
    stage(record, "ADMISSION", admission)
    if not selection or selection.get("model") not in admitted:
        previous_model = str(selection["model"]) if selection else "qwen3.5:2b-q4_K_M"
        selection = _write_selection(root, default, previous_model)
    record.update(status="READY", validated_epoch=int(time.time()),
                  active_model=selection["model"], selection_generation=selection["generation"],
                  current_stage=None, legacy_model_retained=True,
                  roster_capabilities_status="READY" if all(r["tool_call_smoke"] == "PASS" for r in record["models"]) else "DEGRADED")
    persist()
    print(f"[OK] code=MODEL_ROSTER_READY models={len(record['models'])} default={default} active={selection['model']} mode={mode}")
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
            print(json.dumps({"status": "READY", "default_model": roster["default_model"], "selection": value["selection"], "roster_capabilities_status": value["record"].get("roster_capabilities_status", "UNKNOWN"), "optional_failures": value["record"].get("optional_failures", [])}, sort_keys=True))
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
