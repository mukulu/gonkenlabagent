#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: collect-support.sh [--output PATH | --output-dir DIR] [--site PATH] [--index PATH] [--telemetry PATH] [--startup-snapshot PATH] [--target-manifest PATH]

Create a private, content-free GonKenLab Agent support ZIP for upload and review.
When target_probe.py is available, the ZIP also includes a sanitized
non-actuating target hardware/runtime manifest.
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
OUTPUT_DIR=""
SITE="/etc/gonken-agent/config.toml"
INDEX=""
TELEMETRY="/var/lib/gonken-agent/runtime/telemetry.jsonl"
STARTUP_SNAPSHOT="/var/lib/gonken-agent/runtime/startup/latest.json"
TARGET_MANIFEST=""
SUPPORT_TEMP_DIR=""

cleanup() {
  if [[ -n "$SUPPORT_TEMP_DIR" && -d "$SUPPORT_TEMP_DIR" ]]; then
    rm -rf "$SUPPORT_TEMP_DIR"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --site) SITE="${2:-}"; shift 2 ;;
    --index) INDEX="${2:-}"; shift 2 ;;
    --telemetry) TELEMETRY="${2:-}"; shift 2 ;;
    --startup-snapshot) STARTUP_SNAPSHOT="${2:-}"; shift 2 ;;
    --target-manifest) TARGET_MANIFEST="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FAIL] unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done

if [[ -n "$OUTPUT" && -n "$OUTPUT_DIR" ]]; then
  echo "[FAIL] use either --output or --output-dir, not both" >&2
  exit 64
fi
if [[ -n "$OUTPUT_DIR" ]]; then
  if [[ "$OUTPUT_DIR" != /* ]]; then
    echo "[FAIL] --output-dir must be absolute" >&2
    exit 64
  fi
  if [[ ! -d "$OUTPUT_DIR" || -L "$OUTPUT_DIR" ]]; then
    echo "[FAIL] --output-dir must be an existing real directory" >&2
    exit 64
  fi
  OUTPUT="$OUTPUT_DIR/gonken-support-$(date -u +%Y%m%dT%H%M%SZ)-$$.zip"
fi

DEFAULT_OUTPUT=0
if [[ -z "$OUTPUT" ]]; then
  DEFAULT_OUTPUT=1
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    caller_home="$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6)"
    if [[ -n "$caller_home" && -d "$caller_home" ]]; then
      OUTPUT="$caller_home/gonken-support-$(date -u +%Y%m%dT%H%M%SZ).zip"
    fi
  fi
  if [[ -z "$OUTPUT" ]]; then
    mkdir -p /var/lib/gonken-agent/support
    OUTPUT="/var/lib/gonken-agent/support/gonken-support-$(date -u +%Y%m%dT%H%M%SZ).zip"
  fi
fi

args=(support --output "$OUTPUT")
if [[ -f "$SITE" ]]; then args+=(--site "$SITE"); else args+=(--no-site); fi
if [[ -n "$INDEX" ]]; then args+=(--index "$INDEX"); fi
if [[ -f "$TELEMETRY" ]]; then args+=(--telemetry "$TELEMETRY"); fi
if [[ -f "$STARTUP_SNAPSHOT" ]]; then args+=(--startup-snapshot "$STARTUP_SNAPSHOT"); fi
if [[ -z "$TARGET_MANIFEST" && -x "$SCRIPT_DIR/target_probe.py" ]]; then
  SUPPORT_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gonken-support.XXXXXXXX")"
  chmod 700 "$SUPPORT_TEMP_DIR"
  TARGET_MANIFEST="$SUPPORT_TEMP_DIR/target-manifest.json"
  if ! python3 "$SCRIPT_DIR/target_probe.py" --json --output "$TARGET_MANIFEST" >/dev/null 2>&1; then
    TARGET_MANIFEST=""
  fi
fi
if [[ -f "$TARGET_MANIFEST" ]]; then args+=(--target-manifest "$TARGET_MANIFEST"); fi

"$GONKEN_AGENT" "${args[@]}"
if [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" && -f "$OUTPUT" ]]; then
  chown "$SUDO_UID:$SUDO_GID" "$OUTPUT" || true
fi
echo "$OUTPUT"
