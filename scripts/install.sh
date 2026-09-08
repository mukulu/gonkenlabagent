#!/usr/bin/env bash
# GonKenLab Agent resumable installer boundary (M3.2).
#
# This milestone proves source-record validation and the step engine only. It
# does not provision packages, releases, models, services, or hardware.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMMON_LIBRARY="$SCRIPT_DIR/lib/common.sh"
ENGINE_LIBRARY="$SCRIPT_DIR/lib/install_engine.sh"

for library in "$COMMON_LIBRARY" "$ENGINE_LIBRARY"; do
  if [[ ! -r "$library" ]]; then
    printf '%s\n' \
      '[ERROR] code=INSTALL_LAYOUT message=missing installer library remediation=use a complete checkpoint/m3.2 checkout' \
      >&2
    exit 66
  fi
done

# shellcheck source=scripts/lib/common.sh
source "$COMMON_LIBRARY"
# shellcheck source=scripts/lib/install_engine.sh
source "$ENGINE_LIBRARY"

SOURCE_RECORD=""
STATE_DIR=""
LOG_DIR=""
ENGINE_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/install.sh --source-record PATH [OPTIONS]

M3.2 validates the bootstrap record and executes only its bounded step-engine
contract. It does not install GonKenLab Agent.

Options:
  --source-record PATH  Private source.record created by bootstrap (required).
  --state-dir PATH      Private advisory state directory (default: beside record).
  --log-dir PATH        Private atomic event directory (default: below state).
  --engine-only         Return success after the M3.2 boundary steps.
  -h, --help            Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --source-record|--state-dir|--log-dir)
      option="$1"
      (($# >= 2)) || {
        usage >&2
        gonken_error "USAGE" "$option requires a value" "provide an absolute path"
        exit 64
      }
      case "$option" in
        --source-record) SOURCE_RECORD="$2" ;;
        --state-dir) STATE_DIR="$2" ;;
        --log-dir) LOG_DIR="$2" ;;
      esac
      shift 2
      ;;
    --engine-only)
      ENGINE_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      gonken_error "USAGE" "unknown option: $1" "run scripts/install.sh --help"
      exit 64
      ;;
  esac
done

[[ -n "$SOURCE_RECORD" ]] || {
  usage >&2
  gonken_error "USAGE" "--source-record is required" "run bootstrap.sh or provide its private source.record"
  exit 64
}

required_commands=(awk chmod date df dirname getconf git id mkdir mktemp mv python3 rm rmdir sha256sum stat uname)
gonken_require_commands "${required_commands[@]}" || exit 69
gonken_load_source_record "$SOURCE_RECORD" || exit $?
gonken_revalidate_source_record || exit $?

record_parent="$(dirname -- "$SOURCE_RECORD")"
STATE_DIR="${STATE_DIR:-$record_parent/install-state}"
LOG_DIR="${LOG_DIR:-$STATE_DIR/logs}"
gonken_validate_absolute_path "$STATE_DIR" "install state directory" || exit 73
gonken_validate_absolute_path "$LOG_DIR" "install log directory" || exit 73

gonken_source_marker_content() {
  local record_hash
  record_hash="$(sha256sum "$GONKEN_SOURCE_RECORD_PATH" | awk '{print $1}')" || return 74
  printf '%s|%s\n' "$record_hash" "${GONKEN_SOURCE_RECORD[resolved_commit]}"
}

gonken_source_step_precondition() {
  [[ -n "$GONKEN_SOURCE_RECORD_PATH" && -f "$GONKEN_SOURCE_RECORD_PATH" ]]
}

gonken_source_step_postcondition() {
  local marker="$STATE_DIR/artifacts/source-validation.record"
  local content expected actual=""
  content="$(gonken_source_marker_content)" || return 2
  expected="format=gonken-source-validation-v1"$'\n'"record_and_commit=$content"
  [[ -f "$marker" && ! -L "$marker" ]] || return 1
  actual="$(<"$marker")" || return 2
  GONKEN_STEP_EVIDENCE="source_${GONKEN_SOURCE_RECORD[resolved_commit]}"
  [[ "$actual" == "$expected" ]]
}

gonken_source_step_action() {
  local step_id="$1"
  local content
  content="$(gonken_source_marker_content)" || return 74
  gonken_step_checkpoint "$step_id" "during" || return $?
  gonken_atomic_record "$STATE_DIR/artifacts/source-validation.record" 0600 \
    'format=gonken-source-validation-v1' \
    "record_and_commit=$content"
}

gonken_engine_step_precondition() {
  [[ "${GONKEN_STEP_VERSION[source_record_validation]:-}" == "1" ]]
}

gonken_engine_step_postcondition() {
  local marker="$STATE_DIR/artifacts/engine-contract.record"
  local expected actual=""
  expected='format=gonken-engine-contract-v1'$'\n''scope=state_and_resume_only'$'\n''provisioning=forbidden_before_m3_3'
  [[ -f "$marker" && ! -L "$marker" ]] || return 1
  actual="$(<"$marker")" || return 2
  GONKEN_STEP_EVIDENCE="engine_contract_v1"
  [[ "$actual" == "$expected" ]]
}

gonken_engine_step_action() {
  local step_id="$1"
  gonken_step_checkpoint "$step_id" "during" || return $?
  gonken_atomic_record "$STATE_DIR/artifacts/engine-contract.record" 0600 \
    'format=gonken-engine-contract-v1' \
    'scope=state_and_resume_only' \
    'provisioning=forbidden_before_m3_3'
}

gonken_engine_initialize "$STATE_DIR" "$LOG_DIR" || exit $?
gonken_prepare_private_directory "$STATE_DIR/artifacts" "installer artifact directory" || exit $?

gonken_register_step \
  "source_record_validation" "1" \
  "gonken_source_step_precondition" "gonken_source_step_action" "gonken_source_step_postcondition" \
  "engine_state_and_$STATE_DIR/artifacts/source-validation.record" \
  "revalidate_source_then_repair_marker_when_probe_fails" \
  "remove_only_the_validation_marker_if_this_boundary_is_abandoned" || exit $?

gonken_register_step \
  "engine_contract" "1" \
  "gonken_engine_step_precondition" "gonken_engine_step_action" "gonken_engine_step_postcondition" \
  "engine_state_and_$STATE_DIR/artifacts/engine-contract.record" \
  "skip_when_exact_marker_probe_passes_otherwise_rewrite_atomically" \
  "remove_only_the_engine_contract_marker_if_this_boundary_is_abandoned" || exit $?

if gonken_run_registered_steps; then
  :
else
  result=$?
  exit "$result"
fi

printf '[OK] code=M3_2_ENGINE_COMPLETE state=%s logs=%s\n' "$STATE_DIR" "$LOG_DIR"
if ((ENGINE_ONLY == 1)); then
  exit 0
fi

gonken_error \
  "M3_3_UNAVAILABLE" \
  "step engine passed, but immutable application release provisioning is not implemented" \
  "retain this private state and continue only after checkpoint/m3.3" || true
exit 69
