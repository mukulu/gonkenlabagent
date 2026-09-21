from __future__ import annotations
from dataclasses import replace
import unittest
from gonken_agent.config import load_config,ConfigError
from gonken_agent.resources import claims_for_config,gpio_lines,resource_document,ResourceConflict,ResourceClaim,validate_claims
class ResourceTests(unittest.TestCase):
 def config(self,**overrides): return load_config(site_path=None,environ={},cli_overrides=overrides).config
 def test_wake_no_environment_requires_only_actual_indicator(self):
  c=self.config();self.assertEqual(gpio_lines(claims_for_config(c)),(22,))
  d=resource_document(c);self.assertFalse(d['physical_acceptance_claimed'])
  inactive={r['resource'] for r in d['claims'] if r['state']=='INACTIVE_CONFIGURED'}
  self.assertTrue({'GPIO17','GPIO27','GPIO23'}.issubset(inactive))
 def test_ptt_only_requires_ptt(self):
  self.assertEqual(gpio_lines(claims_for_config(self.config(**{'runtime.interaction_mode':'push_to_talk'}))),(17,27))
 def test_real_environment_requirements(self):
  c=self.config(**{'extensions.environment.enabled':True})
  self.assertEqual(gpio_lines(claims_for_config(c)),(2,3,22,23))
 def test_simulation_does_not_claim_real_sensor_or_relay(self):
  c=self.config(**{'extensions.environment.enabled':True,'extensions.environment.sensor_backend':'simulated','extensions.environment.relay_backend':'simulated'})
  self.assertEqual(gpio_lines(claims_for_config(c)),(22,))
 def test_inactive_ptt_does_not_block_relay(self):
  c=self.config(**{'extensions.environment.enabled':True,'extensions.environment.relay_bcm':17})
  self.assertIn(17,gpio_lines(claims_for_config(c)))
 def test_active_ptt_conflict_fails(self):
  with self.assertRaises(ConfigError): self.config(**{'runtime.interaction_mode':'push_to_talk','extensions.environment.enabled':True,'extensions.environment.relay_bcm':17})
 def test_wake_indicator_conflict_stays_enforced(self):
  with self.assertRaises(ConfigError):self.config(**{'extensions.environment.enabled':True,'extensions.environment.relay_bcm':22})
 def test_real_i2c_conflict_stays_enforced(self):
  with self.assertRaises(ConfigError):self.config(**{'extensions.environment.enabled':True,'extensions.environment.relay_bcm':2})
 def test_inactive_values_still_type_range_checked(self):
  for value in (-1,54,True,'bad'):
   with self.subTest(value=value),self.assertRaises(ConfigError):self.config(**{'interaction.push_to_talk_gpio':value})
 def test_touch_can_own_inactive_ptt_pin(self):
  rows=claims_for_config(self.config(),display_profile='osoyoo35-drm',touch=True)
  self.assertIn(17,gpio_lines(rows));self.assertNotIn(27,gpio_lines(rows));self.assertIn(22,gpio_lines(rows))
  self.assertEqual([r.owner for r in rows if r.resource=='GPIO17' and r.state=='ACTIVE_REQUIRED'],['osoyoo_touch'])
 def test_touch_conflicts_with_active_ptt(self):
  with self.assertRaises(ResourceConflict):claims_for_config(self.config(**{'runtime.interaction_mode':'push_to_talk'}),display_profile='osoyoo35-drm',touch=True)
 def test_unknown_backlight_reserves_pin_but_does_not_acquire(self):
  rows=claims_for_config(self.config(),display_profile='osoyoo35-drm')
  self.assertNotIn(18,gpio_lines(rows));self.assertEqual(next(r for r in rows if r.resource=='GPIO18').state,'UNRESOLVED_TARGET_RESOURCE')
  with self.assertRaises(ResourceConflict):claims_for_config(self.config(**{'extensions.environment.enabled':True,'extensions.environment.relay_bcm':18}),display_profile='osoyoo35-drm')
 def test_unverified_backlight_management_refused(self):
  with self.assertRaises(ResourceConflict):claims_for_config(self.config(),display_profile='osoyoo35-drm',backlight_managed=True)
 def test_invalid_display_or_touch_without_profile(self):
  for kwargs in ({'display_profile':'evil'},{'touch':True},{'backlight_managed':True}):
   with self.assertRaises(ValueError):claims_for_config(self.config(),**kwargs)
 def test_fingerprint_changes_with_active_policy(self):
  a=resource_document(self.config());b=resource_document(self.config(**{'runtime.interaction_mode':'push_to_talk'}))
  self.assertNotEqual(a['claims_sha256'],b['claims_sha256'])
 def test_collision_no_hardware(self):
  a=ResourceClaim('GPIO17','gpio','one','proc','ACTIVE_REQUIRED','reason')
  b=replace(a,owner='two')
  with self.assertRaises(ResourceConflict):validate_claims([a,b])
