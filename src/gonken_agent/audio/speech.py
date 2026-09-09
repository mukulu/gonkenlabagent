"""Local speech adapters; models/executables must pass M3.5 before activation."""
import re
import tempfile
import wave
from contextlib import contextmanager
from pathlib import Path
from .process import run, ProcessFailure


def speech_text(text):
    if not isinstance(text, str) or len(text) > 8192:
        raise ValueError('speech text exceeds bound')
    text = re.sub(r'```.*?```', ' ', text, flags=re.S)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'[`*_#<>]', '', text)
    text = ''.join(c for c in text if c.isprintable() or c.isspace())
    return ' '.join(text.split())


def validate_wav(path, max_seconds=60):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 44 < path.stat().st_size <= 12_000_000:
        raise ProcessFailure('INVALID_WAV')
    try:
        with wave.open(str(path), 'rb') as stream:
            if stream.getsampwidth() != 2 or stream.getnchannels() != 1 or stream.getcomptype() != 'NONE':
                raise ProcessFailure('INVALID_WAV')
            rate, frames = stream.getframerate(), stream.getnframes()
            if not 8000 <= rate <= 48000 or not 0 < frames <= rate * max_seconds:
                raise ProcessFailure('INVALID_WAV')
            if len(stream.readframes(frames)) != frames * 2:
                raise ProcessFailure('TRUNCATED_WAV')
            return {'rate': rate, 'frames': frames}
    except (wave.Error, EOFError) as exc:
        raise ProcessFailure('INVALID_WAV') from exc


class Whisper:
    def __init__(self, binary, model, runtime_dir, threads=4):
        self.binary, self.model, self.runtime_dir = Path(binary), Path(model), Path(runtime_dir)
        self.threads = threads

    def transcribe(self, audio, cancel):
        metadata = validate_wav(audio)
        if metadata['rate'] != 16000 or not self.model.is_file():
            raise ProcessFailure('STT_INPUT_OR_MODEL_INVALID')
        with tempfile.TemporaryDirectory(prefix='stt-', dir=self.runtime_dir) as folder:
            prefix = Path(folder) / 'result'
            run([str(self.binary), '-m', str(self.model), '-f', str(audio), '-t', str(self.threads),
                 '-otxt', '-of', str(prefix), '-nt'], cancel=cancel, timeout=120)
            result = prefix.with_suffix('.txt')
            if result.is_symlink() or not result.is_file() or result.stat().st_size > 16384:
                raise ProcessFailure('STT_OUTPUT_INVALID')
            text = result.read_text(encoding='utf-8').strip()
            if not text or len(text) > 4096:
                raise ProcessFailure('STT_OUTPUT_INVALID')
            return text


class Piper:
    def __init__(self, binary, voice, runtime_dir):
        self.binary, self.voice, self.runtime_dir = Path(binary), Path(voice), Path(runtime_dir)

    @contextmanager
    def synthesize(self, text, cancel):
        normalized = speech_text(text)
        if not normalized or not self.voice.is_file() or not Path(str(self.voice) + '.json').is_file():
            raise ProcessFailure('TTS_INPUT_OR_VOICE_INVALID')
        with tempfile.TemporaryDirectory(prefix='tts-', dir=self.runtime_dir) as folder:
            wav = Path(folder) / 'speech.wav'
            run([str(self.binary), '--model', str(self.voice), '--output_file', str(wav)],
                input_bytes=normalized.encode(), cancel=cancel, timeout=60)
            validate_wav(wav)
            yield wav
