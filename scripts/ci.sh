#!/usr/bin/env bash
# Run deterministic repository T0/T1 checks.
# This entry point never installs packages or runs live/manual probes.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT"

echo "[T0] dependency lock drift"
"$PYTHON_BIN" "$SCRIPT_DIR/dependencies.py" render --check

"$PYTHON_BIN" "$SCRIPT_DIR/milestone_status.py" --check
"$PYTHON_BIN" "$SCRIPT_DIR/release_readiness.py" --check --allow-dirty >/dev/null

echo "[T0] source/config syntax"
bash -n bootstrap.sh setup.sh scripts/ci.sh scripts/install.sh \
  scripts/lib/common.sh scripts/lib/install_engine.sh scripts/reconcile-release.sh \
  scripts/update.sh scripts/collect-support.sh scripts/rollback.sh scripts/uninstall.sh \
  tests/fixtures/install_engine_harness.sh
"$PYTHON_BIN" -m compileall -q \
  src tests/unit tests/integration tests/hardware scripts \
  config.py orchestrator.py legacy_orchestrator.py audio brain senses ui
"$PYTHON_BIN" -c '
import json
import tomllib
from pathlib import Path

for filename in (
    "config/defaults.toml",
    "packaging/speech-artifacts.toml",
    "packaging/provenance.toml",
    "pyproject.toml",
    "requirements/profiles.toml",
):
    with Path(filename).open("rb") as handle:
        tomllib.load(handle)
json.loads(Path("config/config.json").read_text(encoding="utf-8"))
'

if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  git diff --check
fi

echo "[T1] unit suite"
"$PYTHON_BIN" -m unittest discover -s tests/unit -t . -v

echo "[T1] deterministic integration suite"
"$PYTHON_BIN" -m unittest discover -s tests/integration -t . -v

echo "T0/T1 checks passed"
