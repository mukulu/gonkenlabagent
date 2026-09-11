#!/usr/bin/env bash
# One-command first-install/update launcher for GonKenLab Agent.
#
# Designed to be streamed over HTTPS:
#   curl -fsSL https://raw.githubusercontent.com/mukulu/gonkenlabagent/main/install-gonken.sh | bash
#
# The launcher only handles base-package preparation and the repository checkout.
# The governed bootstrap remains the authority for all target validation and
# installed-system changes.

set -Eeuo pipefail

# Keep package-manager output deterministic even when a freshly imaged Pi has
# locale variables for locales that have not yet been generated.
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

DEFAULT_SOURCE_URL="https://github.com/mukulu/gonkenlabagent.git"
DEFAULT_SOURCE_REF="main"
SOURCE_URL="${GONKEN_SOURCE_URL:-$DEFAULT_SOURCE_URL}"
SOURCE_REF="${GONKEN_SOURCE_REF:-$DEFAULT_SOURCE_REF}"
INSTALL_DIR="${GONKEN_INSTALL_DIR:-$HOME/gonkenlabagent}"
BOOTSTRAP_ARGS=()

usage() {
  cat <<'USAGE'
Usage: install-gonken.sh [OPTIONS] [BOOTSTRAP OPTIONS]

One-command Raspberry Pi launcher. It installs the small base prerequisites,
creates/updates a clean GonKenLab Agent checkout, then runs ./bootstrap.sh.

Launcher options:
  --source-url URL    Git repository URL (default: official GonKenLab Agent repo).
  --ref REF           Branch/tag to install (default: main).
  --install-dir PATH  Checkout directory (default: ~/gonkenlabagent).
  -h, --help          Show this help.

All other arguments are passed unchanged to bootstrap.sh, for example:
  --bluetooth-audio
  --bluetooth-device AA:BB:CC:DD:EE:FF

Examples:
  install-gonken.sh
  install-gonken.sh --bluetooth-audio --bluetooth-device AA:BB:CC:DD:EE:FF
USAGE
}

while (($#)); do
  case "$1" in
    --source-url|--ref|--install-dir)
      option="$1"
      (($# >= 2)) || { printf '[ERROR] %s requires a value\n' "$option" >&2; exit 64; }
      value="$2"
      case "$option" in
        --source-url) SOURCE_URL="$value" ;;
        --ref) SOURCE_REF="$value" ;;
        --install-dir) INSTALL_DIR="$value" ;;
      esac
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      BOOTSTRAP_ARGS+=("$1")
      shift
      ;;
  esac
done

[[ "$SOURCE_URL" == https://* && "$SOURCE_URL" != *$'\n'* && "$SOURCE_URL" != *$'\r'* ]] || {
  printf '[ERROR] code=LAUNCHER_SOURCE message=source URL must be HTTPS\n' >&2
  exit 64
}
[[ -n "$SOURCE_REF" && "$SOURCE_REF" != -* && "$SOURCE_REF" != *$'\n'* && "$SOURCE_REF" != *$'\r'* ]] || {
  printf '[ERROR] code=LAUNCHER_REF message=ref is empty or unsafe\n' >&2
  exit 64
}
[[ "$INSTALL_DIR" == /* && "$INSTALL_DIR" != *$'\n'* && "$INSTALL_DIR" != *$'\r'* ]] || {
  printf '[ERROR] code=LAUNCHER_PATH message=install directory must be absolute\n' >&2
  exit 64
}

if command -v rfkill >/dev/null 2>&1; then
  wifi_state="$(rfkill list wifi 2>/dev/null || true)"
  if [[ "$wifi_state" == *"Soft blocked: yes"* ]]; then
    printf '[INFO] code=WIFI_RF_KILL message=Wi-Fi_is_soft-blocked;_Ethernet_is_valid_for_installation;_for_Wi-Fi_set_WLAN_country_then_enable_radio_see_docs/INSTALLATION.md\n'
  fi
fi

if [[ "$(id -u)" == "0" ]]; then
  PRIV=()
else
  command -v sudo >/dev/null 2>&1 || {
    printf '[ERROR] code=LAUNCHER_SUDO message=sudo is required for base-package installation\n' >&2
    exit 77
  }
  printf '[RUNNING] code=LAUNCHER_PRIVILEGE message=validating_sudo\n'
  sudo -v || exit 77
  PRIV=(sudo)
fi

printf '[RUNNING] code=LAUNCHER_BASE_PACKAGES message=refreshing_package_metadata\n'
"${PRIV[@]}" env DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 apt-get update
printf '[RUNNING] code=LAUNCHER_BASE_PACKAGES message=installing_git_ca_certificates_python3\n'
"${PRIV[@]}" env DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 apt-get install -y ca-certificates git python3
printf '[OK] code=LAUNCHER_BASE_PACKAGES_READY\n'

FRESH_CLONE=0
if [[ ! -e "$INSTALL_DIR" ]]; then
  FRESH_CLONE=1
  printf '[RUNNING] code=LAUNCHER_CLONE source=%s ref=%s destination=%s\n' "$SOURCE_URL" "$SOURCE_REF" "$INSTALL_DIR"
  mkdir -p -- "$(dirname -- "$INSTALL_DIR")"
  git clone "$SOURCE_URL" "$INSTALL_DIR"
elif [[ ! -d "$INSTALL_DIR/.git" ]]; then
  printf '[ERROR] code=LAUNCHER_CHECKOUT message=install directory exists but is not a Git checkout: %s\n' "$INSTALL_DIR" >&2
  exit 75
fi

origin="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
[[ "$origin" == "$SOURCE_URL" ]] || {
  printf '[ERROR] code=LAUNCHER_CHECKOUT message=origin differs from requested source remediation=use --install-dir for a separate checkout\n' >&2
  exit 75
}
[[ -z "$(git -C "$INSTALL_DIR" status --porcelain --untracked-files=normal)" ]] || {
  printf '[ERROR] code=LAUNCHER_DIRTY message=checkout has local changes remediation=commit/stash/remove them before managed update\n' >&2
  exit 75
}

printf '[RUNNING] code=LAUNCHER_FETCH source=%s ref=%s\n' "$SOURCE_URL" "$SOURCE_REF"
git -C "$INSTALL_DIR" fetch --prune origin "$SOURCE_REF"
resolved="$(git -C "$INSTALL_DIR" rev-parse FETCH_HEAD)"
[[ "$resolved" =~ ^[0-9a-f]{40}$ ]] || {
  printf '[ERROR] code=LAUNCHER_FETCH message=remote ref did not resolve to a full commit\n' >&2
  exit 69
}
if ((FRESH_CLONE == 0)); then
  current="$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true)"
  if [[ -n "$current" && "$current" != "$resolved" ]] \
      && ! git -C "$INSTALL_DIR" merge-base --is-ancestor "$current" "$resolved"; then
    printf '[ERROR] code=LAUNCHER_DIVERGED message=local checkout has commits not contained in requested remote ref remediation=use a separate --install-dir or reconcile Git manually\n' >&2
    exit 75
  fi
fi

if git ls-remote --exit-code --heads "$SOURCE_URL" "$SOURCE_REF" >/dev/null 2>&1; then
  git -C "$INSTALL_DIR" checkout -B "$SOURCE_REF" "$resolved"
  git -C "$INSTALL_DIR" branch --set-upstream-to="origin/$SOURCE_REF" "$SOURCE_REF" >/dev/null 2>&1 || true
else
  git -C "$INSTALL_DIR" checkout --detach "$resolved"
fi

printf '[OK] code=LAUNCHER_CHECKOUT_READY commit=%s directory=%s\n' "$resolved" "$INSTALL_DIR"
printf '[RUNNING] code=LAUNCHER_BOOTSTRAP message=starting_governed_bootstrap\n'
cd "$INSTALL_DIR"
exec ./bootstrap.sh --source-url "$SOURCE_URL" --ref "$SOURCE_REF" "${BOOTSTRAP_ARGS[@]}"
