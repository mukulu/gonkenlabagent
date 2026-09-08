#!/usr/bin/env python3
"""Explicit legacy wake-detector probe; not an accepted X1 evaluation."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if os.environ.get("GONKEN_RUN_HARDWARE_TESTS") != "1":
        print(
            "Legacy wake probe disabled. Read tests/hardware/README.md and set "
            "GONKEN_RUN_HARDWARE_TESTS=1 only with intentional supervision."
        )
        return 2

    sys.path.insert(0, str(ROOT))
    from config import Config
    from senses.wake_word_detector import WakeWordDetector

    config = Config.load()
    try:
        detector = WakeWordDetector(
            model_path=config.wake_word_model,
            threshold=config.wake_word_threshold,
            sample_rate=config.target_sample_rate,
            mic_sample_rate=config.mic_sample_rate,
            mic_name=config.mic_name,
        )
    except Exception as exc:
        print(f"Legacy wake detector failed to initialize: {exc}", file=sys.stderr)
        return 1

    print(f"Loaded legacy model identity: {detector.active_model}")
    print(
        "No spoken phrase is advertised: this model is compatibility evidence, "
        "not the accepted Hey Gonken X1 artifact. Waiting up to 30 seconds."
    )
    detected = False

    def on_wake_word() -> None:
        nonlocal detected
        detected = True
        print("Legacy detector produced an activation.")

    try:
        detector.start(callback=on_wake_word)
        started = time.monotonic()
        while not detected and time.monotonic() - started < 30:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Probe interrupted.")
    finally:
        detector.stop()
    return 0 if detected else 1


if __name__ == "__main__":
    raise SystemExit(main())
