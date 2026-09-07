#!/usr/bin/env python3
"""Diagnostic checks for a GonKenLab Agent installation."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import Config  # noqa: E402


PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def report(status: str, name: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def check_python() -> bool:
    in_venv = sys.prefix != sys.base_prefix
    report(PASS if in_venv else FAIL, "Python virtual environment", sys.executable)
    return in_venv


def check_imports() -> bool:
    modules = {
        "httpx": "httpx",
        "sounddevice": "sounddevice",
        "numpy": "numpy",
        "piper": "piper-tts",
        "openwakeword": "openwakeword",
        "onnxruntime": "onnxruntime",
        "pygame": "pygame",
    }
    ok = True
    for module, package in modules.items():
        try:
            importlib.import_module(module)
            report(PASS, f"Python dependency {package}")
        except Exception as exc:  # diagnostics should continue through all checks
            ok = False
            report(FAIL, f"Python dependency {package}", str(exc))
    return ok


def check_paths(config: Config) -> bool:
    paths = {
        "Piper voice": Path(config.piper_voice),
        "Whisper binary": Path(config.whisper_path),
        "Whisper model": Path(config.whisper_model),
        "Local soul": Path(config.local_soul_path),
    }
    ok = True
    for name, path in paths.items():
        exists = path.is_file()
        report(PASS if exists else FAIL, name, str(path))
        ok &= exists
    return ok


def check_ollama(config: Config) -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/version", timeout=3
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        report(PASS, "Ollama server", str(payload.get("version", "unknown version")))
    except Exception as exc:
        report(FAIL, "Ollama server", str(exc))
        return False

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        installed = {
            line.split()[0]
            for line in result.stdout.splitlines()[1:]
            if line.split()
        }
        present = config.chat_model in installed
        report(
            PASS if present else FAIL,
            "Ollama model",
            config.chat_model,
        )
        return present
    except Exception as exc:
        report(FAIL, "Ollama model list", str(exc))
        return False


def check_audio(config: Config) -> bool:
    try:
        import sounddevice as sd
    except Exception as exc:
        report(FAIL, "Audio library", str(exc))
        return False

    try:
        devices = sd.query_devices()
    except Exception as exc:
        report(FAIL, "Audio device enumeration", str(exc))
        return False

    mic_matches = [
        (i, d["name"])
        for i, d in enumerate(devices)
        if config.mic_name.lower() in d["name"].lower()
        and d["max_input_channels"] > 0
    ]
    speaker_matches = [
        (i, d["name"])
        for i, d in enumerate(devices)
        if config.speaker_name.lower() in d["name"].lower()
        and d["max_output_channels"] > 0
    ]

    report(
        PASS if mic_matches else FAIL,
        "Microphone match",
        repr(mic_matches) if mic_matches else config.mic_name,
    )
    report(
        PASS if speaker_matches else FAIL,
        "Speaker match",
        repr(speaker_matches) if speaker_matches else config.speaker_name,
    )
    return bool(mic_matches and speaker_matches)


def main() -> int:
    print("GonKenLab Agent diagnostics")
    print(f"Repository: {PROJECT_ROOT}")
    print()

    config = Config.load()
    checks = [
        check_python(),
        check_imports(),
        check_paths(config),
        check_ollama(config),
        check_audio(config),
    ]

    print()
    if all(checks):
        print("All core diagnostics passed.")
        return 0

    print("One or more diagnostics failed. Review the FAIL entries above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
