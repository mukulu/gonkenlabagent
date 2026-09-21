"""Content-free Ollama error metadata shared by installer and runtime.

Bodies may contain echoed prompts or credentials. Never retain a server's raw
message, hash of that message, or request messages. Only bounded allowlisted
classifications and request-shape facts may leave this function.
"""
from __future__ import annotations
import json
import re
from typing import Mapping

BODY_LIMIT = 8192
PATHS = {'/api/chat', '/api/tags', '/api/version', '/api/ps', '/api/pull'}

def request_shape(path: str, payload: Mapping | None) -> dict[str, object]:
    data = payload if isinstance(payload, Mapping) else {}
    model = data.get('model')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}', model):
        model = None
    options = data.get('options') if isinstance(data.get('options'), Mapping) else {}
    fmt = data.get('format')
    return {
        'api_path': path if path in PATHS else 'OTHER',
        'model': model,
        'format_kind': 'schema' if isinstance(fmt, Mapping) else 'json' if fmt == 'json' else 'none' if fmt is None else 'invalid',
        'tool_count': min(len(data['tools']), 32) if isinstance(data.get('tools'), list) else 0,
        'think': data.get('think') if type(data.get('think')) is bool else None,
        'context_tokens': options.get('num_ctx') if type(options.get('num_ctx')) is int else None,
        'output_tokens': options.get('num_predict') if type(options.get('num_predict')) is int else None,
        'content_logged': False,
    }

def http_metadata(status: int, path: str, payload: Mapping | None, body: bytes) -> dict[str, object]:
    truncated = len(body) > BODY_LIMIT
    bounded = body[:BODY_LIMIT]
    kind, message = 'NON_JSON', None
    try:
        value = json.loads(bounded)
        if isinstance(value, dict):
            kind = 'JSON_OBJECT'
            if isinstance(value.get('error'), str): message = value['error']
        else: kind = 'JSON_OTHER'
    except (ValueError, UnicodeError):
        pass
    category = 'UNCLASSIFIED'
    if message:
        lowered = message.casefold()
        # Classes are diagnostic hints, never confirmed root-cause claims.
        for code, pattern in (
            ('OUT_OF_MEMORY', r'out of memory|not enough (?:system )?memory|unable to allocate'),
            ('FORMAT_OR_SCHEMA', r'(?:invalid|unsupported).{0,24}(?:schema|format|grammar)'),
            ('MODEL_UNAVAILABLE', r'model.{0,30}(?:not found|does not exist)'),
            ('UNSUPPORTED_CAPABILITY', r'does not support|not supported|unsupported'),
            ('RUNNER_FAILURE', r'runner.{0,24}(?:exited|failed|terminated)'),
            ('EOF', r'\beof\b'),
        ):
            if re.search(pattern, lowered): category = code; break
    return {**request_shape(path, payload), 'http_status': int(status),
            'body_kind': kind, 'body_bytes_examined': len(bounded),
            'body_truncated': truncated, 'error_message_present': message is not None,
            'server_error_class': category, 'root_cause_confirmed': False}
