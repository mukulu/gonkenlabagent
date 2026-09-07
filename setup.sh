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
WHISPER_MODEL="$WHISPER_DIR/models/ggml-base.en-q5_0.bin"

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

if [ ! -x "$WHISPER_BIN" ]; then
  info "Building whisper.cpp …"
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build"
  cmake --build "$WHISPER_DIR/build" --config Release -j"$(nproc)"
  [ -x "$WHISPER_BIN" ] || fail "Whisper binary was not produced at $WHISPER_BIN"
  ok "whisper.cpp built successfully"
else
  ok "whisper.cpp binary already built"
fi

if [ ! -f "$WHISPER_MODEL" ]; then
  info "Preparing Whisper base.en q5_0 model …"
  BASE_MODEL="$WHISPER_DIR/models/ggml-base.en.bin"

  if [ ! -f "$BASE_MODEL" ]; then
    (cd "$WHISPER_DIR" && bash models/download-ggml-model.sh base.en)
  fi

  QUANTIZER="$(find "$WHISPER_DIR/build/bin" -maxdepth 1 -type f -perm -111 -iname '*quant*' | head -n 1 || true)"
  if [ -z "$QUANTIZER" ]; then
    info "Quantizer not found; rebuilding whisper.cpp tools …"
    cmake --build "$WHISPER_DIR/build" --config Release -j"$(nproc)"
    QUANTIZER="$(find "$WHISPER_DIR/build/bin" -maxdepth 1 -type f -perm -111 -iname '*quant*' | head -n 1 || true)"
  fi

  [ -n "$QUANTIZER" ] || fail "Could not locate whisper.cpp quantizer"
  "$QUANTIZER" "$BASE_MODEL" "$WHISPER_MODEL" q5_0
  [ -s "$WHISPER_MODEL" ] || fail "Whisper model was not created"
  ok "Whisper model ready"
else
  ok "Whisper model already present"
fi

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

# ── 8. Installation summary ──────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  GonKenLab Agent installation completed${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo "  Repository: $SCRIPT_DIR"
echo "  Python:     $VENV_PYTHON"
echo "  Ollama:     $OLLAMA_URL"
echo "  Model:      $OLLAMA_MODEL"
echo "  Whisper:    $WHISPER_BIN"
echo "  Audio match defaults: AIRHUG"
echo ""
echo "  Diagnose installation:"
echo "    .venv/bin/python scripts/doctor.py"
echo ""
echo "  Test audio pipeline:"
echo "    .venv/bin/python tests/test_audio_pipeline.py"
echo ""
echo "  Start assistant:"
echo "    .venv/bin/python orchestrator.py"
echo ""
echo "  Wake word: Hey Jarvis (bundled fallback)."
echo "  A trained Hey Gonken model can replace it in a later revision."
echo ""
