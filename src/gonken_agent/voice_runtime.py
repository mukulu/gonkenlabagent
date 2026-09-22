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

import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from .operational import OperationalCommands, NotificationAnnouncer
from .runtime_readiness import configuration_digest
from .audio.endpoint import SpeechEndpoint, complete_wake_utterance
from .audio.pcm_stream import PCMInputStream, PCMStreamError
from .audio.keyword_native import NativeKeywordDetector
from .audio.wake_stream import StreamingWakePipeline, StreamingWakeWindow
from .audio.speech import Piper, Whisper, validate_wav
from .audio.process import ProcessFailure
from .environment import (
    EnvironmentClient,
    EnvironmentClientError,
    EnvironmentClarification,
    EnvironmentIntent,
    environment_error_response,
    environment_success_response,
    parse_environment_intent,
)
from .llm.ollama import OllamaClient, OllamaError
from .llm.models import active_model, LEGACY_MODEL, roster_tags
from .llm.qualification import qualified_rows
from .runtime_readiness import bounded_json
from .tool_broker import ToolBroker, ToolBrokerError, direct_clock_intent
from .interaction.gpiod_ptt import GpiodPushToTalkHardware, GpiodWakeMonitoringLed
from .interaction.push_to_talk import PushToTalk


def _diagnostic_text(value: object) -> str:
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    return "".join(ch if ch.isprintable() else "?" for ch in text)[:320]


def _classify_audio_capture_failure(detail: object, *, backend: str) -> str:
    """Return a stable content-free reason code for common capture failures."""
    text = str(detail).casefold()
    if any(token in text for token in ("permission denied", "access denied", "not permitted")):
        return "AUDIO_CAPTURE_PERMISSION_DENIED"
    if any(token in text for token in ("connection refused", "connection failure", "connection terminated")):
        return "AUDIO_SERVER_UNAVAILABLE"
    if any(token in text for token in ("no such entity", "no such device", "device not found", "unknown pcm")):
        return "AUDIO_CAPTURE_DEVICE_UNAVAILABLE"
    if any(token in text for token in ("device or resource busy", "resource busy")):
        return "AUDIO_CAPTURE_DEVICE_BUSY"
    return "AUDIO_CAPTURE_BACKEND_FAILED" if backend == "pulse" else "AUDIO_CAPTURE_FAILED"


def _write_pcm16_mono_wav(raw_path: Path, destination: Path, *, rate: int) -> dict[str, int]:
    """Wrap bounded raw S16_LE mono PCM in a canonical WAV container.

    ``parecord --raw`` avoids depending on libsndfile WAV finalization when the
    recorder is stopped with SIGINT.  The project owns the small deterministic
    WAV header written here, which is then checked by the normal validator.
    """
    size = raw_path.stat().st_size if raw_path.is_file() else 0
    if size <= 0:
        raise VoiceRuntimeError("AUDIO_CAPTURE_EMPTY")
    if size % 2:
        raise VoiceRuntimeError("AUDIO_CAPTURE_PCM_MISALIGNED", f"bytes={size}")
    with raw_path.open("rb") as source, wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        while True:
            chunk = source.read(64 * 1024)
            if not chunk:
                break
            output.writeframesraw(chunk)
        output.writeframes(b"")
    return {"pcm_bytes": size, "frames": size // 2, "rate": rate}


def _boot_id() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip().casefold()
    except (OSError, UnicodeError):
        return "unknown"
    return value if re.fullmatch(r"[0-9a-f-]{36}", value) else "unknown"


def _process_start_ticks(pid: int | None = None) -> int:
    """Return Linux /proc process start ticks to make PID reuse detectable."""
    process_id = os.getpid() if pid is None else pid
    try:
        text = Path(f"/proc/{process_id}/stat").read_text(encoding="ascii")
        closing = text.rfind(")")
        fields = text[closing + 2 :].split() if closing >= 0 else []
        value = int(fields[19])
    except (OSError, UnicodeError, ValueError, IndexError):
        return 0
    return value if value > 0 else 0


def _readiness_component(code: str) -> str:
    if code.startswith(("AUDIO_", "PARECORD_")):
        return "audio_capture"
    if code.startswith(("TTS_", "PIPER_", "AUDIO_PLAYBACK")):
        return "audio_playback"
    if code.startswith(("LOCAL_MODEL_", "OLLAMA_")):
        return "local_model"
    if code.startswith(("WAKE_LED_", "GPIO_")):
        return "gpio_identity"
    if code.startswith(("STT_", "WHISPER_", "VOICE_TRANSCRIPTION")):
        return "speech_to_text"
    return "voice_runtime"


def _readiness_recoverable(code: str) -> bool:
    # Hardware hotplug, user-session startup and local-model warm-up can recover
    # without reinstalling. Ambiguous identities and invalid static selections
    # require operator/configuration repair and should fail the installer early.
    nonrecoverable = {
        "AUDIO_DEVICE_AMBIGUOUS",
        "AUDIO_CAPTURE_PERMISSION_DENIED",
        "WAKE_LED_GPIO_LINE_AMBIGUOUS",
        "GPIO_LINE_AMBIGUOUS",
        "GPIO_HEADER_UNRESOLVED",
        "LOCAL_MODEL_TOOLS_NOT_QUALIFIED",
        "LOCAL_MODEL_OUTSIDE_ROSTER",
    }
    return code not in nonrecoverable


def _runtime_release_directory() -> Path | None:
    from .release_identity import runtime_release_identity

    return runtime_release_identity().release_dir


def _runtime_release_commit() -> str:
    """Return the immutable release identity executing this package."""
    from .release_identity import runtime_release_identity

    return runtime_release_identity().commit


def _runtime_release_profile() -> str:
    """Return the validated immutable dependency profile for readiness binding."""
    from .release_identity import runtime_release_identity

    return runtime_release_identity().profile


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


WAKE_MATCHER_VERSION = "v09-gonken-recall-2"
WAKE_DEFAULT_PHRASE = "GonKen"
WAKE_CAPTURE_MODE = "pipelined"
WAKE_CAPTURE_WINDOW_SECONDS = 2
WAKE_CAPTURE_QUEUE_SIZE = 2
_WAKE_ALIAS_PHRASES = ("GonKen", "Gonken", "Hey GonKen", "Hey Gonken", "Gon Ken", "Hey Gon Ken")
_WAKE_GONKEN_TOKENS = {"gonken", "gon", "ken"}


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


@dataclass(frozen=True, slots=True)
class WakeMatch:
    phrase: str
    alias: str
    remainder: str
    matched_tokens: tuple[str, ...]
    matcher_version: str = WAKE_MATCHER_VERSION


def wake_matcher_aliases(phrase: str) -> list[str]:
    """Return the governed host-matcher phrases for diagnostics/tests.

    When the configured phrase is the mandatory V09 default ``GonKen``, retain
    ``Hey GonKen`` as a backward-compatible alias.  When an operator explicitly
    configures a longer phrase such as ``Hey Gonken``, do not silently add the
    shorter one-word phrase because that would expand the operator's wake
    surface.
    """

    ordered: list[str] = []
    normalized_phrase_words = _normalize_words(phrase)
    candidates = (phrase, *_WAKE_ALIAS_PHRASES) if normalized_phrase_words in (["gonken"], ["gon", "ken"]) else (phrase,)
    for candidate in candidates:
        normalized = " ".join(candidate.split())
        if normalized and normalized.casefold() not in {item.casefold() for item in ordered}:
            ordered.append(normalized)
    return ordered


def _candidate_token_sequences(words: list[str]) -> list[tuple[list[str], list[tuple[int, int]]]]:
    """Return bounded tokenizations, including adjacent-token joins.

    The matcher is transcript-based.  Adjacent-token joining lets "Gon Ken" or
    a capture boundary represented as two tokens still match the configured
    single-token wake phrase, without opening a raw fuzzy substring surface.
    """

    sequences: list[tuple[list[str], list[tuple[int, int]]]] = [(list(words), [(idx, idx + 1) for idx in range(len(words))])]
    for join_at in range(max(0, len(words) - 1)):
        joined_words: list[str] = []
        spans: list[tuple[int, int]] = []
        idx = 0
        while idx < len(words):
            if idx == join_at:
                joined_words.append(words[idx] + words[idx + 1])
                spans.append((idx, idx + 2))
                idx += 2
            else:
                joined_words.append(words[idx])
                spans.append((idx, idx + 1))
                idx += 1
        sequences.append((joined_words, spans))
    return sequences


def _wake_token_matches(actual: str, expected: str) -> bool:
    if actual == expected:
        return True
    # One-edit matching is restricted to the GonKen-like token.  Short generic
    # tokens such as "hey" remain exact to avoid accepting ordinary speech as a
    # wake phrase.
    if expected == "gonken" and len(actual) >= 5:
        return _edit_distance_at_most_one(actual, expected)
    return False


def _wake_match(text: str, phrase: str) -> WakeMatch | None:
    original_words = _normalize_words(text)
    if not original_words:
        return None
    for alias in wake_matcher_aliases(phrase):
        target = _normalize_words(alias)
        if not target:
            continue
        for candidate_words, spans in _candidate_token_sequences(original_words):
            if len(candidate_words) < len(target):
                continue
            for start in range(0, len(candidate_words) - len(target) + 1):
                selected = candidate_words[start : start + len(target)]
                if all(_wake_token_matches(actual, expected) for actual, expected in zip(selected, target)):
                    source_end = spans[start + len(target) - 1][1]
                    spans_original = list(re.finditer(r"[a-z0-9]+", text.casefold()))
                    tail = text.casefold()[spans_original[source_end - 1].end():]
                    remainder = " ".join(re.sub(r"[?!,;:]", " ", tail).strip(" .").split())
                    return WakeMatch(
                        phrase=phrase,
                        alias=alias,
                        remainder=remainder,
                        matched_tokens=tuple(selected),
                    )
    return None


def _wake_remainder(text: str, phrase: str) -> str | None:
    match = _wake_match(text, phrase)
    return None if match is None else match.remainder


class RollingWakeTranscriptMatcher:
    """Bounded transcript matcher that carries a short tail across captures."""

    def __init__(self, phrase: str, *, max_tail_words: int = 3) -> None:
        self.phrase = phrase
        self.max_tail_words = max(0, int(max_tail_words))
        self._tail: list[str] = []

    def observe(self, transcript: str) -> WakeMatch | None:
        words = _normalize_words(transcript)
        combined = " ".join([*self._tail, *words])
        match = _wake_match(combined, self.phrase)
        self._tail = words[-self.max_tail_words :] if self.max_tail_words else []
        return match


@dataclass(frozen=True, slots=True)
class WakeCaptureWindow:
    sequence: int
    path: Path
    captured_monotonic: float


class WakeCapturePipeline:
    """Continuously capture bounded wake windows while prior audio is transcribed.

    Capture runs in one producer thread and uses a tiny newest-wins queue.  This
    removes the former ``capture -> transcribe -> capture`` blind interval without
    creating an unbounded Whisper backlog.  The consumer still owns transcription
    so only one Whisper process runs at a time.
    """

    def __init__(
        self,
        capture,
        *,
        window_seconds: int = WAKE_CAPTURE_WINDOW_SECONDS,
        queue_size: int = WAKE_CAPTURE_QUEUE_SIZE,
    ) -> None:
        if not 1 <= int(window_seconds) <= 5 or not 1 <= int(queue_size) <= 4:
            raise ValueError("invalid wake capture pipeline bounds")
        self.capture = capture
        self.window_seconds = int(window_seconds)
        self.queue: queue.Queue[WakeCaptureWindow] = queue.Queue(maxsize=int(queue_size))
        self.cancel = threading.Event()
        self.thread: threading.Thread | None = None
        self.dropped_windows = 0
        self.captured_windows = 0
        self._error: BaseException | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("wake capture pipeline already started")
        self.cancel.clear()
        self.thread = threading.Thread(target=self._producer, name="gonken-wake-capture", daemon=True)
        self.thread.start()

    def _producer(self) -> None:
        sequence = 0
        while not self.cancel.is_set():
            try:
                path = Path(self.capture(self.window_seconds, cancel=self.cancel))
            except VoiceRuntimeError as exc:
                if self.cancel.is_set() and exc.code == "AUDIO_CAPTURE_CANCELLED":
                    break
                with self._lock:
                    self._error = exc
                self.cancel.set()
                break
            except BaseException as exc:
                if self.cancel.is_set():
                    break
                with self._lock:
                    self._error = exc
                self.cancel.set()
                break
            if self.cancel.is_set():
                path.unlink(missing_ok=True)
                break
            sequence += 1
            self.captured_windows = sequence
            window = WakeCaptureWindow(sequence, path, time.monotonic())
            if self.queue.full():
                try:
                    stale = self.queue.get_nowait()
                except queue.Empty:
                    pass
                else:
                    stale.path.unlink(missing_ok=True)
                    self.dropped_windows += 1
            self.queue.put_nowait(window)

    def next_window(self, *, timeout: float = 0.25) -> WakeCaptureWindow | None:
        with self._lock:
            error = self._error
        if error is not None:
            raise error
        try:
            return self.queue.get(timeout=max(0.01, float(timeout)))
        except queue.Empty:
            with self._lock:
                error = self._error
            if error is not None:
                raise error
            return None

    def stop(self, *, join_timeout: float = 3.0) -> None:
        self.cancel.set()
        thread = self.thread
        if thread is not None:
            thread.join(timeout=max(0.1, float(join_timeout)))
            if thread.is_alive():
                raise VoiceRuntimeError("WAKE_CAPTURE_STOP_TIMEOUT")
        while True:
            try:
                window = self.queue.get_nowait()
            except queue.Empty:
                break
            window.path.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class ProcessingCue:
    code: str
    text: str
    due_after_seconds: float


class ProcessingCuePlan:
    """Deterministic progress-cue state machine for host tests and runtime."""

    DEFAULT_CUES = (
        ProcessingCue("ACK_DELAY", "Just a second.", 0.9),
        ProcessingCue("STILL_WORKING", "I'm still working on that.", 4.0),
    )

    def __init__(self, cues: tuple[ProcessingCue, ...] | None = None, *, enabled: bool = True) -> None:
        self.cues = cues or self.DEFAULT_CUES
        self.enabled = enabled
        self._spoken: set[str] = set()

    def due(self, *, elapsed_seconds: float, final_ready: bool) -> ProcessingCue | None:
        if not self.enabled or final_ready:
            return None
        for cue in self.cues:
            if cue.code not in self._spoken and elapsed_seconds >= cue.due_after_seconds:
                return cue
        return None

    def mark_spoken(self, cue: ProcessingCue) -> None:
        self._spoken.add(cue.code)


class VoiceCueCache:
    """Local Piper-generated cache for short governed progress cues."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.manifest_path = self.cache_dir / "manifest.json"

    def ensure(self, *, text: str, piper: Piper, stop: threading.Event) -> Path:
        allowed = {"Yes?", *(cue.text for cue in ProcessingCuePlan.DEFAULT_CUES)}
        if text not in allowed:
            raise VoiceRuntimeError("CUE_TEXT_NOT_GOVERNED")
        if self.cache_dir.is_symlink():
            raise VoiceRuntimeError("CUE_CACHE_UNSAFE")
        self.cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.cache_dir.stat().st_uid != os.geteuid() or self.cache_dir.stat().st_mode & 0o022:
            raise VoiceRuntimeError("CUE_CACHE_UNSAFE")
        key = hashlib.sha256(f"{piper.voice}\0{text}".encode("utf-8")).hexdigest()
        wav_path = self.cache_dir / f"{key}.wav"
        manifest = {k:v for k,v in self._read_manifest().items()
                    if isinstance(v,dict) and v.get("text") in allowed}
        entry = manifest.get(key)
        if wav_path.is_symlink():
            raise VoiceRuntimeError("CUE_CACHE_UNSAFE")
        if isinstance(entry, dict) and wav_path.is_file() and wav_path.stat().st_size <= 2097152:
            try:
                validate_wav(wav_path, max_seconds=10)
                if hashlib.sha256(wav_path.read_bytes()).hexdigest() == entry.get("wav_sha256"):
                    return wav_path
            except Exception:
                pass
        with piper.synthesize(text, stop) as generated:
            validate_wav(generated, max_seconds=10)
            if generated.stat().st_size > 2097152:
                raise VoiceRuntimeError("CUE_TOO_LARGE")
            data = generated.read_bytes()
        fd, name = tempfile.mkstemp(prefix=".cue-", dir=self.cache_dir)
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(data); out.flush(); os.fsync(out.fileno())
            os.replace(name,wav_path)
        finally:
            Path(name).unlink(missing_ok=True)
        manifest[key] = {"text": text, "voice": str(piper.voice),
                         "wav_sha256": hashlib.sha256(data).hexdigest(), "physical_evidence": False}
        manifest = dict(list(manifest.items())[-9:])
        fd, name = tempfile.mkstemp(prefix=".manifest-", dir=self.cache_dir)
        try:
            with os.fdopen(fd,"w") as out:
                json.dump(manifest,out,sort_keys=True); out.flush(); os.fsync(out.fileno())
            os.replace(name,self.manifest_path)
        finally:
            Path(name).unlink(missing_ok=True)
        return wav_path

    def _read_manifest(self) -> dict[str, object]:
        try:
            if self.manifest_path.is_file() and not self.manifest_path.is_symlink() and self.manifest_path.stat().st_size <= 65536:
                value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
        except (OSError, json.JSONDecodeError):
            pass
        return {}


_ANNOUNCED_TRANSITION_REASONS = {
    "AUTO_START_THRESHOLD",
    "AUTO_STOP_THRESHOLD",
    "SEMI_AUTO_STOP",
    "SENSOR_STALE_SAFE_OFF",
    "ACTUATOR_ERROR_SAFE_OFF",
}


def _transition_announcement_text(event: dict[str, object]) -> str | None:
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    provenance = event.get("provenance") if isinstance(event.get("provenance"), dict) else {}
    reason = str(detail.get("reason", ""))
    if reason not in _ANNOUNCED_TRANSITION_REASONS:
        return None
    simulated = bool(provenance.get("sensor_is_simulated") or provenance.get("actuator_is_simulated"))
    prefix = "In simulation, " if simulated else ""
    fan_power = str(detail.get("fan_power", "off"))
    if reason in {"AUTO_START_THRESHOLD", "AUTO_STOP_THRESHOLD", "SEMI_AUTO_STOP"}:
        if fan_power not in {"on", "off"}:
            return None
        state = "started" if fan_power == "on" else "stopped"
        return f"{prefix}fan actuator {state}." if simulated else f"Fan actuator {state}."
    if reason == "SENSOR_STALE_SAFE_OFF":
        return f"{prefix}sensor unavailable. Safe off requested."
    if reason == "ACTUATOR_ERROR_SAFE_OFF":
        return f"{prefix}fan actuator error. State unconfirmed."
    return None


class EnvironmentTransitionAnnouncer:
    """Voice-owned observer for daemon transition events.

    The environment daemon records typed events; only the voice runtime may turn
    them into speech, preserving the single audio owner boundary.
    """

    def __init__(self, client_factory, *, limit: int = 8, clock=time.monotonic) -> None:
        self.client_factory = client_factory
        self.limit = limit
        self._seen: set[tuple[str, int]] = set()
        self._seen_order = []
        self._generation = None
        self._clock = clock
        self._next_poll = 0.0

    def pending(self) -> str | None:
        now = self._clock()
        if now < self._next_poll: return None
        self._next_poll = now + 1.0
        try:
            payload = self.client_factory().events(limit=self.limit)
        except EnvironmentClientError:
            return None
        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list):
            return None
        generation = payload.get("generation")
        if generation != self._generation:
            self._seen.clear(); self._seen_order.clear(); self._generation = generation
        for event in events:
            if not isinstance(event, dict):
                continue
            source = str(event.get("source", event.get("event_type", "unknown")))
            try:
                sequence = int(event.get("sequence", -1))
            except (TypeError, ValueError):
                continue
            key = (source, sequence)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._seen_order.append(key)
            if len(self._seen_order) > 128:
                self._seen.discard(self._seen_order.pop(0))
            text = _transition_announcement_text(event)
            if text:
                return text
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

    def _alsa_record_to(self, destination: Path, seconds: int, **options) -> None:
        self._raw_record_to(destination, seconds, backend="alsa", **options)

    def _pulse_record_to(self, destination: Path, seconds: int, **options) -> None:
        self._raw_record_to(destination, seconds, backend="pulse", **options)

    def _raw_record_to(
        self, destination: Path, seconds: int, *, backend: str,
        cancel: threading.Event | None = None, keep_on_cancel: bool = False,
        end_on_silence: bool = False,
    ) -> None:
        """Capture raw PCM; finalize the WAV only after the writer is reaped.

        Both transports have the same bounded container/endpoint contract. A
        killed or interrupted recorder can never leave its placeholder WAV
        header in the file subsequently handed to Whisper.
        """
        rate = int(self.config.audio.processing_rate)
        if backend == "pulse":
            if self.parecord is None:
                raise VoiceRuntimeError("PARECORD_MISSING")
            args = [str(self.parecord), f"--device={self.input_device}", "--raw",
                    "--format=s16le", f"--rate={rate}", "--channels=1"]
        elif backend == "alsa":
            args = [str(self.arecord), "-q", "-D", self.input_device, "-t", "raw",
                    "-f", "S16_LE", "-r", str(rate), "-c", "1", "-d", str(seconds)]
        else:
            raise ValueError("unknown capture backend")
        descriptor, raw_name = tempfile.mkstemp(prefix=".voice-raw-", suffix=".pcm", dir=destination.parent)
        raw_path = Path(raw_name)
        detector = SpeechEndpoint(rate,
            threshold=getattr(self.config.audio, "speech_energy_threshold", 250),
            silence_ms=getattr(self.config.audio, "speech_end_silence_ms", 900)) if end_on_silence else None
        process = None
        cancelled = stopped = False
        maximum = rate * 2 * (seconds + 1)
        try:
            with os.fdopen(descriptor, "wb") as output:
                try:
                    process = subprocess.Popen(args, stdout=output, stderr=subprocess.PIPE, text=True)
                except OSError as exc:
                    raise VoiceRuntimeError("AUDIO_CAPTURE_PROCESS_START_FAILED", backend) from exc
                started = time.monotonic()
                deadline = started + seconds + (2 if backend == "alsa" else 0)
                while process.poll() is None:
                    if raw_path.stat().st_size > maximum:
                        raise VoiceRuntimeError("AUDIO_CAPTURE_OVERSIZE")
                    if cancel is not None and cancel.is_set():
                        cancelled = stopped = True
                        break
                    if detector is not None and detector.observe(raw_path, raw=True):
                        stopped = True
                        break
                    if time.monotonic() >= deadline:
                        if backend == "alsa":
                            raise VoiceRuntimeError("AUDIO_CAPTURE_TIMEOUT")
                        stopped = True
                        break
                    time.sleep(0.02)
                if stopped and process.poll() is None:
                    try:
                        process.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
                try:
                    _, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    process.communicate(timeout=3)
                    raise VoiceRuntimeError("AUDIO_CAPTURE_STOP_TIMEOUT") from exc
            if cancelled and not keep_on_cancel:
                raise VoiceRuntimeError("AUDIO_CAPTURE_CANCELLED")
            if process.returncode != 0 and not (stopped and process.returncode in (-signal.SIGINT, 1, 130)):
                detail = stderr or f"recorder exited rc={process.returncode}"
                raise VoiceRuntimeError(_classify_audio_capture_failure(detail, backend=backend),
                                        f"backend={backend} {_diagnostic_text(detail)}")
            if raw_path.stat().st_size > maximum:
                raise VoiceRuntimeError("AUDIO_CAPTURE_OVERSIZE")
            _write_pcm16_mono_wav(raw_path, destination, rate=rate)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
            raw_path.unlink(missing_ok=True)

    def _record_to(
        self,
        destination: Path,
        seconds: int,
        *,
        cancel: threading.Event | None = None,
        keep_on_cancel: bool = False,
        end_on_silence: bool = False,
    ) -> None:
        if not 1 <= seconds <= 30:
            raise ValueError("capture seconds must be 1..30")
        if self.input_mode.startswith("pipewire-"):
            self._pulse_record_to(destination, seconds, cancel=cancel, keep_on_cancel=keep_on_cancel, end_on_silence=end_on_silence)
        else:
            self._alsa_record_to(destination, seconds, cancel=cancel, keep_on_cancel=keep_on_cancel, end_on_silence=end_on_silence)
        try:
            metadata = validate_wav(destination, max_seconds=seconds + 1)
        except Exception as exc:
            detail = _diagnostic_text(str(exc) or type(exc).__name__)
            raise VoiceRuntimeError(
                "AUDIO_CAPTURE_WAV_INVALID",
                f"backend={self.input_mode} device={self.input_device} {detail}",
            ) from exc
        self.last_capture_metadata = {"rate": metadata["rate"], "maximum_seconds": seconds,
                                      "speech_endpointing": end_on_silence}
        if metadata["rate"] != self.config.audio.processing_rate:
            raise VoiceRuntimeError("AUDIO_CAPTURE_RATE_MISMATCH", f"expected={self.config.audio.processing_rate} observed={metadata['rate']}")

    def capture(
        self,
        seconds: int,
        *,
        cancel: threading.Event | None = None,
        keep_on_cancel: bool = False,
        end_on_silence: bool = False,
    ) -> Path:
        if not self._input_candidates:
            self.refresh()
        descriptor, name = tempfile.mkstemp(prefix="voice-", suffix=".wav", dir=self.runtime_dir)
        os.close(descriptor)
        path = Path(name)
        failures: list[str] = []
        try:
            for route in list(self._input_candidates):
                if cancel is not None and cancel.is_set():
                    raise VoiceRuntimeError("AUDIO_CAPTURE_CANCELLED")
                self._apply_route("input", route)
                path.unlink(missing_ok=True)
                path.touch(mode=0o600)
                try:
                    self._record_to(path, seconds, cancel=cancel, keep_on_cancel=keep_on_cancel, end_on_silence=end_on_silence)
                    return path
                except VoiceRuntimeError as exc:
                    if exc.code == "AUDIO_CAPTURE_CANCELLED":
                        raise
                    failures.append(f"{route[0]}:{exc.code}")
            raise VoiceRuntimeError(
                "AUDIO_CAPTURE_FAILED",
                "routes=" + ",".join(failures)[:240],
            )
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def open_pcm_stream(self, *, cancel: threading.Event):
        if self.config.audio.processing_rate != 16000:
            raise VoiceRuntimeError("AUDIO_STREAM_RATE_INVALID")
        if not self._input_candidates:
            self.refresh()
        failures = []
        for route in list(self._input_candidates):
            if cancel.is_set():
                raise VoiceRuntimeError("AUDIO_CAPTURE_CANCELLED")
            self._apply_route("input", route)
            if self.input_mode.startswith("pipewire-"):
                if self.parecord is None:
                    failures.append(f"{route[0]}:PARECORD_MISSING")
                    continue
                args = [str(self.parecord), f"--device={self.input_device}", "--raw",
                        "--format=s16le", "--rate=16000", "--channels=1"]
            else:
                args = [str(self.arecord), "-q", "-D", self.input_device,
                        "-t", "raw", "-f", "S16_LE", "-r", "16000", "-c", "1"]
            stream = None
            try:
                stream = PCMInputStream(args)
                stream.prime(cancel=cancel)
                return stream
            except PCMStreamError as exc:
                if stream is not None:
                    stream.close()
                if exc.code == "AUDIO_CAPTURE_CANCELLED":
                    raise VoiceRuntimeError(exc.code) from exc
                failures.append(f"{route[0]}:{exc.code}")
        raise VoiceRuntimeError("AUDIO_CAPTURE_FAILED", "routes=" + ",".join(failures)[:240])

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
    """Small in-memory local conversation with deterministic environment actions."""

    def __init__(self, config, *, environment_client_factory=None):
        selected_model = active_model(config.llm.model)
        self.client = OllamaClient(config.llm, timeout=90, model=selected_model)
        self.tool_context_tokens = config.llm.context_tokens
        self.roster_record_path = Path("/var/lib/gonken-agent/ollama/roster.json")
        prompt_path = Path(config.paths.local_prompt)
        if not prompt_path.is_file() or prompt_path.is_symlink() or prompt_path.stat().st_size > 32768:
            raise VoiceRuntimeError("LOCAL_PROMPT_MISSING")
        self.system_prompt = prompt_path.read_text(encoding="utf-8").strip()
        if not self.system_prompt:
            raise VoiceRuntimeError("LOCAL_PROMPT_EMPTY")
        self.history: list[dict[str, str]] = []
        self.environment_client_factory = (
            environment_client_factory
            if environment_client_factory is not None
            else lambda: EnvironmentClient(config.extensions.environment.socket_path, timeout_seconds=2.0)
        )
        self.operations = OperationalCommands(self.environment_client_factory, config=config)
        self.tool_broker = ToolBroker(self.environment_client_factory)
        self.last_metrics: dict[str, object] = {}

    def _admit_model_tools(self, identity: dict[str, str]) -> bool:
        """Check the actual consumer, not catalog support or a previous READY.

        Legacy rollback conversation remains text-only. Governed models must
        match current recorded digest/context/tool qualification before the
        runtime requests tools. Direct deterministic environment intents remain
        independent of this model capability.
        """
        model = identity.get("model")
        if model == LEGACY_MODEL:
            return False
        if model not in roster_tags() or model != self.client.model:
            raise VoiceRuntimeError("LOCAL_MODEL_OUTSIDE_ROSTER")
        context = getattr(self, "tool_context_tokens", None)
        if type(context) is not int or context <= 0:
            raise VoiceRuntimeError("LOCAL_MODEL_TOOLS_NOT_QUALIFIED")
        record = bounded_json(self.roster_record_path, 256 * 1024)
        qualified = qualified_rows(record, [{"name": model, "digest": identity.get("digest")}],
                                   context_tokens=context)
        if qualified.get(model, {}).get("tools") is not True:
            raise VoiceRuntimeError("LOCAL_MODEL_TOOLS_NOT_QUALIFIED")
        return True

    def probe(self, stop: threading.Event) -> dict[str, str]:
        identity = self.client.model_identity(stop)
        self._admit_model_tools(identity)
        # Readiness means inference works, not merely that a tag exists.  This
        # also warms the small local model so the first spoken turn has lower
        # latency after boot.  The probe is not added to conversation history.
        self.client.chat_text(
            [{"role": "user", "content": "Reply with the single word ready."}],
            stop,
        )
        return identity

    def reply(self, question: str, stop: threading.Event) -> str:
        turn_started = time.monotonic_ns()
        self.last_metrics = {"route": "unknown", "model": str(getattr(self.client, "model", "compatibility-adapter")), "content_logged": False}
        question = " ".join(question.split())
        if not question or len(question) > 4096:
            raise VoiceRuntimeError("VOICE_QUESTION_INVALID")

        operations = self._operations()
        answer = operations.handle(question)
        if answer is not None:
            self.last_metrics.update({"route": operations.last_route, "wall_ns": time.monotonic_ns() - turn_started})
            return answer

        messages = [{"role": "system", "content": self.system_prompt}, *self.history,
                    {"role": "user", "content": question}]
        # Bound conversational context independently of the model's token window.
        while sum(len(item["content"]) for item in messages) > 12000 and len(self.history) >= 2:
            del self.history[:2]
            messages = [{"role": "system", "content": self.system_prompt}, *self.history,
                        {"role": "user", "content": question}]
        try:
            broker = getattr(self, "tool_broker", None)
            tools_admitted = False
            if broker is not None and hasattr(self.client, "chat_message"):
                # Check fresh inventory and the bounded qualification record on
                # every model-routed turn. No inference is used to test health.
                tools_admitted = self._admit_model_tools(self.client.model_identity(stop))
            if tools_admitted:
                response = self.client.chat_message(
                    messages, stop, tools=broker.schemas, think=False
                )
                raw_calls = response.get("tool_calls", [])
                if isinstance(raw_calls, list) and raw_calls:
                    self.last_metrics["route"] = "llm_typed_tool"
                    try:
                        answer = broker.execute_calls(raw_calls, user_text=question)
                    except ToolBrokerError:
                        self.last_metrics["route"] = "llm_typed_tool_refused"
                        answer = (
                            "I did not perform that operation because the proposed tool action "
                            "was not independently authorized by your request."
                        )
                else:
                    self.last_metrics["route"] = "llm_text"
                    answer = response.get("content", "")
                for metric in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration", "prompt_eval_count", "eval_count"):
                    value = response.get(metric)
                    if isinstance(value, int) and value >= 0:
                        self.last_metrics[f"ollama_{metric}"] = value
            else:
                # Text-only compatibility path: no tool schema or model-proposed action.
                self.last_metrics["route"] = "llm_compatibility"
                answer = self.client.chat_text(messages, stop)
        except OllamaError as exc:
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_FAILED") from exc
        if not isinstance(answer, str):
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_INVALID")
        answer = " ".join(answer.split())
        if not answer or len(answer) > 4096:
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_INVALID")
        self.history.extend((
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ))
        self.history = self.history[-8:]
        self.last_metrics["wall_ns"] = time.monotonic_ns() - turn_started
        return answer

    def _operations(self):
        if not hasattr(self, "operations"):
            self.operations = OperationalCommands(self.environment_client_factory)
        return self.operations

    def begin_interaction(self):
        self._operations().begin()

    def is_fast_deterministic(self, question: str) -> bool:
        return self._operations().is_fast(question)

    def complete_inline_command(self, question: str) -> bool:
        return self._operations().complete_inline(question)

    def _environment_reply(self, intent: EnvironmentIntent) -> str:
        return self._operations().environment_reply(intent)

    def after_spoken(self):
        return self._operations().after_spoken()

    def speech_failed(self):
        self._operations().speech_failed()

    def confirmation_pending(self):
        return self._operations().power.pending is not None

    def confirm_power(self, text):
        power = self._operations().power
        answer = power.handle(text)
        if answer is None:
            power.cancel()
            return "Power action cancelled."
        return answer

    def close(self) -> None:
        self.client.close()


class PushToTalkVoiceAdapter:
    """Bridge the debounced PTT controller to the production voice pipeline.

    A button press starts a bounded physical capture in one worker.  Release
    cancels the recorder while preserving the partial WAV, turns the recording
    LED off in the controller, and only then transcribes/processes the audio.
    Raw audio remains temporary and is deleted by the normal transcription
    lifecycle or by discard/close paths.
    """

    def __init__(self, appliance: "VoiceAppliance", hardware: GpiodPushToTalkHardware, *, max_capture_seconds: int = 30) -> None:
        if not 1 <= int(max_capture_seconds) <= 30:
            raise ValueError("max_capture_seconds must be 1..30")
        self.appliance = appliance
        self.hardware = hardware
        self.max_capture_seconds = int(max_capture_seconds)
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._path: Path | None = None
        self._error: BaseException | None = None
        self._lock = threading.RLock()

    def available(self) -> bool:
        return not self.appliance.stop.is_set() and self._thread is None

    def led(self, on: bool) -> None:
        self.hardware.led(on)

    def start_capture(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise VoiceRuntimeError("PTT_CAPTURE_ALREADY_ACTIVE")
            self._discard_locked()
            self._cancel.clear()
            self._error = None
            self._thread = threading.Thread(target=self._capture_worker, name="gonken-ptt-capture", daemon=True)
            self._thread.start()
        self.appliance._event("RUNNING", "PTT_RECORDING")

    def _capture_worker(self) -> None:
        try:
            path = self.appliance.audio.capture(
                self.max_capture_seconds,
                cancel=self._cancel,
                keep_on_cancel=True,
            )
        except VoiceRuntimeError as exc:
            if self._cancel.is_set() and exc.code == "AUDIO_CAPTURE_CANCELLED":
                return
            with self._lock:
                self._error = exc
            return
        except BaseException as exc:
            with self._lock:
                self._error = exc
            return
        with self._lock:
            self._path = Path(path)

    def check_capture_error(self) -> None:
        with self._lock:
            thread = self._thread
            error = self._error
        if error is not None and (thread is None or not thread.is_alive()):
            if isinstance(error, VoiceRuntimeError):
                raise error
            raise VoiceRuntimeError("PTT_CAPTURE_FAILED", type(error).__name__) from error

    def stop_capture(self) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._cancel.set()
        thread.join(timeout=5.0)
        if thread.is_alive():
            raise VoiceRuntimeError("PTT_CAPTURE_STOP_TIMEOUT")
        with self._lock:
            self._thread = None
            error = self._error
            self._error = None
        if error is not None:
            if isinstance(error, VoiceRuntimeError):
                raise error
            raise VoiceRuntimeError("PTT_CAPTURE_FAILED", type(error).__name__) from error

    def _discard_locked(self) -> None:
        if self._path is not None:
            self._path.unlink(missing_ok=True)
            self._path = None

    def discard_capture(self) -> None:
        with self._lock:
            self._discard_locked()
        self.appliance._event("INFO", "PTT_CAPTURE_DISCARDED")

    def submit(self) -> None:
        with self._lock:
            path = self._path
            self._path = None
        if path is None:
            self.appliance._event("INFO", "VOICE_NO_SPEECH")
            return
        self.appliance._event("RUNNING", "VOICE_TRANSCRIBING")
        question = self.appliance._transcribe_captured_audio(path)
        if not question:
            self.appliance._event("INFO", "VOICE_NO_SPEECH")
            return
        begin = getattr(getattr(self.appliance, "brain", None), "begin_interaction", None)
        if callable(begin): begin()
        self.appliance._event("RUNNING", "VOICE_THINKING")
        answer = self.appliance._answer_question(question)
        self.appliance._event("RUNNING", "VOICE_SPEAKING")
        deliver = getattr(self.appliance, "_deliver_answer", self.appliance.speak)
        deliver(answer)
        self.appliance._event("OK", "VOICE_TURN_COMPLETE")

    def close(self) -> None:
        error: BaseException | None = None
        try:
            self.stop_capture()
        except BaseException as exc:
            error = exc
        with self._lock:
            self._discard_locked()
        try:
            self.hardware.close(suppress_errors=False)
        except BaseException as exc:
            error = error or exc
        if error is not None:
            raise error


class VoiceAppliance:
    READY_FILE = Path("/run/gonken-agent/ready.json")
    READINESS_FILE = Path("/run/gonken-agent/readiness.json")

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
        self.cue_cache = VoiceCueCache(Path(config.paths.cache_dir) / "voice-cues")
        self.brain = ConversationBrain(config)
        self.transition_announcer = EnvironmentTransitionAnnouncer(
            lambda: EnvironmentClient(config.extensions.environment.socket_path, timeout_seconds=0.15)
        )
        self.notification_announcer = NotificationAnnouncer(
            lambda: EnvironmentClient(config.extensions.environment.socket_path, timeout_seconds=0.15)
        )
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

    def _transcribe_captured_audio(self, path: Path) -> str:
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

    def capture_text(self, seconds: int) -> str:
        audio_config = getattr(getattr(self, "config", None), "audio", None)
        if (getattr(audio_config, "speech_endpointing", False) is True
                and audio_config.processing_rate % 50 == 0):
            path = self.audio.capture(seconds, cancel=self.stop, end_on_silence=True)
        else:
            path = self.audio.capture(seconds)
        return self._transcribe_captured_audio(path)

    def _question_after_wake(self, remainder: str, *, utterance_complete: bool = False) -> str:
        """Use a complete deterministic command immediately, not a partial window.

        Wake windows can end mid-sentence. General questions retain bounded
        follow-up capture; overlap matching avoids duplicating a repeated prefix.
        """
        initial = " ".join(remainder.split())
        fast = getattr(self.brain, "complete_inline_command", None) or getattr(self.brain, "is_fast_deterministic", None)
        inline_ready = bool(initial and callable(fast) and fast(initial))
        if initial and utterance_complete:
            return initial
        following = self.capture_text(8)
        if inline_ready and not utterance_complete and not following:
            # A window ending in speech can omit "after two minutes". Never
            # convert a possibly delayed action into immediate actuation.
            return ""
        if not initial or not following:
            return following or initial
        left, right = initial.split(), following.split()
        if following.casefold().startswith(initial.casefold()):
            return following
        overlap = 0
        for size in range(1, min(len(left), len(right)) + 1):
            if [v.casefold() for v in left[-size:]] == [v.casefold() for v in right[:size]]:
                overlap = size
        return " ".join(left + right[overlap:])

    def speak(self, text: str) -> None:
        with self.piper.synthesize(text, self.stop) as wav:
            self.audio.play(wav)

    def speak_progress_cue(self, text: str) -> None:
        wav = self.cue_cache.ensure(text=text, piper=self.piper, stop=self.stop)
        self.audio.play(wav)

    def _deliver_answer(self, answer: str) -> None:
        """One audio owner, acknowledgement before action, one bounded confirmation."""
        try:
            self.speak(answer)
            after = getattr(self.brain, "after_spoken", None)
            problem = after() if callable(after) else None
            if problem:
                self.speak(problem)
            pending = getattr(self.brain, "confirmation_pending", None)
            if callable(pending) and pending():
                question = self.capture_text(5)
                response = self.brain.confirm_power(question or "cancel")
                self.speak(response)
                problem = after() if callable(after) else None
                if problem: self.speak(problem)
        except Exception:
            failed = getattr(self.brain, "speech_failed", None)
            if callable(failed): failed()
            raise

    def _answer_question(self, question: str) -> str:
        started = time.monotonic_ns()
        fast_check = getattr(self.brain, "is_fast_deterministic", None)
        if not callable(fast_check):
            answer = self.brain.reply(question, self.stop)
        elif fast_check(question):
            answer = self.brain.reply(question, self.stop)
        else:
            answer = self._reply_with_progress_cues(question)
        metrics = getattr(self.brain, "last_metrics", {})
        fields: dict[str, object] = {"total_ms": int((time.monotonic_ns() - started) / 1_000_000)}
        if isinstance(metrics, dict):
            route = metrics.get("route")
            model = metrics.get("model")
            if isinstance(route, str):
                fields["route"] = route
            if isinstance(model, str):
                fields["model"] = model
            for key in ("ollama_total_duration", "ollama_load_duration", "ollama_prompt_eval_duration", "ollama_eval_duration"):
                value = metrics.get(key)
                if isinstance(value, int) and value >= 0:
                    fields[key.replace("duration", "ms")] = int(value / 1_000_000)
        self._event("INFO", "VOICE_TURN_METRICS", **fields)
        return answer

    def _reply_with_progress_cues(self, question: str) -> str:
        plan = ProcessingCuePlan()
        holder: dict[str, object] = {}

        def worker() -> None:
            try:
                holder["answer"] = self.brain.reply(question, self.stop)
            except BaseException as exc:  # preserve exact runtime exception for main thread
                holder["error"] = exc

        thread = threading.Thread(target=worker, name="gonken-reply", daemon=True)
        started = time.monotonic()
        thread.start()
        while thread.is_alive() and not self.stop.is_set():
            cue = plan.due(elapsed_seconds=time.monotonic() - started, final_ready=False)
            if cue is not None:
                self._event("RUNNING", "VOICE_PROGRESS_CUE", cue=cue.code)
                try:
                    self.speak_progress_cue(cue.text)
                finally:
                    plan.mark_spoken(cue)
            thread.join(timeout=0.05)
        thread.join(timeout=0.1)
        if "error" in holder:
            raise holder["error"]  # type: ignore[misc]
        if "answer" not in holder:
            raise VoiceRuntimeError("LOCAL_MODEL_RESPONSE_INTERRUPTED")
        return str(holder["answer"])

    def _announce_environment_transitions(self) -> None:
        announcer = getattr(self, "transition_announcer", None)
        if announcer is None:
            return
        text = announcer.pending()
        if not text:
            return
        self._event("RUNNING", "ENVIRONMENT_TRANSITION_ANNOUNCEMENT")
        self.speak(text)

    def probe(self) -> dict[str, object]:
        audio = self.audio.probe()
        if (self.config.runtime.interaction_mode == "wake_word"
                and getattr(self.config.extensions.wake_word, "backend", "whisper") == "streaming"):
            self._get_keyword_detector()
            audio["wake_backend"] = "streaming-kws-vad"
        identity = self.brain.probe(self.stop)
        return {"audio": audio, "model": identity}

    def _write_readiness_state(
        self, *, status: str, code: str, component: str, recoverable: bool
    ) -> None:
        if not self.publish_ready:
            return
        self.READINESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "gonken-voice-readiness-v1",
            "status": status,
            "code": code,
            "component": component,
            "recoverable": bool(recoverable),
            "wake_phrase": self.config.extensions.wake_word.phrase,
            "release_commit": _runtime_release_commit(),
            "release_profile": _runtime_release_profile(),
            "boot_id": _boot_id(),
            "service_pid": os.getpid(),
            "service_start_ticks": _process_start_ticks(),
            "configuration_sha256": configuration_digest(self.config),
            "observed_epoch": int(time.time()),
        }
        temporary = self.READINESS_FILE.with_name(f".{self.READINESS_FILE.name}.{os.getpid()}")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o644)
        os.replace(temporary, self.READINESS_FILE)

    def _write_ready(self, probe: dict[str, object]) -> None:
        if not self.publish_ready:
            return
        self.READY_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "READY",
            "code": "VOICE_RUNTIME_READY",
            "wake_phrase": self.config.extensions.wake_word.phrase,
            "interaction_mode": self.config.runtime.interaction_mode,
            "audio_backend": probe["audio"]["backend"],
            "model": probe["model"]["model"],
            "model_digest": probe["model"].get("digest"),
            "release_commit": _runtime_release_commit(),
            "release_profile": _runtime_release_profile(),
            "boot_id": _boot_id(),
            "service_pid": os.getpid(),
            "service_start_ticks": _process_start_ticks(),
            "configuration_sha256": configuration_digest(self.config),
            "observed_epoch": int(time.time()),
        }
        temporary = self.READY_FILE.with_name(f".{self.READY_FILE.name}.{os.getpid()}")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.chmod(0o644)
        os.replace(temporary, self.READY_FILE)
        self._write_readiness_state(
            status="READY", code="VOICE_RUNTIME_READY", component="voice_runtime", recoverable=True
        )

    def _clear_ready(self, *, clear_readiness: bool = False) -> None:
        if self.publish_ready:
            self.READY_FILE.unlink(missing_ok=True)
            if clear_readiness:
                self.READINESS_FILE.unlink(missing_ok=True)
        self.ready = False

    def wait_until_ready(self) -> bool:
        delay = 2.0
        while not self.stop.is_set():
            try:
                probe = self.probe()
                # Require the real TTS -> physical playback path before publishing
                # readiness.  This closes the gap between an ALSA device that can
                # open and an appliance that can actually speak.
                if not getattr(self, "_startup_announced", False):
                    self.speak("GonKen assistant is ready.")
                    self._startup_announced = True
                self.cue_cache.ensure(text="Yes?", piper=self.piper, stop=self.stop)
                self._write_ready(probe)
                self.ready = True
                self._event(
                    "READY",
                    "VOICE_RUNTIME_READY",
                    wake_phrase=self.config.extensions.wake_word.phrase,
                    interaction_mode=self.config.runtime.interaction_mode,
                )
                return True
            except Exception as exc:
                self._clear_ready()
                code = exc.code if isinstance(exc, VoiceRuntimeError) else "VOICE_DEPENDENCY_WAIT"
                detail = exc.detail if isinstance(exc, VoiceRuntimeError) else _diagnostic_text(type(exc).__name__)
                self._write_readiness_state(
                    status="WAITING",
                    code=code,
                    component=_readiness_component(code),
                    recoverable=_readiness_recoverable(code),
                )
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
        begin = getattr(self.brain, "begin_interaction", None)
        if callable(begin): begin()
        self._event("RUNNING", "VOICE_LISTENING", seconds=seconds)
        question = self.capture_text(seconds)
        if not question:
            self._event("INFO", "VOICE_NO_SPEECH")
            return None
        if foreground:
            print(f"You: {question}", flush=True)
        self._event("RUNNING", "VOICE_THINKING")
        answer = self._answer_question(question)
        if foreground:
            print(f"GonKen: {answer}", flush=True)
        self._event("RUNNING", "VOICE_SPEAKING")
        self._deliver_answer(answer)
        self._event("OK", "VOICE_TURN_COMPLETE")
        return answer

    def _get_keyword_detector(self):
        detector = getattr(self, "_keyword_detector", None)
        if detector is None:
            wake = self.config.extensions.wake_word
            detector = NativeKeywordDetector(wake.phrase, self.runtime_dir,
                threshold=wake.keyword_threshold)
            self._keyword_detector = detector
        return detector

    def _new_wake_capture_pipeline(self):
        if getattr(self.config.extensions.wake_word, "backend", "whisper") == "streaming":
            return StreamingWakePipeline(self.audio.open_pcm_stream,
                self._get_keyword_detector(), self.runtime_dir,
                threshold=self.config.audio.speech_energy_threshold,
                silence_ms=self.config.audio.speech_end_silence_ms)
        return WakeCapturePipeline(self.audio.capture,
            window_seconds=WAKE_CAPTURE_WINDOW_SECONDS, queue_size=WAKE_CAPTURE_QUEUE_SIZE)

    def _start_wake_standby(self, phrase: str) -> tuple[RollingWakeTranscriptMatcher, WakeCapturePipeline]:
        matcher = RollingWakeTranscriptMatcher(phrase)
        pipeline = self._new_wake_capture_pipeline()
        pipeline.start()
        self._event(
            "RUNNING",
            "WAKE_STANDBY",
            phrase=phrase,
            matcher=WAKE_MATCHER_VERSION,
            capture_mode=getattr(pipeline, "capture_mode", WAKE_CAPTURE_MODE),
            window_seconds=pipeline.window_seconds,
        )
        return matcher, pipeline

    @staticmethod
    def _discard_wake_pipeline(pipeline: WakeCapturePipeline | None, *, suppress: bool = False) -> None:
        if pipeline is None:
            return
        try:
            pipeline.stop()
        except Exception:
            if not suppress:
                raise

    def push_to_talk_loop(self) -> int:
        if self.config.runtime.interaction_mode != "push_to_talk":
            raise VoiceRuntimeError("PTT_INTERACTION_MODE_NOT_ENABLED")
        retry_seconds = 5
        while not self.stop.is_set():
            hardware: GpiodPushToTalkHardware | None = None
            controller: PushToTalk | None = None
            try:
                hardware = GpiodPushToTalkHardware.from_config(self.config)
                hardware.open()
                adapter = PushToTalkVoiceAdapter(self, hardware, max_capture_seconds=30)
                controller = PushToTalk(adapter, debounce=0.03, max_hold=30.0)
                identities = hardware.identities()
                if not self.wait_until_ready():
                    return 0
                self._event(
                    "RUNNING",
                    "PTT_STANDBY",
                    button_bcm=identities["button_bcm"],
                    button_chip=identities["button_chip_path"],
                    button_line=identities["button_line_offset"],
                    led_bcm=identities["led_bcm"],
                    led_chip=identities["led_chip_path"],
                    led_line=identities["led_line_offset"],
                    physical_acceptance_claimed=False,
                )
                while not self.stop.is_set():
                    adapter.check_capture_error()
                    pressed = hardware.pressed()
                    controller.update(pressed, time.monotonic())
                    self.stop.wait(0.02)
                return 0
            except Exception as exc:
                if self.stop.is_set():
                    break
                self._clear_ready()
                code = str(getattr(exc, "code", "PTT_RUNTIME_RECOVERY"))
                detail = getattr(exc, "detail", _diagnostic_text(type(exc).__name__))
                self._write_readiness_state(
                    status="WAITING", component=_readiness_component(code), code=code,
                    recoverable=_readiness_recoverable(code),
                )
                fields: dict[str, object] = {"retry_seconds": retry_seconds}
                if detail:
                    fields["detail"] = detail
                self._event("WAITING", str(code), **fields)
                self.stop.wait(retry_seconds)
            finally:
                if controller is not None:
                    try:
                        controller.close()
                    except Exception as exc:
                        if not self.stop.is_set():
                            self._event("WAITING", "PTT_CLEANUP_FAILED", detail=_diagnostic_text(type(exc).__name__))
                elif hardware is not None:
                    try:
                        hardware.close(suppress_errors=True)
                    except Exception:
                        pass
        return 0

    def _new_wake_monitor_led(self) -> GpiodWakeMonitoringLed:
        return GpiodWakeMonitoringLed.from_config(self.config)

    def wake_loop(self) -> int:
        if not self.config.extensions.wake_word.enabled:
            raise VoiceRuntimeError("WAKE_WORD_DISABLED")
        phrase = self.config.extensions.wake_word.phrase
        retry_seconds = 5
        while not self.stop.is_set():
            monitor_led: GpiodWakeMonitoringLed | None = None
            pipeline: WakeCapturePipeline | None = None
            try:
                # Privacy boundary: continuous standby capture is not declared
                # READY until the dedicated monitoring indicator line can be
                # acquired and initialized OFF.  Physical LED visibility remains
                # a Raspberry Pi acceptance gate.
                monitor_led = self._new_wake_monitor_led()
                monitor_led.open()
                monitor_metadata = monitor_led.metadata()
                if not self.wait_until_ready():
                    break
                monitor_led.set(True)
                matcher, pipeline = self._start_wake_standby(phrase)
                self._event(
                    "INFO",
                    "WAKE_MONITOR_LED_ACTIVE",
                    gpio=monitor_metadata["logical_bcm"],
                    chip=monitor_metadata["chip_path"],
                    line=monitor_metadata["line_offset"],
                    physical_acceptance_claimed=False,
                )
                reported_drops = 0
                while not self.stop.is_set():
                    notices = getattr(self, "notification_announcer", None)
                    announcement = notices.pending() if notices is not None else None
                    is_notice = announcement is not None
                    announcer = getattr(self, "transition_announcer", None)
                    if not announcement:
                        announcement = announcer.pending() if announcer is not None else None
                    if announcement:
                        self._discard_wake_pipeline(pipeline)
                        pipeline = None
                        monitor_led.set(False)
                        self._event("RUNNING", "ENVIRONMENT_TRANSITION_ANNOUNCEMENT")
                        self.speak(announcement)
                        if is_notice: notices.spoken()
                        if self.stop.wait(0.2):
                            break
                        monitor_led.set(True)
                        matcher, pipeline = self._start_wake_standby(phrase)
                        reported_drops = 0
                        continue

                    assert pipeline is not None
                    window = pipeline.next_window(timeout=0.25)
                    if window is None:
                        continue
                    recognition_started = time.monotonic()
                    streaming = isinstance(window, StreamingWakeWindow)
                    capture_mode = getattr(pipeline, "capture_mode", WAKE_CAPTURE_MODE)
                    if streaming:
                        self._discard_wake_pipeline(pipeline)
                        pipeline = None
                        monitor_led.set(False)
                        utterance_complete = window.utterance_complete
                        if not utterance_complete:
                            window.path.unlink(missing_ok=True)
                            self._event("INFO", "VOICE_UTTERANCE_LIMIT", action="discarded_not_executed")
                            if window.native_keyword:
                                self.speak("Please repeat a shorter command.")
                            monitor_led.set(True)
                            matcher, pipeline = self._start_wake_standby(phrase)
                            continue
                        if window.native_keyword and not window.command_activity:
                            window.path.unlink(missing_ok=True)
                            match = WakeMatch(phrase, phrase, "", (), "native-kws-v1")
                        else:
                            heard = self._transcribe_captured_audio(window.path)
                            # Native attention is not authority to execute unrelated
                            # speech. Full inline commands still carry the wake name.
                            match = _wake_match(heard, phrase)
                        self._event("INFO", "WAKE_STREAM_METRICS",
                            native_keyword=window.native_keyword,
                            utterance_ms=window.utterance_ms,
                            keyword_decode_max_ms=window.keyword_decode_max_ms,
                            transcription_ms=round((time.monotonic()-recognition_started)*1000),
                            fallback=not window.native_keyword)
                    else:
                        utterance_complete = complete_wake_utterance(window.path)
                        heard = self._transcribe_captured_audio(window.path)
                        match = matcher.observe(heard)
                        if pipeline.dropped_windows > reported_drops:
                            reported_drops = pipeline.dropped_windows
                            self._event("INFO", "WAKE_CAPTURE_WINDOWS_DROPPED",
                                count=reported_drops, reason="recognition_backlog_newest_wins")
                    recognition_ms = round((time.monotonic() - recognition_started) * 1000)
                    if match is None:
                        if streaming:
                            monitor_led.set(True)
                            matcher, pipeline = self._start_wake_standby(phrase)
                        continue

                    # Stop/cancel standby capture and its visible monitoring
                    # indicator before any assistant speech so self-speech
                    # cannot enter the wake queue.
                    dropped_at_detection = getattr(pipeline, "dropped_windows", 0)
                    self._discard_wake_pipeline(pipeline)
                    pipeline = None
                    monitor_led.set(False)
                    self._event(
                        "OK",
                        "WAKE_DETECTED",
                        alias=match.alias,
                        matcher=match.matcher_version,
                        capture_mode=capture_mode,
                        recognition_ms=recognition_ms,
                        dropped_windows=dropped_at_detection,
                    )
                    if not match.remainder:
                        self.speak_progress_cue("Yes?")
                    begin = getattr(self.brain, "begin_interaction", None)
                    if callable(begin): begin()
                    question = self._question_after_wake(match.remainder, utterance_complete=utterance_complete)
                    if not question:
                        self._event("INFO", "VOICE_NO_SPEECH")
                    else:
                        answer = self._answer_question(question)
                        self._event("RUNNING", "VOICE_SPEAKING")
                        self._deliver_answer(answer)
                        self._event("OK", "VOICE_TURN_COMPLETE")

                    if self.stop.wait(0.2):
                        break
                    monitor_led.set(True)
                    matcher, pipeline = self._start_wake_standby(phrase)
                    reported_drops = 0
                return 0
            except Exception as exc:
                if self.stop.is_set():
                    break
                self._clear_ready()
                code = str(getattr(exc, "code", "VOICE_RUNTIME_RECOVERY"))
                detail = getattr(exc, "detail", _diagnostic_text(type(exc).__name__))
                self._write_readiness_state(
                    status="WAITING", component=_readiness_component(code), code=code,
                    recoverable=_readiness_recoverable(code),
                )
                fields: dict[str, object] = {"retry_seconds": retry_seconds}
                if detail:
                    fields["detail"] = detail
                self._event("WAITING", str(code), **fields)
                self.stop.wait(retry_seconds)
            finally:
                self._discard_wake_pipeline(pipeline, suppress=True)
                if monitor_led is not None:
                    try:
                        monitor_led.close(suppress_errors=True)
                    except Exception:
                        pass
        return 0

    def close(self) -> None:
        self._clear_ready(clear_readiness=True)
        self.stop.set()
        detector = getattr(self, "_keyword_detector", None)
        if detector is not None:
            detector.close()
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
        if config.runtime.interaction_mode == "push_to_talk":
            return appliance.push_to_talk_loop()
        return appliance.wake_loop()
    finally:
        appliance.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
