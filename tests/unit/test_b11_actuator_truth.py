from __future__ import annotations
import unittest
from gonken_agent.environment.actuators import GpiodRelayFanActuator, ActuatorAdapterError
from gonken_agent.environment.domain import FanPower
from tests.unit.test_v09_environment_hardware_adapters import FakeGpiod

class RelayCommandTruthTests(unittest.TestCase):
    def relay(self, **kw):
        module=FakeGpiod(**kw)
        return GpiodRelayFanActuator(line_offset=23,active_high=True,gpiod_module=module),module
    def test_no_command_or_claim_before_open(self):
        relay,module=self.relay()
        report=relay.command_diagnostics()
        self.assertIsNone(report['relay_commanded']);self.assertFalse(report['gpio_claimed'])
        self.assertEqual(module.requests,[])
    def test_initial_off_and_exclusive_owner_then_on_are_acknowledged(self):
        relay,module=self.relay();relay.set_power('on');info=relay.resolved_identity()
        self.assertEqual(info['relay_commanded'],'on');self.assertTrue(info['gpio_claimed'])
        self.assertEqual(info['gpio_consumer'],'gonken-environment');self.assertEqual(info['gpio_write_count'],2)
        self.assertFalse(info['fan_motion_observed']);self.assertFalse(info['software_speed_control'])
        for _ in range(100):relay.set_power('on')
        self.assertEqual(relay.command_diagnostics()['gpio_write_count'],2)
    def test_write_failure_cannot_report_intended_on_as_commanded(self):
        relay,module=self.relay(fail_set=True)
        with self.assertRaises(ActuatorAdapterError):relay.set_power('on')
        report=relay.command_diagnostics()
        self.assertIsNone(report['relay_commanded']);self.assertEqual(report['gpio_write_errors'],1)
        self.assertEqual(report['last_write_result'],'FAILED');self.assertTrue(report['gpio_claimed'])
    def test_failed_close_releases_but_does_not_claim_off(self):
        relay,module=self.relay();relay.set_power('on');module.last_request.fail_set=True
        with self.assertRaises(ActuatorAdapterError):relay.close()
        report=relay.command_diagnostics()
        self.assertFalse(report['gpio_claimed']);self.assertIsNone(report['relay_commanded'])
        self.assertTrue(module.last_request.released);self.assertEqual(report['gpio_write_errors'],1)
    def test_request_busy_and_recovery_are_separate_from_physical_motion(self):
        relay,module=self.relay(fail_request=True)
        with self.assertRaises(ActuatorAdapterError):relay.set_power('on')
        self.assertEqual(relay.command_diagnostics()['gpio_request_errors'],1)
        module.fail_request=False;relay.set_power('on')
        self.assertEqual(relay.command_diagnostics()['relay_commanded'],'on')
        self.assertFalse(relay.command_diagnostics()['fan_motion_observed'])
    def test_successful_close_has_no_live_command_after_release(self):
        relay,module=self.relay();relay.set_power('on');relay.close()
        self.assertEqual(relay.commanded_power,FanPower.OFF)
        self.assertIsNone(relay.command_diagnostics()['relay_commanded'])
        count=relay.command_diagnostics()['gpio_write_count'];relay.close()
        self.assertEqual(relay.command_diagnostics()['gpio_write_count'],count)
    def test_invalid_polarity_fails_closed(self):
        for polarity in (0,1,'false',None):
            with self.assertRaises(ActuatorAdapterError):GpiodRelayFanActuator(line_offset=23,active_high=polarity)

if __name__=='__main__':unittest.main()
