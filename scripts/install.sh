#!/usr/bin/env bash
# GonKenLab Agent resumable installer (through M3.3).
#
# M3.3 adds immutable application releases and durable activation. It still
# does not provision Ollama, speech artifacts, services, or hardware.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMMON_LIBRARY="$SCRIPT_DIR/lib/common.sh"
ENGINE_LIBRARY="$SCRIPT_DIR/lib/install_engine.sh"
RELEASE_MANAGER="$SCRIPT_DIR/release_manager.py"

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
STATE_DIR_EXPLICIT=0
LOG_DIR=""
LOG_DIR_EXPLICIT=0
SYSTEM_ROOT=""
SYSTEM_ROOT_EXPLICIT=0
ENGINE_ONLY=0
RELEASE_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/install.sh --source-record PATH [OPTIONS]

M3.3 validates the bootstrap record, builds an immutable application release,
and activates it through the durable journal. Models and services remain absent.

Options:
  --source-record PATH  Private source.record created by bootstrap (required).
  --state-dir PATH      Private advisory state directory (default: beside record).
  --log-dir PATH        Private atomic event directory (default: below state).
  --system-root PATH    Development-only FHS test root (default: private staging).
  --engine-only         Return success after the M3.2 boundary steps.
  --release-only        Return success after the M3.3 release boundary.
  -h, --help            Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --source-record|--state-dir|--log-dir|--system-root)
      option="$1"
      (($# >= 2)) || {
        usage >&2
        gonken_error "USAGE" "$option requires a value" "provide an absolute path"
        exit 64
      }
      case "$option" in
        --source-record) SOURCE_RECORD="$2" ;;
        --state-dir)
          STATE_DIR="$2"
          STATE_DIR_EXPLICIT=1
          ;;
        --log-dir)
          LOG_DIR="$2"
          LOG_DIR_EXPLICIT=1
          ;;
        --system-root)
          SYSTEM_ROOT="$2"
          SYSTEM_ROOT_EXPLICIT=1
          ;;
      esac
      shift 2
      ;;
    --engine-only)
      ENGINE_ONLY=1
      shift
      ;;
    --release-only)
      RELEASE_ONLY=1
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

required_commands=(awk chmod date df dirname getconf git id mkdir mktemp mv python3 readlink rm rmdir sha256sum stat uname)
gonken_require_commands "${required_commands[@]}" || exit 69
gonken_load_source_record "$SOURCE_RECORD" || exit $?
gonken_revalidate_source_record || exit $?

record_parent="$(dirname -- "$SOURCE_RECORD")"

if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]]; then
  if [[ "$(id -u)" != "0" ]]; then
    gonken_error "INSTALL_PRIVILEGE" "target release installation requires root after preflight" "rerun bootstrap and allow its validated sudo transition"
    exit 77
  fi
  if ((SYSTEM_ROOT_EXPLICIT == 1)) && [[ "$SYSTEM_ROOT" != "/" ]]; then
    gonken_error "INSTALL_ROOT" "target mode cannot redirect the installed-system root" "use the real supported target or development mode"
    exit 64
  fi
  SYSTEM_ROOT="/"
  RELEASE_PROFILE="core-pi-trixie-py313"
  SERVICE_USER="gonken-agent"
  gonken_require_commands apt-get || exit 69
else
  SYSTEM_ROOT="${SYSTEM_ROOT:-$record_parent/development-root}"
  gonken_validate_absolute_path "$SYSTEM_ROOT" "development system root" || exit 73
  if ((ENGINE_ONLY == 0)); then
    gonken_prepare_private_directory "$SYSTEM_ROOT" "development system root" || exit $?
  fi
  RELEASE_PROFILE="dev-py312"
  SERVICE_USER="$(id -un)" || exit 73
fi

if [[ "$SYSTEM_ROOT" == "/" ]]; then
  RELEASE_ROOT="/usr/local/lib/gonken-agent"
  INSTALL_STATE_ROOT="/var/lib/gonken-agent/install"
  BIN_ROOT="/usr/local/bin"
else
  RELEASE_ROOT="$SYSTEM_ROOT/usr/local/lib/gonken-agent"
  INSTALL_STATE_ROOT="$SYSTEM_ROOT/var/lib/gonken-agent/install"
  BIN_ROOT="$SYSTEM_ROOT/usr/local/bin"
fi

if ((ENGINE_ONLY == 1)); then
  STATE_DIR="${STATE_DIR:-$record_parent/install-state}"
  LOG_DIR="${LOG_DIR:-$STATE_DIR/logs}"
else
  if ((STATE_DIR_EXPLICIT == 1 || LOG_DIR_EXPLICIT == 1)); then
    gonken_error "INSTALL_STATE" "full release installation cannot redirect its global lock/state paths" "use --system-root in development or omit state/log overrides on target"
    exit 64
  fi
  STATE_DIR="$INSTALL_STATE_ROOT/engine"
  LOG_DIR="$INSTALL_STATE_ROOT/logs"
fi
gonken_validate_absolute_path "$STATE_DIR" "install state directory" || exit 73
gonken_validate_absolute_path "$LOG_DIR" "install log directory" || exit 73

[[ -r "$RELEASE_MANAGER" ]] || {
  gonken_error "INSTALL_LAYOUT" "missing release manager" "use a complete checkpoint/m3.3 checkout"
  exit 66
}

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

gonken_prerequisite_precondition() {
  [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "development" || "$(id -u)" == "0" ]]
}

gonken_prerequisite_postcondition() {
  local command_name
  for command_name in git python3; do
    command -v "$command_name" >/dev/null 2>&1 || return 1
  done
  if ! python3 -c 'import setuptools, venv' >/dev/null 2>&1; then
    [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]] && return 1
    return 69
  fi
  if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]]; then
    for command_name in getent groupadd runuser useradd; do
      command -v "$command_name" >/dev/null 2>&1 || return 1
    done
  fi
  GONKEN_STEP_EVIDENCE="python_${GONKEN_SOURCE_RECORD[python_version]}_${RELEASE_PROFILE}"
}

gonken_prerequisite_action() {
  local step_id="$1"
  [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]] || return 69
  DEBIAN_FRONTEND=noninteractive apt-get update || return 69
  gonken_step_checkpoint "$step_id" "during" || return $?
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git python3-pip python3-setuptools python3-venv util-linux || return 69
}

gonken_account_precondition() {
  gonken_prerequisite_postcondition
}

gonken_account_postcondition() {
  if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "development" ]]; then
    GONKEN_STEP_EVIDENCE="development_user_$SERVICE_USER"
    return 0
  fi
  local passwd_record group_record name password uid gid gecos home shell group_name group_password group_gid members
  passwd_record="$(getent passwd gonken-agent)" || return 1
  group_record="$(getent group gonken-agent)" || return 2
  IFS=: read -r name password uid gid gecos home shell <<<"$passwd_record"
  IFS=: read -r group_name group_password group_gid members <<<"$group_record"
  if [[ "$name" != "gonken-agent" || "$gid" != "$group_gid" \
      || "$home" != "/var/lib/gonken-agent" || "$shell" != "/usr/sbin/nologin" ]]; then
    return 2
  fi
  GONKEN_STEP_EVIDENCE="service_uid_${uid}_gid_${gid}"
}

gonken_account_action() {
  local step_id="$1"
  [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]] || return 0
  getent group gonken-agent >/dev/null 2>&1 || groupadd --system gonken-agent || return 73
  gonken_step_checkpoint "$step_id" "during" || return $?
  getent passwd gonken-agent >/dev/null 2>&1 || useradd --system \
    --gid gonken-agent --home-dir /var/lib/gonken-agent \
    --shell /usr/sbin/nologin --no-create-home gonken-agent || return 73
}

gonken_layout_precondition() {
  gonken_account_postcondition
}

gonken_layout_postcondition() {
  local entrypoint="$BIN_ROOT/gonken-agent"
  [[ -d "$RELEASE_ROOT" && ! -L "$RELEASE_ROOT" \
    && -d "$RELEASE_ROOT/releases" && ! -L "$RELEASE_ROOT/releases" \
    && -d "$INSTALL_STATE_ROOT" && ! -L "$INSTALL_STATE_ROOT" \
    && "$(stat -c %a -- "$INSTALL_STATE_ROOT" 2>/dev/null)" == "700" \
    && -L "$entrypoint" ]] || return 1
  [[ "$(readlink -- "$entrypoint")" == "$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$RELEASE_ROOT/current/.venv/bin/gonken-agent" "$BIN_ROOT")" ]] || return 1
  GONKEN_STEP_EVIDENCE="layout_${RELEASE_ROOT}"
}

gonken_layout_action() {
  local step_id="$1"
  gonken_step_checkpoint "$step_id" "during" || return $?
  python3 "$RELEASE_MANAGER" init-layout \
    --release-root "$RELEASE_ROOT" \
    --state-root "$INSTALL_STATE_ROOT" \
    --bin-root "$BIN_ROOT"
}

gonken_release_precondition() {
  gonken_layout_postcondition
}

gonken_release_postcondition() {
  python3 "$RELEASE_MANAGER" validate \
    --release "$RELEASE_ROOT/releases/${GONKEN_SOURCE_RECORD[resolved_commit]}" \
    --commit "${GONKEN_SOURCE_RECORD[resolved_commit]}" \
    --profile "$RELEASE_PROFILE" \
    --service-user "$SERVICE_USER" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="release_${GONKEN_SOURCE_RECORD[resolved_commit]}"
}

gonken_release_action() {
  python3 "$RELEASE_MANAGER" build \
    --source-url "${GONKEN_SOURCE_RECORD[source_url]}" \
    --source-ref "${GONKEN_SOURCE_RECORD[requested_ref]}" \
    --commit "${GONKEN_SOURCE_RECORD[resolved_commit]}" \
    --release-root "$RELEASE_ROOT" \
    --profile "$RELEASE_PROFILE" \
    --service-user "$SERVICE_USER"
}

gonken_activation_precondition() {
  gonken_release_postcondition
}

gonken_activation_postcondition() {
  python3 "$RELEASE_MANAGER" status \
    --release-root "$RELEASE_ROOT" \
    --state-root "$INSTALL_STATE_ROOT" \
    --service-user "$SERVICE_USER" \
    --expect-commit "${GONKEN_SOURCE_RECORD[resolved_commit]}" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="active_${GONKEN_SOURCE_RECORD[resolved_commit]}"
}

gonken_activation_action() {
  python3 "$RELEASE_MANAGER" activate \
    --release-root "$RELEASE_ROOT" \
    --state-root "$INSTALL_STATE_ROOT" \
    --service-user "$SERVICE_USER" \
    --commit "${GONKEN_SOURCE_RECORD[resolved_commit]}"
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

if ((ENGINE_ONLY == 0)); then
  gonken_register_step \
    "release_prerequisites" "1" \
    "gonken_prerequisite_precondition" "gonken_prerequisite_action" "gonken_prerequisite_postcondition" \
    "target_only_apt_bootstrap_prerequisites" \
    "probe_distro_tools_then_install_only_missing_target_prerequisites" \
    "apt_is_convergent_and_not_project_transactional" || exit $?

  gonken_register_step \
    "runtime_account" "1" \
    "gonken_account_precondition" "gonken_account_action" "gonken_account_postcondition" \
    "target_only_system_group_and_nonlogin_user" \
    "skip_exact_account_or_create_missing_account_once" \
    "existing_accounts_are_never_deleted_or_rewritten" || exit $?

  gonken_register_step \
    "release_layout" "1" \
    "gonken_layout_precondition" "gonken_layout_action" "gonken_layout_postcondition" \
    "root_owned_release_state_and_stable_entrypoint_paths" \
    "repair_missing_owned_directories_and_constant_entrypoint_link" \
    "remove_only_project_owned_empty_layout_after_manual_review" || exit $?

  gonken_register_step \
    "immutable_release" "1" \
    "gonken_release_precondition" "gonken_release_action" "gonken_release_postcondition" \
    "verified_source_candidate_venv_and_release_${GONKEN_SOURCE_RECORD[resolved_commit]}" \
    "validate_final_release_or_clean_identity_scoped_partial_and_rebuild" \
    "failed_candidate_never_changes_current" || exit $?

  gonken_register_step \
    "activate_release" "1" \
    "gonken_activation_precondition" "gonken_activation_action" "gonken_activation_postcondition" \
    "durable_activation_journal_and_atomic_current_pointer" \
    "reconcile_known_phase_then_complete_or_restore_previous_release" \
    "postcheck_failure_restores_previous_validated_release" || exit $?
fi

if gonken_run_registered_steps; then
  :
else
  result=$?
  exit "$result"
fi

if ((ENGINE_ONLY == 1)); then
  printf '[OK] code=M3_2_ENGINE_COMPLETE state=%s logs=%s\n' "$STATE_DIR" "$LOG_DIR"
  exit 0
fi

printf '[OK] code=M3_3_RELEASE_COMPLETE commit=%s release_root=%s\n' \
  "${GONKEN_SOURCE_RECORD[resolved_commit]}" "$RELEASE_ROOT"
if ((RELEASE_ONLY == 1)); then
  exit 0
fi

gonken_error \
  "M3_4_UNAVAILABLE" \
  "immutable release passed, but Ollama and model provisioning are not implemented" \
  "retain the validated release and continue only after checkpoint/m3.4" || true
exit 69
