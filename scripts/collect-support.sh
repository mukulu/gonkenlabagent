#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: collect-support.sh [--output PATH | --output-dir DIR] [--site PATH] [--index PATH] [--telemetry PATH] [--startup-snapshot PATH] [--target-manifest PATH] [--json]

Create one canonical .tar.bz2 support archive. Output path and safe owner-only
publication are owned by the support command. The default is the invoking
administrator's home when known. Explicit destinations must already exist.
USAGE
}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
args=(support)
SITE="/etc/gonken-agent/config.toml"
TELEMETRY="/var/lib/gonken-agent/runtime/telemetry.jsonl"
STARTUP_SNAPSHOT="/var/lib/gonken-agent/runtime/startup/latest.json"
TARGET_MANIFEST=""
SUPPORT_TEMP_DIR=""
cleanup() { if [[ -n "$SUPPORT_TEMP_DIR" && -d "$SUPPORT_TEMP_DIR" ]]; then rm -rf -- "$SUPPORT_TEMP_DIR"; fi; }
trap cleanup EXIT
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output|--output-dir|--site|--index|--telemetry|--startup-snapshot|--target-manifest)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "[FAIL] $1 requires a value" >&2; exit 64; }
      case "$1" in
        --site) SITE="$2" ;;
        --telemetry) TELEMETRY="$2" ;;
        --startup-snapshot) STARTUP_SNAPSHOT="$2" ;;
        --target-manifest) TARGET_MANIFEST="$2" ;;
        *) args+=("$1" "$2") ;;
      esac
      shift 2 ;;
    --json) args+=(--json); shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done
if [[ -x "$SCRIPT_DIR/../.venv/bin/gonken-agent" ]]; then
  GONKEN_AGENT="$SCRIPT_DIR/../.venv/bin/gonken-agent"
elif command -v gonken-agent >/dev/null 2>&1; then
  GONKEN_AGENT="$(command -v gonken-agent)"
else
  echo "[FAIL] gonken-agent executable not found" >&2; exit 127
fi
if [[ -f "$SITE" ]]; then args+=(--site "$SITE"); else args+=(--no-site); fi
if [[ -f "$TELEMETRY" ]]; then args+=(--telemetry "$TELEMETRY"); fi
if [[ -f "$STARTUP_SNAPSHOT" ]]; then args+=(--startup-snapshot "$STARTUP_SNAPSHOT"); fi
if [[ -z "$TARGET_MANIFEST" && -x "$SCRIPT_DIR/target_probe.py" ]]; then
  SUPPORT_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gonken-support.XXXXXXXX")"
  chmod 700 "$SUPPORT_TEMP_DIR"
  TARGET_MANIFEST="$SUPPORT_TEMP_DIR/target-manifest.json"
  if ! timeout --kill-after=2s 20s python3 "$SCRIPT_DIR/target_probe.py" --json --output "$TARGET_MANIFEST" >/dev/null 2>&1; then
    TARGET_MANIFEST=""
  fi
fi
if [[ -f "$TARGET_MANIFEST" ]]; then args+=(--target-manifest "$TARGET_MANIFEST"); fi
"$GONKEN_AGENT" "${args[@]}"
