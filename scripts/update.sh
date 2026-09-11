#!/usr/bin/env bash
# Explicit administrator-invoked update. Never runs at boot.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ROOT="/usr/local/lib/gonken-agent"
STATE_ROOT="/var/lib/gonken-agent/install"
SOURCE_URL="https://github.com/mukulu/gonkenlabagent.git"
SOURCE_REF="main"
PROFILE="core-pi-trixie-py313"
SERVICE_USER="gonken-agent"
SYSTEMCTL="/usr/bin/systemctl"
RESTART_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/update.sh [OPTIONS]

Build and activate an immutable GonKenLab Agent release from an explicit source
ref. This command is administrator-invoked and never runs at boot.

Options:
  --release-root PATH  Installed release root.
  --state-root PATH    Root-owned activation-state directory.
  --source-url URL     HTTPS Git source; file:// only in isolated tests.
  --ref REF            Branch or tag to update from.
  --profile NAME       Dependency profile.
  --service-user USER  Account used for post-switch smoke checks.
  --systemctl PATH     systemctl path for service restart.
  --no-restart         Do not restart gonken-agent.service after update.
  -h, --help           Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --release-root|--state-root|--source-url|--ref|--profile|--service-user|--systemctl)
      (($# >= 2)) || { usage >&2; exit 64; }
      case "$1" in
        --release-root) RELEASE_ROOT="$2" ;;
        --state-root) STATE_ROOT="$2" ;;
        --source-url) SOURCE_URL="$2" ;;
        --ref) SOURCE_REF="$2" ;;
        --profile) PROFILE="$2" ;;
        --service-user) SERVICE_USER="$2" ;;
        --systemctl) SYSTEMCTL="$2" ;;
      esac
      shift 2
      ;;
    --no-restart)
      RESTART_ARGS+=(--no-restart)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 64
      ;;
  esac
done

exec python3 "$SCRIPT_DIR/update_manager.py" \
  --release-root "$RELEASE_ROOT" \
  --state-root "$STATE_ROOT" \
  --source-url "$SOURCE_URL" \
  --ref "$SOURCE_REF" \
  --profile "$PROFILE" \
  --service-user "$SERVICE_USER" \
  --systemctl "$SYSTEMCTL" \
  "${RESTART_ARGS[@]}"
