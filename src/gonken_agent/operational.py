"""Shared deterministic voice/terminal commands, with no LLM dependency."""
from __future__ import annotations
import math
import time
from pathlib import Path
from .command_intents import CommandIntent, CommandClarification, parse_command, execute_command
from .environment import (EnvironmentIntent, EnvironmentClarification, EnvironmentClientError,
                          parse_environment_intent, environment_error_response, environment_success_response)
from .tool_broker import direct_clock_intent
from .power import PowerSession, PowerError, power_related, execute_confirmed

class OperationalCommands:
    def __init__(self, client_factory, *, config=None, power_executor=execute_confirmed):
        self.client_factory=client_factory
        self.config=config
        power_config=getattr(getattr(config,"extensions",None),"voice_power",None)
        self.power=PowerSession(enabled=getattr(power_config,"enabled",False))
        self.power_executor=power_executor
        self.reading_receipt=None
        self.last_route='unknown'

    def begin(self):
        self.power.begin(); self.reading_receipt=None

    def is_fast(self, question):
        return (power_related(question) or question.casefold().strip().startswith('confirm ')
                or parse_command(question) is not None or direct_clock_intent(question) is not None
                or isinstance(parse_environment_intent(question),(EnvironmentIntent,EnvironmentClarification)))

    def complete_inline(self, question):
        # Clarifications/partial phrases are fast once captured, but an inline
        # wake fragment must not discard the remainder of an unfinished command.
        return (power_related(question) or isinstance(parse_command(question),CommandIntent)
                or direct_clock_intent(question) is not None
                or isinstance(parse_environment_intent(question),EnvironmentIntent))

    def handle(self, question):
        self.reading_receipt=None
        answer=self.power.handle(question)
        if answer is not None:
            self.last_route='power_confirmation_fast_path'; return answer
        parsed=parse_command(question)
        if isinstance(parsed,CommandClarification):
            self.last_route='schedule_clarification_fast_path'; return parsed.message
        if isinstance(parsed,CommandIntent):
            self.last_route='schedule_fast_path'
            try: return execute_command(parsed,self.client_factory())[0]
            except EnvironmentClientError as exc: return environment_error_response(exc)
            except ValueError: return 'The timer reply was invalid. Check timer status before repeating the command.'
        answer=direct_clock_intent(question)
        if answer is not None: self.last_route='system_clock_fast_path'; return answer
        intent=parse_environment_intent(question)
        if isinstance(intent,EnvironmentClarification):
            self.last_route='environment_clarification_fast_path'; return intent.message
        if isinstance(intent,EnvironmentIntent):
            self.last_route='environment_fast_path'; return self.environment_reply(intent)
        return None

    def environment_reply(self, intent):
        try:
            client=self.client_factory()
            if intent.operation=='sensor.read': result=client.read_sensor()
            elif intent.operation=='status.get': result=client.status()
            elif intent.operation=='policy.get': result=client.policy_get()
            elif intent.operation=='fan.set': result=client.fan_set(str(intent.params['power']))
            elif intent.operation=='mode.set': result=client.mode_set(str(intent.params['mode']))
            elif intent.operation=='policy.update': result=client.policy_update(**dict(intent.params))
            else: raise EnvironmentClientError('UNKNOWN_OPERATION','unsupported environment operation')
        except EnvironmentClientError as exc: return environment_error_response(exc)
        if intent.operation=='sensor.read' and intent.response_kind != 'humidity':
            self.reading_receipt=result.get('announcement_token')
        return environment_success_response(intent,result,concise=True)

    def speech_failed(self):
        self.reading_receipt=None; self.power.cancel()

    def after_spoken(self):
        receipt,self.reading_receipt=self.reading_receipt,None
        if isinstance(receipt,dict) and set(receipt)=={'id','generation'}:
            try: self.client_factory().acknowledge_notification(receipt['id'],receipt['generation'])
            except EnvironmentClientError: pass
        try:
            authorization=self.power.consume()
            if authorization:
                env=self.config.extensions.environment
                self.power_executor(authorization,client_factory=self.client_factory,
                                    environment_required=env.enabled,
                                    real_environment=env.enabled and env.relay_backend=='libgpiod')
        except PowerError as exc:
            return f'Power action was not confirmed complete: {exc.code.lower().replace("_"," ")}. I will not retry automatically.'
        return None


class NotificationAnnouncer:
    """Voice-owned, bounded numeric notices. No model calls or parallel audio."""
    def __init__(self, client_factory, *, clock=time.monotonic):
        self.client_factory=client_factory; self.clock=clock; self.next_poll=0.0; self.current=None

    def pending(self):
        now=self.clock()
        if now < self.next_poll: return None
        self.next_poll=now+1.0
        try: payload=self.client_factory().notifications()
        except EnvironmentClientError: return None
        self.current=None
        if not isinstance(payload,dict): return None
        provenance=payload.get('provenance',{})
        if not isinstance(provenance,dict): return None
        simulated=provenance.get('sensor_is_simulated') is not False
        rows=payload.get('notifications')
        if not isinstance(rows,list): return None
        for row in rows[:8]:
            if not isinstance(row,dict) or row.get('generation')!=payload.get('generation'): continue
            values=[row.get(k) for k in ('temperature_c','relative_humidity_pct','observed_monotonic','expires_monotonic')]
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in values): continue
            temp,humidity,observed,expires=values
            if not 0<=now-observed<=30 or expires<=now or not isinstance(row.get('id'),str): continue
            kind=row.get('kind')
            prefix='In simulation, ' if simulated else ''
            if kind=='humidity': text=f'{prefix}room humidity is {humidity:.1f} percent.'
            elif kind=='environment': text=f'{prefix}room temperature is {temp:.1f} degrees Celsius and humidity is {humidity:.1f} percent.'
            elif kind in {'temperature','temperature_delta'}: text=f'{prefix}room temperature is {temp:.1f} degrees Celsius.'
            else: continue
            self.current={'id':row['id'],'generation':row['generation']}
            return text
        return None

    def spoken(self):
        receipt,self.current=self.current,None
        if receipt:
            try: self.client_factory().acknowledge_notification(receipt['id'],receipt['generation'])
            except EnvironmentClientError: pass
