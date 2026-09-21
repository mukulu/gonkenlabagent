from __future__ import annotations
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from gonken_agent.config import load_config
from gonken_agent.resources import resource_document
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
pre=load('a03_gpio_pre',ROOT/'scripts/gpio_identity_preflight.py')
target=load('a03_gpio_target',ROOT/'scripts/target_probe.py')
class GpioConsumerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.site=self.root/'config.toml';self.site.write_text('[runtime]\ninteraction_mode="wake_word"\n')
  self.requirements=pre.configured_requirements(self.site)
  self.payload={'format':pre.FORMAT,'status':'PASS','code':'GPIO_HEADER_RESOLVED','physical_acceptance_claimed':False,'boot_id':pre.boot_id(),'claims_sha256':self.requirements['claims_sha256'],'required_claims':self.requirements['claims'],'lines':{'GPIO22':{'chip_path':'/dev/gpiochip0','line_offset':22}}}
 def test_selected_config_only_requires_wake_indicator(self):self.assertEqual(self.requirements['required_gpio_lines'],[22])
 def test_missing_site_not_default_green(self):
  with self.assertRaises(ValueError):pre.configured_requirements(self.root/'missing')
 def test_empty_set_does_not_load_gpiod(self):
  self.assertEqual(pre.probe((),gpiod_module=object(),chip_paths=())['code'],'GPIO_HEADER_NOT_REQUIRED')
 def test_invalid_direct_line_input(self):
  for lines in ((True,),(22,22),(99,)):
   self.assertEqual(pre.probe(lines,gpiod_module=object())['status'],'FAIL')
 def test_record_binding_accepts_only_current(self):
  self.assertTrue(pre.record_matches(self.payload,self.requirements))
  for key,value in (('boot_id','old'),('claims_sha256','bad'),('physical_acceptance_claimed',True),('lines',{'GPIO17':{}})):
   bad={**self.payload,key:value};self.assertFalse(pre.record_matches(bad,self.requirements))
 def test_fresh_resolution_drift_rejected(self):
  fresh=copy.deepcopy(self.payload);fresh['lines']['GPIO22']['chip_path']='/dev/gpiochip4'
  self.assertFalse(pre.record_matches(self.payload,self.requirements,fresh))
 def test_cli_consumes_profile_and_records_owner(self):
  out=self.root/'evidence.json'
  with patch.object(pre,'probe',return_value={'format':pre.FORMAT,'status':'PASS','code':'GPIO_HEADER_RESOLVED','lines':self.payload['lines']}) as probe,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(pre.main(['--config',str(self.site),'--output',str(out),'--json']),0)
  probe.assert_called_once_with((22,))
  saved=json.loads(out.read_text());self.assertTrue(pre.record_matches(saved,self.requirements))
  with patch.object(pre,'probe',side_effect=AssertionError('validation must not acquire hardware')):
   self.assertEqual(pre.main(['--config',str(self.site),'--validate-record',str(out)]),0)
 def test_historical_topology_is_not_a_current_requirement(self):
  self.assertEqual(target.replay_gpio_identity({'gpiochips':[]})['code'],'GPIO_REQUIREMENTS_MISSING')
 def test_replay_empty_profile_allowed_without_gpio(self):
  d={'gpiochips':[],'resource_claims':{'format':'gonken-resource-claims-v1','required_gpio_lines':[]}}
  self.assertEqual(target.replay_gpio_identity(d)['code'],'GPIO_HEADER_NOT_REQUIRED')
 def test_replay_invalid_requirement_rejected(self):
  for lines in ([True],[22,22],[54]):
   d={'resource_claims':{'format':'gonken-resource-claims-v1','required_gpio_lines':lines}}
   self.assertEqual(target.replay_gpio_identity(d)['status'],'FAIL')
 def test_installer_current_claim_comparison_not_literal_four_pins(self):
  text=(ROOT/'scripts/install.sh').read_text();a=text.index('gonken_target_gpio_identity_postcondition()');b=text.index('gonken_target_gpio_identity_action()',a);text=text[a:b]
  self.assertIn('--validate-record',text);self.assertIn('--fresh-json "$fresh"',text);self.assertIn('runuser -u "$SERVICE_USER"',text);self.assertNotIn('"GPIO17","GPIO22","GPIO23","GPIO27"',text)
