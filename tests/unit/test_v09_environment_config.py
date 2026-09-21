from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from gonken_agent.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"


class V09EnvironmentConfigTests(unittest.TestCase):
    def test_schema_two_defaults_add_disabled_environment_static_contract(self) -> None:
        effective = load_config(defaults_path=DEFAULTS, site_path=None, environ={})
        env = effective.config.extensions.environment
        self.assertEqual(effective.config.schema_version, 2)
        self.assertFalse(env.enabled)
        self.assertEqual(env.sensor_backend, "sht31")
        self.assertEqual(env.i2c_address, 0x44)
        self.assertEqual(env.relay_backend, "libgpiod")
        self.assertEqual(env.relay_bcm, 23)
        self.assertEqual(env.safe_state, "off")
        self.assertEqual(env.socket_path, "/run/gonken-environment/control.sock")
        self.assertEqual(env.policy_path, "/var/lib/gonken-environment/policy.json")
        self.assertEqual(effective.sources["extensions.environment.enabled"], "defaults")

    def test_schema_one_site_config_migrates_without_downgrading_effective_schema(self) -> None:
        raw = tomllib.loads(DEFAULTS.read_text(encoding="utf-8"))
        raw["schema_version"] = 1
        raw["extensions"].pop("environment")
        rendered = "schema_version = 1\n\n[llm]\nmodel = \"site-model\"\n\n[extensions.wake_word]\nphrase = \"Hey Gonken\"\n"
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "schema1-site.toml"
            site.write_text(rendered, encoding="utf-8")
            effective = load_config(defaults_path=DEFAULTS, site_path=site, environ={})
        self.assertEqual(effective.config.schema_version, 2)
        self.assertEqual(effective.config.llm.model, "site-model")
        self.assertFalse(effective.config.extensions.environment.enabled)
        self.assertEqual(effective.sources["schema_version"], "defaults")
        self.assertEqual(effective.sources["llm.model"], "site")
        self.assertEqual(effective.sources["extensions.environment.policy_path"], "defaults")

    def test_environment_static_policy_bounds_are_cross_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site.toml"
            site.write_text(
                "[extensions.environment]\n"
                "temperature_policy_min_c = 10.0\n"
                "temperature_policy_max_c = 11.0\n"
                "maximum_hysteresis_c = 15.0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "maximum_hysteresis"):
                load_config(defaults_path=DEFAULTS, site_path=site, environ={})

    def test_enabled_relay_cannot_reuse_other_enabled_resources(self) -> None:
        for mode, pins in (("wake_word", (2,3,22)), ("push_to_talk", (2,3,17,27))):
            for pin in pins:
                with self.subTest(mode=mode,pin=pin), self.assertRaisesRegex(ConfigError, "conflict"):
                    load_config(defaults_path=DEFAULTS,site_path=None,environ={},cli_overrides={
                        "runtime.interaction_mode": mode, "extensions.environment.enabled":True,
                        "extensions.environment.relay_bcm":pin})

    def test_dormant_relay_field_is_not_a_reservation(self) -> None:
        for pin in (2,3,17,22,27):
            value=load_config(defaults_path=DEFAULTS,site_path=None,environ={},cli_overrides={"extensions.environment.relay_bcm":pin})
            self.assertFalse(value.config.extensions.environment.enabled)


if __name__ == "__main__":
    unittest.main()
