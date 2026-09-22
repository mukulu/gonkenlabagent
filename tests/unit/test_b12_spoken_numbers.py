from __future__ import annotations
import unittest
from gonken_agent.command_intents import parse_command, CommandClarification
from gonken_agent.environment.intents import parse_environment_intent, EnvironmentClarification
from gonken_agent.spoken_numbers import normalize_spoken_numbers
from gonken_agent.environment.automation import Automation, AutomationError

class SpokenNumbersTests(unittest.TestCase):
    def test_threshold_pair_spoken(self):
        i = parse_environment_intent('Set fan on threshold to twenty eight and off threshold to twenty-six')
        self.assertEqual(i.params, {'start_c':28., 'stop_c':26.})
    def test_decimal(self):
        i = parse_environment_intent('Set fan off threshold to twenty six point five')
        self.assertEqual(i.params, {'stop_c':26.5})
    def test_delay_phrase(self):
        i=parse_command('Turn the fan on after twenty one minutes for three minutes')
        self.assertEqual(i.params['delay_seconds'],1260)
    def test_negative_delay_not_made_positive(self):
        self.assertIsInstance(parse_command('Start the fan after minus two minutes'),CommandClarification)
    def test_article_is_not_changed(self):
        self.assertEqual(normalize_spoken_numbers('a fan'), 'a fan')
    def test_repeated_words_not_guessed(self):
        self.assertIsInstance(parse_command('Start the fan after twenty twenty minutes'),CommandClarification)
    def test_ambiguous_units_not_converted(self):
        self.assertIsInstance(parse_command('Tell me when temperature increases by two minutes'),CommandClarification)
    def test_quote_and_hypothetical_threshold_not_action(self):
        for text in ['What if the fan turns on at 28 and off at 26?', 'The note says turn the fan on at 28', '"set fan on threshold to 28"']:
            with self.subTest(text=text):self.assertIsInstance(parse_environment_intent(text),EnvironmentClarification)
    def test_query_does_not_set_threshold(self):
        self.assertIsInstance(parse_environment_intent('Does the fan start at 28?'),EnvironmentClarification)
    def test_ambiguous_two_power_states(self):
        self.assertIsInstance(parse_environment_intent('Turn the fan on and off'),EnvironmentClarification)
    def test_extreme_input_bounded(self):
        self.assertEqual(normalize_spoken_numbers('one '*2000),'')
    def test_report_invalid_lease(self):
        with self.assertRaises(AutomationError):Automation().add({'kind':'temperature','lease_seconds':120},now=0,snapshot={},minimum_on=60,minimum_off=60)

if __name__=='__main__': unittest.main()
