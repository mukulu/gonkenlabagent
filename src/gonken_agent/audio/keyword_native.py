"""Narrow ctypes adapter to Debian Trixie's libpocketsphinx.so.3 KWS ABI.

No Python extension, network, LM, transcript, microphone or GPIO owner is added.
The distro owns the acoustic model and library. Only configured phonetic wake
phrases are decoded. Keyword hits are attention cues, not actuation authority;
inline commands still require a wake-bearing full-utterance Whisper transcript.
"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tempfile


class KeywordError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class KeywordHit:
    start_sample: int
    end_sample: int


class NativeKeywordDetector:
    MODEL = Path('/usr/share/pocketsphinx/model/en-us/en-us')
    # Explicit phonetic alternatives, not renaming another assistant's model.
    PHONES = ('G AA N K EH N', 'G AO N K EH N', 'G AH N K EH N',
              'G OW N K EH N', 'G AA NG K AH N', 'G AO NG K AH N')

    def __init__(self, phrase: str, runtime_dir: Path, *, threshold: float = 1e-20):
        words = ' '.join(re.findall(r'[a-z]+', phrase.casefold()))
        if words not in {'gonken', 'gon ken', 'hey gonken', 'hey gon ken'}:
            raise KeywordError('WAKE_NATIVE_PHRASE_UNSUPPORTED')
        if not 1e-50 <= threshold <= 1e-5 or sys.byteorder != 'little':
            raise KeywordError('WAKE_NATIVE_POLICY_INVALID')
        self.decoder = self.config = None
        self.active = False
        self.position = self.base = 0
        try:
            self.ps = C.CDLL('libpocketsphinx.so.3')
            self.sb = C.CDLL('libsphinxbase.so.3')
        except OSError as exc:
            raise KeywordError('WAKE_NATIVE_LIBRARY_MISSING') from exc
        if not all((self.MODEL / name).is_file() for name in ('mdef', 'means', 'variances', 'sendump', 'feat.params')):
            raise KeywordError('WAKE_NATIVE_MODEL_MISSING')
        self._bind()
        try:
            with tempfile.TemporaryDirectory(prefix='wake-lexicon-', dir=runtime_dir) as temp:
                dictionary, keywords = Path(temp)/'dictionary', Path(temp)/'keywords'
                dictionary.write_text('hey HH EY\n' + ''.join(f'gk{i} {ph}\n' for i, ph in enumerate(self.PHONES)), encoding='ascii')
                prefix = 'hey ' if words.startswith('hey ') else ''
                keywords.write_text(''.join(f'{prefix}gk{i}\n' for i in range(len(self.PHONES))), encoding='ascii')
                argv = ['gonken-kws', '-hmm', str(self.MODEL), '-dict', str(dictionary),
                        '-samprate', '16000', '-kws_threshold', str(threshold), '-kws_delay', '5',
                        '-remove_silence', 'no', '-logfn', '/dev/null']
                # cmd_ln_parse_r borrows strings: retain the argv for config lifetime.
                self.argv = (C.c_char_p * len(argv))(*(v.encode('utf-8') for v in argv))
                self.config = self.sb.cmd_ln_parse_r(None, self.ps.ps_args(), len(argv), self.argv, 1)
                if not self.config:
                    raise KeywordError('WAKE_NATIVE_CONFIG_FAILED')
                self.decoder = self.ps.ps_init(self.config)
                if not self.decoder:
                    raise KeywordError('WAKE_NATIVE_MODEL_INVALID')
                if self.ps.ps_set_kws(self.decoder, b'gonken', str(keywords).encode()) < 0 or self.ps.ps_set_search(self.decoder, b'gonken') < 0:
                    raise KeywordError('WAKE_NATIVE_SEARCH_FAILED')
            self.reset()
        except BaseException:
            self.close()
            raise

    def _bind(self):
        v, i, s, p = C.c_void_p, C.c_int, C.c_char_p, C.POINTER
        signatures = {
            'ps_args': (v, []), 'ps_init': (v, [v]), 'ps_free': (i, [v]),
            'ps_set_kws': (i, [v, s, s]), 'ps_set_search': (i, [v, s]),
            'ps_start_stream': (i, [v]), 'ps_start_utt': (i, [v]), 'ps_end_utt': (i, [v]),
            'ps_process_raw': (i, [v, p(C.c_int16), C.c_size_t, i, i]),
            'ps_get_hyp': (s, [v, p(i)]), 'ps_seg_iter': (v, [v]),
            'ps_seg_next': (v, [v]), 'ps_seg_free': (None, [v]),
            'ps_seg_frames': (None, [v, p(i), p(i)]),
        }
        try:
            for name, (result, args) in signatures.items():
                fn = getattr(self.ps, name); fn.restype = result; fn.argtypes = args
            self.sb.cmd_ln_parse_r.restype = v
            self.sb.cmd_ln_parse_r.argtypes = [v, v, i, p(s), i]
            self.sb.cmd_ln_free_r.restype = i; self.sb.cmd_ln_free_r.argtypes = [v]
        except AttributeError as exc:
            raise KeywordError('WAKE_NATIVE_ABI_UNSUPPORTED') from exc

    def reset(self, *, base_sample: int = 0):
        if not self.decoder:
            raise KeywordError('WAKE_NATIVE_CLOSED')
        if self.active:
            self.ps.ps_end_utt(self.decoder)
            self.active = False
        if self.ps.ps_start_stream(self.decoder) < 0 or self.ps.ps_start_utt(self.decoder) < 0:
            raise KeywordError('WAKE_NATIVE_RESET_FAILED')
        self.active = True
        self.base = self.position = base_sample

    def feed(self, pcm: bytes) -> KeywordHit | None:
        if not self.active or not self.decoder:
            raise KeywordError('WAKE_NATIVE_CLOSED')
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2 or len(pcm) > 2560:
            raise ValueError('invalid keyword PCM frame')
        samples = (C.c_int16 * (len(pcm)//2)).from_buffer_copy(pcm)
        if self.ps.ps_process_raw(self.decoder, samples, len(samples), 0, 0) < 0:
            raise KeywordError('WAKE_NATIVE_DECODE_FAILED')
        self.position += len(samples)
        if not self.ps.ps_get_hyp(self.decoder, None):
            return None
        seg = self.ps.ps_seg_iter(self.decoder)
        hit = None
        # Iterate to completion (next frees the iterator). Bound malformed ABI output.
        for _ in range(32):
            if not seg:
                break
            start, end = C.c_int(), C.c_int()
            self.ps.ps_seg_frames(seg, C.byref(start), C.byref(end))
            lo, hi = self.base + start.value * 160, self.base + (end.value + 1) * 160
            # Short fragments are not accepted as the multi-phoneme name.
            if self.base <= lo < hi <= self.position and 5600 <= hi-lo <= 32000:
                hit = KeywordHit(lo, hi)
            seg = self.ps.ps_seg_next(seg)
        if seg:
            self.ps.ps_seg_free(seg)
            raise KeywordError('WAKE_NATIVE_SEGMENT_BOUND')
        return hit

    def close(self):
        if self.decoder:
            if self.active:
                self.ps.ps_end_utt(self.decoder)
            self.ps.ps_free(self.decoder)
            self.decoder = None
        self.active = False
        if self.config:
            self.sb.cmd_ln_free_r(self.config)
            self.config = None
