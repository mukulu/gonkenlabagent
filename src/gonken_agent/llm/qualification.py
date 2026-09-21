"""Pure qualification evidence checks. Inventory presence is not capability proof."""
from __future__ import annotations
from collections.abc import Mapping

RECORD_FORMAT = 'gonken-ollama-roster-record-v2'

def qualified_rows(record: object, inventory: list[dict], *, context_tokens: int | None = None) -> dict[str, dict]:
    if not isinstance(record, Mapping) or record.get('format') != RECORD_FORMAT or record.get('status') != 'READY':
        return {}
    if context_tokens is not None and record.get('context_tokens') != context_tokens:
        return {}
    rows = record.get('models')
    if not isinstance(rows, list): return {}
    installed = {}
    for item in inventory:
        if not isinstance(item, Mapping) or not isinstance(item.get('name'), str): return {}
        if item['name'] in installed: return {}
        installed[item['name']] = item.get('digest')
    result = {}
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get('tag'), str): return {}
        tag = row['tag']
        if tag in seen: return {}
        seen.add(tag)
        if not isinstance(row.get('stages'), list): continue
        stages = {}
        for v in row['stages']:
            if not isinstance(v, Mapping) or not isinstance(v.get('stage'), str) or v['stage'] in stages: return {}
            stages[v['stage']] = v.get('status')
        digest = row.get('digest')
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(c not in '0123456789abcdef' for c in digest) or
                installed.get(tag) != digest or row.get('inference_status') != 'PASS' or
                any(stages.get(s) != 'PASS' for s in ('IDENTITY', 'INFERENCE', 'UNLOAD'))):
            continue
        result[tag] = {'inference': True, 'tools': row.get('tool_call_smoke') == 'PASS' and stages.get('TOOLS') == 'PASS', 'digest': digest}
    return result


def required_tools_ready(qualified: Mapping, required_models: tuple[str, ...]) -> bool:
    """A capability policy predicate, not inventory/execution/physical evidence."""
    return bool(required_models) and all(
        isinstance(qualified.get(tag), Mapping) and qualified[tag].get('tools') is True
        for tag in required_models
    )
