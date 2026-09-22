#!/usr/bin/env bash
# Resumable, postcondition-driven installation step engine (M3.2).
# Source after scripts/lib/common.sh.

if [[ -n "${GONKEN_INSTALL_ENGINE_SH_LOADED:-}" ]]; then
  return 0
fi
readonly GONKEN_INSTALL_ENGINE_SH_LOADED=1

declare -ag GONKEN_STEP_ORDER=()
declare -Ag GONKEN_STEP_VERSION=()
declare -Ag GONKEN_STEP_PRECONDITION=()
declare -Ag GONKEN_STEP_ACTION=()
declare -Ag GONKEN_STEP_POSTCONDITION=()
declare -Ag GONKEN_STEP_MUTATIONS=()
declare -Ag GONKEN_STEP_RERUN=()
declare -Ag GONKEN_STEP_ROLLBACK=()
declare -ag GONKEN_TRACKED_TEMPS=()

GONKEN_ENGINE_STATE_DIR=""
GONKEN_ENGINE_LOG_DIR=""
GONKEN_ENGINE_EVENTS_DIR=""
GONKEN_ENGINE_LOCK_DIR=""
GONKEN_ENGINE_LOCK_FILE=""
GONKEN_ENGINE_LOCK_OWNED=0
GONKEN_ENGINE_INITIALIZED=0
GONKEN_ENGINE_TRAPS_ENABLED=0
GONKEN_ENGINE_TRAP_ACTIVE=0
GONKEN_ENGINE_CURRENT_STEP="none"
GONKEN_ENGINE_EVENT_SEQUENCE=0
GONKEN_ENGINE_RUN_ID=""
GONKEN_STEP_EVIDENCE="none"
declare -Ag GONKEN_SOURCE_RECORD=()
GONKEN_SOURCE_RECORD_PATH=""

gonken_record_value_is_safe() {
  local value="$1"
  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]]
}

gonken_validate_record_field() {
  local record="$1"
  [[ "$record" =~ ^[a-z][a-z0-9_]*= ]] || return 1
  gonken_record_value_is_safe "$record"
}

gonken_track_temp() {
  local path="$1"
  GONKEN_TRACKED_TEMPS+=("$path")
}

gonken_untrack_temp() {
  local target="$1"
  local path
  local -a retained=()
  for path in "${GONKEN_TRACKED_TEMPS[@]}"; do
    [[ "$path" == "$target" ]] || retained+=("$path")
  done
  GONKEN_TRACKED_TEMPS=("${retained[@]}")
}

gonken_cleanup_tracked_temps() {
  local path
  for path in "${GONKEN_TRACKED_TEMPS[@]}"; do
    [[ -n "$path" && "$path" == /* && ! -d "$path" ]] && rm -f -- "$path"
  done
  GONKEN_TRACKED_TEMPS=()
}

gonken_atomic_record() {
  local destination="$1"
  local mode="$2"
  shift 2
  local directory temporary record

  gonken_validate_absolute_path "$destination" "record destination" || return 73
  [[ "$mode" =~ ^0?[67]00$ ]] || {
    gonken_error "INSTALL_STATE" "unsupported private record mode: $mode" "use mode 0600 or 0700"
    return 73
  }
  [[ ! -L "$destination" ]] || {
    gonken_error "INSTALL_STATE" "record destination is a symlink" "replace it with a regular private file"
    return 73
  }
  directory="$(dirname -- "$destination")"
  [[ -d "$directory" && ! -L "$directory" && -w "$directory" ]] || {
    gonken_error "INSTALL_STATE" "record parent is not a writable real directory" "repair the private installer directory"
    return 73
  }
  for record in "$@"; do
    gonken_validate_record_field "$record" || {
      gonken_error "INSTALL_STATE" "invalid record field" "write single-line lowercase key=value fields"
      return 73
    }
  done

  temporary="$(umask 077; mktemp -- "$directory/.gonken-tmp.XXXXXXXX")" || {
    gonken_error "INSTALL_STATE" "cannot create same-directory temporary record" "check installer state filesystem permissions and space"
    return 73
  }
  gonken_track_temp "$temporary"
  if ! printf '%s\n' "$@" >"$temporary" || ! chmod "$mode" "$temporary" \
      || ! mv -- "$temporary" "$destination"; then
    rm -f -- "$temporary"
    gonken_untrack_temp "$temporary"
    gonken_error "INSTALL_STATE" "cannot atomically replace record" "check installer state filesystem health and space"
    return 73
  fi
  gonken_untrack_temp "$temporary"
}

gonken_read_record() {
  local path="$1"
  local allowed_name="$2"
  local output_name="$3"
  local -n allowed_ref="$allowed_name"
  local -n output_ref="$output_name"
  local line key value
  local -A allowed_set=()

  [[ -f "$path" && ! -L "$path" ]] || {
    gonken_error "INSTALL_RECORD" "record is missing, non-regular, or a symlink: $path" "provide the exact private record created by bootstrap"
    return 65
  }
  for key in "${allowed_ref[@]}"; do
    allowed_set["$key"]=1
  done
  output_ref=()
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ ! "$line" =~ ^[a-z][a-z0-9_]*= || "$line" == *$'\r'* ]]; then
      gonken_error "INSTALL_RECORD" "record contains a malformed line" "regenerate the record with bootstrap"
      return 65
    fi
    key="${line%%=*}"
    value="${line#*=}"
    if [[ -z "${allowed_set[$key]:-}" ]]; then
      gonken_error "INSTALL_RECORD" "record contains unknown field: $key" "regenerate the record with the supported bootstrap"
      return 65
    fi
    if [[ -v "output_ref[$key]" ]]; then
      gonken_error "INSTALL_RECORD" "record contains duplicate field: $key" "regenerate the record with bootstrap"
      return 65
    fi
    output_ref["$key"]="$value"
  done <"$path"
}

gonken_private_file_permissions() {
  local path="$1"
  local expected_uid="$2"
  local effective_uid file_uid file_mode parent parent_uid parent_mode
  effective_uid="$(id -u)" || return 65
  file_uid="$(stat -c %u -- "$path" 2>/dev/null)" || return 65
  file_mode="$(stat -c %a -- "$path" 2>/dev/null)" || return 65
  parent="$(dirname -- "$path")"
  parent_uid="$(stat -c %u -- "$parent" 2>/dev/null)" || return 65
  parent_mode="$(stat -c %a -- "$parent" 2>/dev/null)" || return 65
  [[ "$file_mode" =~ ^[0-7]{3,4}$ && "$parent_mode" =~ ^[0-7]{3,4}$ ]] || return 65
  if [[ "$file_uid" != "$parent_uid" \
      || ("$file_uid" != "$expected_uid" && "$file_uid" != "$effective_uid") \
      || ("$effective_uid" != "0" && "$expected_uid" != "$effective_uid") \
      || $((8#$file_mode & 077)) -ne 0 || $((8#$parent_mode & 077)) -ne 0 ]]; then
    gonken_error \
      "INSTALL_RECORD_PERMISSIONS" \
      "source record and parent must be private and owned by the recorded or effective administrator" \
      "use the untouched mode-600 record in its mode-700 bootstrap directory"
    return 65
  fi
}

gonken_load_source_record() {
  local path="$1"
  local key invoking_uid
  local -a required_fields=(
    format source_url requested_ref resolved_commit platform_mode invoking_user
    kernel_name architecture userspace_bits python_version os_id os_version_id
    os_codename os_build_id os_release_sha256 pi_issue_sha256
    rpi_image_reference pi_model pid1 systemd_version free_kib memory_kib
    observed_epoch existing_checkout
  )
  local -a optional_fields=(bluetooth_audio bluetooth_device source_mode environment_profile environment_sensor_address environment_mode model_provision_mode appliance_preset)
  local -a fields=("${required_fields[@]}" "${optional_fields[@]}")
  gonken_validate_absolute_path "$path" "source record" || return 65
  gonken_read_record "$path" fields GONKEN_SOURCE_RECORD || return $?
  for key in "${required_fields[@]}"; do
    if [[ ! -v "GONKEN_SOURCE_RECORD[$key]" ]]; then
      gonken_error "INSTALL_RECORD" "source record is missing field: $key" "rerun bootstrap to create a complete record"
      return 65
    fi
  done
  GONKEN_SOURCE_RECORD[bluetooth_audio]="${GONKEN_SOURCE_RECORD[bluetooth_audio]:-disabled}"
  GONKEN_SOURCE_RECORD[bluetooth_device]="${GONKEN_SOURCE_RECORD[bluetooth_device]:-}"
  GONKEN_SOURCE_RECORD[source_mode]="${GONKEN_SOURCE_RECORD[source_mode]:-remote}"
  GONKEN_SOURCE_RECORD[environment_profile]="${GONKEN_SOURCE_RECORD[environment_profile]:-none}"
  GONKEN_SOURCE_RECORD[environment_mode]="${GONKEN_SOURCE_RECORD[environment_mode]:-preserve}"
  GONKEN_SOURCE_RECORD[environment_sensor_address]="${GONKEN_SOURCE_RECORD[environment_sensor_address]:-0x44}"
  GONKEN_SOURCE_RECORD[appliance_preset]="${GONKEN_SOURCE_RECORD[appliance_preset]:-none}"
  GONKEN_SOURCE_RECORD[model_provision_mode]="${GONKEN_SOURCE_RECORD[model_provision_mode]:-online}"
  [[ "${GONKEN_SOURCE_RECORD[format]}" == "gonken-bootstrap-source-v1" ]] || {
    gonken_error "INSTALL_RECORD_VERSION" "unsupported source record format" "rerun the matching supported bootstrap"
    return 65
  }
  [[ "${GONKEN_SOURCE_RECORD[resolved_commit]}" =~ ^[0-9a-f]{40}$ ]] || {
    gonken_error "INSTALL_RECORD" "source record has an invalid resolved commit" "rerun bootstrap against an advertised ref"
    return 65
  }
  [[ "${GONKEN_SOURCE_RECORD[source_mode]}" == "remote" \
      || "${GONKEN_SOURCE_RECORD[source_mode]}" == "local-checkpoint" ]] || {
    gonken_error "INSTALL_RECORD" "source record has an invalid source mode" "rerun bootstrap with a supported source mode"
    return 65
  }
  [[ "${GONKEN_SOURCE_RECORD[platform_mode]}" == "target" \
      || "${GONKEN_SOURCE_RECORD[platform_mode]}" == "development" ]] || {
    gonken_error "INSTALL_RECORD" "source record has an invalid platform mode" "rerun bootstrap on a supported target or development host"
    return 65
  }
  [[ "${GONKEN_SOURCE_RECORD[bluetooth_audio]}" == "disabled" \
      || "${GONKEN_SOURCE_RECORD[bluetooth_audio]}" == "requested" ]] || {
    gonken_error "INSTALL_RECORD" "source record has an invalid Bluetooth feature request" "rerun bootstrap with or without --bluetooth-audio"
    return 65
  }
  if [[ "${GONKEN_SOURCE_RECORD[bluetooth_audio]}" == "requested" \
      && "${GONKEN_SOURCE_RECORD[platform_mode]}" != "target" ]]; then
    gonken_error "INSTALL_RECORD" "Bluetooth audio setup is target-only" "omit Bluetooth options on development hosts"
    return 65
  fi
  if ((${#GONKEN_SOURCE_RECORD[bluetooth_device]} > 120)) \
      || [[ "${GONKEN_SOURCE_RECORD[bluetooth_device]}" == *$'\n'* \
        || "${GONKEN_SOURCE_RECORD[bluetooth_device]}" == *$'\r'* ]]; then
    gonken_error "INSTALL_RECORD" "recorded Bluetooth selector is unsafe" "rerun bootstrap with a short name or MAC selector"
    return 65
  fi
  case "${GONKEN_SOURCE_RECORD[environment_profile]}" in
    none|full-simulation|real-sensor-simulated-actuator|sensor-deferred-relay|full-real) ;;
    *)
      gonken_error "INSTALL_RECORD" "source record has an invalid environment profile" "rerun bootstrap with a supported --environment-profile"
      return 65
      ;;
  esac
  case "${GONKEN_SOURCE_RECORD[appliance_preset]}" in
    none) ;;
    responsive-room) [[ "${GONKEN_SOURCE_RECORD[environment_profile]}" == "full-real" ]] || return 65 ;;
    *) gonken_error "INSTALL_RECORD" "invalid appliance preset" "rerun bootstrap"; return 65 ;;
  esac
  case "${GONKEN_SOURCE_RECORD[environment_mode]}" in
    preserve|manual|semi_automatic|automatic|disabled) ;;
    *) gonken_error "INSTALL_RECORD" "invalid environment mode" "rerun bootstrap with a documented mode"; return 65 ;;
  esac
  if [[ "${GONKEN_SOURCE_RECORD[environment_mode]}" != "preserve" && "${GONKEN_SOURCE_RECORD[environment_profile]}" == "none" ]]; then
    gonken_error "INSTALL_RECORD" "environment mode requires a selected profile" "rerun bootstrap"; return 65
  fi
  case "${GONKEN_SOURCE_RECORD[environment_sensor_address]}" in
    0x44|0x45) ;;
    *)
      gonken_error "INSTALL_RECORD" "source record has an invalid SHT31 address" "rerun bootstrap with --sensor-address 0x44 or 0x45"
      return 65
      ;;
  esac
  case "${GONKEN_SOURCE_RECORD[model_provision_mode]}" in
    online|preseeded-offline) ;;
    *)
      gonken_error "INSTALL_RECORD" "source record has an invalid model provisioning mode" "rerun bootstrap with --model-provision-mode online or preseeded-offline"
      return 65
      ;;
  esac
  if [[ "${GONKEN_SOURCE_RECORD[environment_profile]}" != "none" \
      && "${GONKEN_SOURCE_RECORD[platform_mode]}" != "target" ]]; then
    gonken_error "INSTALL_RECORD" "environment commissioning is target-only" "use environment profile none on development hosts"
    return 65
  fi
  [[ "${GONKEN_SOURCE_RECORD[invoking_user]}" =~ ^(root|[a-z_][a-z0-9_-]*[$]?)$ ]] || {
    gonken_error "INSTALL_RECORD" "source record has an invalid invoking user" "rerun bootstrap from a real local account"
    return 65
  }
  invoking_uid="$(id -u -- "${GONKEN_SOURCE_RECORD[invoking_user]}" 2>/dev/null)" || {
    gonken_error "INSTALL_RECORD_PERMISSIONS" "recorded invoking user no longer resolves" "rerun bootstrap from the intended administrator account"
    return 65
  }
  gonken_private_file_permissions "$path" "$invoking_uid" || {
    gonken_error "INSTALL_RECORD_PERMISSIONS" "cannot verify private source-record ownership or mode" "use the untouched bootstrap record"
    return 65
  }
  for key in userspace_bits free_kib memory_kib observed_epoch; do
    [[ "${GONKEN_SOURCE_RECORD[$key]}" =~ ^[0-9]+$ ]] || {
      gonken_error "INSTALL_RECORD" "source record has invalid numeric field: $key" "rerun bootstrap"
      return 65
    }
  done
  if [[ -n "${GONKEN_SOURCE_RECORD[existing_checkout]}" ]]; then
    gonken_validate_absolute_path "${GONKEN_SOURCE_RECORD[existing_checkout]}" "recorded checkout" || return 65
  fi
  GONKEN_SOURCE_RECORD_PATH="$path"
}

gonken_revalidate_source_record() {
  local mode="${GONKEN_SOURCE_RECORD[platform_mode]}"
  local source_url="${GONKEN_SOURCE_RECORD[source_url]}"
  local source_ref="${GONKEN_SOURCE_RECORD[requested_ref]}"
  local source_mode="${GONKEN_SOURCE_RECORD[source_mode]}"
  local kernel architecture userspace python_version clock_epoch free_kib memory_kib
  local pid1 pi_model rpi_issue os_hash pi_hash systemd_version

  gonken_validate_source_request "$source_url" "$source_ref" "$mode" "$source_mode" || return 65
  kernel="$(uname -s)" || return 78
  architecture="$(uname -m)" || return 78
  userspace="$(getconf LONG_BIT)" || return 78
  python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')" || return 78
  if [[ "$kernel" != "${GONKEN_SOURCE_RECORD[kernel_name]}" \
      || "$architecture" != "${GONKEN_SOURCE_RECORD[architecture]}" \
      || "$userspace" != "${GONKEN_SOURCE_RECORD[userspace_bits]}" \
      || "$python_version" != "${GONKEN_SOURCE_RECORD[python_version]}" ]]; then
    gonken_error "INSTALL_HOST_CHANGED" "host kernel, architecture, userspace, or Python changed after preflight" "rerun bootstrap to obtain a current source record"
    return 78
  fi

  if [[ "$mode" == "target" ]]; then
    pid1="$(tr -d '\000\r\n' </proc/1/comm 2>/dev/null || true)"
    pi_model="$(tr -d '\000\r\n' </proc/device-tree/model 2>/dev/null || true)"
    rpi_issue=""
    [[ -r /etc/rpi-issue ]] && IFS= read -r rpi_issue </etc/rpi-issue || true
    gonken_validate_target_platform /etc/os-release "$kernel" "$architecture" \
      "$userspace" "$python_version" "$pid1" "$pi_model" "$rpi_issue" || return 78
    os_hash="$(sha256sum /etc/os-release | awk '{print $1}')" || return 78
    pi_hash="$(sha256sum /etc/rpi-issue | awk '{print $1}')" || return 78
    systemd_version="$(systemctl --version | awk 'NR == 1 {print $2; exit}')" || return 78
    if [[ "$os_hash" != "${GONKEN_SOURCE_RECORD[os_release_sha256]}" \
        || "$pi_hash" != "${GONKEN_SOURCE_RECORD[pi_issue_sha256]}" \
        || "$pi_model" != "${GONKEN_SOURCE_RECORD[pi_model]}" \
        || "$pid1" != "${GONKEN_SOURCE_RECORD[pid1]}" \
        || "$systemd_version" != "${GONKEN_SOURCE_RECORD[systemd_version]}" ]]; then
      gonken_error "INSTALL_HOST_CHANGED" "target image, board, or init changed after preflight" "rerun bootstrap before installation"
      return 78
    fi
  else
    gonken_validate_development_platform "$kernel" "$architecture" "$userspace" "$python_version" || return 78
    [[ "${GONKEN_SOURCE_RECORD[os_id]}" == "development" \
      && "${GONKEN_SOURCE_RECORD[os_version_id]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[os_codename]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[os_build_id]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[os_release_sha256]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[pi_issue_sha256]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[rpi_image_reference]}" == "not-applicable" \
      && "${GONKEN_SOURCE_RECORD[pi_model]}" == "development-host" \
      && "${GONKEN_SOURCE_RECORD[pid1]}" == "not-required" \
      && "${GONKEN_SOURCE_RECORD[systemd_version]}" == "not-required" ]] || {
      gonken_error "INSTALL_RECORD" "development source record contains target-like or inconsistent facts" "rerun bootstrap in explicit development-host mode"
      return 65
    }
  fi

  clock_epoch="$(date +%s)" || return 78
  free_kib="$(df -Pk "$(dirname -- "$GONKEN_SOURCE_RECORD_PATH")" | awk 'END {print $4}')" || return 78
  memory_kib="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)" || return 78
  gonken_validate_resources "$free_kib" "$memory_kib" "$clock_epoch" "$mode" || return 78
  if ((clock_epoch < ${GONKEN_SOURCE_RECORD[observed_epoch]})); then
    gonken_error "INSTALL_HOST_CHANGED" "system clock moved backwards after preflight" "synchronize time and rerun bootstrap"
    return 78
  fi
  gonken_validate_existing_checkout "${GONKEN_SOURCE_RECORD[existing_checkout]}" "$source_url" "$source_mode" || return 78
  if [[ "$source_mode" == "local-checkpoint" ]]; then
    gonken_resolve_local_checkpoint "${GONKEN_SOURCE_RECORD[existing_checkout]}" "$source_ref" || return 69
  else
    gonken_resolve_remote_ref "$source_url" "$source_ref" || return 69
  fi
  if [[ "$GONKEN_RESOLVED_COMMIT" != "${GONKEN_SOURCE_RECORD[resolved_commit]}" ]]; then
    gonken_error "INSTALL_SOURCE_CHANGED" "advertised source ref moved after preflight" "review the new commit and rerun bootstrap"
    return 69
  fi
}

gonken_prepare_private_directory() {
  local path="$1"
  local label="$2"
  local migration_policy="${3:-strict}"
  local mode owner effective_uid
  effective_uid="$(id -u)" || return 73
  gonken_validate_absolute_path "$path" "$label" || return 73
  if [[ -e "$path" ]]; then
    [[ -d "$path" && ! -L "$path" ]] || {
      gonken_error "INSTALL_STATE" "$label is not a real directory" "select a private real directory"
      return 73
    }
    mode="$(stat -c %a -- "$path" 2>/dev/null)" || return 73
    owner="$(stat -c %u -- "$path" 2>/dev/null)" || return 73
    if [[ "$owner" == "$effective_uid" \
        && "$mode" =~ ^[0-7]{3,4}$ && $((8#$mode & 077)) -eq 0 ]]; then
      return 0
    fi
    # One historical speech-record writer accidentally normalized the exact
    # root-owned installer state directory to 0755.  A caller may opt in to
    # repairing that single known-safe legacy mode.  Generic private paths
    # remain fail-closed, as do foreign ownership and group/other-writable modes.
    if [[ "$migration_policy" == "repair-owned-0755" \
        && "$owner" == "$effective_uid" && "$mode" == "755" ]]; then
      chmod 0700 "$path" || return 73
      printf '[OK] code=INSTALL_STATE_REPAIRED path=%s old_mode=755 new_mode=700 owner_uid=%s\n' \
        "$path" "$owner"
      return 0
    fi
    gonken_error \
      "INSTALL_STATE" \
      "$label has unsafe ownership or mode (uid=$owner mode=$mode)" \
      "use an effective-user-owned mode-0700 directory"
    return 73
  else
    local parent
    parent="$(dirname -- "$path")" || return 73
    mkdir -p -- "$parent" || {
      gonken_error "INSTALL_STATE" "cannot create parent for $label" "check parent ownership, permissions, and space"
      return 73
    }
    (umask 077; mkdir -- "$path") || {
      gonken_error "INSTALL_STATE" "cannot create $label" "check parent ownership, permissions, and space"
      return 73
    }
    chmod 0700 "$path" || return 73
  fi
}

gonken_register_step() {
  local step_id="$1"
  local version="$2"
  local precondition="$3"
  local action="$4"
  local postcondition="$5"
  local mutations="$6"
  local rerun="$7"
  local rollback="$8"
  local item

  [[ "$step_id" =~ ^[a-z][a-z0-9_-]{0,63}$ ]] || {
    gonken_error "INSTALL_STEP_DEFINITION" "invalid step ID: $step_id" "use a stable lowercase identifier"
    return 64
  }
  [[ "$version" =~ ^[1-9][0-9]*$ ]] || {
    gonken_error "INSTALL_STEP_DEFINITION" "invalid step version for $step_id" "use a positive integer schema version"
    return 64
  }
  [[ -z "${GONKEN_STEP_VERSION[$step_id]:-}" ]] || {
    gonken_error "INSTALL_STEP_DEFINITION" "duplicate step ID: $step_id" "register each stable step exactly once"
    return 64
  }
  for item in "$precondition" "$action" "$postcondition"; do
    declare -F "$item" >/dev/null || {
      gonken_error "INSTALL_STEP_DEFINITION" "missing function $item for $step_id" "define every step probe and action before registration"
      return 64
    }
  done
  for item in "$mutations" "$rerun" "$rollback"; do
    [[ -n "$item" ]] && gonken_record_value_is_safe "$item" || {
      gonken_error "INSTALL_STEP_DEFINITION" "invalid metadata for $step_id" "declare non-empty single-line step metadata"
      return 64
    }
  done

  GONKEN_STEP_ORDER+=("$step_id")
  GONKEN_STEP_VERSION["$step_id"]="$version"
  GONKEN_STEP_PRECONDITION["$step_id"]="$precondition"
  GONKEN_STEP_ACTION["$step_id"]="$action"
  GONKEN_STEP_POSTCONDITION["$step_id"]="$postcondition"
  GONKEN_STEP_MUTATIONS["$step_id"]="$mutations"
  GONKEN_STEP_RERUN["$step_id"]="$rerun"
  GONKEN_STEP_ROLLBACK["$step_id"]="$rollback"
}

gonken_log_event() {
  local level="$1"
  local code="$2"
  local step_id="$3"
  local message="$4"
  local event_path epoch
  ((GONKEN_ENGINE_EVENT_SEQUENCE += 1))
  epoch="$(date +%s)" || epoch="unknown"
  printf -v event_path '%s/%s.%06d.event' \
    "$GONKEN_ENGINE_EVENTS_DIR" "$GONKEN_ENGINE_RUN_ID" "$GONKEN_ENGINE_EVENT_SEQUENCE"
  gonken_atomic_record "$event_path" 0600 \
    'format=gonken-install-event-v1' \
    "run_id=$GONKEN_ENGINE_RUN_ID" \
    "sequence=$GONKEN_ENGINE_EVENT_SEQUENCE" \
    "observed_epoch=$epoch" \
    "level=$level" \
    "code=$code" \
    "step_id=$step_id" \
    "message=$message"
}

gonken_allocate_run_id() {
  local base candidate suffix=0
  base="$(date +%s).$BASHPID" || return 73
  candidate="$base"
  while [[ -e "$GONKEN_ENGINE_EVENTS_DIR/$candidate.000001.event" \
      || -L "$GONKEN_ENGINE_EVENTS_DIR/$candidate.000001.event" ]]; do
    ((suffix += 1))
    candidate="$base.$suffix"
  done
  GONKEN_ENGINE_RUN_ID="$candidate"
}

gonken_step_state_path() {
  printf '%s/steps/%s.record\n' "$GONKEN_ENGINE_STATE_DIR" "$1"
}

gonken_write_step_state() {
  local step_id="$1"
  local status="$2"
  local message="$3"
  local epoch state_path
  epoch="$(date +%s)" || epoch="unknown"
  state_path="$(gonken_step_state_path "$step_id")"
  gonken_atomic_record "$state_path" 0600 \
    'format=gonken-install-step-v1' \
    "step_id=$step_id" \
    "step_version=${GONKEN_STEP_VERSION[$step_id]}" \
    "status=$status" \
    "run_id=$GONKEN_ENGINE_RUN_ID" \
    "observed_epoch=$epoch" \
    "planned_mutations=${GONKEN_STEP_MUTATIONS[$step_id]}" \
    "rerun_behavior=${GONKEN_STEP_RERUN[$step_id]}" \
    "rollback_implication=${GONKEN_STEP_ROLLBACK[$step_id]}" \
    "evidence=$GONKEN_STEP_EVIDENCE" \
    "message=$message"
}

gonken_complete_state_is_current() {
  local step_id="$1"
  local state_path
  local -a allowed=(format step_id step_version status run_id observed_epoch planned_mutations rerun_behavior rollback_implication evidence message)
  local -A state=()
  state_path="$(gonken_step_state_path "$step_id")"
  [[ -f "$state_path" && ! -L "$state_path" ]] || return 1
  gonken_read_record "$state_path" allowed state >/dev/null 2>&1 || return 1
  [[ "${state[format]:-}" == "gonken-install-step-v1" \
    && "${state[step_id]:-}" == "$step_id" \
    && "${state[step_version]:-}" == "${GONKEN_STEP_VERSION[$step_id]}" \
    && "${state[status]:-}" == "complete" \
    && "${state[planned_mutations]:-}" == "${GONKEN_STEP_MUTATIONS[$step_id]}" \
    && "${state[rerun_behavior]:-}" == "${GONKEN_STEP_RERUN[$step_id]}" \
    && "${state[rollback_implication]:-}" == "${GONKEN_STEP_ROLLBACK[$step_id]}" \
    && "${state[evidence]:-}" == "$GONKEN_STEP_EVIDENCE" ]]
}

gonken_boot_id() {
  local boot_id=""
  [[ -r /proc/sys/kernel/random/boot_id ]] || return 1
  IFS= read -r boot_id </proc/sys/kernel/random/boot_id || return 1
  [[ "$boot_id" =~ ^[0-9a-fA-F-]{36}$ ]] || return 1
  printf '%s\n' "${boot_id,,}"
}

gonken_process_start_ticks() {
  local pid="$1"
  local stat_line remainder
  local -a fields=()
  [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/stat" ]] || return 1
  IFS= read -r stat_line <"/proc/$pid/stat" || return 1
  remainder="${stat_line##*) }"
  read -r -a fields <<<"$remainder"
  ((${#fields[@]} >= 20)) || return 1
  [[ "${fields[19]}" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${fields[19]}"
}

gonken_acquire_engine_lock() {
  local owner_pid="" owner_boot="" owner_start="" current_boot="" current_start=""
  local result installer_pid="$BASHPID"
  local -a owner_fields=(format pid boot_id process_start_ticks)
  local -A owner=()
  GONKEN_ENGINE_LOCK_DIR="$GONKEN_ENGINE_STATE_DIR/engine.lock"
  GONKEN_ENGINE_LOCK_FILE="$GONKEN_ENGINE_LOCK_DIR/owner.record"
  current_boot="$(gonken_boot_id)" || {
    gonken_error "INSTALL_LOCK" "cannot read the current Linux boot identity" "repair procfs before installation"
    return 75
  }
  if mkdir -- "$GONKEN_ENGINE_LOCK_DIR" 2>/dev/null; then
    if ! chmod 0700 "$GONKEN_ENGINE_LOCK_DIR"; then
      rmdir -- "$GONKEN_ENGINE_LOCK_DIR" 2>/dev/null || true
      return 73
    fi
  else
    [[ -d "$GONKEN_ENGINE_LOCK_DIR" && ! -L "$GONKEN_ENGINE_LOCK_DIR" ]] || {
      gonken_error "INSTALL_LOCK" "installer lock path is unsafe" "remove the non-directory lock path after inspection"
      return 75
    }
    if ! gonken_read_record "$GONKEN_ENGINE_LOCK_FILE" owner_fields owner >/dev/null 2>&1 \
        || [[ "${owner[format]:-}" != "gonken-install-lock-v1" \
          || ! "${owner[pid]:-}" =~ ^[1-9][0-9]*$ \
          || ! "${owner[boot_id]:-}" =~ ^[0-9a-fA-F-]{36}$ \
          || ! "${owner[process_start_ticks]:-}" =~ ^([0-9]+|unavailable)$ ]]; then
      gonken_error "INSTALL_LOCK" "existing installer lock has corrupt or unknown ownership" "inspect and remove the ambiguous lock manually"
      return 75
    fi
    owner_pid="${owner[pid]}"
    owner_boot="${owner[boot_id],,}"
    owner_start="${owner[process_start_ticks]}"
    if [[ "$owner_boot" == "$current_boot" ]] && kill -0 "$owner_pid" 2>/dev/null; then
      current_start="$(gonken_process_start_ticks "$owner_pid" 2>/dev/null || true)"
      if [[ "$owner_start" == "unavailable" || "$owner_start" == "$current_start" ]]; then
        gonken_error "INSTALL_BUSY" "another installer process owns the state lock" "wait for process $owner_pid to finish, then rerun"
        return 75
      fi
    fi
    rm -f -- "$GONKEN_ENGINE_LOCK_FILE"
    rmdir -- "$GONKEN_ENGINE_LOCK_DIR" 2>/dev/null || {
      gonken_error "INSTALL_LOCK" "stale installer lock contains unexpected data" "inspect and remove the stale lock manually"
      return 75
    }
    mkdir -- "$GONKEN_ENGINE_LOCK_DIR" || return 75
    chmod 0700 "$GONKEN_ENGINE_LOCK_DIR" || return 73
  fi
  current_start="$(gonken_process_start_ticks "$installer_pid" 2>/dev/null || true)"
  [[ -n "$current_start" ]] || current_start="unavailable"
  GONKEN_ENGINE_LOCK_OWNED=1
  if gonken_atomic_record "$GONKEN_ENGINE_LOCK_FILE" 0600 \
      'format=gonken-install-lock-v1' \
      "pid=$installer_pid" \
      "boot_id=$current_boot" \
      "process_start_ticks=$current_start"; then
    :
  else
    result=$?
    gonken_release_engine_lock
    return "$result"
  fi
}

gonken_release_engine_lock() {
  if ((GONKEN_ENGINE_LOCK_OWNED == 1)) && [[ -n "$GONKEN_ENGINE_LOCK_DIR" \
      && -d "$GONKEN_ENGINE_LOCK_DIR" && ! -L "$GONKEN_ENGINE_LOCK_DIR" ]]; then
    rm -f -- "$GONKEN_ENGINE_LOCK_FILE"
    rmdir -- "$GONKEN_ENGINE_LOCK_DIR" 2>/dev/null || true
  fi
  GONKEN_ENGINE_LOCK_OWNED=0
}

gonken_engine_cleanup() {
  gonken_cleanup_tracked_temps
  gonken_release_engine_lock
}

gonken_engine_handle_signal() {
  local signal_name="$1"
  ((GONKEN_ENGINE_TRAP_ACTIVE == 0)) || exit 75
  GONKEN_ENGINE_TRAP_ACTIVE=1
  trap - INT TERM HUP EXIT
  if ((GONKEN_ENGINE_INITIALIZED == 1)); then
    if [[ "$GONKEN_ENGINE_CURRENT_STEP" != "none" \
        && -n "${GONKEN_STEP_VERSION[$GONKEN_ENGINE_CURRENT_STEP]:-}" ]]; then
      gonken_write_step_state "$GONKEN_ENGINE_CURRENT_STEP" "interrupted" "received_$signal_name" || true
    fi
    gonken_log_event "error" "INSTALL_INTERRUPTED" "$GONKEN_ENGINE_CURRENT_STEP" "received_$signal_name" || true
  fi
  gonken_engine_cleanup
  gonken_error "INSTALL_INTERRUPTED" "installer interrupted by $signal_name" "rerun the same command; probes will determine repair or completion" || true
  exit 75
}

gonken_engine_enable_traps() {
  trap 'gonken_engine_handle_signal INT' INT
  trap 'gonken_engine_handle_signal TERM' TERM
  trap 'gonken_engine_handle_signal HUP' HUP
  trap 'gonken_engine_cleanup' EXIT
  GONKEN_ENGINE_TRAPS_ENABLED=1
}

gonken_engine_initialize() {
  local state_dir="$1"
  local log_dir="$2"
  gonken_prepare_private_directory "$state_dir" "install state directory" || return $?
  gonken_prepare_private_directory "$state_dir/steps" "install step-state directory" || return $?
  gonken_prepare_private_directory "$log_dir" "install log directory" || return $?
  gonken_prepare_private_directory "$log_dir/events" "install event directory" || return $?
  GONKEN_ENGINE_STATE_DIR="$state_dir"
  GONKEN_ENGINE_LOG_DIR="$log_dir"
  GONKEN_ENGINE_EVENTS_DIR="$log_dir/events"
  gonken_allocate_run_id || {
    gonken_error "INSTALL_STATE" "cannot allocate an immutable event run ID" "check installer event-directory permissions and clock"
    return 73
  }
  GONKEN_ENGINE_INITIALIZED=1
  gonken_acquire_engine_lock || return $?
  gonken_engine_enable_traps
  gonken_log_event "info" "INSTALL_START" "none" "step_engine_started" || return $?
}

gonken_step_checkpoint() {
  local step_id="$1"
  local boundary="$2"
  local requested="${GONKEN_INSTALL_TEST_INTERRUPT:-}"
  [[ "${GONKEN_ENABLE_TEST_FAILURES:-0}" == "1" ]] || return 0
  [[ "$requested" == "$step_id:$boundary" ]] || return 0
  case "${GONKEN_INSTALL_TEST_INTERRUPT_MODE:-term}" in
    term) kill -TERM "$BASHPID" ;;
    kill) kill -KILL "$BASHPID" ;;
    *)
      gonken_error "INSTALL_TEST_CONTROL" "unknown test interruption mode" "use term or kill"
      return 64
      ;;
  esac
}

gonken_run_step() {
  local step_id="$1"
  local precondition="${GONKEN_STEP_PRECONDITION[$step_id]}"
  local action="${GONKEN_STEP_ACTION[$step_id]}"
  local postcondition="${GONKEN_STEP_POSTCONDITION[$step_id]}"
  local result
  GONKEN_ENGINE_CURRENT_STEP="$step_id"
  GONKEN_STEP_EVIDENCE="none"

  if "$precondition" "$step_id"; then
    :
  else
    result=$?
    gonken_write_step_state "$step_id" "failed" "precondition_failed" || return $?
    gonken_log_event "error" "INSTALL_PRECONDITION" "$step_id" "precondition_failed" || return $?
    gonken_error "INSTALL_PRECONDITION" "precondition failed for step $step_id" "correct the reported condition and rerun"
    return "$result"
  fi

  if "$postcondition" "$step_id"; then
    if ! gonken_complete_state_is_current "$step_id"; then
      gonken_write_step_state "$step_id" "complete" "postcondition_already_satisfied" || return $?
    fi
    gonken_log_event "info" "INSTALL_STEP_SATISFIED" "$step_id" "postcondition_satisfied_without_action" || return $?
    printf '[OK] code=INSTALL_STEP_SATISFIED step=%s version=%s\n' \
      "$step_id" "${GONKEN_STEP_VERSION[$step_id]}"
    GONKEN_ENGINE_CURRENT_STEP="none"
    return 0
  else
    result=$?
  fi
  if ((result != 1)); then
    gonken_write_step_state "$step_id" "failed" "postcondition_probe_error_before_action" || return $?
    gonken_log_event "error" "INSTALL_PROBE" "$step_id" "postcondition_probe_error_before_action" || return $?
    gonken_error "INSTALL_PROBE" "postcondition probe errored for step $step_id" "repair the probe dependency and rerun"
    return "$result"
  fi

  gonken_write_step_state "$step_id" "running" "action_required" || return $?
  gonken_log_event "info" "INSTALL_STEP_ACTION" "$step_id" "postcondition_missing_action_started" || return $?
  printf '[RUNNING] code=INSTALL_STEP_ACTION step=%s version=%s\n' \
    "$step_id" "${GONKEN_STEP_VERSION[$step_id]}"
  gonken_step_checkpoint "$step_id" "before" || return $?
  if "$action" "$step_id"; then
    :
  else
    result=$?
    if ((result == 78)); then
      gonken_write_step_state "$step_id" "paused" "planned_resume_required" || return $?
      gonken_log_event "info" "INSTALL_PAUSED" "$step_id" "planned_resume_exit_78" || return $?
      printf '[PAUSED] code=INSTALL_PAUSED step=%s version=%s action=resume_after_required_system_transition\n' \
        "$step_id" "${GONKEN_STEP_VERSION[$step_id]}"
      GONKEN_ENGINE_CURRENT_STEP="none"
      return 78
    fi
    gonken_write_step_state "$step_id" "failed" "action_failed" || return $?
    gonken_log_event "error" "INSTALL_ACTION" "$step_id" "action_failed_exit_$result" || return $?
    gonken_error "INSTALL_ACTION" "action failed for step $step_id with exit $result" "inspect the event log, correct the cause, and rerun"
    return "$result"
  fi
  gonken_step_checkpoint "$step_id" "after" || return $?
  if "$postcondition" "$step_id"; then
    :
  else
    result=$?
    ((result == 1)) && result=74
    gonken_write_step_state "$step_id" "failed" "postcondition_failed_after_action" || return $?
    gonken_log_event "error" "INSTALL_POSTCONDITION" "$step_id" "postcondition_failed_after_action" || return $?
    gonken_error "INSTALL_POSTCONDITION" "step $step_id action did not establish its postcondition" "inspect the event log and step artifacts before rerunning"
    return "$result"
  fi
  gonken_write_step_state "$step_id" "complete" "postcondition_verified_after_action" || return $?
  gonken_log_event "info" "INSTALL_STEP_COMPLETE" "$step_id" "postcondition_verified_after_action" || return $?
  printf '[OK] code=INSTALL_STEP_COMPLETE step=%s version=%s\n' \
    "$step_id" "${GONKEN_STEP_VERSION[$step_id]}"
  GONKEN_ENGINE_CURRENT_STEP="none"
}

gonken_run_registered_steps() {
  local step_id
  ((${#GONKEN_STEP_ORDER[@]} > 0)) || {
    gonken_error "INSTALL_STEP_DEFINITION" "no installation steps are registered" "register at least one bounded step"
    return 64
  }
  for step_id in "${GONKEN_STEP_ORDER[@]}"; do
    gonken_run_step "$step_id" || return $?
  done
  gonken_log_event "info" "INSTALL_COMPLETE" "none" "all_registered_postconditions_satisfied" || return $?
  gonken_release_engine_lock
  GONKEN_ENGINE_CURRENT_STEP="none"
}
