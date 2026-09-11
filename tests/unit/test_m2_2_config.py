from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import tomllib
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from gonken_agent import cli
from gonken_agent.config import (
    ENV_FIELDS,
    PATH_FIELDS,
    REDACTED,
    ConfigError,
    _dump_toml,
    default_config_path,
    load_config,
    migrate_legacy,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"


def flatten(data: dict[str, object], prefix: str = "") -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, dotted))
        else:
            result[dotted] = value
    return result


def env_string(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class AuthorityAndPrecedenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with DEFAULTS.open("rb") as handle:
            cls.raw_defaults = tomllib.load(handle)
        cls.leaves = flatten(cls.raw_defaults)

    def test_checkout_finds_the_source_controlled_defaults(self) -> None:
        self.assertEqual(default_config_path(), DEFAULTS)
        effective = load_config(site_path=None, environ={})
        self.assertEqual(asdict(effective.config), self.raw_defaults)
        self.assertEqual(set(effective.sources), set(self.leaves))

    def test_site_source_is_recorded_for_every_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site.toml"
            site.write_text(DEFAULTS.read_text(encoding="utf-8"), encoding="utf-8")
            effective = load_config(site_path=site, environ={})

        for dotted in self.leaves:
            with self.subTest(dotted=dotted):
                self.assertEqual(effective.sources[dotted], "site")

    def test_environment_source_is_recorded_for_every_field(self) -> None:
        reverse = {dotted: variable for variable, dotted in ENV_FIELDS.items()}
        environment = {
            reverse[dotted]: env_string(value)
            for dotted, value in self.leaves.items()
        }
        effective = load_config(site_path=None, environ=environment)

        for dotted in self.leaves:
            with self.subTest(dotted=dotted):
                self.assertEqual(
                    effective.sources[dotted], f"env:{reverse[dotted]}"
                )

    def test_cli_source_is_recorded_for_every_field(self) -> None:
        effective = load_config(
            site_path=None, environ={}, cli_overrides=self.leaves
        )
        for dotted in self.leaves:
            with self.subTest(dotted=dotted):
                self.assertEqual(effective.sources[dotted], f"cli:{dotted}")

    def test_defaults_site_environment_cli_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site.toml"
            site.write_text('[llm]\nmodel = "site-model"\n', encoding="utf-8")
            effective = load_config(
                site_path=site,
                environ={"GONKEN_LLM_MODEL": "environment-model"},
                cli_overrides={"llm.model": "cli-model"},
            )
        self.assertEqual(effective.config.llm.model, "cli-model")
        self.assertEqual(effective.sources["llm.model"], "cli:llm.model")

    def test_environment_beats_site_without_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site.toml"
            site.write_text('[llm]\nmodel = "site-model"\n', encoding="utf-8")
            effective = load_config(
                site_path=site,
                environ={"GONKEN_LLM_MODEL": "environment-model"},
            )
        self.assertEqual(effective.config.llm.model, "environment-model")

    def test_unrelated_process_environment_is_ignored(self) -> None:
        effective = load_config(
            site_path=None,
            environ={"GONKEN_INSTALL_DIR": "/tmp/installer-only"},
        )
        self.assertEqual(effective.config.llm.model, self.raw_defaults["llm"]["model"])

    def test_legacy_adapter_uses_authority_and_never_accepts_json(self) -> None:
        from config import Config as LegacyConfig

        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site.toml"
            site.write_text('[audio]\ninput_match = "site microphone"\n', encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"GONKEN_AUDIO_OUTPUT_MATCH": "environment speaker"},
                clear=True,
            ):
                legacy = LegacyConfig.load(str(site))
        self.assertEqual(legacy.mic_name, "site microphone")
        self.assertEqual(legacy.speaker_name, "environment speaker")
        with self.assertRaisesRegex(ConfigError, "migration input"):
            LegacyConfig.load(str(ROOT / "config" / "config.json"))

    def test_installer_reads_model_and_endpoint_from_config_cli(self) -> None:
        installer = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("config show --effective --json", installer)
        self.assertIn('OLLAMA_MODEL="$(config_value llm.model)"', installer)
        self.assertIn('OLLAMA_URL="$(config_value llm.base_url)"', installer)
        self.assertIn('export OLLAMA_HOST="$OLLAMA_URL"', installer)
        self.assertNotIn("OLLAMA_MODEL:-", installer)
        self.assertNotIn("OLLAMA_URL:-", installer)

    def test_resumable_installer_explicitly_requests_unredacted_speech_paths(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn(
            'config show --effective --json --show-paths',
            installer,
        )
        self.assertIn('value["paths"]["whisper_binary"]', installer)
        self.assertIn('value["paths"]["whisper_model"]', installer)
        self.assertIn('value["paths"]["piper_voice"]', installer)

    def test_defaults_are_declared_as_wheel_data(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            metadata["tool"]["setuptools"]["data-files"]["share/gonken-agent"],
            ["config/defaults.toml"],
        )


class ValidationTests(unittest.TestCase):
    INVALID_OVERRIDES = {
        "newer schema": {"schema_version": 2},
        "identity change": {"assistant.name": "Other"},
        "language": {"assistant.language": "en-CA"},
        "runtime mode": {"runtime.mode": "cloud"},
        "interaction mode": {"runtime.interaction_mode": "wake_word"},
        "provider": {"llm.provider": "remote"},
        "remote llm": {"llm.base_url": "http://192.168.1.10:11434"},
        "llm path": {"llm.base_url": "http://127.0.0.1:11434/api"},
        "empty model": {"llm.model": ""},
        "small context": {"llm.context_tokens": 128},
        "output beyond context": {"llm.max_output_tokens": 4096},
        "keep alive": {"llm.keep_alive": "forever"},
        "empty input": {"audio.input_match": ""},
        "audio relation": {"audio.processing_rate": 44100},
        "stt threads": {"stt.threads": 0},
        "unsafe stt model": {"stt.model": "../../model"},
        "unsafe tts voice": {"tts.voice": "../../voice"},
        "gpio range": {"interaction.push_to_talk_gpio": 40},
        "gpio conflict": {"interaction.recording_led_gpio": 17},
        "top k": {"retrieval.top_k": 0},
        "retention": {"privacy.raw_audio_retention": "keep"},
        "content logging": {"privacy.interaction_logging": True},
        "dashboard bind": {"dashboard.bind": "0.0.0.0"},
        "dashboard port": {"dashboard.port": 70000},
        "relative path": {"paths.state_dir": "var/lib/gonken-agent"},
        "path escape": {"paths.state_dir": "/var/lib/../tmp"},
        "wake extension": {"extensions.wake_word.enabled": True},
        "voice power": {"extensions.voice_power.enabled": True},
        "wake threshold": {"extensions.wake_word.threshold": 1.0},
        "wake gpio conflict": {"extensions.wake_word.monitoring_led_gpio": 17},
    }

    def test_invalid_values_are_rejected(self) -> None:
        for label, overrides in self.INVALID_OVERRIDES.items():
            with self.subTest(label=label), self.assertRaises(ConfigError):
                load_config(site_path=None, environ={}, cli_overrides=overrides)

    def test_unknown_site_key_and_invalid_type_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unknown = root / "unknown.toml"
            unknown.write_text("[llm]\nmodle = 'typo'\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "unknown configuration key"):
                load_config(site_path=unknown, environ={})

            wrong_type = root / "wrong.toml"
            wrong_type.write_text("[dashboard]\nport = '8080'\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "must be int"):
                load_config(site_path=wrong_type, environ={})

    def test_invalid_environment_boolean_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "must be a boolean"):
            load_config(
                site_path=None,
                environ={"GONKEN_DASHBOARD_ENABLED": "sometimes"},
            )

    def test_unknown_cli_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unknown configuration key"):
            load_config(
                site_path=None, environ={}, cli_overrides={"llm.modle": "typo"}
            )

    def test_loopback_ipv4_ipv6_and_localhost_are_allowed(self) -> None:
        for url in (
            "http://127.0.0.2:11434",
            "http://[::1]:11434",
            "https://localhost:11434",
        ):
            with self.subTest(url=url):
                loaded = load_config(
                    site_path=None,
                    environ={},
                    cli_overrides={"llm.base_url": url},
                )
                self.assertEqual(loaded.config.llm.base_url, url)


class EffectiveOutputTests(unittest.TestCase):
    def test_effective_output_redacts_all_absolute_paths(self) -> None:
        effective = load_config(site_path=None, environ={})
        raw = effective.as_dict(redact=False)
        redacted = effective.as_dict(redact=True)
        raw_flat = flatten(raw)
        redacted_flat = flatten(redacted)

        for dotted in PATH_FIELDS:
            with self.subTest(dotted=dotted):
                if raw_flat[dotted]:
                    self.assertEqual(redacted_flat[dotted], REDACTED)
                    self.assertNotEqual(raw_flat[dotted], REDACTED)

    def test_cli_json_is_redacted_and_reports_sources(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main([
                "config", "show", "--effective", "--no-site", "--json",
                "--set", "llm.model=one-shot-model",
            ])
        payload = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(payload["config"]["llm"]["model"], "one-shot-model")
        self.assertEqual(payload["sources"]["llm"]["model"], "cli:llm.model")
        self.assertEqual(payload["config"]["paths"]["state_dir"], REDACTED)

    def test_cli_show_paths_is_explicit_and_preserves_default_redaction(self) -> None:
        redacted_output = io.StringIO()
        with contextlib.redirect_stdout(redacted_output):
            redacted_result = cli.main([
                "config", "show", "--effective", "--no-site", "--json",
            ])
        shown_output = io.StringIO()
        with contextlib.redirect_stdout(shown_output):
            shown_result = cli.main([
                "config", "show", "--effective", "--no-site", "--json",
                "--show-paths",
            ])
        redacted = json.loads(redacted_output.getvalue())
        shown = json.loads(shown_output.getvalue())

        self.assertEqual(redacted_result, 0)
        self.assertEqual(shown_result, 0)
        self.assertEqual(redacted["config"]["paths"]["whisper_model"], REDACTED)
        self.assertEqual(
            shown["config"]["paths"]["whisper_model"],
            "/var/lib/gonken-agent/models/whisper/base.en-q5_1.bin",
        )
        self.assertEqual(
            shown["config"]["paths"]["piper_voice"],
            "/var/lib/gonken-agent/models/piper/en_US-ljspeech-medium/en_US-ljspeech-medium.onnx",
        )

    def test_cli_config_error_is_stable_and_nonzero(self) -> None:
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            result = cli.main([
                "config", "show", "--effective", "--no-site",
                "--set", "dashboard.bind=0.0.0.0",
            ])
        self.assertEqual(result, cli.EXIT_FAILED)
        self.assertIn("loopback", error.getvalue())

    def test_human_output_does_not_expose_absolute_config_paths(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main(["config", "show", "--effective", "--no-site"])
        self.assertEqual(result, 0)
        self.assertNotIn(str(ROOT), output.getvalue())
        self.assertIn("paths.state_dir = '<redacted>' [defaults]", output.getvalue())


class MigrationTests(unittest.TestCase):
    def test_actual_legacy_files_migrate_repeatably_without_mutation(self) -> None:
        legacy_json = ROOT / "config" / "config.json"
        legacy_env = ROOT / ".env.example"
        json_before = legacy_json.read_bytes()
        env_before = legacy_env.read_bytes()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "config.toml"
            backup_dir = root / "backups"
            first = migrate_legacy(
                legacy_json=legacy_json,
                legacy_env=legacy_env,
                output=output,
                backup_dir=backup_dir,
            )
            output_before = output.read_bytes()
            backup_dir.chmod(0o755)
            for backup in first.backups:
                backup.chmod(0o644)
            second = migrate_legacy(
                legacy_json=legacy_json,
                legacy_env=legacy_env,
                output=output,
                backup_dir=backup_dir,
            )
            migrated = load_config(site_path=output, environ={})

            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertEqual(first.backups, second.backups)
            self.assertEqual(len(list(backup_dir.iterdir())), 2)
            self.assertEqual(output.read_bytes(), output_before)
            self.assertEqual(migrated.config.llm.model, "qwen2.5:1.5b")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup_dir.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all((p.stat().st_mode & 0o777) == 0o600 for p in first.backups))

        self.assertEqual(legacy_json.read_bytes(), json_before)
        self.assertEqual(legacy_env.read_bytes(), env_before)

    def test_unknown_or_unsafe_legacy_input_creates_no_output(self) -> None:
        cases = (
            {"unexpected": "value"},
            {"state_path": "../../escape"},
            {"enable_ui": True},
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config" / "config.json"
            legacy.parent.mkdir()
            for number, payload in enumerate(cases):
                with self.subTest(payload=payload):
                    legacy.write_text(json.dumps(payload), encoding="utf-8")
                    output = root / f"output-{number}.toml"
                    with self.assertRaises(ConfigError):
                        migrate_legacy(
                            legacy_json=legacy,
                            legacy_env=None,
                            output=output,
                        )
                    self.assertFalse(output.exists())

    def test_relative_legacy_path_cannot_escape_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config" / "config.json"
            legacy.parent.mkdir()
            legacy.write_text(
                json.dumps({"whisper_model": "../../outside.bin"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigError, "escapes checkout"):
                migrate_legacy(
                    legacy_json=legacy,
                    legacy_env=None,
                    output=root / "site.toml",
                )

    def test_populated_external_credential_is_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = root / ".env"
            env.write_text("OPENWEATHER_API_KEY=secret\n", encoding="utf-8")
            output = root / "site.toml"
            with self.assertRaisesRegex(ConfigError, "unsupported in offline core"):
                migrate_legacy(legacy_json=None, legacy_env=env, output=output)
            self.assertFalse(output.exists())

    def test_existing_different_output_is_never_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config.json"
            legacy.write_text(json.dumps({"chat_model": "migrated"}), encoding="utf-8")
            output = root / "site.toml"
            original = '[llm]\nmodel = "administrator-value"\n'
            output.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "different content"):
                migrate_legacy(legacy_json=legacy, legacy_env=None, output=output)
            self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_serializer_round_trip_is_deterministic(self) -> None:
        payload = {"llm": {"model": "quoted \\\" model"}, "dashboard": {"port": 9000}}
        rendered = _dump_toml(payload)
        self.assertEqual(tomllib.loads(rendered), payload)
        self.assertEqual(_dump_toml(payload), rendered)

    def test_cli_migration_reports_repeat_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "config.json"
            legacy.write_text(json.dumps({"chat_model": "legacy-model"}), encoding="utf-8")
            output = root / "site.toml"
            arguments = [
                "config", "migrate", "--legacy-json", str(legacy),
                "--legacy-env", str(root / "missing.env"),
                "--output", str(output), "--json",
            ]
            first_output = io.StringIO()
            with contextlib.redirect_stdout(first_output):
                first = cli.main(arguments)
            second_output = io.StringIO()
            with contextlib.redirect_stdout(second_output):
                second = cli.main(arguments)

        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertTrue(json.loads(first_output.getvalue())["changed"])
        self.assertFalse(json.loads(second_output.getvalue())["changed"])


if __name__ == "__main__":
    unittest.main()
