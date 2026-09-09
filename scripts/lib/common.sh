#!/usr/bin/env bash
# Shared, dependency-light bootstrap functions. Source this file from Bash.

if [[ -n "${GONKEN_COMMON_SH_LOADED:-}" ]]; then
  return 0
fi
readonly GONKEN_COMMON_SH_LOADED=1

readonly GONKEN_TARGET_MIN_FREE_KIB=8388608
readonly GONKEN_TARGET_MIN_RAM_KIB=3670016
readonly GONKEN_DEVELOPMENT_MIN_RAM_KIB=1048576
readonly GONKEN_MIN_CLOCK_EPOCH=1735689600

GONKEN_INVOKING_USER=""
GONKEN_PRIVILEGE_MODE=""
GONKEN_PRIVILEGE_PREFIX=()
GONKEN_RESOLVED_COMMIT=""
GONKEN_STAGING_DIR=""

gonken_error() {
  local code="$1"
  local message="$2"
  local remediation="$3"
  printf '[ERROR] code=%s message=%s remediation=%s\n' \
    "$code" "$message" "$remediation" >&2
  return 1
}

gonken_require_commands() {
  local missing=()
  local command_name
  for command_name in "$@"; do
    command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
  done
  if ((${#missing[@]})); then
    gonken_error \
      "PREFLIGHT_COMMAND" \
      "missing required commands: ${missing[*]}" \
      "install the named Raspberry Pi OS packages, then rerun preflight"
    return 1
  fi
}

gonken_validate_absolute_path() {
  local path="$1"
  local label="$2"
  if [[ -z "$path" || "$path" != /* || "$path" == *$'\n'* || "$path" == *$'\r'* ]]; then
    gonken_error \
      "PREFLIGHT_PATH" \
      "$label must be an absolute single-line path" \
      "supply an existing absolute path"
    return 1
  fi
  if [[ "$path" == *'/../'* || "$path" == */.. || "$path" == *'/./'* || "$path" == */. ]]; then
    gonken_error \
      "PREFLIGHT_PATH" \
      "$label must not contain dot traversal components" \
      "supply a canonical absolute path"
    return 1
  fi
}

gonken_read_os_field() {
  local file="$1"
  local requested="$2"
  local key value
  [[ -r "$file" ]] || return 1
  while IFS='=' read -r key value; do
    if [[ "$key" == "$requested" ]]; then
      value="${value%$'\r'}"
      if [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" == \'*\' && ${#value} -ge 2 ]]; then
        value="${value:1:${#value}-2}"
      fi
      printf '%s\n' "$value"
      return 0
    fi
  done <"$file"
  return 1
}

gonken_validate_target_platform() {
  local os_release="$1"
  local kernel_name="$2"
  local architecture="$3"
  local userspace_bits="$4"
  local python_version="$5"
  local pid1_name="$6"
  local pi_model="$7"
  local rpi_issue="$8"
  local os_id version_id codename

  os_id="$(gonken_read_os_field "$os_release" ID)" || os_id=""
  version_id="$(gonken_read_os_field "$os_release" VERSION_ID)" || version_id=""
  codename="$(gonken_read_os_field "$os_release" VERSION_CODENAME)" || codename=""

  if [[ "$kernel_name" != "Linux" \
      || ("$os_id" != "debian" && "$os_id" != "raspbian") \
      || "$version_id" != "13" || "$codename" != "trixie" ]]; then
    gonken_error \
      "PREFLIGHT_PLATFORM" \
      "target requires Raspberry Pi OS based on Debian 13 trixie" \
      "flash the supported Raspberry Pi OS Lite 64-bit image"
    return 1
  fi
  if [[ "$architecture" != "aarch64" || "$userspace_bits" != "64" ]]; then
    gonken_error \
      "PREFLIGHT_ARCH" \
      "target requires AArch64 kernel and 64-bit userspace" \
      "flash Raspberry Pi OS Lite 64-bit"
    return 1
  fi
  if [[ "$python_version" != 3.13.* ]]; then
    gonken_error \
      "PREFLIGHT_PYTHON" \
      "target requires distribution Python 3.13; found $python_version" \
      "use the supported Trixie image without replacing system Python"
    return 1
  fi
  if [[ "$pid1_name" != "systemd" ]]; then
    gonken_error \
      "PREFLIGHT_INIT" \
      "target requires systemd as PID 1; found ${pid1_name:-unknown}" \
      "boot the supported Raspberry Pi OS normally"
    return 1
  fi
  if [[ "$pi_model" != Raspberry\ Pi\ 5* ]]; then
    gonken_error \
      "PREFLIGHT_HARDWARE" \
      "target requires Raspberry Pi 5; found ${pi_model:-unknown}" \
      "run on the declared Raspberry Pi 5 target"
    return 1
  fi
  if [[ "$rpi_issue" != *"Raspberry Pi reference"* ]]; then
    gonken_error \
      "PREFLIGHT_IMAGE" \
      "target lacks Raspberry Pi OS image provenance" \
      "flash the supported official Raspberry Pi OS Lite 64-bit image"
    return 1
  fi
}

gonken_validate_development_platform() {
  local kernel_name="$1"
  local architecture="$2"
  local userspace_bits="$3"
  local python_version="$4"
  if [[ "$kernel_name" != "Linux" || "$userspace_bits" != "64" \
      || ("$architecture" != "x86_64" && "$architecture" != "aarch64") ]]; then
    gonken_error \
      "PREFLIGHT_DEV_PLATFORM" \
      "development mode requires 64-bit Linux x86_64 or AArch64" \
      "use a documented Linux development host"
    return 1
  fi
  if [[ "$python_version" != 3.12.* && "$python_version" != 3.13.* ]]; then
    gonken_error \
      "PREFLIGHT_DEV_PYTHON" \
      "development mode requires Python 3.12 or 3.13; found $python_version" \
      "use a supported development interpreter"
    return 1
  fi
}

gonken_validate_resources() {
  local free_kib="$1"
  local memory_kib="$2"
  local clock_epoch="$3"
  local platform_mode="$4"
  local minimum_memory="$GONKEN_TARGET_MIN_RAM_KIB"

  if [[ "$platform_mode" == "development" ]]; then
    minimum_memory="$GONKEN_DEVELOPMENT_MIN_RAM_KIB"
  fi
  if [[ ! "$free_kib" =~ ^[0-9]+$ || "$free_kib" -lt "$GONKEN_TARGET_MIN_FREE_KIB" ]]; then
    gonken_error \
      "PREFLIGHT_DISK" \
      "at least 8 GiB free staging space is required; found ${free_kib:-invalid} KiB" \
      "free storage or select a larger staging filesystem"
    return 1
  fi
  if [[ ! "$memory_kib" =~ ^[0-9]+$ || "$memory_kib" -lt "$minimum_memory" ]]; then
    gonken_error \
      "PREFLIGHT_RAM" \
      "insufficient RAM for $platform_mode mode; found ${memory_kib:-invalid} KiB" \
      "use the declared 4GB target or a supported development host"
    return 1
  fi
  if [[ ! "$clock_epoch" =~ ^[0-9]+$ || "$clock_epoch" -lt "$GONKEN_MIN_CLOCK_EPOCH" ]]; then
    gonken_error \
      "PREFLIGHT_TIME" \
      "system clock is implausible for TLS validation" \
      "synchronize date and time, then rerun preflight"
    return 1
  fi
}

gonken_establish_privilege() {
  local uid current_user sudo_uid
  uid="$(id -u)" || {
    gonken_error "PREFLIGHT_IDENTITY" "cannot determine effective UID" "repair the id command"
    return 1
  }
  if [[ "$uid" == "0" ]]; then
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
      if [[ ! "${SUDO_USER}" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
        gonken_error "PREFLIGHT_IDENTITY" "invalid SUDO_USER value" "invoke sudo from a real local account"
        return 1
      fi
      sudo_uid="$(id -u -- "$SUDO_USER" 2>/dev/null)" || sudo_uid=""
      if [[ ! "$sudo_uid" =~ ^[0-9]+$ || "$sudo_uid" == "0" ]]; then
        gonken_error "PREFLIGHT_IDENTITY" "SUDO_USER is not a non-root account" "invoke sudo from the intended administrator account"
        return 1
      fi
      GONKEN_INVOKING_USER="$SUDO_USER"
      GONKEN_PRIVILEGE_MODE="sudo-root"
    else
      GONKEN_INVOKING_USER="root"
      GONKEN_PRIVILEGE_MODE="direct-root"
    fi
    GONKEN_PRIVILEGE_PREFIX=()
    return 0
  fi

  current_user="$(id -un)" || {
    gonken_error "PREFLIGHT_IDENTITY" "cannot determine invoking user" "repair the local account database"
    return 1
  }
  if ! command -v sudo >/dev/null 2>&1; then
    gonken_error \
      "PREFLIGHT_SUDO" \
      "sudo is unavailable for non-root user $current_user" \
      "install sudo or invoke bootstrap as root"
    return 1
  fi
  if ! sudo -v; then
    gonken_error \
      "PREFLIGHT_SUDO" \
      "sudo validation failed for $current_user" \
      "confirm administrator access, then rerun bootstrap"
    return 1
  fi
  GONKEN_INVOKING_USER="$current_user"
  GONKEN_PRIVILEGE_MODE="validated-sudo"
  GONKEN_PRIVILEGE_PREFIX=(sudo -n)
}

gonken_normalize_source_url() {
  local source_url="$1"
  source_url="${source_url%/}"
  source_url="${source_url%.git}"
  printf '%s\n' "$source_url"
}

gonken_validate_source_request() {
  local source_url="$1"
  local source_ref="$2"
  local platform_mode="$3"
  if [[ -z "$source_url" || "$source_url" == *$'\n'* || "$source_url" == *$'\r'* \
      || "$source_url" == *'?'* || "$source_url" == *'#'* ]]; then
    gonken_error "PREFLIGHT_SOURCE" "source URL is empty or unsafe" "use a plain HTTPS repository URL"
    return 1
  fi
  if [[ "$source_url" == https://* ]]; then
    if [[ ! "$source_url" =~ ^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?/[^[:space:]]+$ ]]; then
      gonken_error "PREFLIGHT_SOURCE" "HTTPS source URL has no valid host/path" "use a plain repository HTTPS URL"
      return 1
    fi
    if [[ "$source_url" =~ ^https://[^/]*@ ]]; then
      gonken_error "PREFLIGHT_SOURCE" "credentials are forbidden in source URLs" "use credential-free HTTPS configuration"
      return 1
    fi
  elif [[ "$platform_mode" == "development" && "$source_url" == file:///* ]]; then
    :
  else
    gonken_error \
      "PREFLIGHT_SOURCE" \
      "target source must use HTTPS; file URLs are development-only" \
      "provide --source-url https://host/owner/repository.git"
    return 1
  fi
  if [[ -z "$source_ref" || "$source_ref" == -* || "$source_ref" == *$'\n'* \
      || "$source_ref" == *$'\r'* || "$source_ref" == *'..'* \
      || "$source_ref" == *'@{'* ]]; then
    gonken_error "PREFLIGHT_REF" "source ref is empty or unsafe" "use an advertised branch or tag name"
    return 1
  fi
  if ! git check-ref-format --branch "$source_ref" >/dev/null 2>&1; then
    gonken_error "PREFLIGHT_REF" "invalid branch or tag name: $source_ref" "use an advertised branch or tag name"
    return 1
  fi
}

gonken_validate_existing_checkout() {
  local checkout_path="$1"
  local expected_source="$2"
  local status origin normalized_origin normalized_expected
  local -a checkout_git=(git -c "safe.directory=$checkout_path" -C "$checkout_path")
  [[ -n "$checkout_path" ]] || return 0
  [[ ! -L "$checkout_path" ]] || {
    gonken_error "PREFLIGHT_CHECKOUT" "existing checkout path is a symlink" "use an explicit real directory"
    return 1
  }
  [[ -e "$checkout_path" ]] || return 0
  [[ -d "$checkout_path" ]] || {
    gonken_error "PREFLIGHT_CHECKOUT" "existing checkout path is not a directory" "choose an empty path or clean Git checkout"
    return 1
  }
  if [[ -d "$checkout_path/.git" ]]; then
    status="$("${checkout_git[@]}" status --porcelain=v1 --untracked-files=normal)" || {
      gonken_error "PREFLIGHT_CHECKOUT" "cannot inspect existing Git checkout" "repair or replace the checkout"
      return 1
    }
    if [[ -n "$status" ]]; then
      gonken_error \
        "PREFLIGHT_CHECKOUT_DIRTY" \
        "existing checkout has tracked, staged, or untracked changes" \
        "commit, preserve elsewhere, or remove the changes before bootstrap"
      return 1
    fi
    origin="$("${checkout_git[@]}" remote get-url origin 2>/dev/null)" || origin=""
    normalized_origin="$(gonken_normalize_source_url "$origin")"
    normalized_expected="$(gonken_normalize_source_url "$expected_source")"
    if [[ -z "$origin" || "$normalized_origin" != "$normalized_expected" ]]; then
      gonken_error \
        "PREFLIGHT_CHECKOUT_ORIGIN" \
        "existing checkout origin does not match requested source" \
        "use the intended repository or pass its exact HTTPS source URL"
      return 1
    fi
    return 0
  fi
  if [[ -n "$(ls -A -- "$checkout_path" 2>/dev/null)" ]]; then
    gonken_error \
      "PREFLIGHT_CHECKOUT" \
      "existing path is non-empty and is not a Git checkout" \
      "choose an empty path or preserve its contents elsewhere"
    return 1
  fi
}

gonken_validate_staging_parent() {
  local staging_parent="$1"
  [[ -d "$staging_parent" && ! -L "$staging_parent" ]] || {
    gonken_error "PREFLIGHT_STAGING" "staging parent must be an existing real directory" "create and pass an absolute staging directory"
    return 1
  }
  [[ -w "$staging_parent" ]] || {
    gonken_error "PREFLIGHT_STAGING" "staging parent is not writable" "choose a writable filesystem with sufficient space"
    return 1
  }
}

gonken_resolve_remote_ref() {
  local source_url="$1"
  local source_ref="$2"
  local output sha refname
  local -A branches=()
  local -A tags=()
  local -A peeled=()
  local -a selected=()

  if ! output="$(GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code "$source_url" \
      "refs/heads/$source_ref" "refs/tags/$source_ref" \
      "refs/tags/$source_ref^{}" 2>/dev/null)"; then
    gonken_error \
      "PREFLIGHT_NETWORK" \
      "cannot reach source or resolve advertised ref $source_ref" \
      "check network, DNS, TLS time, repository access, and ref spelling"
    return 1
  fi
  while read -r sha refname; do
    [[ "$sha" =~ ^[0-9a-fA-F]{40}$ ]] || continue
    if [[ "$refname" == *'^{}' ]]; then
      peeled["${sha,,}"]=1
    elif [[ "$refname" == refs/heads/* ]]; then
      branches["${sha,,}"]=1
    else
      tags["${sha,,}"]=1
    fi
  done <<<"$output"
  selected=("${!branches[@]}")
  if ((${#peeled[@]})); then
    selected+=("${!peeled[@]}")
  else
    selected+=("${!tags[@]}")
  fi
  local -A unique=()
  for sha in "${selected[@]}"; do
    unique["$sha"]=1
  done
  selected=("${!unique[@]}")
  if ((${#selected[@]} != 1)); then
    gonken_error \
      "PREFLIGHT_REF" \
      "source ref is missing or ambiguous across branch/tag namespaces" \
      "use a unique advertised branch or tag"
    return 1
  fi
  GONKEN_RESOLVED_COMMIT="${selected[0]}"
}

gonken_create_staging() {
  local staging_parent="$1"
  shift
  local staging_dir manifest_temp record

  for record in "$@"; do
    if [[ ! "$record" =~ ^[a-z][a-z0-9_]*= || "$record" == *$'\n'* || "$record" == *$'\r'* ]]; then
      gonken_error "PREFLIGHT_STAGING" "invalid source-record field" "use single-line key=value records"
      return 1
    fi
  done

  umask 077
  staging_dir="$(mktemp -d -- "${staging_parent%/}/gonken-agent-bootstrap.XXXXXXXX")" || {
    gonken_error "PREFLIGHT_STAGING" "cannot create private staging directory" "check staging filesystem permissions and space"
    return 1
  }
  manifest_temp="$staging_dir/source.record.tmp"
  if ! printf '%s\n' "$@" >"$manifest_temp"; then
    rm -f -- "$manifest_temp"
    rmdir -- "$staging_dir" 2>/dev/null || true
    gonken_error "PREFLIGHT_STAGING" "cannot write source manifest" "check staging filesystem health"
    return 1
  fi
  chmod 0600 "$manifest_temp" || {
    rm -f -- "$manifest_temp"
    rmdir -- "$staging_dir" 2>/dev/null || true
    gonken_error "PREFLIGHT_STAGING" "cannot protect source manifest" "check staging filesystem permissions"
    return 1
  }
  mv -- "$manifest_temp" "$staging_dir/source.record" || {
    rm -f -- "$manifest_temp"
    rmdir -- "$staging_dir" 2>/dev/null || true
    gonken_error "PREFLIGHT_STAGING" "cannot finalize source manifest" "check staging filesystem health"
    return 1
  }
  GONKEN_STAGING_DIR="$staging_dir"
}
