"""Physical, fully-local voice appliance runtime.

The production path deliberately depends only on the Python standard library
plus the already provisioned external binaries (ALSA utils, whisper.cpp, Piper,
and loopback Ollama).  It supports two entry points:

* a long-running wake-phrase loop used by systemd and ``gonken-agent run``;
* one explicit capture/answer/speak turn used by ``gonken-agent talk``.

No transcript or answer is persisted.  System-service logs contain categorical
state only; foreground ``talk`` may print the current transcript/answer to the
operator's terminal.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from .audio.speech import Piper, Whisper, validate_wav
from .audio.process import ProcessFailure
from .llm.ollama import OllamaClient, OllamaError


def _diagnostic_text(value: object) -> str:
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    return "".join(ch if ch.isprintable() else "?" for ch in text)[:320]


class VoiceRuntimeError(RuntimeError):
    """Categorical appliance-runtime failure with bounded content-free detail."""

    def __init__(self, code: str, detail: str = ""):
        if not re.fullmatch(r"[A-Z0-9_]{3,64}", code):
            code = "VOICE_RUNTIME_FAILED"
        super().__init__(code)
        self.code = code
        self.detail = _diagnostic_text(detail)


def _which(name: str) -> Path:
    value = shutil.which(name)
    if not value:
        raise VoiceRuntimeError(f"{name.upper().replace('-', '_')}_MISSING")
    path = Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise VoiceRuntimeError(f"{name.upper().replace('-', '_')}_INVALID")
    return path


def _optional_which(name: str) -> Path | None:
    value = shutil.which(name)
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def _safe_run(args: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VoiceRuntimeError("AUDIO_COMMAND_FAILED", f"{args[0]} {type(exc).__name__}") from exc


def _normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) <= 1
    short, long = (left, right) if len(left) < len(right) else (right, left)
    index = misses = 0
    for char in long:
        if index < len(short) and char == short[index]:
            index += 1
        else:
            misses += 1
            if misses > 1:
                return False
    return True


def _wake_remainder(text: str, phrase: str) -> str | None:
    words = _normalize_words(text)
    target = _normalize_words(phrase)
    if not target or len(words) < len(target):
        return None
    for start in range(0, len(words) - len(target) + 1):
        candidate = words[start : start + len(target)]
        matches = all(
            actual == expected
            or (len(expected) >= 5 and _edit_distance_at_most_one(actual, expected))
            for actual, expected in zip(candidate, target)
        )
        if matches:
            return " ".join(words[start + len(target) :]).strip()
    return None


class AudioBackend:
    """Adaptive physical audio backend.

    Bluetooth setup owns the PipeWire/Pulse default sink/source.  A mere
    Bluetooth record is not enough to force ALSA ``default``: that was the FIX5
    regression seen on the real Pi, where a valid USB microphone was present
    while the PipeWire capture route was not usable.  FIX6 resolves input and
    output independently:

    * prefer the managed PipeWire/Pulse endpoint when it is actually available;
    * otherwise use one unambiguous direct ALSA USB device;
    * allow mixed USB-input/Bluetooth-output operation;
    * retry once through the direct ALSA fallback if a Pulse endpoint disappears.
    """

    def __init__(self, config, *, runtime_dir: Path | None = None):
        self.config = config
        self.arecord = _which("arecord")
        self.aplay = _which("aplay")
        self.pactl = _optional_which("pactl")
        self.parecord = _optional_which("parecord")
        self.paplay = _optional_which("paplay")
        self.runtime_dir = Path(runtime_dir or config.paths.runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.input_device = ""
        self.output_device = ""
        self.input_mode = ""
        self.output_mode = ""
        self.mode = ""
        self._input_candidates: list[tuple[str, str]] = []
        self._output_candidates: list[tuple[str, str]] = []
        # Do not resolve physical devices in the constructor.  At boot the
        # service can legitimately start before USB enumeration or Bluetooth
        # reconnection completes; readiness owns the bounded retry loop.

    @property
    def bluetooth_configured(self) -> bool:
        return Path("/etc/gonken-agent/bluetooth-device.record").is_file()

    def _managed_bluetooth_token(self) -> str | None:
        path = Path("/etc/gonken-agent/bluetooth-device.record")
        if not path.is_file() or path.is_symlink():
            return None
        try:
            if path.stat().st_size > 8192:
                return None
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("address="):
                    address = line.partition("=")[2].strip()
                    if re.fullmatch(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", address):
                        return address.replace(":", "_").casefold()
        except (OSError, UnicodeError):
            return None
        return None

    @staticmethod
    def _parse_cards(output: str) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        pattern = re.compile(
            r"^card\s+(\d+):\s*([^\[]+)\[([^\]]+)\],\s*device\s+(\d+):\s*(.*)$",
            re.I,
        )
        for raw in output.splitlines():
            match = pattern.match(raw.strip())
            if not match:
                continue
            card, short, long_name, device, tail = match.groups()
            card_id = short.strip()
            locator = card_id if re.fullmatch(r"[A-Za-z0-9_]+", card_id) else card
            text = " ".join((short.strip(), long_name.strip(), tail.strip()))
            rows.append((f"plughw:CARD={locator},DEV={device}", text, device))
        return rows

    @staticmethod
    def _one_card(rows: list[tuple[str, str, str]]) -> str | None:
        if not rows:
            return None
        cards: dict[str, list[tuple[str, str, str]]] = {}
        for row in rows:
            cards.setdefault(row[0].split(",", 1)[0], []).append(row)
        if len(cards) != 1:
            return None
        choices = next(iter(cards.values()))
        zero = [row for row in choices if row[2] == "0"]
        return (zero[0] if zero else choices[0])[0]

    def _select(self, tool: Path, selector: str) -> str:
        selector = selector.strip()
        if selector.casefold() == "default":
            return "default"
        result = _safe_run([str(tool), "-l"], timeout=8)
        rows = self._parse_cards(result.stdout + result.stderr)
        if not selector or selector.casefold() == "auto":
            usb = [row for row in rows if "usb" in row[1].casefold()]
            selected = self._one_card(usb)
            if selected:
                return selected
            if len({row[0].split(",", 1)[0] for row in usb}) > 1:
                raise VoiceRuntimeError("AUDIO_DEVICE_AMBIGUOUS", "multiple USB audio cards")
            non_hdmi = [
                row for row in rows
                if not any(token in row[1].casefold() for token in ("hdmi", "displayport", "vc4"))
            ]
            selected = self._one_card(non_hdmi)
            if selected:
                return selected
            if rows:
                raise VoiceRuntimeError("AUDIO_DEVICE_AMBIGUOUS", "multiple non-HDMI audio cards")
            raise VoiceRuntimeError("AUDIO_DEVICE_NOT_FOUND", f"{tool.name} reported no usable devices")
        matches = [row for row in rows if selector.casefold() in row[1].casefold()]
        if not matches:
            raise VoiceRuntimeError("AUDIO_DEVICE_NOT_FOUND", f"selector={selector}")
        selected = self._one_card(matches)
        if selected:
            return selected
        raise VoiceRuntimeError("AUDIO_DEVICE_AMBIGUOUS", f"selector={selector}")

    def _alsa_candidate(self, direction: str) -> str | None:
        tool = self.arecord if direction == "input" else self.aplay
        selector = self.config.audio.input_match if direction == "input" else self.config.audio.output_match
        try:
            return self._select(tool, selector)
        except VoiceRuntimeError as exc:
            if exc.code in {"AUDIO_DEVICE_NOT_FOUND", "AUDIO_DEVICE_AMBIGUOUS"}:
                return None
            raise

    def _pulse_names(self, direction: str) -> list[str]:
        if self.pactl is None:
            return []
        if direction == "input" and self.parecord is None:
            return []
        if direction == "output" and self.paplay is None:
            return []
        info = _safe_run([str(self.pactl), "info"], timeout=8)
        if info.returncode != 0:
            return []
        noun = "sources" if direction == "input" else "sinks"
        listing = _safe_run([str(self.pactl), "list", noun, "short"], timeout=8)
        if listing.returncode != 0:
            return []
        names: list[str] = []
        for line in listing.stdout.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            name = fields[1]
            lowered = name.casefold()
            if direction == "input" and lowered.endswith(".monitor"):
                continue
            names.append(name)
        return names

    def _pulse_usb_candidate(self, direction: str) -> str | None:
        # Prefer a wired PipeWire/Pulse USB node when exactly one exists.  This
        # avoids fighting PipeWire for direct ALSA ownership while preserving
        # the project's wired-first policy.
        prefix = "alsa_input" if direction == "input" else "alsa_output"
        candidates = [
            name for name in self._pulse_names(direction)
            if "usb" in name.casefold() and prefix in name.casefold()
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _pulse_bluetooth_candidate(self, direction: str) -> str | None:
        if not self.bluetooth_configured:
            return None
        token = self._managed_bluetooth_token()
        if token is None:
            return None
        prefix = "bluez_input" if direction == "input" else "bluez_output"
        candidates = [
            name for name in self._pulse_names(direction)
            if prefix in name.casefold() and token in name.casefold()
        ]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _dedupe_routes(routes: list[tuple[str, str]]) -> list[tuple[str, str]]:
        output: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for route in routes:
            if route not in seen:
                output.append(route)
                seen.add(route)
        return output

    def _route_candidates(self, direction: str) -> list[tuple[str, str]]:
        selector = (
            self.config.audio.input_match if direction == "input"
            else self.config.audio.output_match
        ).strip()
        alsa = self._alsa_candidate(direction)
        pulse_usb = self._pulse_usb_candidate(direction)
        pulse_bluetooth = self._pulse_bluetooth_candidate(direction)
        routes: list[tuple[str, str]] = []

        if not selector or selector.casefold() == "auto":
            # Deterministic policy: connected wired audio first, then the exact
            # configured/connected Bluetooth endpoint.  Keep both Pulse USB and
            # direct ALSA USB as candidates because one may be busy/unavailable
            # while the other is usable on a particular Pi image.
            if pulse_usb:
                routes.append(("pipewire-usb", pulse_usb))
            if alsa:
                routes.append(("alsa-usb", alsa))
            if pulse_bluetooth:
                routes.append(("pipewire-bluetooth", pulse_bluetooth))
        else:
            # An explicit site selector outranks automatic transport preference.
            if alsa:
                routes.append(("alsa-selected", alsa))
            if pulse_bluetooth:
                routes.append(("pipewire-bluetooth", pulse_bluetooth))

        return self._dedupe_routes(routes)

    def _apply_route(self, direction: str, route: tuple[str, str]) -> None:
        mode, device = route
        if direction == "input":
            self.input_mode, self.input_device = mode, device
        else:
            self.output_mode, self.output_device = mode, device
        self.mode = (
            self.input_mode if self.input_mode == self.output_mode
            else f"{self.input_mode}+{self.output_mode}"
        )

    def refresh(self) -> None:
        self._input_candidates = self._route_candidates("input")
        self._output_candidates = self._route_candidates("output")
        if not self._input_candidates:
            code = "AUDIO_INPUT_NOT_FOUND"
            if self.bluetooth_configured:
                code = "AUDIO_INPUT_NOT_FOUND_USB_OR_BLUETOOTH"
            raise VoiceRuntimeError(code, "no usable wired or configured Bluetooth capture route")
        if not self._output_candidates:
            code = "AUDIO_OUTPUT_NOT_FOUND"
            if self.bluetooth_configured:
                code = "AUDIO_OUTPUT_NOT_FOUND_USB_OR_BLUETOOTH"
            raise VoiceRuntimeError(code, "no usable wired or configured Bluetooth playback route")
        self._apply_route("input", self._input_candidates[0])
        self._apply_route("output", self._output_candidates[0])

    def _alsa_record_to(self, destination: Path, seconds: int) -> None:
        args = [
            str(self.arecord), "-q", "-D", self.input_device,
            "-t", "wav", "-f", "S16_LE", "-r", str(self.config.audio.processing_rate),
            "-c", "1", "-d", str(seconds), str(destination),
        ]
        result = _safe_run(args, timeout=seconds + 8)
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "arecord returned nonzero"
            raise VoiceRuntimeError("AUDIO_CAPTURE_FAILED", f"backend=alsa device={self.input_device} {_diagnostic_text(detail)}")

    def _pulse_record_to(self, destination: Path, seconds: int) -> None:
        if self.parecord is None:
            raise VoiceRuntimeError("PARECORD_MISSING")
        args = [
            str(self.parecord), f"--device={self.input_device}", "--file-format=wav",
            "--format=s16le", f"--rate={self.config.audio.processing_rate}", "--channels=1",
            str(destination),
        ]
        try:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except OSError as exc:
            raise VoiceRuntimeError("AUDIO_CAPTURE_FAILED", f"parecord {type(exc).__name__}") from exc
        started = time.monotonic()
        stderr = ""
        try:
            while time.monotonic() - started < seconds:
                if process.poll() is not None:
                    stderr = process.stderr.read() if process.stderr else ""
                    raise VoiceRuntimeError("AUDIO_CAPTURE_FAILED", f"backend=pulse device={self.input_device} {_diagnostic_text(stderr)}")
                time.sleep(0.05)
            process.send_signal(signal.SIGINT)
            try:
                _stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _stdout, stderr = process.communicate(timeout=3)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
        if not destination.is_file() or destination.stat().st_size < 44:
            raise VoiceRuntimeError("AUDIO_CAPTURE_FAILED", f"backend=pulse device={self.input_device} {_diagnostic_text(stderr)}")

    def _record_to(self, destination: Path, seconds: int) -> None:
        if not 1 <= seconds <= 30:
            raise ValueError("capture seconds must be 1..30")
        if self.input_mode.startswith("pipewire-"):
            self._pulse_record_to(destination, seconds)
        else:
            self._alsa_record_to(destination, seconds)
        try:
            metadata = validate_wav(destination, max_seconds=seconds + 1)
        except Exception as exc:
            raise VoiceRuntimeError("AUDIO_CAPTURE_INVALID", f"backend={self.input_mode} device={self.input_device} {type(exc).__name__}") from exc
        if metadata["rate"] != self.config.audio.processing_rate:
            raise VoiceRuntimeError("AUDIO_CAPTURE_RATE_MISMATCH", f"expected={self.config.audio.processing_rate} observed={metadata['rate']}")

    def capture(self, seconds: int) -> Path:
        if not self._input_candidates:
            self.refresh()
        descriptor, name = tempfile.mkstemp(prefix="voice-", suffix=".wav", dir=self.runtime_dir)
        os.close(descriptor)
        path = Path(name)
        failures: list[str] = []
        try:
            for route in list(self._input_candidates):
                self._apply_route("input", route)
                path.unlink(missing_ok=True)
                path.touch(mode=0o600)
                try:
                    self._record_to(path, seconds)
                    return path
                except VoiceRuntimeError as exc:
                    failures.append(f"{route[0]}:{exc.code}")
            raise VoiceRuntimeError(
                "AUDIO_CAPTURE_FAILED",
                "routes=" + ",".join(failures)[:240],
            )
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def _alsa_play(self, wav_path: Path) -> None:
        result = _safe_run([str(self.aplay), "-q", "-D", self.output_device, str(wav_path)], timeout=70)
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "aplay returned nonzero"
            raise VoiceRuntimeError("AUDIO_PLAYBACK_FAILED", f"backend=alsa device={self.output_device} {_diagnostic_text(detail)}")

    def _pulse_play(self, wav_path: Path) -> None:
        if self.paplay is None:
            raise VoiceRuntimeError("PAPLAY_MISSING")
        result = _safe_run([str(self.paplay), f"--device={self.output_device}", str(wav_path)], timeout=70)
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "paplay returned nonzero"
            raise VoiceRuntimeError("AUDIO_PLAYBACK_FAILED", f"backend=pulse device={self.output_device} {_diagnostic_text(detail)}")

    def play(self, wav_path: Path) -> None:
        validate_wav(wav_path)
        if not self._output_candidates:
            self.refresh()
        failures: list[str] = []
        for route in list(self._output_candidates):
            self._apply_route("output", route)
            try:
                if self.output_mode.startswith("pipewire-"):
                    self._pulse_play(wav_path)
                else:
                    self._alsa_play(wav_path)
                return
            except VoiceRuntimeError as exc:
                failures.append(f"{route[0]}:{exc.code}")
        raise VoiceRuntimeError(
            "AUDIO_PLAYBACK_FAILED",
            "routes=" + ",".join(failures)[:240],
        )

    def probe(self) -> dict[str, str]:
        self.refresh()
        capture = self.capture(1)
        capture.unlink(missing_ok=True)
        descriptor, name = tempfile.mkstemp(prefix="probe-", suffix=".wav", dir=self.runtime_dir)
        os.close(descriptor)
        path = Path(name)
        try:
            with wave.open(str(path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(b"\x00\x00" * 1600)
            self.play(path)
        finally:
            path.unlink(missing_ok=True)
        return {
            "backend": self.mode,
            "input": "ready",
            "output": "ready",
            "input_backend": self.input_mode,
            "output_backend": self.output_mode,
        }


class ConversationBrain:
    """Small in-memory local conversation with no cloud or persistent content."""

    def __init__(self, config):
        self.client = OllamaClient(config.llm, timeout=90)
        prompt_path = Path(config.paths.local_prompt)
        if not prompt_path.is_file() or prompt_path.is_symlink() or prompt_path.stat().st_size > 32768:
            raise VoiceRuntimeError("LOCAL_PROMPT_MISSING")
        self.system_prompt = prompt_path.read_text(encoding="utf-8").strip()
        if not self.system_prompt:
            raise VoiceRuntimeError("LOCAL_PROMPT_EMPTY")
        self.history: list[dict[str, str]] = []

    def probe(self, stop: threading.Event) -> dict[str, str]:
        identity = self.client.model_identity(stop)
        # Readiness means inference works, not merely that a tag exists.  This
        # also warms the small local model so the first spoken turn has lower
        # latency after boot.  The probe is not added to conversation history.
        self.client.chat_text(
            [{"role": "user", "content": "Reply with the single word ready."}],
            stop,
        )
        return identity

    def reply(self, question: str, stop: threading.Event) -> str:
        question = " ".join(question.split())
        if not question or len(question) > 4096:
            raise VoiceRuntimeError("VOICE_QUESTION_INVALID")
        messages = [{"role": "system", "content": self.system_prompt}, *self.history,
                    {"role": "user", "content": question}]
        # Bound conversational context independently of the model's token window.
        while sum(len(item["content"]) for item in messages) > 12000 and len(self.history) >= 2:
            del self.history[:2]
            messages = [{"role": "system", "content": self.system_prompt}, *self.history,
                        {"role": "user", "content": question}]
        try:
            answer = self.client.chat_text(messages, stop)
        except OllamaError as exc:
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_FAILED") from exc
        answer = " ".join(answer.split())
        if not answer or len(answer) > 4096:
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_INVALID")
        self.history.extend((
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ))
        self.history = self.history[-8:]
        return answer

    def close(self) -> None:
        self.client.close()


class VoiceAppliance:
    READY_FILE = Path("/run/gonken-agent/ready.json")

    def __init__(self, config, *, emitter=print, foreground: bool = False):
        self.config = config
        self.emit = emitter
        self.stop = threading.Event()
        configured_runtime = Path(config.paths.runtime_dir)
        if foreground and not os.access(configured_runtime, os.W_OK):
            configured_runtime = Path(tempfile.gettempdir()) / f"gonken-agent-{os.getuid()}"
            configured_runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.runtime_dir = configured_runtime
        self.audio = AudioBackend(config, runtime_dir=self.runtime_dir)
        self.whisper = Whisper(
            config.paths.whisper_binary,
            config.paths.whisper_model,
            self.runtime_dir,
            threads=config.stt.threads,
        )
        self.piper = Piper(
            "/usr/local/bin/piper",
            config.paths.piper_voice,
            self.runtime_dir,
        )
        self.brain = ConversationBrain(config)
        self.ready = False
        self.publish_ready = not foreground
        self._last_wait_code = ""

    def _event(self, level: str, code: str, **fields: object) -> None:
        rendered = " ".join(f"{key}={str(value).replace(' ', '_')}" for key, value in fields.items())
        self.emit(f"[{level}] code={code}{(' ' + rendered) if rendered else ''}", flush=True)

    def request_stop(self, *_args) -> None:
        self.stop.set()

    def _transcribe_path(self, path: Path) -> str:
        try:
            return self.whisper.transcribe(path, self.stop)
        finally:
            path.unlink(missing_ok=True)

    def capture_text(self, seconds: int) -> str:
        path = self.audio.capture(seconds)
        try:
            text = self._transcribe_path(path)
        except ProcessFailure as exc:
            if self.stop.is_set():
                return ""
            # whisper.cpp legitimately produces no transcript for silence.  The
            # speech adapter uses STT_OUTPUT_INVALID for that bounded empty-output
            # case; a wake listener must treat it as "nothing heard", not as a
            # dependency outage that tears down appliance readiness.
            if str(exc) == "STT_OUTPUT_INVALID":
                return ""
            raise VoiceRuntimeError("VOICE_TRANSCRIPTION_FAILED") from exc
        except Exception as exc:
            if self.stop.is_set():
                return ""
            raise VoiceRuntimeError("VOICE_TRANSCRIPTION_FAILED") from exc
        return " ".join(text.split())

    def speak(self, text: str) -> None:
        with self.piper.synthesize(text, self.stop) as wav:
            self.audio.play(wav)

    def probe(self) -> dict[str, object]:
        audio = self.audio.probe()
        identity = self.brain.probe(self.stop)
        return {"audio": audio, "model": identity}

    def _write_ready(self, probe: dict[str, object]) -> None:
        if not self.publish_ready:
            return
        self.READY_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "READY",
            "code": "VOICE_RUNTIME_READY",
            "wake_phrase": self.config.extensions.wake_word.phrase,
            "audio_backend": probe["audio"]["backend"],
            "model": probe["model"]["model"],
            "observed_epoch": int(time.time()),
        }
        temporary = self.READY_FILE.with_name(f".{self.READY_FILE.name}.{os.getpid()}")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o644)
        os.replace(temporary, self.READY_FILE)

    def _clear_ready(self) -> None:
        if self.publish_ready:
            self.READY_FILE.unlink(missing_ok=True)
        self.ready = False

    def wait_until_ready(self) -> bool:
        delay = 2.0
        while not self.stop.is_set():
            try:
                probe = self.probe()
                # Require the real TTS -> physical playback path before publishing
                # readiness.  This closes the gap between an ALSA device that can
                # open and an appliance that can actually speak.
                self.speak("GonKen assistant is ready.")
                self._write_ready(probe)
                self.ready = True
                self._event("READY", "VOICE_RUNTIME_READY", wake_phrase=self.config.extensions.wake_word.phrase)
                return True
            except Exception as exc:
                self._clear_ready()
                code = exc.code if isinstance(exc, VoiceRuntimeError) else "VOICE_DEPENDENCY_WAIT"
                detail = exc.detail if isinstance(exc, VoiceRuntimeError) else _diagnostic_text(type(exc).__name__)
                fingerprint = f"{code}:{detail}"
                if fingerprint != self._last_wait_code:
                    fields: dict[str, object] = {"retry_seconds": int(delay)}
                    if detail:
                        fields["detail"] = detail
                    self._event("WAITING", code, **fields)
                    self._last_wait_code = fingerprint
                self.stop.wait(delay)
                delay = min(30.0, delay * 1.5)
        return False

    def one_turn(self, *, seconds: int = 8, foreground: bool = False) -> str | None:
        self._event("RUNNING", "VOICE_LISTENING", seconds=seconds)
        question = self.capture_text(seconds)
        if not question:
            self._event("INFO", "VOICE_NO_SPEECH")
            return None
        if foreground:
            print(f"You: {question}", flush=True)
        self._event("RUNNING", "VOICE_THINKING")
        answer = self.brain.reply(question, self.stop)
        if foreground:
            print(f"GonKen: {answer}", flush=True)
        self._event("RUNNING", "VOICE_SPEAKING")
        self.speak(answer)
        self._event("OK", "VOICE_TURN_COMPLETE")
        return answer

    def wake_loop(self) -> int:
        if not self.config.extensions.wake_word.enabled:
            raise VoiceRuntimeError("WAKE_WORD_DISABLED")
        phrase = self.config.extensions.wake_word.phrase
        if not self.wait_until_ready():
            return 0
        self._event("RUNNING", "WAKE_STANDBY", phrase=phrase)
        while not self.stop.is_set():
            try:
                heard = self.capture_text(2)
                if _wake_remainder(heard, phrase) is None:
                    continue
                self._event("OK", "WAKE_DETECTED")
                # Wake detection and question capture are intentionally two
                # separate turns.  A two-second phrase-spotting window can cut a
                # same-breath question mid-sentence; acknowledging first gives
                # the user a deterministic cue and a full bounded question
                # window.
                try:
                    self.speak("Yes?")
                except Exception:
                    pass
                question = self.capture_text(8)
                if not question:
                    self._event("INFO", "VOICE_NO_SPEECH")
                    continue
                answer = self.brain.reply(question, self.stop)
                self._event("RUNNING", "VOICE_SPEAKING")
                self.speak(answer)
                self._event("OK", "VOICE_TURN_COMPLETE")
                self._event("RUNNING", "WAKE_STANDBY", phrase=phrase)
            except Exception as exc:
                if self.stop.is_set():
                    break
                self._clear_ready()
                code = exc.code if isinstance(exc, VoiceRuntimeError) else "VOICE_RUNTIME_RECOVERY"
                detail = exc.detail if isinstance(exc, VoiceRuntimeError) else _diagnostic_text(type(exc).__name__)
                fields: dict[str, object] = {"retry_seconds": 5}
                if detail:
                    fields["detail"] = detail
                self._event("WAITING", code, **fields)
                self.stop.wait(5)
                if not self.wait_until_ready():
                    break
                self._event("RUNNING", "WAKE_STANDBY", phrase=phrase)
        return 0

    def close(self) -> None:
        self._clear_ready()
        self.stop.set()
        self.brain.close()


def run_appliance(config, *, one_turn: bool = False, seconds: int = 8, foreground: bool = False) -> int:
    appliance = VoiceAppliance(config, foreground=foreground)
    previous: dict[int, object] = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, appliance.request_stop)
        if one_turn:
            if not appliance.wait_until_ready():
                return 1
            return 0 if appliance.one_turn(seconds=seconds, foreground=foreground) is not None else 2
        return appliance.wake_loop()
    finally:
        appliance.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
