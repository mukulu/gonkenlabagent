#!/usr/bin/env bash
# Deterministic fake-step process used only by M3.2 integration tests.

set -Eeuo pipefail

if (($# != 3)); then
  echo "usage: install_engine_harness.sh STATE_DIR LOG_DIR WORK_DIR" >&2
  exit 64
fi

STATE_DIR="$1"
LOG_DIR="$2"
WORK_DIR="$3"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$PROJECT_ROOT/scripts/lib/common.sh"
# shellcheck source=scripts/lib/install_engine.sh
source "$PROJECT_ROOT/scripts/lib/install_engine.sh"

fake_precondition() {
  [[ -d "$WORK_DIR" && ! -L "$WORK_DIR" ]]
}

fake_postcondition() {
  local step_id="$1"
  local marker="$WORK_DIR/$step_id.marker"
  local actual=""
  [[ -f "$marker" && ! -L "$marker" ]] || return 1
  actual="$(<"$marker")" || return 2
  GONKEN_STEP_EVIDENCE="${step_id}_marker_v1"
  [[ "$actual" == "complete=$step_id" ]]
}

fake_action() {
  local step_id="$1"
  local partial="$WORK_DIR/$step_id.partial"
  printf 'partial=%s\n' "$step_id" >"$partial"
  chmod 0600 "$partial"
  gonken_track_temp "$partial"
  gonken_step_checkpoint "$step_id" "during" || return $?
  printf 'complete=%s\n' "$step_id" >"$partial"
  mv -- "$partial" "$WORK_DIR/$step_id.marker"
  gonken_untrack_temp "$partial"
}

gonken_engine_initialize "$STATE_DIR" "$LOG_DIR"
gonken_register_step \
  "alpha" "1" "fake_precondition" "fake_action" "fake_postcondition" \
  "engine_state_and_$WORK_DIR/alpha.marker" \
  "probe_then_repair_alpha" "remove_alpha_marker_only"
gonken_register_step \
  "beta" "1" "fake_precondition" "fake_action" "fake_postcondition" \
  "engine_state_and_$WORK_DIR/beta.marker" \
  "probe_then_repair_beta" "remove_beta_marker_only"
gonken_run_registered_steps
