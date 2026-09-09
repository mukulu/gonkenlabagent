"""Single-owner runtime transition contract."""
from enum import StrEnum


class State(StrEnum):
    BOOTING = 'BOOTING'
    WAITING = 'WAITING_DEPENDENCIES'
    IDLE = 'IDLE'
    RECORDING = 'RECORDING'
    TRANSCRIBING = 'TRANSCRIBING'
    RETRIEVING = 'RETRIEVING'
    GENERATING = 'GENERATING'
    SPEAKING = 'SPEAKING'
    DEGRADED = 'DEGRADED'
    STOPPING = 'STOPPING'


TRANSITIONS = {
    State.BOOTING: {State.WAITING, State.STOPPING},
    State.WAITING: {State.IDLE, State.DEGRADED, State.STOPPING},
    State.IDLE: {State.RECORDING, State.RETRIEVING, State.DEGRADED, State.STOPPING},
    State.RECORDING: {State.TRANSCRIBING, State.DEGRADED, State.STOPPING},
    State.TRANSCRIBING: {State.RETRIEVING, State.DEGRADED, State.STOPPING},
    State.RETRIEVING: {State.GENERATING, State.DEGRADED, State.STOPPING},
    State.GENERATING: {State.SPEAKING, State.IDLE, State.DEGRADED, State.STOPPING},
    State.SPEAKING: {State.IDLE, State.DEGRADED, State.STOPPING},
    State.DEGRADED: {State.WAITING, State.STOPPING},
    State.STOPPING: set(),
}


class StateMachine:
    def __init__(self):
        self.state = State.BOOTING

    def transition(self, target):
        if target not in TRANSITIONS[self.state]:
            raise ValueError(f'invalid transition {self.state} -> {target}')
        self.state = target
