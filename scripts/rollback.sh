#!/usr/bin/env bash
# Explicit administrator-invoked rollback to the previous validated release.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ROOT="/usr/local/lib/gonken-agent"
STATE_ROOT="/var/lib/gonken-agent/install"
SERVICE_USER="gonken-agent"
SYSTEMCTL="/usr/bin/systemctl"
RESTART_SERVICE=1

usage() {
  cat <<'EOF'
Usage: scripts/rollback.sh [OPTIONS]

Roll back the active GonKenLab Agent release to the previous validated release.
This script is explicit and administrator-invoked; it is never run at boot.

Options:
  --release-root PATH  Installed release root.
  --state-root PATH    Root-owned activation-state directory.
  --service-user USER  Account used for post-switch smoke checks.
  --systemctl PATH     systemctl path for service restart.
  --no-restart         Do not restart gonken-agent.service after rollback.
  -h, --help           Show this help.
EOF
}

while (($#)); do
  case "$1" in
    --release-root|--state-root|--service-user|--systemctl)
      (($# >= 2)) || { usage >&2; exit 64; }
      case "$1" in
        --release-root) RELEASE_ROOT="$2" ;;
        --state-root) STATE_ROOT="$2" ;;
        --service-user) SERVICE_USER="$2" ;;
        --systemctl) SYSTEMCTL="$2" ;;
      esac
      shift 2
      ;;
    --no-restart)
      RESTART_SERVICE=0
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

python3 "$SCRIPT_DIR/release_manager.py" rollback-previous \
  --release-root "$RELEASE_ROOT" \
  --state-root "$STATE_ROOT" \
  --service-user "$SERVICE_USER"

if ((RESTART_SERVICE == 1)); then
  "$SYSTEMCTL" restart gonken-agent.service
fi
