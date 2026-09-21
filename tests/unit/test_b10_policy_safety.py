from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from gonken_agent.environment.policy import EnvironmentPolicy, PolicyStore, PolicyError
from gonken_agent.environment.domain import PolicyBounds

class RealPolicySafetyTests(unittest.TestCase):
    def test_nonfinite_and_boolean_thresholds_rejected(self):
        p = EnvironmentPolicy.default()
        for value in (float("nan"), float("inf"), float("-inf"), True, False, "28"):
            for key in ("start_c", "stop_c"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(PolicyError):
                        replace(p, **{key: value}).validated(bounds=PolicyBounds())
                    with self.assertRaises(PolicyError):
                        p.updated(bounds=PolicyBounds(), **{key: value})
                    data=p.to_mapping(); data[key]=value
                    with self.assertRaises(PolicyError):
                        EnvironmentPolicy.from_mapping(data, bounds=PolicyBounds())

    def test_fractional_boolean_and_string_dwell_never_coerced(self):
        p=EnvironmentPolicy.default()
        for value in (True, 5.9, "60"):
            for key in ("minimum_on_seconds", "minimum_off_seconds"):
                with self.subTest(key=key, value=value), self.assertRaises(PolicyError):
                    p.updated(bounds=PolicyBounds(), **{key:value})

    def test_duplicate_and_nonfinite_json_preserves_policy_file(self):
        for text in ('{"generation":1,"generation":2}', '{"start_c":NaN}'):
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/"policy.json";path.write_text(text)
                with self.assertRaises(PolicyError):PolicyStore(path,bounds=PolicyBounds()).load()
                self.assertEqual(path.read_text(), text)

    def test_mode_only_update_preserves_thresholds_and_dwell(self):
        p=replace(EnvironmentPolicy.default(),start_c=29.5,stop_c=27,minimum_on_seconds=90)
        updated=p.updated(bounds=PolicyBounds(), expected_generation=p.generation,mode="automatic")
        for key in ("start_c","stop_c","minimum_on_seconds","minimum_off_seconds"):
            self.assertEqual(getattr(p,key),getattr(updated,key))
        self.assertEqual(updated.generation,p.generation+1)
