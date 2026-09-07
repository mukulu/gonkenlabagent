# GonKenLab Agent — Local Voice Assistant for Raspberry Pi 5

GonKenLab Agent is a Raspberry Pi 5 voice assistant built around local speech recognition, a local Qwen model through Ollama, and local Piper speech synthesis. External weather, news, and cloud-AI integrations are optional.

### Live Demo

Weather Report:
https://github.com/user-attachments/assets/6698d96d-14a2-45af-920d-24787662d25a

Local System Info:
https://github.com/user-attachments/assets/66fed292-bbec-45cc-ad6e-ddb9f11b678d




---

## Live Demo

**Weather Report:**

https://github.com/user-attachments/assets/6698d96d-14a2-45af-920d-24787662d25a

**Local System Info:**

https://github.com/user-attachments/assets/66fed292-bbec-45cc-ad6e-ddb9f11b678d

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RASPBERRY PI 5                           │
│                                                                 │
│  ┌──────────┐    "Hey Jarvis"     ┌──────────────────────────┐  │
│  │ USB Mic  │ ──────────────────► │  Wake Word Detector      │  │
│  │ (48kHz)  │                     │  (openWakeWord + ONNX)   │  │
│  └──────────┘                     └───────────┬──────────────┘  │
│                                               │ wake!           │
│                                               ▼                 │
│                                   ┌──────────────────────────┐  │
│                                   │  Audio Manager           │  │
│                                   │  Record → Silence detect │  │
│                                   └───────────┬──────────────┘  │
│                                               │ raw audio       │
│                                               ▼                 │
│                                   ┌──────────────────────────┐  │
│                                   │  Whisper.cpp (STT)       │  │
│                                   │  48kHz → 16kHz → text    │  │
│                                   └───────────┬──────────────┘  │
│                                               │ text            │
│                                               ▼                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    LLM Router (Ollama)                     │  │
│  │                   Qwen 2.5 · 1.5 B                        │  │
│  │                                                            │  │
│  │  Simple chat ──► respond directly                          │  │
│  │  Time/Date   ──► time_tool        (local)                  │  │
│  │  Weather     ──► weather_tool     (OpenWeatherMap API)     │  │
│  │  News        ──► news_tool        (NewsAPI)                │  │
│  │  System      ──► system_tool      (CPU temp, RAM, uptime)  │  │
│  │  Jokes       ──► joke_tool        (Official Joke API)      │  │
│  │  Complex     ──► cloud_handoff    (Kimi K2 / Moonshot)     │  │
│  └────────────────────────────────┬───────────────────────────┘  │
│                                   │ response text               │
│                                   ▼                              │
│                       ┌──────────────────────┐                   │
│                       │  Piper TTS           │                   │
│                       │  text → speech (.wav)│                   │
│                       └──────────┬───────────┘                   │
│                                  │                               │
│                 ┌────────────────┼────────────────┐              │
│                 ▼                                  ▼              │
│        ┌──────────────┐                  ┌────────────────┐      │
│        │  USB Speaker │                  │  PyGame Face   │      │
│        │  (ALSA)      │                  │  (800×480 LCD) │      │
│        └──────────────┘                  └────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | How it works | API key needed? |
|---|---|---|
| **Wake word** — "Hey Jarvis" | Bundled openWakeWord fallback; custom Hey Gonken model planned | No |
| **Local chat** — greetings, identity, simple Q&A | Qwen 2.5:1.5b via Ollama | No |
| **Time & date** | Python `datetime` | No |
| **System status** — CPU temp, RAM, uptime, disk | Reads `/proc` and `/sys` | No |
| **Jokes** | Official Joke API (free, no key) | No |
| **Weather** | OpenWeatherMap | `OPENWEATHER_API_KEY` |
| **News headlines** | NewsAPI | `NEWSAPI_KEY` |
| **Cloud AI answers** — complex / creative queries | Kimi K2 (Moonshot) | `MOONSHOT_API_KEY` |
| **Animated face UI** | PyGame on Wayland (800×480 LCD) | No |
| **Natural speech** | Piper TTS (British English voice) | No |
| **Speech recognition** | Whisper.cpp (quantised base.en model) | No |

---

## Hardware Requirements

- Raspberry Pi 5 (4 GB+ RAM recommended)
- USB microphone
- USB speaker
- 800×480 LCD display *(optional — Jansky works headless too)*
- MicroSD card (32 GB+)

---

## Quick Start (One-Command Install)

> **Prerequisite:** A fresh **Raspberry Pi OS (Bookworm, 64-bit)** installation with internet access.

### 1. Clone the repo

```bash
git clone https://github.com/mukulu/gonkenlabagent.git
cd gonkenlabagent
```

### 2. Run the install script

```bash
chmod +x setup.sh
./setup.sh
```

This single script handles **everything** listed in the [Manual Installation](#manual-installation) section below. It takes ~15-20 minutes on a Pi 5 depending on your internet speed.

### 3. Add API keys (optional)

```bash
cp .env.example .env
nano .env          # paste your keys
```

| Key | Where to get it | What you lose without it |
|---|---|---|
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) (free tier) | Weather lookups |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org/) (free tier) | News headlines |
| `MOONSHOT_API_KEY` | [platform.moonshot.ai](https://platform.moonshot.ai/) | Cloud AI for complex questions |

### 4. Verify and run GonKenLab Agent

```bash
.venv/bin/python scripts/doctor.py
.venv/bin/python tests/test_audio_pipeline.py
.venv/bin/python orchestrator.py
```

Say **"Hey Jarvis"** and start talking. This is the bundled openWakeWord fallback until a custom **Hey Gonken** model is added.

---

## Manual Installation

Use this if you prefer to install step-by-step instead of using `setup.sh`.

### 1 — System packages

```bash
sudo apt update && sudo apt install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git curl wget \
  libsdl2-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  portaudio19-dev libasound2-dev \
  alsa-utils
```

### 2 — Python virtual environment

```bash
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip setuptools wheel
```

### 3 — Python dependencies

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

### 4 — Ollama + Qwen 2.5

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen2.5:1.5b
```

### 5 — Whisper.cpp

```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release

# Download the quantised English model
bash models/download-ggml-model.sh base.en
# Quantise it (smaller + faster on Pi)
./build/bin/quantize models/ggml-base.en.bin models/ggml-base.en-q5_0.bin q5_0
cd ..
```

### 6 — Piper TTS voice

```bash
mkdir -p piper/voices
# Download British English voice (or pick another from https://rhasspy.github.io/piper-samples/)
wget -O piper/voices/en_GB-semaine-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx
wget -O piper/voices/en_GB-semaine-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json
```

### 7 — Wake word model

This repository currently uses openWakeWord’s bundled **"Hey Jarvis"** model as a fallback. A custom **"Hey Gonken"** ONNX model is not yet bundled; it must be trained and tested before changing the actual activation phrase.

### 8 — API keys

```bash
cp .env.example .env
nano .env   # fill in your keys (all optional)
```

### 9 — Run

```bash
.venv/bin/python orchestrator.py
```

---

## Project Structure

```
gonkenlabagent/
├── orchestrator.py              # Main entry point — ties everything together
├── config.py                    # Dataclass config, loads .env + config.json
├── setup.sh                     # One-command install script
├── requirements.txt             # Python runtime dependencies
├── .env.example                 # Template for API keys
├── scripts/doctor.py            # Installation and hardware diagnostics
│
├── audio/
│   ├── audio_manager.py         # Mic recording (silence detection) + speaker playback
│   ├── tts_engine.py            # Piper TTS wrapper (text → WAV)
│   └── stt_engine.py            # Whisper.cpp wrapper (audio → text)
│
├── brain/
│   ├── router.py                # Intent routing — keyword + LLM tool-calling
│   ├── ollama_client.py         # Ollama HTTP client (chat + streaming)
│   ├── cloud_client.py          # Kimi K2 / Moonshot HTTP client
│   ├── tool_definitions.py      # Tool schemas + system prompt for Qwen
│   └── tools/
│       ├── time_tool.py         # Current time & date
│       ├── weather_tool.py      # OpenWeatherMap lookup
│       ├── news_tool.py         # NewsAPI top headlines
│       ├── system_tool.py       # CPU temp, RAM, uptime, disk
│       └── joke_tool.py         # Random joke API
│
├── senses/
│   └── wake_word_detector.py    # openWakeWord listener (threaded)
│
├── ui/
│   └── ui_manager.py            # PyGame animated face (Wayland/framebuffer)
│
├── config/
│   ├── config.json              # Runtime config (paths, thresholds, display)
│   ├── local_soul.md            # Personality prompt for local LLM
│   └── cloud_soul.md            # Personality prompt for cloud LLM
│
├── assets/
│   ├── face/                    # PNG face expressions for the UI
│   └── fillers/                 # Pre-generated filler WAVs ("Thinking...", etc.)
│
├── piper/voices/                # Piper TTS voice files (downloaded during setup)
├── whisper.cpp/                 # Whisper.cpp source + compiled binary + model
└── tests/
    ├── test_router.py           # Router / intent detection tests
    ├── test_wake_word.py        # Wake word detector test
    └── test_audio_pipeline.py   # End-to-end audio pipeline test
```

---

## Configuration

All runtime settings live in `config/config.json`. Key values:

| Setting | Default | Description |
|---|---|---|
| `chat_model` | `qwen2.5:1.5b` | Ollama model for routing + chat |
| `wake_word_threshold` | `0.5` | Wake word confidence threshold (0–1) |
| `mic_sample_rate` | `48000` | Native sample rate of your USB mic |
| `local_location` | `Kingston, CA` | Default city for weather lookups |
| `display_width` / `display_height` | `800` / `480` | UI resolution |
| `enable_ui` | `false` | Set `true` only when the optional display UI is configured |

API keys are loaded from `.env` and are **never** written to `config.json`.

---

## Testing Individual Components

```bash
# Test the LLM router (requires Ollama running)
.venv/bin/python tests/test_router.py

# Test wake word detection
.venv/bin/python tests/test_wake_word.py

# Test full audio pipeline (mic → STT → TTS → speaker)
.venv/bin/python tests/test_audio_pipeline.py
```

---

## How It Works (Flow)

1. **Wake word** — the current repository listens for the bundled openWakeWord **"Hey Jarvis"** fallback. A custom **"Hey Gonken"** model is planned as a separate improvement.
2. **Record** — Once triggered, the mic stream is paused from wake-word duty and handed to the Audio Manager, which records until silence is detected (1.5 s of quiet).
3. **Transcribe** — The recorded audio (48 kHz) is downsampled to 16 kHz and sent to Whisper.cpp, which returns the text.
4. **Route** — The Router sends the text to Ollama (Qwen 2.5:1.5b) with tool-calling enabled. If the model returns a structured tool call, that tool runs. Otherwise, keyword-based fallback detection kicks in.
5. **Respond** — The response text is synthesised to speech by Piper TTS and played through the USB speaker via ALSA.
6. **UI** — Throughout the flow the PyGame face reflects the current state: idle → listening → thinking → speaking → idle.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| AIRHUG microphone not found | Check `arecord -l` and the Python device list. AIRHUG is the default; override with `GONKEN_MIC_NAME` in `.env` if needed. |
| AIRHUG speaker not found | Check `aplay -l`. AIRHUG is the default; override with `GONKEN_SPEAKER_NAME` in `.env` if needed. |
| Whisper not found | Run `which whisper-cpp`. If it's elsewhere, update `whisper_path` in `config/config.json`. |
| Ollama not running | Run `ollama serve` in another terminal, then `ollama pull qwen2.5:1.5b`. |
| No display / PyGame crash | Set `"enable_ui": false` in `config/config.json` to run headless. |
| Weather / News / Cloud AI says "not configured" | Add the matching API key to `.env`. |

---

## License

MIT
