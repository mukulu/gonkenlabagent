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
    }
    ok = True
    for module, package in modules.items():
        try:
            importlib.import_module(module)
            report(PASS, f"Python dependency {package}")
        except Exception as exc:
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


def check_whisper_runtime(config: Config) -> bool:
    path = Path(config.whisper_path)
    if not path.is_file():
        return False
    try:
        result = subprocess.run(
            [str(path), "-h"], capture_output=True, text=True, timeout=15
        )
    except Exception as exc:
        report(FAIL, "Whisper runtime", str(exc))
        return False

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        report(FAIL, "Whisper runtime", detail or f"exit {result.returncode}")
        return False

    report(PASS, "Whisper runtime", "whisper-cli starts successfully")
    return True


def check_piper_runtime(config: Config) -> bool:
    try:
        from piper import PiperVoice

        PiperVoice.load(config.piper_voice)
        report(PASS, "Piper voice runtime", Path(config.piper_voice).name)
        return True
    except Exception as exc:
        report(FAIL, "Piper voice runtime", str(exc))
        return False


def check_openwakeword_runtime() -> bool:
    try:
        import numpy as np
        import openwakeword
        from openwakeword.model import Model

        model_path = (
            Path(openwakeword.__file__).resolve().parent
            / "resources"
            / "models"
            / "hey_jarvis_v0.1.onnx"
        )
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
        prediction = model.predict(np.zeros(1280, dtype=np.int16))
        if not isinstance(prediction, dict):
            raise RuntimeError("unexpected prediction result")
        report(PASS, "openWakeWord ONNX runtime", model_path.name)
        return True
    except Exception as exc:
        report(FAIL, "openWakeWord ONNX runtime", str(exc))
        return False


def check_ollama(config: Config) -> bool:
    try:
        with urllib.request.urlopen(
            f"{config.ollama_base_url}/api/version", timeout=3
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
        report(PASS if present else FAIL, "Ollama model", config.chat_model)
        return present
    except Exception as exc:
        report(FAIL, "Ollama model list", str(exc))
        return False


def check_audio(config: Config) -> bool:
    """Report audio readiness without making unplugged hardware a software failure."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
    except Exception as exc:
        report(WARN, "Audio device enumeration", str(exc))
        return True

    available = [
        (i, d["name"], int(d["max_input_channels"]), int(d["max_output_channels"]))
        for i, d in enumerate(devices)
    ]
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
        PASS if mic_matches else WARN,
        "Microphone match",
        repr(mic_matches) if mic_matches else f"wanted {config.mic_name!r}",
    )
    report(
        PASS if speaker_matches else WARN,
        "Speaker match",
        repr(speaker_matches) if speaker_matches else f"wanted {config.speaker_name!r}",
    )
    if not mic_matches or not speaker_matches:
        print(f"[WARN] Available audio devices: {available}")
        print(
            "[WARN] Override device-name matching in site TOML or with "
            "GONKEN_AUDIO_INPUT_MATCH and GONKEN_AUDIO_OUTPUT_MATCH."
        )
    return True


def main() -> int:
    print("GonKenLab Agent diagnostics")
    print(f"Repository: {PROJECT_ROOT}")
    print()

    config = Config.load()
    checks = [
        check_python(),
        check_imports(),
        check_paths(config),
        check_whisper_runtime(config),
        check_piper_runtime(config),
        check_openwakeword_runtime(),
        check_ollama(config),
        check_audio(config),
    ]

    print()
    if all(checks):
        print("All required software diagnostics passed. Hardware warnings may remain above.")
        return 0

    print("One or more required software diagnostics failed. Review the FAIL entries above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
