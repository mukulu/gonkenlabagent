#!/usr/bin/env bash
# ==============================================================
# GonKenLab Agent — one-command installer for Raspberry Pi 5
# ==============================================================
# Usage: chmod +x setup.sh && ./setup.sh
#
# The installer is intentionally safe to rerun. It:
#   1. installs required system packages;
#   2. creates/reuses the Python virtual environment;
#   3. installs Python dependencies;
#   4. installs Ollama, starts/waits for its server, pulls Qwen,
#      and performs a non-interactive Qwen smoke test;
#   5. builds/reuses whisper.cpp and its model;
#   6. downloads/reuses the Piper voice;
#   7. creates .env only when it does not already exist.
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${YELLOW}[→]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
OLLAMA_URL="http://127.0.0.1:11434"
VENV_DIR="$SCRIPT_DIR/venv313"
WHISPER_DIR="$SCRIPT_DIR/whisper.cpp"
WHISPER_BIN="/usr/local/bin/whisper-cpp"
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
    sudo systemctl daemon-reload || true
    sudo systemctl enable --now ollama || sudo systemctl start ollama
  else
    # Fallback for installations without an Ollama systemd unit.
    if ! pgrep -x ollama >/dev/null 2>&1; then
      nohup ollama serve >"$SCRIPT_DIR/ollama.log" 2>&1 &
    fi
  fi

  for _ in $(seq 1 45); do
    if ollama_ready; then
      ok "Ollama server is ready"
      return 0
    fi
    sleep 1
  done

  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl status ollama --no-pager 2>/dev/null || true
  fi
  [ -f "$SCRIPT_DIR/ollama.log" ] && tail -n 40 "$SCRIPT_DIR/ollama.log" || true
  fail "Ollama was installed but its server did not become ready at $OLLAMA_URL"
}

# ── 1. System packages ───────────────────────────────────────
info "Installing system packages …"
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils
ok "System packages installed"

# ── 2. Python virtual environment ────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  info "Creating Python virtual environment …"
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip -q
ok "Virtual environment ready ($VENV_DIR)"

# ── 3. Python dependencies ───────────────────────────────────
info "Installing Python packages …"
python -m pip install -q \
  httpx \
  sounddevice \
  numpy \
  piper-tts \
  openwakeword \
  onnxruntime \
  pygame
ok "Python packages installed"

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
OLLAMA_SMOKE_OUTPUT="$(ollama run "$OLLAMA_MODEL" 'Reply with exactly: OK' 2>&1)" \
  || fail "Qwen smoke test failed: $OLLAMA_SMOKE_OUTPUT"
ok "Qwen is runnable through Ollama"

# ── 5. whisper.cpp ───────────────────────────────────────────
if [ ! -d "$WHISPER_DIR/.git" ]; then
  info "Cloning whisper.cpp …"
  rm -rf "$WHISPER_DIR"
  git clone https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
fi

if [ ! -x "$WHISPER_BIN" ]; then
  info "Building whisper.cpp …"
  cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build"
  cmake --build "$WHISPER_DIR/build" --config Release -j"$(nproc)"
  sudo cp "$WHISPER_DIR/build/bin/whisper-cli" "$WHISPER_BIN"
  sudo chmod +x "$WHISPER_BIN"
  ok "whisper.cpp installed to $WHISPER_BIN"
else
  ok "whisper.cpp binary already installed"
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
    cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build"
    cmake --build "$WHISPER_DIR/build" --config Release -j"$(nproc)"
    QUANTIZER="$(find "$WHISPER_DIR/build/bin" -maxdepth 1 -type f -perm -111 -iname '*quant*' | head -n 1 || true)"
  fi
  [ -n "$QUANTIZER" ] || fail "Could not locate whisper.cpp quantizer"

  "$QUANTIZER" "$BASE_MODEL" "$WHISPER_MODEL" q5_0
  ok "Whisper model ready: $WHISPER_MODEL"
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

# ── 7. .env ──────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  chmod 600 "$SCRIPT_DIR/.env"
  info "Created .env from template (API keys remain optional)"
else
  ok ".env already exists; leaving it unchanged"
fi

# ── Installation summary ─────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  GonKenLab Agent installation completed${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
echo "  Repository: $SCRIPT_DIR"
echo "  Ollama:     $OLLAMA_URL"
echo "  Model:      $OLLAMA_MODEL"
echo "  Microphone/speaker default match: AIRHUG"
echo ""
echo "  Test audio pipeline:"
echo "    source venv313/bin/activate"
echo "    python tests/test_audio_pipeline.py"
echo ""
echo "  Start assistant:"
echo "    python orchestrator.py"
echo ""
echo "  Note: the repository currently has no custom Hey Gonken wake-word model."
echo "  Wake-word training will be handled separately."
echo ""
