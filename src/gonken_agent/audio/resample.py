"""PCM16 mono integer decimation with a windowed-sinc anti-alias FIR.

Supports the configured 48kHz -> 16kHz path without an unpinned dependency.
Arbitrary ratios are rejected. On-Pi CPU/latency acceptance remains required.
"""
import math
import struct


def pcm16_mono(pcm, channels):
    if channels not in (1, 2) or len(pcm) % (2 * channels):
        raise ValueError('invalid PCM16 channel/frame layout')
    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
    if channels == 2:
        samples = tuple(round((samples[i] + samples[i + 1]) / 2) for i in range(0, len(samples), 2))
    return samples


def resample(pcm, source_rate, target_rate=16000, channels=1):
    if source_rate not in (16000, 32000, 48000) or target_rate != 16000:
        raise ValueError('supported paths: 16/32/48kHz to 16kHz')
    values = pcm16_mono(pcm, channels)
    factor = source_rate // target_rate
    if factor == 1:
        out = values
    else:
        half = 48
        cutoff = 0.45 / factor
        weights = []
        for n in range(-half, half + 1):
            sinc = 2 * cutoff if n == 0 else math.sin(2 * math.pi * cutoff * n) / (math.pi * n)
            weights.append(sinc * (0.54 + 0.46 * math.cos(math.pi * n / half)))
        total = sum(weights)
        weights = [w / total for w in weights]
        out = [max(-32768, min(32767, round(sum(values[j] * weights[j - i + half]
                for j in range(max(0, i - half), min(len(values), i + half + 1))))))
               for i in range(0, len(values), factor)]
    return struct.pack('<' + 'h' * len(out), *out)
