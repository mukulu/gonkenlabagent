"""Wake word detection using openWakeWord."""

import os
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

try:
    import openwakeword
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False


DEFAULT_MIC_NAME = os.getenv("GONKEN_MIC_NAME", "AIRHUG")


def _find_mic_device(name_substring: str) -> int:
    """Find an input-capable microphone by case-insensitive name substring."""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if (
            name_substring.lower() in device["name"].lower()
            and device["max_input_channels"] > 0
        ):
            return i

    raise RuntimeError(
        "Mic '{}' not found. Available (index, name, inputs): {}".format(
            name_substring,
            [
                (i, d["name"], int(d["max_input_channels"]))
                for i, d in enumerate(devices)
            ],
        )
    )


def _find_bundled_model(name: str) -> str:
    """Find a bundled openWakeWord model by name."""
    pkg_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    for model_file in pkg_dir.glob(f"{name}*.onnx"):
        return str(model_file)
    raise FileNotFoundError(f"Bundled model {name} not found in {pkg_dir}")


class WakeWordDetector:
    """Detect a configured wake word from the USB microphone."""

    def __init__(
        self,
        model_path: str = "",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        inference_framework: str = "onnx",
        gain_target_peak: float = 0.9,
        mic_name: Optional[str] = None,
    ):
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError(
                "openwakeword is not installed in the project environment. Run ./setup.sh"
            )

        self.threshold = threshold
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.gain_target_peak = gain_target_peak
        self.mic_name = mic_name or os.getenv("GONKEN_MIC_NAME", DEFAULT_MIC_NAME)
        self.inference_framework = inference_framework.lower()

        if self.inference_framework != "onnx":
            raise ValueError(
                "GonKenLab Agent configures openWakeWord in ONNX-only mode. "
                "Use inference_framework='onnx'."
            )

        if self.mic_sample_rate % self.sample_rate != 0:
            raise ValueError(
                "mic_sample_rate must be an integer multiple of sample_rate"
            )
        self.downsample_factor = self.mic_sample_rate // self.sample_rate
        self.mic_chunk_size = 1280 * self.downsample_factor

        self.mic_device = _find_mic_device(self.mic_name)
        device_name = sd.query_devices()[self.mic_device]["name"]
        print(f"    Wake word mic: device {self.mic_device} ({device_name})")

        use_custom = bool(model_path and Path(model_path).exists())
        if use_custom:
            self.model = Model(
                wakeword_models=[model_path],
                inference_framework=self.inference_framework,
            )
            self.active_model = Path(model_path).name
        else:
            jarvis_path = _find_bundled_model("hey_jarvis")
            self.model = Model(
                wakeword_models=[jarvis_path],
                inference_framework=self.inference_framework,
            )
            self.active_model = "hey_jarvis (bundled fallback)"
            if model_path:
                print(
                    f"    Wake word model not found at {model_path}; "
                    "using bundled 'hey_jarvis'."
                )
            else:
                print("    Wake word model: bundled 'hey_jarvis'.")

        self._running = False
        self._stop_event = Event()
        self._resume_event = Event()
        self._thread: Optional[Thread] = None
        self._callback: Optional[Callable] = None
        self._paused = False
        self._audio_queue: Queue = Queue()
        self._gain = 4.0

    def start(self, callback: Callable[[], None]):
        self._callback = callback
        self._running = True
        self._paused = False
        self._stop_event.clear()
        self._resume_event.set()
        self._thread = Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        self._resume_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def pause(self):
        self._paused = True
        self._resume_event.clear()

    def resume(self):
        self._paused = False
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except Empty:
                break
        self._resume_event.set()

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        peak = np.max(np.abs(audio))
        if peak < 50:
            return audio.astype(np.int16)
        target = self.gain_target_peak * 32767
        desired_gain = min(target / peak, 15.0)
        self._gain = 0.3 * desired_gain + 0.7 * self._gain
        self._gain = min(self._gain, 15.0)
        gained = np.clip(audio * self._gain, -32768, 32767)
        return gained.astype(np.int16)

    def _listen_loop(self):
        while self._running:
            self._resume_event.wait()
            if not self._running:
                break

            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    break

            def audio_callback(indata, frames, time_info, status):
                self._audio_queue.put(bytes(indata))

            try:
                stream = sd.RawInputStream(
                    device=self.mic_device,
                    samplerate=self.mic_sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self.mic_chunk_size,
                    latency="high",
                    callback=audio_callback,
                )
                stream.start()
            except Exception as exc:
                print(f"Wake word stream error: {exc}")
                if self._running:
                    self._stop_event.wait(timeout=1.0)
                continue

            detected = False
            while self._running and not self._paused:
                try:
                    raw = self._audio_queue.get(timeout=0.1)
                except Empty:
                    continue

                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
                normalized = self._normalize(audio)
                downsampled = normalized[:: self.downsample_factor]

                predictions = self.model.predict(downsampled)
                for model_name, score in predictions.items():
                    if score >= self.threshold:
                        print(
                            "Wake word detected! ({}, score: {:.3f})".format(
                                model_name, score
                            )
                        )
                        detected = True
                        break

                if detected:
                    break

            stream.stop()
            stream.close()

            if detected and self._callback:
                self._paused = True
                self._resume_event.clear()
                self.model.reset()
                self._callback()
