#!/usr/bin/env bash
# Explicit current-hardware deployment; delegates all installer logic to bootstrap.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
args=()
mode=automatic
preset=responsive-room
while (($#)); do
  case "$1" in
    -h|--help)
      cat <<'EOF'
Usage: ./install-room-appliance.sh [OPTIONS]
Deploy this exact local checkpoint with real SHT31 (I2C1/0x44), the active-high
GPIO23 room-fan relay, and automatic temperature control. No simulated fallback.
Running this command authorizes the real daemon to switch room-fan power according
to the selected policy. First startup is safe-OFF. The responsive-room preset
selects qwen3:0.6b, ON >=28 C, OFF <=26 C; existing valid dwell is preserved.
Factory minimum ON/OFF dwell is 60 seconds. Other profiles are never silently migrated.
Do not attach/reseat wiring while powered; the relay circuit must already be wired.

Options delegated to bootstrap:
  --appliance-preset P    responsive-room (default) or none to preserve model/thresholds
  --environment-mode M     automatic (default), preserve, manual, semi_automatic, disabled
  --sensor-address ADDR    0x44 (default) or 0x45
  --model-provision-mode M online (default) or preseeded-offline
  --bluetooth-audio        optional Bluetooth setup; usable USB remains valid
  --bluetooth-device ID    optional configured device selector
  --preflight-only         inspect without installing/starting hardware
  --staging-parent PATH    bootstrap staging directory

Generic/explicit simulation installations remain available through bootstrap.sh.
This wrapper never rewrites an arbitrary administrator configuration.
EOF
      exit 0 ;;
    --appliance-preset)
      (($# >= 2)) || { echo "Missing preset" >&2; exit 64; }
      preset="$2"; shift 2 ;;
    --environment-mode)
      (($# >= 2)) || { echo 'Missing mode' >&2; exit 64; }
      mode="$2"; shift 2 ;;
    --sensor-address|--model-provision-mode|--bluetooth-device|--staging-parent)
      (($# >= 2)) || { echo 'Missing option value' >&2; exit 64; }
      args+=("$1" "$2"); shift 2 ;;
    --bluetooth-audio|--preflight-only) args+=("$1"); shift ;;
    *) printf '[ERROR] unsupported room-appliance option: %s\n' "$1" >&2; exit 64 ;;
  esac
done
printf '[CONFIG] profile=full-real mode=%s sensor=SHT31 relay=GPIO23 simulation=false\n' "$mode"
exec "$ROOT/bootstrap.sh" --local-checkpoint --environment-profile full-real --environment-mode "$mode" --appliance-preset "$preset" "${args[@]}"
