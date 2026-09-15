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
bash -n bootstrap.sh install-gonken.sh setup.sh scripts/ci.sh scripts/install.sh \
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

CI_LOG_DIR="${GONKEN_CI_LOG_DIR:-$PROJECT_ROOT/build/ci-logs}"
mkdir -p "$CI_LOG_DIR"

echo "[T1] unit suite (bounded per module)"
"$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
  --root "$PROJECT_ROOT" \
  --suite-dir tests/unit \
  --label unit \
  --log-dir "$CI_LOG_DIR/unit" \
  --manifest "$CI_LOG_DIR/unit_manifest.json" \
  --timeout-seconds "${GONKEN_CI_UNIT_MODULE_TIMEOUT:-180}" \
  --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"

echo "[T1] deterministic integration suite (bounded per module)"
"$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
  --root "$PROJECT_ROOT" \
  --suite-dir tests/integration \
  --label integration \
  --log-dir "$CI_LOG_DIR/integration" \
  --manifest "$CI_LOG_DIR/integration_manifest.json" \
  --timeout-seconds "${GONKEN_CI_INTEGRATION_MODULE_TIMEOUT:-300}" \
  --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"

echo "T0/T1 checks passed"
