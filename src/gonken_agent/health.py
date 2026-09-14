"""Content-free component health and fixed readiness exit codes."""
from dataclasses import dataclass
from enum import StrEnum


class Readiness(StrEnum):
    READY = 'READY'
    DEGRADED = 'DEGRADED'
    FAILED = 'FAILED'
    MAINTENANCE = 'MAINTENANCE'


EXIT_CODES = {Readiness.READY: 0, Readiness.DEGRADED: 2,
              Readiness.FAILED: 1, Readiness.MAINTENANCE: 2}
COMPONENTS = frozenset({'config', 'filesystem', 'ollama', 'model', 'whisper',
                        'piper', 'input_audio', 'output_audio', 'gpio', 'index',
                        'dashboard', 'privacy', 'service', 'environment'})


@dataclass(frozen=True)
class ComponentHealth:
    component: str
    status: Readiness
    code: str

    def __post_init__(self):
        if self.component not in COMPONENTS or not isinstance(self.status, Readiness):
            raise ValueError('unknown health component/status')
        if not self.code or len(self.code) > 64 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in self.code):
            raise ValueError('health code must be a content-free constant')


def summary(components):
    rows = list(components)
    if len({r.component for r in rows}) != len(rows):
        raise ValueError('duplicate health component')
    states = {r.status for r in rows}
    overall = next((s for s in (Readiness.FAILED, Readiness.MAINTENANCE, Readiness.DEGRADED) if s in states), Readiness.READY)
    if not rows:
        overall = Readiness.DEGRADED
    return {'status': overall.value, 'exit_code': EXIT_CODES[overall],
            'components': [{'component': r.component, 'status': r.status.value, 'code': r.code} for r in sorted(rows, key=lambda r: r.component)]}
