#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: collect-support.sh [--output PATH] [--site PATH] [--index PATH] [--telemetry PATH] [--startup-snapshot PATH]

Create a private, content-free GonKenLab Agent support ZIP for upload and review.
The output path must not already exist.
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/../.venv/bin/gonken-agent" ]]; then
  GONKEN_AGENT="$SCRIPT_DIR/../.venv/bin/gonken-agent"
elif command -v gonken-agent >/dev/null 2>&1; then
  GONKEN_AGENT="$(command -v gonken-agent)"
else
  echo "[FAIL] gonken-agent executable not found" >&2
  exit 127
fi

OUTPUT=""
SITE="/etc/gonken-agent/config.toml"
INDEX=""
TELEMETRY="/var/lib/gonken-agent/runtime/telemetry.jsonl"
STARTUP_SNAPSHOT="/var/lib/gonken-agent/runtime/startup/latest.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="${2:-}"; shift 2 ;;
    --site) SITE="${2:-}"; shift 2 ;;
    --index) INDEX="${2:-}"; shift 2 ;;
    --telemetry) TELEMETRY="${2:-}"; shift 2 ;;
    --startup-snapshot) STARTUP_SNAPSHOT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

if [[ -z "$OUTPUT" ]]; then
  mkdir -p /var/lib/gonken-agent/support
  OUTPUT="/var/lib/gonken-agent/support/gonken-support-$(date -u +%Y%m%dT%H%M%SZ).zip"
fi

args=(support --output "$OUTPUT")
if [[ -f "$SITE" ]]; then args+=(--site "$SITE"); else args+=(--no-site); fi
if [[ -n "$INDEX" ]]; then args+=(--index "$INDEX"); fi
if [[ -f "$TELEMETRY" ]]; then args+=(--telemetry "$TELEMETRY"); fi
if [[ -f "$STARTUP_SNAPSHOT" ]]; then args+=(--startup-snapshot "$STARTUP_SNAPSHOT"); fi

"$GONKEN_AGENT" "${args[@]}"
echo "$OUTPUT"
