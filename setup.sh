#!/usr/bin/env bash
# ==============================================================
# GonKenLab Agent — one-command installer for Raspberry Pi 5
# ==============================================================
# Usage: chmod +x setup.sh && ./setup.sh
#
# Safe to rerun. Python dependencies are installed only inside
# the repository-owned .venv; the Debian/Raspberry Pi OS system
# Python is never modified with pip.
# ==============================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

on_error() {
  local exit_code=$?
  local line_no=${1:-unknown}
  echo -e "${RED}[✗]${NC} Setup failed at line ${line_no} (exit ${exit_code})." >&2
  exit "$exit_code"
}
trap 'on_error $LINENO' ERR

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${GONKEN_VENV_DIR:-$SCRIPT_DIR/.venv}"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
LEGACY_VENV_DIR="$SCRIPT_DIR/venv313"
OPENWAKEWORD_VERSION="${OPENWAKEWORD_VERSION:-0.6.0}"

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OLLAMA_LOG="${XDG_RUNTIME_DIR:-/tmp}/gonkenlabagent-ollama.log"

WHISPER_DIR="$SCRIPT_DIR/whisper.cpp"
WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
WHISPER_REF="${WHISPER_REF:-b4938}"
WHISPER_MODEL_NAME="${WHISPER_MODEL_NAME:-base.en-q5_1}"
WHISPER_MODEL="$WHISPER_DIR/models/ggml-${WHISPER_MODEL_NAME}.bin"
WHISPER_SAMPLE="$WHISPER_DIR/samples/jfk.wav"

PIPER_VOICE="$SCRIPT_DIR/piper/voices/en_GB-semaine-medium.onnx"

ollama_ready() {
  curl -fsS "$OLLAMA_URL/api/version" >/dev/null 2>&1
}

start_ollama() {
  if ollama_ready; then
    ok "Ollama server is already running"
    return 0
  fi

  info "Starting Ollama server …"

  if command -v systemctl >/dev/null 2>&1 \
      && systemctl list-unit-files --type=service 2>/dev/null \
        | grep -q '^ollama\.service'; then
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
    sudo systemctl enable ollama >/dev/null 2>&1 || true
    sudo systemctl start ollama || true
  fi

  # Some Ollama installations do not create a systemd unit. Fall back to a
  # user-owned background server rather than failing immediately.
  if ! ollama_ready && ! pgrep -f '[o]llama serve' >/dev/null 2>&1; then
    nohup ollama serve >"$OLLAMA_LOG" 2>&1 &
  fi

  for _ in $(seq 1 60); do
    if ollama_ready; then
      ok "Ollama server is ready"
      return 0
    fi
    sleep 1
  done

  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl status ollama --no-pager 2>/dev/null || true
  fi
  [ -f "$OLLAMA_LOG" ] && tail -n 50 "$OLLAMA_LOG" || true
  fail "Ollama did not become ready at $OLLAMA_URL"
}

venv_is_valid() {
  [ -x "$VENV_PYTHON" ] || return 1
  "$VENV_PYTHON" -c \
    'import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)' \
    >/dev/null 2>&1 || return 1
  "$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || return 1
}

create_venv() {
  info "Creating Python virtual environment at $VENV_DIR …"
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR" || \
    fail "Could not create $VENV_DIR. Ensure python3-venv is installed."

  # venv normally bootstraps pip through ensurepip. Run it explicitly as a
  # recovery step for minimal Debian/Raspberry Pi OS images.
  "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true

  venv_is_valid || \
    fail "Virtual environment was created but pip is unavailable inside it."
}

whisper_binary_runs() {
  [ -x "$WHISPER_BIN" ] || return 1
  timeout 15 "$WHISPER_BIN" -h >/dev/null 2>&1
}

whisper_static_configured() {
  [ -f "$WHISPER_DIR/build/CMakeCache.txt" ] || return 1
  grep -Fxq 'BUILD_SHARED_LIBS:BOOL=OFF' "$WHISPER_DIR/build/CMakeCache.txt"
}

build_whisper_static() {
  info "Building a self-contained whisper.cpp CLI …"
  rm -rf "$WHISPER_DIR/build"
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DWHISPER_BUILD_TESTS=OFF \
    -DWHISPER_BUILD_SERVER=OFF \
    -DWHISPER_BUILD_EXAMPLES=ON \
    -DWHISPER_CURL=OFF
  cmake --build "$WHISPER_DIR/build" --config Release \
    --target whisper-cli -j"$(nproc)"
  [ -x "$WHISPER_BIN" ] || fail "Whisper binary was not produced at $WHISPER_BIN"
  whisper_static_configured || fail "Whisper build is not configured with BUILD_SHARED_LIBS=OFF"
  whisper_binary_runs || fail "Whisper binary was built but cannot start"
  if ldd "$WHISPER_BIN" 2>/dev/null | grep -q 'not found'; then
    ldd "$WHISPER_BIN" >&2 || true
    fail "Whisper binary still has unresolved shared-library dependencies"
  fi
  ok "whisper.cpp CLI built and runtime-validated"
}

# ── 1. System packages ───────────────────────────────────────
info "Installing required system packages …"
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils
ok "System packages installed"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || \
  fail "$PYTHON_BIN was not found after package installation"

if [ -d "$LEGACY_VENV_DIR" ] && [ "$LEGACY_VENV_DIR" != "$VENV_DIR" ]; then
  info "Legacy venv313 detected; it is ignored. .venv is the canonical environment."
fi
[ -f "$REQUIREMENTS_FILE" ] || \
  fail "Missing dependency file: $REQUIREMENTS_FILE"

# ── 2. Python virtual environment ────────────────────────────
if [ -d "$VENV_DIR" ] && ! venv_is_valid; then
  info "Existing virtual environment is incomplete or stale; recreating it …"
  create_venv
elif [ ! -d "$VENV_DIR" ]; then
  create_venv
else
  ok "Existing virtual environment is valid"
fi

# Always call pip through the venv interpreter. This intentionally avoids
# Debian/Raspberry Pi OS PEP 668 restrictions on the system Python.
info "Updating packaging tools inside .venv …"
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

# ── 3. Python dependencies ───────────────────────────────────
info "Installing Python dependencies into .venv …"
"$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"

# openWakeWord 0.6.0 declares tflite-runtime as a Linux dependency even when
# the application uses ONNX Runtime only. Python 3.13 ARM64 has no compatible
# tflite-runtime wheel, so install the package itself without dependency
# resolution and provide its ONNX-side dependencies explicitly above.
info "Installing openWakeWord ${OPENWAKEWORD_VERSION} in ONNX-only mode …"
"$VENV_PYTHON" -m pip install --no-deps "openwakeword==${OPENWAKEWORD_VERSION}"

info "Preparing and validating openWakeWord ONNX models …"
"$VENV_PYTHON" - <<'PY'
from pathlib import Path

import numpy as np
import openwakeword
from openwakeword.model import Model
from openwakeword.utils import download_file

model_dir = Path(openwakeword.__file__).resolve().parent / "resources" / "models"
model_dir.mkdir(parents=True, exist_ok=True)

onnx_urls = [
    openwakeword.FEATURE_MODELS["melspectrogram"]["download_url"].replace(
        ".tflite", ".onnx"
    ),
    openwakeword.FEATURE_MODELS["embedding"]["download_url"].replace(
        ".tflite", ".onnx"
    ),
    openwakeword.MODELS["hey_jarvis"]["download_url"].replace(
        ".tflite", ".onnx"
    ),
]

for url in onnx_urls:
    destination = model_dir / url.rsplit("/", 1)[-1]
    if not destination.is_file() or destination.stat().st_size == 0:
        if destination.exists():
            destination.unlink()
        download_file(url, str(model_dir))

required = [
    model_dir / "melspectrogram.onnx",
    model_dir / "embedding_model.onnx",
    model_dir / "hey_jarvis_v0.1.onnx",
]
missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
if missing:
    raise RuntimeError("Missing openWakeWord ONNX model files: " + ", ".join(missing))

model = Model(
    wakeword_models=[str(model_dir / "hey_jarvis_v0.1.onnx")],
    inference_framework="onnx",
)
prediction = model.predict(np.zeros(1280, dtype=np.int16))
if not isinstance(prediction, dict):
    raise RuntimeError("openWakeWord ONNX smoke test returned an unexpected result")

print("openWakeWord ONNX smoke test passed")
PY

ok "Python environment ready ($VENV_DIR)"

# ── 4. Ollama + Qwen ─────────────────────────────────────────
if ! command -v ollama >/dev/null 2>&1; then
  info "Installing Ollama …"
  curl -fsSL https://ollama.com/install.sh | sh
else
  ok "Ollama already installed"
fi

start_ollama

if ollama list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Fxq "$OLLAMA_MODEL"; then
  ok "$OLLAMA_MODEL already present"
else
  info "Pulling $OLLAMA_MODEL (this may take a few minutes) …"
  ollama pull "$OLLAMA_MODEL"
  ok "$OLLAMA_MODEL downloaded"
fi

info "Running a Qwen smoke test …"
if command -v timeout >/dev/null 2>&1; then
  OLLAMA_SMOKE_OUTPUT="$(timeout 180 ollama run "$OLLAMA_MODEL" 'Reply with exactly: OK' 2>&1)" || \
    fail "Qwen smoke test failed: $OLLAMA_SMOKE_OUTPUT"
else
  OLLAMA_SMOKE_OUTPUT="$(ollama run "$OLLAMA_MODEL" 'Reply with exactly: OK' 2>&1)" || \
    fail "Qwen smoke test failed: $OLLAMA_SMOKE_OUTPUT"
fi
[ -n "$OLLAMA_SMOKE_OUTPUT" ] || fail "Qwen smoke test returned no output"
ok "Qwen is runnable through Ollama"

# ── 5. whisper.cpp ───────────────────────────────────────────
if [ ! -d "$WHISPER_DIR/.git" ]; then
  info "Cloning whisper.cpp …"
  rm -rf "$WHISPER_DIR"
  git clone https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
else
  ok "whisper.cpp source already present"
fi

# Pin the dependency to a known release so a future upstream change does not
# silently break fresh Raspberry Pi installations.
if ! git -C "$WHISPER_DIR" rev-parse -q --verify "${WHISPER_REF}^{commit}" >/dev/null; then
  info "Fetching whisper.cpp release ${WHISPER_REF} …"
  git -C "$WHISPER_DIR" fetch --depth 1 origin \
    "refs/tags/${WHISPER_REF}:refs/tags/${WHISPER_REF}"
fi
git -C "$WHISPER_DIR" checkout --detach -q "$WHISPER_REF"

# A file can exist and still be unusable. In particular, older builds used
# shared libwhisper/libggml objects that were not on Raspberry Pi's linker path.
# Repair any such build automatically and use static project libraries.
if ! whisper_static_configured || ! whisper_binary_runs; then
  info "Whisper build is missing, stale, or not runnable; rebuilding …"
  build_whisper_static
else
  ok "whisper.cpp binary is self-contained and runnable"
fi

# Download an official pre-quantised Whisper model. This avoids local
# quantisation tools and keeps fresh installs deterministic.
if [ ! -s "$WHISPER_MODEL" ]; then
  info "Downloading Whisper ${WHISPER_MODEL_NAME} model …"
  rm -f "$WHISPER_MODEL"
  (cd "$WHISPER_DIR" && bash models/download-ggml-model.sh "$WHISPER_MODEL_NAME")
  [ -s "$WHISPER_MODEL" ] || fail "Whisper model was not downloaded to $WHISPER_MODEL"
  ok "Whisper model ready"
else
  ok "Whisper model already present"
fi

[ -s "$WHISPER_SAMPLE" ] || fail "Whisper validation sample is missing: $WHISPER_SAMPLE"
info "Running Whisper transcription smoke test …"
WHISPER_TEST_LOG="$(mktemp)"
if ! WHISPER_TEST_OUTPUT="$(timeout 120 "$WHISPER_BIN" \
    -m "$WHISPER_MODEL" -f "$WHISPER_SAMPLE" -l en -t 2 \
    --no-timestamps -np 2>"$WHISPER_TEST_LOG")"; then
  cat "$WHISPER_TEST_LOG" >&2 || true
  rm -f "$WHISPER_TEST_LOG"
  fail "Whisper could not transcribe its bundled validation sample"
fi
rm -f "$WHISPER_TEST_LOG"
[ -n "${WHISPER_TEST_OUTPUT//[[:space:]]/}" ] || \
  fail "Whisper validation produced an empty transcription"
ok "Whisper runtime and transcription validated"

# ── 6. Piper TTS voice ──────────────────────────────────────
if [ ! -f "$PIPER_VOICE" ]; then
  info "Downloading Piper TTS voice …"
  mkdir -p "$(dirname "$PIPER_VOICE")"
  wget -q -O "$PIPER_VOICE" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
  wget -q -O "${PIPER_VOICE}.json" \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json
  ok "Piper voice downloaded"
else
  ok "Piper voice already present"
fi

[ -s "$PIPER_VOICE" ] || fail "Piper voice file is missing or empty: $PIPER_VOICE"
[ -s "${PIPER_VOICE}.json" ] || fail "Piper voice config is missing or empty: ${PIPER_VOICE}.json"

# ── 7. Local environment file ────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  chmod 600 "$SCRIPT_DIR/.env"
  info "Created .env from template (API keys remain optional)"
else
  ok ".env already exists; leaving it unchanged"
fi

# ── 8. Post-install verification ──────────────────────────────
info "Running installation diagnostics …"
"$VENV_PYTHON" "$SCRIPT_DIR/scripts/doctor.py" || \
  fail "Required software diagnostics failed. Review the FAIL entries above."

HARDWARE_STATUS="checked"
if [ "${GONKEN_SKIP_HARDWARE_TEST:-0}" = "1" ]; then
  HARDWARE_STATUS="skipped"
  info "Skipping physical audio smoke test because GONKEN_SKIP_HARDWARE_TEST=1"
else
  info "Running software + available-hardware smoke test …"
  "$VENV_PYTHON" "$SCRIPT_DIR/scripts/smoke_test.py" || \
    fail "Smoke test failed. Check the messages above."
fi

# ── 9. Installation summary ──────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  GonKenLab Agent is ready${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo "  Repository: $SCRIPT_DIR"
echo "  Python:     $VENV_PYTHON"
echo "  Ollama:     $OLLAMA_URL"
echo "  Model:      $OLLAMA_MODEL"
echo "  Whisper:    $WHISPER_BIN"
echo "  Whisper model: $WHISPER_MODEL_NAME"
echo "  Hardware check: $HARDWARE_STATUS"
echo ""
if [ "$HARDWARE_STATUS" = "skipped" ]; then
  echo "  Hardware checks were skipped; run .venv/bin/python scripts/smoke_test.py before use."
else
  echo "  Software checks passed. Audio hardware is PASS/WARN as reported above."
fi
echo ""
echo "  Start the assistant with:"
echo "    cd $SCRIPT_DIR"
echo "    .venv/bin/python orchestrator.py"
echo ""
echo "  Then say: Hey Jarvis"
echo ""
echo "  The current wake word is the bundled Hey Jarvis ONNX model."
echo "  A trained Hey Gonken model can replace it in a later revision."
echo ""
