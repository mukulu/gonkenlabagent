"""Audio manager for microphone input and speaker output."""

import subprocess
import wave
from threading import Lock
from typing import Optional

import numpy as np
import sounddevice as sd


def _available_devices():
    return [
        (
            i,
            d["name"],
            int(d["max_input_channels"]),
            int(d["max_output_channels"]),
        )
        for i, d in enumerate(sd.query_devices())
    ]


def _find_device_by_name(name_substring: str, kind: str) -> int:
    """Find a sounddevice device index by case-insensitive substring."""
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"

    for i, device in enumerate(devices):
        if (
            name_substring.lower() in device["name"].lower()
            and device[channel_key] > 0
        ):
            return i

    raise RuntimeError(
        "Audio device matching '{}' ({}) not found. "
        "Available (index, name, inputs, outputs): {}".format(
            name_substring,
            kind,
            _available_devices(),
        )
    )


def _find_alsa_card_by_name(name_substring: str) -> str:
    """Find an ALSA playback card and return a plughw:N,0 device string."""
    try:
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, check=True
        )
        needle = name_substring.lower()
        for line in result.stdout.splitlines():
            if line.startswith("card ") and needle in line.lower():
                card_num = line.split(":", 1)[0].replace("card ", "").strip()
                return f"plughw:{card_num},0"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # "default" is safer than silently assuming card 0 is the desired speaker.
    return "default"


class AudioManager:
    """Manage microphone capture and speaker playback with TTS muting."""

    def __init__(
        self,
        sample_rate: int,
        mic_sample_rate: int,
        mic_name: str,
        speaker_name: str,
        channels: int = 1,
        dtype: str = "int16",
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        if sample_rate <= 0 or mic_sample_rate % sample_rate:
            raise ValueError("mic_sample_rate must be divisible by sample_rate")
        self.downsample_factor = mic_sample_rate // sample_rate
        self.channels = channels
        self.dtype = dtype
        self.mic_name = mic_name
        self.speaker_name = speaker_name
        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

        self.mic_device = _find_device_by_name(self.mic_name, "input")
        self.speaker_device = _find_device_by_name(self.speaker_name, "output")
        self.speaker_alsa = _find_alsa_card_by_name(self.speaker_name)

        devices = sd.query_devices()
        print(
            "    Mic: device {} ({})".format(
                self.mic_device, devices[self.mic_device]["name"]
            )
        )
        print(
            "    Speaker: device {} ({}) via {}".format(
                self.speaker_device,
                devices[self.speaker_device]["name"],
                self.speaker_alsa,
            )
        )

    def mute(self):
        """Mute microphone input during TTS playback."""
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        """Unmute microphone input."""
        with self._mute_lock:
            self.is_muted = False

    def _normalize(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        """Apply gain normalization for weak USB microphones."""
        peak = np.max(np.abs(audio.astype(np.float64)))
        if peak < 50:
            return audio
        gain = (target_peak * 32767) / peak
        return np.clip(
            audio.astype(np.float64) * gain, -32768, 32767
        ).astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        max_duration: float = 30.0,
    ) -> Optional[np.ndarray]:
        """Record until silence, then convert 48 kHz input to 16 kHz."""
        if self.is_muted:
            return None

        self._audio_buffer = []
        self._recording = True
        silence_samples = 0
        silence_samples_needed = int(
            silence_duration * self.mic_sample_rate / 4096
        )
        max_samples = int(max_duration * self.mic_sample_rate / 4096)
        total_samples = 0

        def callback(indata, frames, time, status):
            if self.is_muted or not self._recording:
                return
            self._audio_buffer.append(indata.copy())

        stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.mic_sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=4096,
            latency="high",
            callback=callback,
        )
        stream.start()

        try:
            while self._recording and total_samples < max_samples:
                sd.sleep(100)
                total_samples += 1

                if self._audio_buffer:
                    recent = self._audio_buffer[-1]
                    rms = (
                        np.sqrt(np.mean(recent.astype(np.float32) ** 2)) / 32768
                    )
                    if rms < silence_threshold:
                        silence_samples += 1
                        if silence_samples >= silence_samples_needed:
                            break
                    else:
                        silence_samples = 0
        finally:
            stream.stop()
            stream.close()

        self._recording = False

        if not self._audio_buffer:
            return None

        raw_audio = np.concatenate(self._audio_buffer, axis=0).flatten()
        normalized = self._normalize(raw_audio)

        return normalized[:: self.downsample_factor]

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        """Save an audio array as a mono 16-bit WAV file."""
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def play_wav(self, filepath: str):
        """Play a WAV file through the configured USB speaker."""
        self.mute()
        try:
            subprocess.run(
                ["aplay", "-D", self.speaker_alsa, filepath],
                check=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            # Fall back to sounddevice using the explicitly resolved output.
            try:
                with wave.open(filepath, "rb") as wf:
                    audio_data = np.frombuffer(
                        wf.readframes(wf.getnframes()), dtype=np.int16
                    )
                    sd.play(
                        audio_data,
                        wf.getframerate(),
                        device=self.speaker_device,
                    )
                    sd.wait()
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"Playback failed via ALSA ({exc}) and sounddevice "
                    f"({fallback_exc})"
                ) from fallback_exc
        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        """Play an audio array through the configured speaker."""
        self.mute()
        try:
            sd.play(audio, self.sample_rate, device=self.speaker_device)
            sd.wait()
        finally:
            self.unmute()
