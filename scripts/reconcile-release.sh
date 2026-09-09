#!/usr/bin/env bash
# Pre-start release reconciliation. M6 will wire this into systemd.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ROOT="/usr/local/lib/gonken-agent"
STATE_ROOT="/var/lib/gonken-agent/install"
SERVICE_USER="gonken-agent"

usage() {
  cat <<'EOF'
Usage: reconcile-release.sh [OPTIONS]

Options:
  --release-root PATH  Immutable release root.
  --state-root PATH    Root-owned activation-state directory.
  --service-user USER  Account used for post-switch smoke checks.
EOF
}

while (($#)); do
  case "$1" in
    --release-root|--state-root|--service-user)
      (($# >= 2)) || { usage >&2; exit 64; }
      option="$1"
      value="$2"
      case "$option" in
        --release-root) RELEASE_ROOT="$value" ;;
        --state-root) STATE_ROOT="$value" ;;
        --service-user) SERVICE_USER="$value" ;;
      esac
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 64 ;;
  esac
done

exec python3 "$SCRIPT_DIR/release_manager.py" reconcile \
  --release-root "$RELEASE_ROOT" \
  --state-root "$STATE_ROOT" \
  --service-user "$SERVICE_USER"
