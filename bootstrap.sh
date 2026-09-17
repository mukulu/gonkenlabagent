#!/usr/bin/env bash
# GonKenLab Agent bootstrap and validated installer handoff.
#
# Preflight remains mutation-free. A normal target invocation crosses the
# already-validated noninteractive sudo boundary before installed-system work.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_LIBRARY="$SCRIPT_DIR/scripts/lib/common.sh"

if [[ ! -r "$COMMON_LIBRARY" ]]; then
  printf '%s\n' \
    '[ERROR] code=BOOTSTRAP_LAYOUT message=missing scripts/lib/common.sh remediation=run bootstrap.sh from a complete GonKenLab Agent checkout' \
    >&2
  exit 66
fi

# shellcheck source=scripts/lib/common.sh
source "$COMMON_LIBRARY"

SOURCE_URL="https://github.com/mukulu/gonkenlabagent.git"
SOURCE_REF="main"
SOURCE_MODE="remote"
SOURCE_URL_EXPLICIT=0
SOURCE_REF_EXPLICIT=0
PREFLIGHT_ONLY=0
PLATFORM_MODE="target"
STAGING_PARENT="/var/tmp"
EXISTING_CHECKOUT=""
EXISTING_CHECKOUT_EXPLICIT=0
BLUETOOTH_AUDIO="disabled"
BLUETOOTH_DEVICE=""
ENVIRONMENT_PROFILE="none"
ENVIRONMENT_SENSOR_ADDRESS="0x44"

usage() {
  cat <<'EOF'
Usage: ./bootstrap.sh [OPTIONS]

Preflight-only performs no installation. A normal target invocation performs the
complete governed install through local model, speech artifacts and system service.
The official repository and main branch are defaults, so ./bootstrap.sh is enough
for the standard installation.

Options:
  --preflight-only          Return success after writing the source manifest.
  --development-host       Validate the documented Linux development-host
                           contract instead of Raspberry Pi production target.
  --local-checkpoint       Bind installation to this clean packaged Git checkout
                           instead of resolving a remote ref. Intended for the
                           supervised downloadable-checkpoint Raspberry Pi run.
  --source-url URL         HTTPS Git source (default: official repository; file://
                           allowed only for --development-host validation).
  --ref REF                Advertised remote branch or tag (default: main).
  --existing-checkout PATH Validate an existing/empty absolute checkout path.
  --staging-parent PATH    Existing absolute staging parent (default: /var/tmp).
  --bluetooth-audio        Opt in to headless PipeWire/BlueZ setup, pairing,
                           and trusted-device auto-reconnect after core install.
  --bluetooth-device VALUE Optional Bluetooth name substring or exact MAC.
                           Without it, exactly one unpaired audio device must
                           appear during the guided pairing checkpoint.
  --environment-profile P Commission an explicit room-environment profile.
                           Choices: none, full-simulation,
                           real-sensor-simulated-actuator,
                           sensor-deferred-relay, full-real.
                           The default is none; real relay profiles require a
                           later supervised physical-commissioning gate.
  --sensor-address ADDR    SHT31 address for real-sensor profiles: 0x44 or 0x45
                           (default: 0x44).
  -h, --help               Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --preflight-only)
      PREFLIGHT_ONLY=1
      shift
      ;;
    --development-host)
      PLATFORM_MODE="development"
      shift
      ;;
    --local-checkpoint)
      SOURCE_MODE="local-checkpoint"
      shift
      ;;
    --bluetooth-audio)
      BLUETOOTH_AUDIO="requested"
      shift
      ;;
    --source-url|--ref|--existing-checkout|--staging-parent|--bluetooth-device|--environment-profile|--sensor-address)
      option="$1"
      (($# >= 2)) || {
        usage >&2
        gonken_error "USAGE" "$option requires a value" "provide a non-empty value"
        exit 64
      }
      value="$2"
      case "$option" in
        --source-url) SOURCE_URL="$value"; SOURCE_URL_EXPLICIT=1 ;;
        --ref) SOURCE_REF="$value"; SOURCE_REF_EXPLICIT=1 ;;
        --existing-checkout)
          EXISTING_CHECKOUT="$value"
          EXISTING_CHECKOUT_EXPLICIT=1
          ;;
        --staging-parent) STAGING_PARENT="$value" ;;
        --bluetooth-device)
          BLUETOOTH_DEVICE="$value"
          BLUETOOTH_AUDIO="requested"
          ;;
        --environment-profile) ENVIRONMENT_PROFILE="$value" ;;
        --sensor-address) ENVIRONMENT_SENSOR_ADDRESS="$value" ;;
      esac
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      gonken_error "USAGE" "unknown option: $1" "run ./bootstrap.sh --help"
      exit 64
      ;;
  esac
done

if [[ "$SOURCE_MODE" == "local-checkpoint" ]]; then
  if ((SOURCE_URL_EXPLICIT == 1 || SOURCE_REF_EXPLICIT == 1 || EXISTING_CHECKOUT_EXPLICIT == 1)); then
    gonken_error "PREFLIGHT_SOURCE" "--local-checkpoint cannot be combined with --source-url, --ref, or --existing-checkout" "run it from the exact extracted checkpoint directory" || true
    exit 64
  fi
  [[ -d "$SCRIPT_DIR/.git" ]] || {
    gonken_error "PREFLIGHT_CHECKOUT" "--local-checkpoint requires the complete packaged Git checkout" "extract the checkpoint ZIP including .git and rerun from its root" || true
    exit 66
  }
  EXISTING_CHECKOUT="$SCRIPT_DIR"
  EXISTING_CHECKOUT_EXPLICIT=1
  SOURCE_URL="file://$SCRIPT_DIR"
  SOURCE_REF="$(git -c "safe.directory=$SCRIPT_DIR" -C "$SCRIPT_DIR" rev-parse 'HEAD^{commit}' 2>/dev/null || true)"
fi

if ((EXISTING_CHECKOUT_EXPLICIT == 0)) && [[ -d "$SCRIPT_DIR/.git" ]]; then
  EXISTING_CHECKOUT="$SCRIPT_DIR"
fi

if [[ "$PLATFORM_MODE" != "target" && "$BLUETOOTH_AUDIO" == "requested" ]]; then
  gonken_error "PREFLIGHT_BLUETOOTH" "Bluetooth audio setup is target-only" "omit Bluetooth options on development hosts" || true
  exit 64
fi
case "$ENVIRONMENT_PROFILE" in
  none|full-simulation|real-sensor-simulated-actuator|sensor-deferred-relay|full-real) ;;
  *)
    gonken_error "PREFLIGHT_ENVIRONMENT_PROFILE" "unsupported environment profile: $ENVIRONMENT_PROFILE" "choose a profile listed by ./bootstrap.sh --help" || true
    exit 64
    ;;
esac
case "$ENVIRONMENT_SENSOR_ADDRESS" in
  0x44|0x45) ;;
  *)
    gonken_error "PREFLIGHT_ENVIRONMENT_SENSOR" "unsupported SHT31 address: $ENVIRONMENT_SENSOR_ADDRESS" "use 0x44 or 0x45" || true
    exit 64
    ;;
esac
if [[ "$PLATFORM_MODE" != "target" && "$ENVIRONMENT_PROFILE" != "none" ]]; then
  gonken_error "PREFLIGHT_ENVIRONMENT_PROFILE" "environment commissioning is target-only" "use profile none on development hosts" || true
  exit 64
fi
if [[ -n "$BLUETOOTH_DEVICE" ]]; then
  if ((${#BLUETOOTH_DEVICE} > 120)) || [[ "$BLUETOOTH_DEVICE" == *$'\n'* || "$BLUETOOTH_DEVICE" == *$'\r'* ]]; then
    gonken_error "PREFLIGHT_BLUETOOTH" "Bluetooth selector is unsafe or too long" "use an exact MAC address or short device-name substring" || true
    exit 64
  fi
fi

gonken_validate_absolute_path "$STAGING_PARENT" "staging parent" || exit 78
if [[ -n "$EXISTING_CHECKOUT" ]]; then
  gonken_validate_absolute_path "$EXISTING_CHECKOUT" "existing checkout" || exit 78
fi

required_commands=(awk chmod date df getconf git id ls mktemp mv python3 rm rmdir sha256sum stat uname)
if [[ "$PLATFORM_MODE" == "target" ]]; then
  required_commands+=(apt-get systemctl tr)
fi
gonken_require_commands "${required_commands[@]}" || exit 69
gonken_validate_source_request "$SOURCE_URL" "$SOURCE_REF" "$PLATFORM_MODE" "$SOURCE_MODE" || exit 78
gonken_validate_staging_parent "$STAGING_PARENT" || exit 78

kernel_name="$(uname -s)" || {
  gonken_error "PREFLIGHT_PLATFORM" "uname failed" "repair the base operating system"
  exit 78
}
architecture="$(uname -m)" || {
  gonken_error "PREFLIGHT_PLATFORM" "architecture probe failed" "repair the base operating system"
  exit 78
}
userspace_bits="$(getconf LONG_BIT)" || {
  gonken_error "PREFLIGHT_PLATFORM" "userspace-width probe failed" "install a supported 64-bit operating system"
  exit 78
}
python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')" || {
  gonken_error "PREFLIGHT_PLATFORM" "python3 version probe failed" "install the distribution python3 package"
  exit 78
}

if [[ "$PLATFORM_MODE" == "target" ]]; then
  pid1_name="$(tr -d '\000\r\n' </proc/1/comm 2>/dev/null || true)"
  pi_model="$(tr -d '\000\r\n' </proc/device-tree/model 2>/dev/null || true)"
  rpi_issue=""
  if [[ -r /etc/rpi-issue ]]; then
    IFS= read -r rpi_issue </etc/rpi-issue || true
  fi
  gonken_validate_target_platform \
    /etc/os-release "$kernel_name" "$architecture" "$userspace_bits" \
    "$python_version" "$pid1_name" "$pi_model" "$rpi_issue" || exit 78
  os_id="$(gonken_read_os_field /etc/os-release ID)"
  os_version_id="$(gonken_read_os_field /etc/os-release VERSION_ID)"
  os_codename="$(gonken_read_os_field /etc/os-release VERSION_CODENAME)"
  os_build_id="$(gonken_read_os_field /etc/os-release BUILD_ID)" || os_build_id="not-reported"
  os_release_sha256="$(sha256sum /etc/os-release | awk '{print $1}')"
  pi_issue_sha256="$(sha256sum /etc/rpi-issue | awk '{print $1}')"
  systemd_version="$(systemctl --version | awk 'NR == 1 {print $2; exit}')"
  [[ "$systemd_version" =~ ^[0-9]+$ ]] || {
    gonken_error "PREFLIGHT_INIT" "cannot determine systemd version" "repair the systemd installation"
    exit 78
  }
else
  gonken_validate_development_platform \
    "$kernel_name" "$architecture" "$userspace_bits" "$python_version" || exit 78
  pid1_name="not-required"
  pi_model="development-host"
  rpi_issue="not-applicable"
  os_id="development"
  os_version_id="not-applicable"
  os_codename="not-applicable"
  os_build_id="not-applicable"
  os_release_sha256="not-applicable"
  pi_issue_sha256="not-applicable"
  systemd_version="not-required"
fi

free_kib="$(df -Pk "$STAGING_PARENT" | awk 'END {print $4}')" || {
  gonken_error "PREFLIGHT_DISK" "free-space probe failed" "check the staging filesystem"
  exit 78
}
memory_kib="$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)" || {
  gonken_error "PREFLIGHT_RAM" "memory probe failed" "check /proc/meminfo"
  exit 78
}
clock_epoch="$(date +%s)" || {
  gonken_error "PREFLIGHT_TIME" "clock probe failed" "repair the system clock"
  exit 78
}
gonken_validate_resources \
  "$free_kib" "$memory_kib" "$clock_epoch" "$PLATFORM_MODE" || exit 78

# Sudo validation intentionally happens once, after quick local platform and
# resource rejection but before checkout inspection or remote source access.
gonken_establish_privilege || exit 77
gonken_validate_existing_checkout "$EXISTING_CHECKOUT" "$SOURCE_URL" "$SOURCE_MODE" || exit 78
if [[ "$SOURCE_MODE" == "local-checkpoint" ]]; then
  gonken_resolve_local_checkpoint "$EXISTING_CHECKOUT" "$SOURCE_REF" || exit 69
else
  gonken_resolve_remote_ref "$SOURCE_URL" "$SOURCE_REF" || exit 69
fi

gonken_create_staging "$STAGING_PARENT" \
  'format=gonken-bootstrap-source-v1' \
  "source_url=$SOURCE_URL" \
  "source_mode=$SOURCE_MODE" \
  "requested_ref=$SOURCE_REF" \
  "resolved_commit=$GONKEN_RESOLVED_COMMIT" \
  "platform_mode=$PLATFORM_MODE" \
  "invoking_user=$GONKEN_INVOKING_USER" \
  "kernel_name=$kernel_name" \
  "architecture=$architecture" \
  "userspace_bits=$userspace_bits" \
  "python_version=$python_version" \
  "os_id=$os_id" \
  "os_version_id=$os_version_id" \
  "os_codename=$os_codename" \
  "os_build_id=$os_build_id" \
  "os_release_sha256=$os_release_sha256" \
  "pi_issue_sha256=$pi_issue_sha256" \
  "rpi_image_reference=$rpi_issue" \
  "pi_model=$pi_model" \
  "pid1=$pid1_name" \
  "systemd_version=$systemd_version" \
  "free_kib=$free_kib" \
  "memory_kib=$memory_kib" \
  "observed_epoch=$clock_epoch" \
  "existing_checkout=$EXISTING_CHECKOUT" \
  "bluetooth_audio=$BLUETOOTH_AUDIO" \
  "bluetooth_device=$BLUETOOTH_DEVICE" \
  "environment_profile=$ENVIRONMENT_PROFILE" \
  "environment_sensor_address=$ENVIRONMENT_SENSOR_ADDRESS" || exit 73

printf '[OK] code=PREFLIGHT_COMPLETE staging=%s\n' "$GONKEN_STAGING_DIR"
printf '[OK] source_commit=%s source_mode=%s privilege_mode=%s platform_mode=%s\n' \
  "$GONKEN_RESOLVED_COMMIT" "$SOURCE_MODE" "$GONKEN_PRIVILEGE_MODE" "$PLATFORM_MODE"

if ((PREFLIGHT_ONLY == 1)); then
  exit 0
fi

if [[ "$PLATFORM_MODE" == "target" && "${#GONKEN_PRIVILEGE_PREFIX[@]}" -gt 0 ]]; then
  exec "${GONKEN_PRIVILEGE_PREFIX[@]}" -- "$SCRIPT_DIR/scripts/install.sh" \
    --source-record "$GONKEN_STAGING_DIR/source.record"
fi

exec "$SCRIPT_DIR/scripts/install.sh" \
  --source-record "$GONKEN_STAGING_DIR/source.record"
