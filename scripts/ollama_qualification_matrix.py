#!/usr/bin/env python3
"""One bounded, content-free Ollama experiment; never changes production pins.

Run only during an explicitly confirmed maintenance window. Each invocation uses
one admitted model and one request shape. Results are evidence, not a model
admission record. The command never runs a returned tool or changes selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_roster_manager as roster
import ollama_manager as om
from gonken_agent.llm.errors import request_shape
from gonken_agent.llm.models import admitted_model, roster_tags

CASES = ("plain", "json", "schema", "tools", "schema-tools")
SCHEMA = {"type": "object", "properties": {"ready": {"type": "boolean"}}, "required": ["ready"], "additionalProperties": False}
TOOL = {"type": "function", "function": {"name": "readiness_probe", "description": "Report test readiness; never operates hardware.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}


def case_payload(model: str, case: str, context_tokens: int, output_tokens: int, thinking: bool = False) -> dict:
    admitted_model(model)
    if case not in CASES or type(context_tokens) is not int or not 256 <= context_tokens <= 32768 or type(output_tokens) is not int or not 1 <= output_tokens <= min(1024, context_tokens) or type(thinking) is not bool:
        raise ValueError("invalid governed experiment settings")
    tools = case in {"tools", "schema-tools"}
    prompt = "Call the readiness_probe tool with no arguments." if tools else 'Reply with the JSON object {"ready":true}.'
    value = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": thinking, "keep_alive": 0,
             "options": {"temperature": 0, "seed": 0, "num_ctx": context_tokens, "num_predict": output_tokens}}
    if case == "json": value["format"] = "json"
    if case in {"schema", "schema-tools"}: value["format"] = SCHEMA
    if tools: value["tools"] = [TOOL]
    return value


def response_summary(response: object, case: str, model: str) -> dict:
    if not isinstance(response, dict): return {"status": "FAIL", "code": "EXPERIMENT_NON_OBJECT"}
    message = response.get("message")
    message = message if isinstance(message, dict) else {}
    text = message.get("content")
    common = {"done": response.get("done") is True, "model_matches": response.get("model") == model,
              "content_bytes": len(text.encode("utf-8")) if isinstance(text, str) else 0,
              "thinking_present": bool(message.get("thinking")), "content_retained": False}
    valid = common["done"] and common["model_matches"]
    if case in {"tools", "schema-tools"}:
        calls = message.get("tool_calls")
        function = calls[0].get("function") if isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], dict) else None
        valid = valid and isinstance(function, dict) and function.get("name") == "readiness_probe" and function.get("arguments") == {}
    elif case in {"json", "schema"}:
        try: content = json.loads(text) if isinstance(text, str) else None
        except (ValueError, TypeError): content = None
        valid = valid and isinstance(content, dict) and set(content) == {"ready"} and content["ready"] is True
    else:
        valid = valid and isinstance(text, str) and bool(text.strip())
    common.update({"status": "PASS" if valid else "FAIL", "code": "EXPERIMENT_RESPONSE_VALID" if valid else "EXPERIMENT_RESPONSE_INVALID"})
    for key in ("total_duration", "load_duration", "eval_count", "eval_duration", "prompt_eval_count"):
        value = response.get(key)
        if type(value) is int and value >= 0: common[key] = value
    return common


def experiment(endpoint: str, model: str, case: str, context_tokens: int, output_tokens: int,
               output: Path, *, maintenance_confirmed: bool, timeout: float = 60, thinking: bool = False, api=None) -> dict:
    if not maintenance_confirmed:
        raise ValueError("explicit maintenance confirmation required; stop the voice service first")
    if isinstance(timeout, bool) or not 1 <= timeout <= 120: raise ValueError("timeout must be 1..120 seconds")
    endpoint = om.validate_endpoint(endpoint)
    request = case_payload(model, case, context_tokens, output_tokens, thinking)
    output = Path(output)
    if not output.is_absolute() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError("output must be an absolute non-symlink path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
    record = {"format": "gonken-ollama-experiment-v1", "attempt_id": str(uuid.uuid4()), "status": "STARTING",
              "experiment_only": True, "physical_acceptance_claimed": False, "production_pins_changed": False,
              "tool_execution": False, "request": request_shape("/api/chat", request), "case": case,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "stages": []}
    api = api or om._api
    def save(): roster._atomic_json(output, record)
    def step(name, call):
        row = {"stage": name, "status": "RUNNING"}; record["stages"].append(row); save()
        start = time.monotonic()
        try:
            value = call()
            row["status"] = "PASS"
            return value
        except Exception as exc:
            row.update({"status": "FAIL", "error": roster._record_error(exc)})
            raise
        finally:
            row["elapsed_ms"] = round((time.monotonic() - start) * 1000); save()
    attempted = False
    try:
        version = step("VERSION", lambda: api(endpoint, "/api/version", timeout=min(5, timeout)))
        # Version is bounded metadata, never arbitrary server content.
        import re
        value = version.get("version") if isinstance(version, dict) else None
        record["runtime_version"] = value if isinstance(value, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]{1,32})?", value) else "UNKNOWN"
        models = step("INVENTORY", lambda: api(endpoint, "/api/tags", timeout=min(5, timeout)))
        spec = admitted_model(model)
        item = roster._model_item(models.get("models", []), {"tag": model, "digest_prefix": spec.digest_prefix, "quantization": spec.quantization})
        if item is None: raise ValueError("admitted model is not installed")
        record["model_digest"] = item["digest"]
        loaded = step("IDLE", lambda: api(endpoint, "/api/ps", timeout=min(5, timeout)))
        if not isinstance(loaded, dict) or loaded.get("models") != []:
            raise ValueError("Ollama has a resident model; do not interfere with an active appliance")
        attempted = True
        response = step("REQUEST", lambda: api(endpoint, "/api/chat", request, timeout=timeout))
        record["response"] = response_summary(response, case, model)
        record["status"] = record["response"]["status"]
    except Exception as exc:
        record.update({"status": "FAIL", "failure": roster._record_error(exc)})
    finally:
        if attempted:
            try:
                step("UNLOAD", lambda: api(endpoint, "/api/chat", {"model": model, "messages": [], "keep_alive": 0, "stream": False}, timeout=min(10, timeout)))
                loaded = step("UNLOAD_CONFIRM", lambda: api(endpoint, "/api/ps", timeout=min(5, timeout)))
                if not isinstance(loaded, dict) or loaded.get("models") != []: raise ValueError("unload not confirmed")
            except Exception as exc:
                record["cleanup_failure"] = roster._record_error(exc); record["status"] = "FAIL"
        record["finished_epoch"] = int(time.time()); save()
    return record


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, choices=roster_tags()); p.add_argument("--case", required=True, choices=CASES)
    p.add_argument("--endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--context", type=int, default=2048); p.add_argument("--output-tokens", type=int, default=128)
    p.add_argument("--timeout", type=float, default=60); p.add_argument("--thinking", action="store_true")
    p.add_argument("--output", type=Path, required=True); p.add_argument("--maintenance-confirmed", action="store_true")
    args=p.parse_args(argv)
    try:
        result=experiment(args.endpoint,args.model,args.case,args.context,args.output_tokens,args.output,
                          maintenance_confirmed=args.maintenance_confirmed,timeout=args.timeout,thinking=args.thinking)
    except (OSError, ValueError, om.OllamaError) as exc:
        print(f"[ERROR] code=EXPERIMENT_INPUT type={type(exc).__name__}",file=sys.stderr); return 64
    print(f"[EXPERIMENT] status={result['status']} case={args.case} output={args.output} physical_acceptance=false")
    return 0 if result["status"] == "PASS" else 75

if __name__ == "__main__": raise SystemExit(main())
