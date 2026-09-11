#!/usr/bin/env bash
# GonKenLab Agent resumable installer and appliance-readiness convergence.

set -Eeuo pipefail

# Avoid package-manager noise when the image advertises an ungenerated site locale.
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

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
OLLAMA_ONLY=0
SPEECH_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/install.sh --source-record PATH [OPTIONS]

M6.2 validates and activates the application release, provisions the pinned
Ollama runtime/model and Whisper/Piper speech chain on a supported target, then
installs the governed headless service and prints a content-free readiness summary.

Options:
  --source-record PATH  Private source.record created by bootstrap (required).
  --state-dir PATH      Private advisory state directory (default: beside record).
  --log-dir PATH        Private atomic event directory (default: below state).
  --system-root PATH    Development-only FHS test root (default: private staging).
  --engine-only         Return success after the M3.2 boundary steps.
  --release-only        Return success after the M3.3 release boundary.
  --ollama-only         Return success after the M3.4 Ollama/model boundary.
  --speech-only         Return success after the M3.5 speech boundary.
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
    --ollama-only)
      OLLAMA_ONLY=1
      shift
      ;;
    --speech-only)
      SPEECH_ONLY=1
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
    for command_name in aplay arecord cmake c++ getent groupadd runuser systemd-tmpfiles tar useradd usermod zstd; do
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
    alsa-utils build-essential cmake \
    ca-certificates git python3-pip python3-setuptools python3-venv \
    tar util-linux zstd || return 69
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
  local memberships
  memberships="$(id -nG gonken-agent 2>/dev/null)" || return 2
  [[ " $memberships " == *" audio "* ]] || return 1
  if getent group gpio >/dev/null 2>&1; then
    [[ " $memberships " == *" gpio "* ]] || return 1
  fi
  GONKEN_STEP_EVIDENCE="service_uid_${uid}_gid_${gid}_audio_gpio_access"
}

gonken_account_action() {
  local step_id="$1"
  [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" ]] || return 0
  getent group gonken-agent >/dev/null 2>&1 || groupadd --system gonken-agent || return 73
  gonken_step_checkpoint "$step_id" "during" || return $?
  getent passwd gonken-agent >/dev/null 2>&1 || useradd --system \
    --gid gonken-agent --home-dir /var/lib/gonken-agent \
    --shell /usr/sbin/nologin --no-create-home gonken-agent || return 73
  local groups="audio"
  getent group audio >/dev/null 2>&1 || {
    gonken_error "INSTALL_ACCOUNT" "required audio group is missing" "repair Raspberry Pi OS account/group database"
    return 73
  }
  if getent group gpio >/dev/null 2>&1; then
    groups="audio,gpio"
  fi
  usermod -a -G "$groups" gonken-agent || return 73
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

gonken_ollama_account_postcondition() {
  local passwd_record group_record name password uid gid gecos home shell group_name group_password group_gid members
  passwd_record="$(getent passwd ollama)" || return 1
  group_record="$(getent group ollama)" || return 2
  IFS=: read -r name password uid gid gecos home shell <<<"$passwd_record"
  IFS=: read -r group_name group_password group_gid members <<<"$group_record"
  [[ "$name" == "ollama" && "$gid" == "$group_gid" \
    && "$home" == "/var/lib/ollama" && "$shell" == "/usr/sbin/nologin" \
    && -d /var/lib/ollama && ! -L /var/lib/ollama \
    && -d /var/lib/ollama/models && ! -L /var/lib/ollama/models \
    && "$(stat -c %U:%G /var/lib/ollama/models 2>/dev/null)" == "ollama:ollama" \
    && "$(stat -c %a /var/lib/ollama/models 2>/dev/null)" == "750" ]] || return 2
  GONKEN_STEP_EVIDENCE="ollama_uid_${uid}_gid_${gid}"
}

gonken_ollama_account_action() {
  local step_id="$1"
  local path
  for path in /var/lib/ollama /var/lib/ollama/models; do
    if [[ -L "$path" || (-e "$path" && ! -d "$path") ]]; then
      gonken_error "OLLAMA_LAYOUT" "unsafe existing Ollama data path: $path" "move the conflict after administrator review"
      return 73
    fi
  done
  getent group ollama >/dev/null 2>&1 || groupadd --system ollama || return 73
  gonken_step_checkpoint "$step_id" "during" || return $?
  getent passwd ollama >/dev/null 2>&1 || useradd --system \
    --gid ollama --home-dir /var/lib/ollama \
    --shell /usr/sbin/nologin --no-create-home ollama || return 73
  mkdir -p /var/lib/ollama/models || return 73
  chown ollama:ollama /var/lib/ollama /var/lib/ollama/models || return 73
  chmod 0750 /var/lib/ollama /var/lib/ollama/models || return 73
}

gonken_load_effective_ollama_config() {
  local config_json
  config_json="$("$BIN_ROOT/gonken-agent" config show --effective --json)" || return 65
  mapfile -t OLLAMA_EFFECTIVE < <(python3 -c '
import json, sys
value = json.load(sys.stdin)["config"]
print(value["llm"]["base_url"])
print(value["llm"]["model"])
print(value["llm"]["context_tokens"])
' <<<"$config_json") || return 65
  [[ "${#OLLAMA_EFFECTIVE[@]}" == "3" ]] || return 65
  OLLAMA_ENDPOINT="${OLLAMA_EFFECTIVE[0]}"
  OLLAMA_MODEL="${OLLAMA_EFFECTIVE[1]}"
  OLLAMA_CONTEXT_TOKENS="${OLLAMA_EFFECTIVE[2]}"
}

gonken_ollama_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/ollama_manager.py"
}

gonken_ollama_manifest() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/packaging/ollama-artifacts.toml"
}

gonken_speech_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/speech_manager.py"
}

gonken_speech_manifest() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/packaging/speech-artifacts.toml"
}

gonken_install_summary_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/install_summary.py"
}

gonken_service_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/service_manager.py"
}

gonken_service_unit_template() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/packaging/systemd/gonken-agent.service"
}

gonken_service_tmpfiles_template() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/packaging/tmpfiles/gonken-agent.conf"
}

gonken_bluetooth_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/bluetooth_manager.py"
}

gonken_bluetooth_unit_template() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/packaging/systemd/gonken-bluetooth-autoconnect.service"
}

gonken_appliance_manager() {
  printf '%s\n' "$RELEASE_ROOT/current/maintenance/appliance_manager.py"
}

readonly BLUETOOTH_RECORD="/etc/gonken-agent/bluetooth-device.record"
readonly BLUETOOTH_AUDIO_USER="gonken-agent"

gonken_ollama_template_arguments() {
  printf '%s\n' \
    --endpoint "$OLLAMA_ENDPOINT" \
    --context-tokens "$OLLAMA_CONTEXT_TOKENS" \
    --unit-template "$RELEASE_ROOT/current/maintenance/packaging/systemd/ollama.service" \
    --dropin-template "$RELEASE_ROOT/current/maintenance/packaging/systemd/ollama.service.d/gonken-agent.conf" \
    --systemctl /usr/bin/systemctl
}

gonken_ollama_binary_postcondition() {
  python3 "$(gonken_ollama_manager)" binary-status \
    --manifest "$(gonken_ollama_manifest)" --system-root / >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="ollama_binary_pinned"
}

gonken_ollama_binary_action() {
  python3 "$(gonken_ollama_manager)" install-binary \
    --manifest "$(gonken_ollama_manifest)" --system-root / --zstd /usr/bin/zstd
}

gonken_ollama_service_postcondition() {
  local -a arguments
  gonken_load_effective_ollama_config || return 65
  mapfile -t arguments < <(gonken_ollama_template_arguments)
  python3 "$(gonken_ollama_manager)" service-status \
    --manifest "$(gonken_ollama_manifest)" --system-root / \
    "${arguments[@]}" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="ollama_service_${OLLAMA_ENDPOINT}"
}

gonken_ollama_service_action() {
  local -a arguments
  gonken_load_effective_ollama_config || return 65
  mapfile -t arguments < <(gonken_ollama_template_arguments)
  python3 "$(gonken_ollama_manager)" install-service \
    --manifest "$(gonken_ollama_manifest)" --system-root / "${arguments[@]}"
}

gonken_ollama_model_postcondition() {
  local -a arguments
  gonken_load_effective_ollama_config || return 65
  mapfile -t arguments < <(gonken_ollama_template_arguments)
  python3 "$(gonken_ollama_manager)" model-status \
    --manifest "$(gonken_ollama_manifest)" --system-root / \
    "${arguments[@]}" --model "$OLLAMA_MODEL" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="ollama_model_${OLLAMA_MODEL}"
}

gonken_ollama_model_action() {
  local -a arguments
  gonken_load_effective_ollama_config || return 65
  mapfile -t arguments < <(gonken_ollama_template_arguments)
  python3 "$(gonken_ollama_manager)" provision-model \
    --manifest "$(gonken_ollama_manifest)" --system-root / \
    "${arguments[@]}" --model "$OLLAMA_MODEL"
}


gonken_load_effective_speech_config() {
  local config_json
  config_json="$("$BIN_ROOT/gonken-agent" config show --effective --json --show-paths)" || return 65
  mapfile -t SPEECH_EFFECTIVE < <(python3 -c '
import json, sys
value = json.load(sys.stdin)["config"]
print(value["stt"]["model"])
print(value["stt"]["threads"])
print(value["tts"]["voice"])
print(value["paths"]["whisper_binary"])
print(value["paths"]["whisper_model"])
print(value["paths"]["piper_voice"])
' <<<"$config_json") || return 65
  if [[ "${#SPEECH_EFFECTIVE[@]}" != "6" ]]; then
    gonken_error "SPEECH_CONFIG" "effective speech configuration output is incomplete" "restore the validated packaged configuration and rerun"
    return 65
  fi
  SPEECH_STT_MODEL="${SPEECH_EFFECTIVE[0]}"
  SPEECH_STT_THREADS="${SPEECH_EFFECTIVE[1]}"
  SPEECH_TTS_VOICE="${SPEECH_EFFECTIVE[2]}"
  SPEECH_WHISPER_BINARY="${SPEECH_EFFECTIVE[3]}"
  SPEECH_WHISPER_MODEL="${SPEECH_EFFECTIVE[4]}"
  SPEECH_PIPER_VOICE="${SPEECH_EFFECTIVE[5]}"
  if [[ "$SPEECH_STT_MODEL" != "base.en-q5_1" \
      || "$SPEECH_TTS_VOICE" != "en_US-ljspeech-medium" \
      || "$SPEECH_WHISPER_BINARY" != "/usr/local/bin/whisper-cli" \
      || "$SPEECH_WHISPER_MODEL" != "/var/lib/gonken-agent/models/whisper/base.en-q5_1.bin" \
      || "$SPEECH_PIPER_VOICE" != "/var/lib/gonken-agent/models/piper/en_US-ljspeech-medium/en_US-ljspeech-medium.onnx" ]]; then
    gonken_error "SPEECH_CONFIG" "effective speech model or runtime paths differ from the pinned installer contract" "review /etc/gonken-agent/config.toml and restore the supported speech defaults"
    return 65
  fi
  if [[ ! "$SPEECH_STT_THREADS" =~ ^[0-9]+$ \
      || "$SPEECH_STT_THREADS" -lt 1 || "$SPEECH_STT_THREADS" -gt 16 ]]; then
    gonken_error "SPEECH_CONFIG" "effective STT thread count is outside the supported range" "set stt.threads between 1 and 16 and rerun"
    return 65
  fi
}

gonken_speech_model_arguments() {
  printf '%s\n'     --whisper-model-path "$SPEECH_WHISPER_MODEL"     --piper-voice-path "$SPEECH_PIPER_VOICE"
}

gonken_whisper_postcondition() {
  python3 "$(gonken_speech_manager)" whisper-status     --manifest "$(gonken_speech_manifest)" --system-root / >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="whisper_runtime_pinned"
}

gonken_whisper_action() {
  python3 "$(gonken_speech_manager)" install-whisper     --manifest "$(gonken_speech_manifest)" --system-root /     --git /usr/bin/git --cmake /usr/bin/cmake
}

gonken_piper_postcondition() {
  python3 "$(gonken_speech_manager)" piper-status     --manifest "$(gonken_speech_manifest)" --system-root / >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="piper_runtime_pinned"
}

gonken_piper_action() {
  python3 "$(gonken_speech_manager)" install-piper     --manifest "$(gonken_speech_manifest)" --system-root /
}

gonken_speech_models_postcondition() {
  local -a arguments
  gonken_load_effective_speech_config || return 65
  mapfile -t arguments < <(gonken_speech_model_arguments)
  python3 "$(gonken_speech_manager)" models-status     --manifest "$(gonken_speech_manifest)" --system-root /     "${arguments[@]}" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="speech_models_${SPEECH_STT_MODEL}_${SPEECH_TTS_VOICE}"
}

gonken_speech_models_action() {
  local -a arguments
  gonken_load_effective_speech_config || return 65
  mapfile -t arguments < <(gonken_speech_model_arguments)
  python3 "$(gonken_speech_manager)" provision-models     --manifest "$(gonken_speech_manifest)" --system-root / "${arguments[@]}"
}

gonken_speech_smoke_postcondition() {
  local -a arguments
  gonken_load_effective_speech_config || return 65
  mapfile -t arguments < <(gonken_speech_model_arguments)
  python3 "$(gonken_speech_manager)" smoke-status     --manifest "$(gonken_speech_manifest)" --system-root /     "${arguments[@]}" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="speech_smoke_${SPEECH_TTS_VOICE}"
}

gonken_speech_smoke_action() {
  local -a arguments
  gonken_load_effective_speech_config || return 65
  mapfile -t arguments < <(gonken_speech_model_arguments)
  python3 "$(gonken_speech_manager)" run-smoke     --manifest "$(gonken_speech_manifest)" --system-root /     "${arguments[@]}" --threads "$SPEECH_STT_THREADS"
}

gonken_app_service_postcondition() {
  python3 "$(gonken_service_manager)" status \
    --system-root / \
    --unit-template "$(gonken_service_unit_template)" \
    --tmpfiles-template "$(gonken_service_tmpfiles_template)" \
    --systemctl /usr/bin/systemctl \
    --systemd-tmpfiles /usr/bin/systemd-tmpfiles >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="gonken_agent_service_enabled_headless_degraded"
}

gonken_app_service_action() {
  python3 "$(gonken_service_manager)" install \
    --system-root / \
    --unit-template "$(gonken_service_unit_template)" \
    --tmpfiles-template "$(gonken_service_tmpfiles_template)" \
    --systemctl /usr/bin/systemctl \
    --systemd-tmpfiles /usr/bin/systemd-tmpfiles
}

gonken_bluetooth_stack_postcondition() {
  python3 "$(gonken_bluetooth_manager)" stack-status \
    --audio-user "$BLUETOOTH_AUDIO_USER" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="bluetooth_stack_pipewire_bluez_headless"
}

gonken_bluetooth_stack_action() {
  printf '[RUNNING] code=BLUETOOTH_PACKAGES message=installing_headless_bluez_pipewire_stack\n'
  DEBIAN_FRONTEND=noninteractive apt-get update || return 69
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    bluez rfkill pipewire pipewire-pulse pipewire-audio pipewire-alsa \
    pulseaudio-utils wireplumber || return 69
  python3 "$(gonken_bluetooth_manager)" prepare \
    --audio-user "$BLUETOOTH_AUDIO_USER"
}

gonken_bluetooth_pair_postcondition() {
  python3 "$(gonken_bluetooth_manager)" status \
    --audio-user "$BLUETOOTH_AUDIO_USER" \
    --record "$BLUETOOTH_RECORD" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="bluetooth_device_paired_trusted"
}

gonken_bluetooth_pair_action() {
  local selector="${GONKEN_SOURCE_RECORD[bluetooth_device]:-}"
  python3 "$(gonken_bluetooth_manager)" pair \
    --audio-user "$BLUETOOTH_AUDIO_USER" \
    --record "$BLUETOOTH_RECORD" \
    --selector "$selector" \
    --timeout 120
}

gonken_bluetooth_autoconnect_postcondition() {
  python3 "$(gonken_bluetooth_manager)" autoconnect-status \
    --record "$BLUETOOTH_RECORD" \
    --unit-template "$(gonken_bluetooth_unit_template)" >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="bluetooth_trusted_device_autoconnect_service"
}

gonken_bluetooth_autoconnect_action() {
  python3 "$(gonken_bluetooth_manager)" install-autoconnect \
    --record "$BLUETOOTH_RECORD" \
    --unit-template "$(gonken_bluetooth_unit_template)"
}

gonken_appliance_postcondition() {
  python3 "$(gonken_appliance_manager)" status >/dev/null 2>&1 || return 1
  GONKEN_STEP_EVIDENCE="voice_appliance_ready_and_enabled"
}

gonken_appliance_action() {
  python3 "$(gonken_appliance_manager)" activate --timeout 180
}

if ((ENGINE_ONLY == 0)); then
  SERVICE_HOME="$(dirname -- "$INSTALL_STATE_ROOT")" || exit 73
  if [[ -L "$SERVICE_HOME" || (-e "$SERVICE_HOME" && ! -d "$SERVICE_HOME") ]]; then
    gonken_error "INSTALL_LAYOUT" "service home is not a real directory: $SERVICE_HOME" "replace the unsafe path after inspection"
    exit 73
  fi
  mkdir -p -- "$SERVICE_HOME" || exit 73
  if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" && "$(stat -c %u -- "$SERVICE_HOME")" != "0" ]]; then
    gonken_error "INSTALL_LAYOUT" "target service home must be root-owned: $SERVICE_HOME" "restore root ownership before installation"
    exit 73
  fi
  chmod 0755 "$SERVICE_HOME" || exit 73
  if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" \
      && "$INSTALL_STATE_ROOT" == "/var/lib/gonken-agent/install" ]]; then
    # FIX4 migration: repair only the known historical 0755 drift of the
    # root-owned managed installer state.  New installs and all other private
    # directories remain strictly mode 0700.
    gonken_prepare_private_directory \
      "$INSTALL_STATE_ROOT" "private install state root" "repair-owned-0755" || exit $?
  else
    gonken_prepare_private_directory "$INSTALL_STATE_ROOT" "private install state root" || exit $?
  fi
fi

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
    "release_prerequisites" "4" \
    "gonken_prerequisite_precondition" "gonken_prerequisite_action" "gonken_prerequisite_postcondition" \
    "target_only_apt_bootstrap_prerequisites" \
    "probe_distro_tools_then_install_only_missing_target_prerequisites" \
    "apt_is_convergent_and_not_project_transactional" || exit $?

  gonken_register_step \
    "runtime_account" "2" \
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

  if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" && "$RELEASE_ONLY" == "0" ]]; then
    gonken_register_step \
      "ollama_account_and_store" "1" \
      "gonken_activation_postcondition" "gonken_ollama_account_action" "gonken_ollama_account_postcondition" \
      "dedicated_ollama_account_and_private_model_store" \
      "accept_only_exact_existing_identity_or_create_once" \
      "existing_accounts_and_model_blobs_are_never_deleted" || exit $?

    gonken_register_step \
      "ollama_binary" "1" \
      "gonken_ollama_account_postcondition" "gonken_ollama_binary_action" "gonken_ollama_binary_postcondition" \
      "checksum_verified_immutable_named_ollama_release" \
      "resume_download_then_validate_or_activate_exact_release" \
      "unverified_payload_never_reaches_the_stable_entrypoint" || exit $?

    gonken_register_step \
      "ollama_service" "1" \
      "gonken_ollama_binary_postcondition" "gonken_ollama_service_action" "gonken_ollama_service_postcondition" \
      "exact_systemd_unit_dropin_enablement_and_loopback_readiness" \
      "refuse_conflicts_then_restart_and_probe_exact_api_version" \
      "administrator_owned_conflicting_units_are_never_overwritten" || exit $?

    gonken_register_step \
      "ollama_model" "1" \
      "gonken_ollama_service_postcondition" "gonken_ollama_model_action" "gonken_ollama_model_postcondition" \
      "authoritative_tag_full_digest_and_deterministic_smoke_record" \
      "resume_blob_pull_then_require_digest_prefix_and_inference" \
      "existing_model_blobs_are_retained_and_tag_drift_fails_closed" || exit $?

    if ((OLLAMA_ONLY == 0)); then
      gonken_register_step         "whisper_runtime" "1"         "gonken_ollama_model_postcondition" "gonken_whisper_action" "gonken_whisper_postcondition"         "immutable_whisper_cpp_release_and_stable_cli"         "rebuild_only_checked_runtime_when_identity_or_arch_probe_fails"         "unverified_whisper_binary_never_reaches_stable_entrypoint" || exit $?

      gonken_register_step         "piper_runtime" "1"         "gonken_whisper_postcondition" "gonken_piper_action" "gonken_piper_postcondition"         "separate_piper_cli_venv_from_exact_hash_lock"         "reinstall_only_checked_runtime_when_identity_or_arch_probe_fails"         "application_release_venv_is_not_reused_for_gpl_tts_runtime" || exit $?

      gonken_register_step         "speech_models" "1"         "gonken_piper_postcondition" "gonken_speech_models_action" "gonken_speech_models_postcondition"         "checksum_verified_whisper_model_and_piper_voice_pair"         "resume_downloads_and_repair_missing_zero_byte_or_bad_checksum_pairs"         "noncommercial_legacy_voice_is_never_provisioned" || exit $?

      gonken_register_step         "speech_smoke" "1"         "gonken_speech_models_postcondition" "gonken_speech_smoke_action" "gonken_speech_smoke_postcondition"         "content_free_real_tts_then_stt_smoke_record"         "rerun_smoke_when_validation_record_is_missing_or_drifted"         "smoke_samples_are_temporary_and_not_retained" || exit $?

      if ((SPEECH_ONLY == 0)); then
        gonken_register_step         "application_service" "2"         "gonken_speech_smoke_postcondition" "gonken_app_service_action" "gonken_app_service_postcondition"         "exact_systemd_unit_tmpfiles_root_reconcile_and_degraded_headless_supervisor"         "upgrade_known_managed_unit_then_enable_start_and_capture_failure_context"         "no_privilege_or_power_grants_are_added_to_long_running_service" || exit $?

        if [[ "${GONKEN_SOURCE_RECORD[bluetooth_audio]:-disabled}" == "requested" ]]; then
          gonken_register_step \
            "bluetooth_audio_stack" "2" \
            "gonken_app_service_postcondition" "gonken_bluetooth_stack_action" "gonken_bluetooth_stack_postcondition" \
            "optional_bluez_pipewire_wireplumber_headless_audio_stack" \
            "install_only_when_explicitly_requested_and_reuse_when_healthy" \
            "USB_audio_remains_the_supported_fallback" || exit $?

          gonken_register_step \
            "bluetooth_audio_pairing" "1" \
            "gonken_bluetooth_stack_postcondition" "gonken_bluetooth_pair_action" "gonken_bluetooth_pair_postcondition" \
            "one_explicit_trusted_audio_device_record" \
            "guide_pairing_when_missing_and_never_select_ambiguous_devices" \
            "remove_only_the_managed_pairing_record_to_reselect" || exit $?

          gonken_register_step \
            "bluetooth_audio_autoconnect" "2" \
            "gonken_bluetooth_pair_postcondition" "gonken_bluetooth_autoconnect_action" "gonken_bluetooth_autoconnect_postcondition" \
            "bounded_trusted_device_reconnect_service" \
            "enable_once_then_retry_connection_when_device_is_powered_later" \
            "disable_extension_service_without_affecting_USB_core" || exit $?
        fi

        gonken_register_step \
          "appliance_readiness" "1" \
          "gonken_app_service_postcondition" "gonken_appliance_action" "gonken_appliance_postcondition" \
          "physical_audio_local_model_wake_runtime_and_enabled_boot_service" \
          "restart_service_wait_for_content_free_ready_record_and_retry_dependencies" \
          "service_remains_enabled_and_runtime_recovers_without_reinstalling_models" || exit $?
      fi
    fi
  fi
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

if [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" != "target" ]]; then
  gonken_error \
    "M3_4_TARGET_REQUIRED" \
    "Ollama provisioning is implemented only for the validated Raspberry Pi target" \
    "use --release-only on development hosts or run bootstrap on the supported target" || true
  exit 69
fi

gonken_load_effective_ollama_config || {
  gonken_error "OLLAMA_CONFIG" "cannot load authoritative effective LLM configuration" "repair the installed config and rerun"
  exit 65
}

printf '[OK] code=M3_4_OLLAMA_COMPLETE model=%s endpoint=%s\n' "$OLLAMA_MODEL" "$OLLAMA_ENDPOINT"
if ((OLLAMA_ONLY == 1)); then
  exit 0
fi

gonken_load_effective_speech_config || {
  gonken_error "SPEECH_CONFIG" "cannot load authoritative effective speech configuration" "repair the installed config and rerun"
  exit 65
}

printf '[OK] code=M3_5_SPEECH_COMPLETE stt=%s voice=%s whisper=%s\n'   "$SPEECH_STT_MODEL" "$SPEECH_TTS_VOICE" "$SPEECH_WHISPER_BINARY"
if ((SPEECH_ONLY == 1)); then
  exit 0
fi

python3 "$(gonken_install_summary_manager)" \
  --system-root / \
  --commit "${GONKEN_SOURCE_RECORD[resolved_commit]}" \
  --json
printf '[OK] code=M3_6_INSTALL_SUMMARY status=READY ready=true next=USE_ASSISTANT\n'
printf '[OK] code=M6_2_SERVICE_COMPLETE status=READY ready=true autostart=enabled\n'
if [[ "${GONKEN_SOURCE_RECORD[bluetooth_audio]:-disabled}" == "requested" ]]; then
  printf '[OK] code=X4_BLUETOOTH_SETUP status=READY paired=true autoconnect=true usb_fallback=true\n'
fi
printf '[READY] code=INSTALLATION_COMPLETE service=gonken-agent.service autostart=enabled reboot_required=false wake_phrase=Hey_Gonken\n'
printf '[INFO] code=NEXT_ACTION message=say_Hey_Gonken_or_run_gonken-agent_talk;_see_docs/OPERATIONS.md_for_manual_control\n'
exit 0
