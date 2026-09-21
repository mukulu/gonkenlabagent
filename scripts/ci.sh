#!/usr/bin/env bash
# Run deterministic repository T0/T1 checks.
# This entry point never installs packages or runs live/manual probes.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'USAGE'
Usage: scripts/ci.sh [--phase PHASE]...

Run deterministic host checks. Without --phase, all phases run in order.

Phases:
  t0                  dependency, milestone, readiness, syntax and static gates
  unit                bounded per-module unit suite
  integration         bounded deterministic integration suite, excluding long lifecycle modules
  speech-lifecycle    bounded per-case speech lifecycle integration suite
  release-lifecycle   bounded per-case release lifecycle integration suite
  all                 all phases in the canonical order

Examples:
  ./scripts/ci.sh
  ./scripts/ci.sh --phase t0 --phase unit
  ./scripts/ci.sh --phase speech-lifecycle
  ./scripts/ci.sh --phase release-lifecycle
USAGE
}

SELECTED_PHASES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)
      [[ $# -ge 2 ]] || { echo "ERROR: --phase requires a value" >&2; usage >&2; exit 2; }
      SELECTED_PHASES+=("$2")
      shift 2
      ;;
    --list-phases)
      printf '%s\n' t0 unit integration speech-lifecycle release-lifecycle all
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${#SELECTED_PHASES[@]} -eq 0 ]]; then
  SELECTED_PHASES=(all)
fi

for phase in "${SELECTED_PHASES[@]}"; do
  case "$phase" in
    t0|unit|integration|speech-lifecycle|release-lifecycle|all) ;;
    *) echo "ERROR: unknown phase: $phase" >&2; usage >&2; exit 2 ;;
  esac
done

has_phase() {
  local wanted="$1"
  local phase
  for phase in "${SELECTED_PHASES[@]}"; do
    [[ "$phase" == all || "$phase" == "$wanted" ]] && return 0
  done
  return 1
}

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT"

CI_LOG_DIR="${GONKEN_CI_LOG_DIR:-$PROJECT_ROOT/build/ci-logs}"
mkdir -p "$CI_LOG_DIR"

if has_phase t0; then
  "$PYTHON_BIN" "$SCRIPT_DIR/current_state.py" --check
  "$PYTHON_BIN" "$SCRIPT_DIR/repository_contract.py" --allow-dirty >/dev/null

  echo "[T0] dependency lock drift"
  "$PYTHON_BIN" "$SCRIPT_DIR/dependencies.py" render --check

  "$PYTHON_BIN" "$SCRIPT_DIR/milestone_status.py" --check
  "$PYTHON_BIN" "$SCRIPT_DIR/release_readiness.py" --validate --allow-dirty >/dev/null

  echo "[T0] source/config syntax"
  bash -n bootstrap.sh install-gonken.sh install-room-appliance.sh setup.sh scripts/ci.sh scripts/install.sh \
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

  echo "[T0] V09 documentation/evidence boundary"
  "$PYTHON_BIN" "$SCRIPT_DIR/validate_v09_docs.py" --json >/dev/null

  if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    git diff --check
  fi
fi

if has_phase unit; then
  echo "[T1] unit suite (bounded per module)"
  "$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
    --root "$PROJECT_ROOT" \
    --suite-dir tests/unit \
    --label unit \
    --log-dir "$CI_LOG_DIR/unit" \
    --manifest "$CI_LOG_DIR/unit_manifest.json" \
    --timeout-seconds "${GONKEN_CI_UNIT_MODULE_TIMEOUT:-180}" \
    --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"
fi

if has_phase integration; then
  echo "[T1] deterministic integration suite (bounded per module)"
  "$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
    --root "$PROJECT_ROOT" \
    --suite-dir tests/integration \
    --exclude-module tests.integration.test_release_lifecycle_process \
    --exclude-module tests.integration.test_speech_lifecycle_process \
    --label integration \
    --log-dir "$CI_LOG_DIR/integration" \
    --manifest "$CI_LOG_DIR/integration_manifest.json" \
    --timeout-seconds "${GONKEN_CI_INTEGRATION_MODULE_TIMEOUT:-300}" \
    --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"
fi

if has_phase speech-lifecycle; then
  echo "[T1] speech lifecycle integration suite (bounded per case)"
  "$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
    --root "$PROJECT_ROOT" \
    --suite-dir tests/integration \
    --module tests.integration.test_speech_lifecycle_process \
    --granularity case \
    --label integration-speech-lifecycle \
    --log-dir "$CI_LOG_DIR/integration-speech-lifecycle" \
    --manifest "$CI_LOG_DIR/integration_speech_lifecycle_manifest.json" \
    --timeout-seconds "${GONKEN_CI_SPEECH_CASE_TIMEOUT:-240}" \
    --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"
fi

if has_phase release-lifecycle; then
  echo "[T1] release lifecycle integration suite (bounded per case)"
  "$PYTHON_BIN" "$SCRIPT_DIR/bounded_unittest.py" \
    --root "$PROJECT_ROOT" \
    --suite-dir tests/integration \
    --module tests.integration.test_release_lifecycle_process \
    --granularity case \
    --label integration-release-lifecycle \
    --log-dir "$CI_LOG_DIR/integration-release-lifecycle" \
    --manifest "$CI_LOG_DIR/integration_release_lifecycle_manifest.json" \
    --timeout-seconds "${GONKEN_CI_RELEASE_CASE_TIMEOUT:-240}" \
    --heartbeat-seconds "${GONKEN_CI_HEARTBEAT_SECONDS:-15}"
fi

echo "Selected T0/T1 checks passed: ${SELECTED_PHASES[*]}"
