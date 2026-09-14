#!/usr/bin/env bash
# Explicit administrator-invoked uninstall. Keeps data by default.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -f "$SCRIPT_DIR/packaging/systemd/gonken-agent.service" ]]; then
  TEMPLATE_ROOT="$SCRIPT_DIR"
else
  TEMPLATE_ROOT="$PROJECT_ROOT"
fi
SYSTEM_ROOT="/"
SYSTEMCTL="/usr/bin/systemctl"
PURGE_ARGS=()

usage() {
  cat <<'EOF'
Usage: scripts/uninstall.sh [OPTIONS]

Remove GonKenLab Agent-owned service, entrypoint, and immutable release files.
Data is retained by default. Shared Ollama units, binaries, users, and model
stores are not removed.

Options:
  --system-root PATH                  Development-only FHS test root.
  --systemctl PATH                    systemctl path.
  --purge-data --confirm-purge PHRASE Purge retained GonKenLab data.
  -h, --help                          Show this help.

Purge phrase:
  purge-gonken-agent-data
EOF
}

while (($#)); do
  case "$1" in
    --system-root|--systemctl|--confirm-purge)
      (($# >= 2)) || { usage >&2; exit 64; }
      case "$1" in
        --system-root) SYSTEM_ROOT="$2" ;;
        --systemctl) SYSTEMCTL="$2" ;;
        --confirm-purge) PURGE_ARGS+=(--confirm-purge "$2") ;;
      esac
      shift 2
      ;;
    --purge-data)
      PURGE_ARGS+=(--purge-data)
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

exec python3 "$SCRIPT_DIR/uninstall_manager.py" \
  --system-root "$SYSTEM_ROOT" \
  --unit-template "$TEMPLATE_ROOT/packaging/systemd/gonken-agent.service" \
  --tmpfiles-template "$TEMPLATE_ROOT/packaging/tmpfiles/gonken-agent.conf" \
  --environment-unit-template "$TEMPLATE_ROOT/packaging/systemd/gonken-environment.service" \
  --environment-tmpfiles-template "$TEMPLATE_ROOT/packaging/tmpfiles/gonken-environment.conf" \
  --systemctl "$SYSTEMCTL" \
  "${PURGE_ARGS[@]}"
