"""Bounded, deterministic operational grammar. Text is never an executable plan."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class CommandIntent:
    operation: str
    params: dict[str, Any]

@dataclass(frozen=True)
class CommandClarification:
    message: str

WORDS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(), range(21)))
WORDS.update({'thirty':30, 'forty':40, 'fifty':50, 'sixty':60, 'a':1, 'an':1})
NUMBER = r'(?:[0-9]+(?:\.[0-9]+)?|' + '|'.join(WORDS) + r')'
SPAN = rf'({NUMBER})\s+(seconds?|minutes?|hours?)'
FAN = r'(?:the\s+)?(?:room\s+)?fan'
READING = r'(?:the\s+)?(?:room\s+)?(temperature(?: and humidity)?|humidity|conditions)'


def normalized(text: str) -> str | None:
    if not isinstance(text, str) or len(text) > 4096 or any(ord(c) < 32 and c not in '\n\t\r' for c in text):
        return None
    return ' '.join(text.casefold().split()).removeprefix('please ').rstrip('.?!')


def seconds(value: str, unit: str) -> float:
    number = WORDS[value] if value in WORDS else float(value)
    return float(number) * (3600 if unit.startswith('hour') else 60 if unit.startswith('minute') else 1)


def parse_command(text: str) -> CommandIntent | CommandClarification | None:
    """Only full, direct commands produce intents; ambiguity cannot enter an LLM action path."""
    value = normalized(text)
    if value is None:
        return CommandClarification('That command contains invalid or excessive text.')
    if value in {'cancel timers', 'cancel all timers', 'cancel all schedules', 'stop all timers'}:
        return CommandIntent('automation.cancel', {})
    if value in {'list timers', 'show timers', 'list schedules', 'show schedules', 'what timers are set', 'what are my timers'}:
        return CommandIntent('automation.list', {})
    m = re.fullmatch(r'(?:cancel|stop) (?:timer|schedule) ([0-9a-f]{8})', value)
    if m: return CommandIntent('automation.cancel', {'job_id': m[1]})

    m = re.fullmatch(rf'(?:turn|switch) {FAN} (on|off) (?:in|after) {SPAN}(?: (?:and (?:turn|switch) (?:it|{FAN}) off |)for {SPAN})?', value)
    if m:
        params: dict[str, Any] = {'kind': 'fan_'+m[1], 'delay_seconds': seconds(m[2], m[3])}
        if m[4]:
            if m[1] != 'on': return CommandClarification('Use a duration with fan on, not fan off.')
            params.update(kind='fan_run', duration_seconds=seconds(m[4], m[5]))
        return CommandIntent('automation.add', params)
    m = re.fullmatch(rf'(start|stop) {FAN} (?:in|after) {SPAN}', value)
    if m:
        return CommandIntent('automation.add', {'kind':'fan_on' if m[1]=='start' else 'fan_off', 'delay_seconds': seconds(m[2], m[3])})
    m = re.fullmatch(rf'(?:run {FAN}|(?:turn|switch) {FAN} on) for {SPAN}', value)
    if m: return CommandIntent('automation.add', {'kind':'fan_run', 'duration_seconds':seconds(m[1],m[2])})
    m = re.fullmatch(rf'(?:(?:switch|turn) {FAN} on and off|cycle {FAN}) every {SPAN}(?: for {SPAN})?', value)
    if m:
        params = {'kind':'fan_cycle', 'interval_seconds':seconds(m[1],m[2])}
        if m[3]: params['lease_seconds'] = seconds(m[3],m[4])
        return CommandIntent('automation.add', params)
    m = re.fullmatch(rf'(?:tell me|report|announce) {READING} (in|after|every) {SPAN}(?: for {SPAN})?', value)
    if m:
        kind = {'temperature and humidity':'environment', 'conditions':'environment'}.get(m[1], m[1])
        params = {'kind': kind, ('interval_seconds' if m[2]=='every' else 'delay_seconds'): seconds(m[3],m[4])}
        # First recurring report is due after one interval, not immediately.
        if m[2]=='every': params['delay_seconds'] = seconds(m[3],m[4])
        if m[5]:
            if m[2] != 'every': return CommandClarification('A reporting duration requires an every interval.')
            params['lease_seconds'] = seconds(m[5],m[6])
        return CommandIntent('automation.add', params)
    m = re.fullmatch(rf'(?:tell me|notify me|announce) when (?:the )?(?:room )?temperature (?:rises|increases) by ({NUMBER}) degrees?(?: celsius)?(?: (?:from|above) (?:the )?last (?:mentioned|announced|reported) temperature)?', value)
    if m:
        delta = float(WORDS[m[1]] if m[1] in WORDS else m[1])
        return CommandIntent('automation.add', {'kind':'temperature_delta', 'delta_c':delta})
    # Command-like scheduling input must be clarified/refused, not forwarded to
    # a model which might claim it scheduled something or drop the time qualifier.
    if (re.search(r'\b(timer|timers|schedule|schedules)\b', value)
        or (re.match(r'(?:turn|switch|start|stop|run|cycle|tell me|report|announce|notify me)\b', value)
            and re.search(r'\b(in|after|every|for|when|if|increases|rises)\b', value))):
        return CommandClarification('No schedule was created. Use a complete command, for example: turn the fan on in two minutes for three minutes; or tell me the temperature every two minutes. Temperature increases must be in degrees Celsius.')
    return None


def execute_command(intent: CommandIntent, client) -> tuple[str, dict]:
    """Execute only a parser-produced typed environment request, never shell/GPIO."""
    if intent.operation == 'automation.add':
        result = client.automation_add(**intent.params)
        job = result.get('job', result)
        if not isinstance(job, dict) or not isinstance(job.get('id'), str):
            raise ValueError('invalid_schedule_reply')
        text = f"Timer {job['id']} scheduled. "
        kind = str(intent.params['kind'])
        if kind.startswith('fan_'):
            text += 'Fan timing respects the safety dwell; timed fan commands use manual control. '
        if kind=='temperature_delta': text += f"I will report a rise of {intent.params['delta_c']:g} degrees Celsius from the last spoken reading. "
        if intent.params.get('interval_seconds') or kind=='temperature_delta':
            text += f"It expires after {intent.params.get('lease_seconds', 28800)/3600:g} hours. "
        text += 'Timers clear on daemon restart. Say cancel all timers to cancel.'
        return text, result
    if intent.operation == 'automation.list':
        result = client.automation_list()
        jobs = result.get('jobs', [])
        if not jobs: return 'There are no active timers.', result
        return f"{len(jobs)} active timers: " + '; '.join(f"{j['id']}, {j['kind'].replace('_',' ')}" for j in jobs[:8]) + '.', result
    if intent.operation == 'automation.cancel':
        result = client.automation_cancel(intent.params.get('job_id'))
        return 'Cancelled the requested timers. An active timed fan run is commanded off; automatic mode is not changed.', result
    raise ValueError('unsupported_command_operation')
