from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import gonken_agent
from gonken_agent import cli


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "gonken_agent"
INVENTORY_PATH = ROOT / "packaging" / "provenance.toml"
OPTIONAL_ROOTS = {
    "gpiozero",
    "httpx",
    "numpy",
    "onnxruntime",
    "openwakeword",
    "piper",
    "pygame",
    "requests",
    "scipy",
    "sklearn",
    "sounddevice",
}


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


class PackageTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self) -> None:
        metadata = load_toml(ROOT / "pyproject.toml")

        self.assertEqual(
            metadata["project"]["name"], gonken_agent.IDENTITY.package_name
        )
        self.assertEqual(metadata["project"]["version"], gonken_agent.__version__)
        self.assertEqual(metadata["project"]["requires-python"], ">=3.12,<3.14")
        self.assertNotIn("license", metadata["project"])
        self.assertEqual(metadata["project"]["dependencies"], [])

    def test_public_import_is_dependency_light(self) -> None:
        source = ROOT / "src"
        script = f"""
import sys
forbidden = {OPTIONAL_ROOTS!r}
before = forbidden.intersection(sys.modules)
sys.path.insert(0, {str(source)!r})
import gonken_agent
loaded = sorted(forbidden.intersection(sys.modules) - before)
if loaded:
    raise SystemExit('optional dependencies imported by gonken_agent: ' + ', '.join(loaded))
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_identity_is_immutable_and_authoritative(self) -> None:
        self.assertEqual(gonken_agent.IDENTITY.product_name, "GonKenLab Agent")
        self.assertEqual(gonken_agent.IDENTITY.spoken_name, "GonKenLab")
        self.assertEqual(gonken_agent.IDENTITY.service_name, "gonken-agent")


class CliTests(unittest.TestCase):
    def test_checkout_compatibility_launcher_uses_package_cli(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "orchestrator.py"), "version"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), gonken_agent.__version__)

    def test_version_command(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main(["version"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), gonken_agent.__version__)

    def test_json_status_is_honest_and_machine_readable(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main(["status", "--json"])
        payload = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(payload["product"], "GonKenLab Agent")
        self.assertIs(payload["core_runtime_ready"], False)
        self.assertIs(payload["redistribution_approved"], False)
        self.assertEqual(payload["redistribution_policy"], "prohibited")
        self.assertEqual(payload["package_foundation"], "complete")
        self.assertEqual(payload["configuration_foundation"], "complete")
        self.assertEqual(payload["extensions"]["wake_word"], "enabled")
        self.assertEqual(payload["extensions"]["bluetooth"], "disabled")

    def test_packaged_run_enters_voice_appliance_runtime(self) -> None:
        with mock.patch("gonken_agent.voice_runtime.run_appliance", return_value=0) as runtime:
            result = cli.main(["run"])
        self.assertEqual(result, 0)
        runtime.assert_called_once()

    def test_legacy_run_crosses_explicit_adapter(self) -> None:
        with mock.patch.object(cli, "run_legacy_source", return_value=0) as adapter:
            result = cli.main(["run", "--legacy-source"])

        self.assertEqual(result, 0)
        adapter.assert_called_once_with()


class BoundaryTests(unittest.TestCase):
    def test_core_package_has_no_optional_dependency_imports(self) -> None:
        violations: dict[str, list[str]] = {}
        for path in PACKAGE.rglob("*.py"):
            if "extensions" in path.relative_to(PACKAGE).parts:
                continue
            forbidden = sorted(import_roots(path).intersection(OPTIONAL_ROOTS))
            if forbidden:
                violations[str(path.relative_to(ROOT))] = forbidden

        self.assertEqual(violations, {})

    def test_extension_namespace_has_no_eager_implementation_imports(self) -> None:
        extension_init = PACKAGE / "extensions" / "__init__.py"
        self.assertEqual(import_roots(extension_init).intersection(OPTIONAL_ROOTS), set())

    def test_product_name_literal_is_centralized_in_package(self) -> None:
        occurrences = []
        for path in PACKAGE.rglob("*.py"):
            if path.name == "identity.py":
                continue
            if "GonKenLab Agent" in path.read_text(encoding="utf-8"):
                occurrences.append(str(path.relative_to(ROOT)))

        self.assertEqual(occurrences, [])


class IdentityTests(unittest.TestCase):
    def test_inherited_identity_is_absent_from_active_surfaces(self) -> None:
        # Construct terms so this validation file does not flag its own fixtures.
        inherited = ["Jan" + "sky", "May" + "ukh", "Pi" + "Bot"]
        phrase = "Hey" + r"\s+" + "Jar" + "vis"
        pattern = re.compile(
            r"\b(?:" + "|".join(inherited) + r")\b|" + phrase,
            re.IGNORECASE,
        )
        violations: list[str] = []

        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".md",
                ".py",
                ".sh",
                ".json",
                ".toml",
            }:
                continue
            relative = path.relative_to(ROOT)
            if relative == Path("PRD.md") or relative.parts[:2] == (
                "docs",
                "development",
            ):
                continue
            if relative == Path("tests/unit/test_m2_1.py"):
                continue
            if pattern.search(path.read_text(encoding="utf-8")):
                violations.append(str(relative))

        self.assertEqual(violations, [])


class ProvenanceTests(unittest.TestCase):
    def test_every_tracked_media_asset_has_verified_inventory_hash(self) -> None:
        inventory = load_toml(INVENTORY_PATH)
        records = {record["path"]: record for record in inventory["assets"]}
        asset_paths = {
            str(path.relative_to(ROOT))
            for path in (ROOT / "assets").rglob("*")
            if path.is_file()
        }

        self.assertEqual(set(records), asset_paths)
        for relative, record in records.items():
            payload = (ROOT / relative).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
            self.assertIs(record["included_in_wheel"], False)
            self.assertEqual(record["provenance"], "unknown")
            self.assertEqual(record["license"], "NOASSERTION")

        self.assertIn(
            "quarantined internal compatibility evidence",
            inventory["unknown_media_policy"],
        )

    def test_every_legacy_requirement_is_inventory_tracked(self) -> None:
        requirements = {
            re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip().lower()
            for line in (ROOT / "requirements" / "legacy-prototype.in")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        dependency_names = {
            item["name"] for item in load_toml(INVENTORY_PATH)["dependencies"]
        }

        self.assertTrue(requirements.issubset(dependency_names))
        self.assertIn("openwakeword", dependency_names)

    def test_inventory_and_metadata_block_redistribution_claims(self) -> None:
        inventory = load_toml(INVENTORY_PATH)
        project = load_toml(ROOT / "pyproject.toml")["project"]

        self.assertEqual(inventory["project_source_license"], "NOASSERTION")
        self.assertEqual(
            inventory["project_license_status"],
            "intentionally-unlicensed-no-redistribution",
        )
        self.assertIs(inventory["redistribution_approved"], False)
        self.assertTrue(inventory["redistribution_policy"].startswith("prohibited"))
        self.assertNotIn("license", project)
        self.assertEqual(project["dependencies"], [])

    def test_no_redistribution_policy_is_consistent_across_surfaces(self) -> None:
        status = cli._status()
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        provenance = (ROOT / "docs/development/LICENSE_PROVENANCE.md").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIs(status["redistribution_approved"], False)
        self.assertEqual(status["redistribution_policy"], "prohibited")
        self.assertIn("prohibits redistribution", readme)
        self.assertIn("no redistribution", provenance)


if __name__ == "__main__":
    unittest.main()
