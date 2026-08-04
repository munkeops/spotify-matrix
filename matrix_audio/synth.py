"""A tiny chiptune synth, used to generate the arcade's sound effects.

Effects are generated rather than shipped as opaque files, so a sound can be
retuned by editing a line instead of finding new audio, and every game's blips
sit in the same sonic world. Pure standard library: no numpy, no assets.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from array import array
from pathlib import Path

SAMPLE_RATE = 22050
AMPLITUDE = 0.35


def _envelope(index: int, total: int, attack: float, release: float) -> float:
    """A simple attack/release shape, which is most of what makes a blip a blip."""
    if total <= 1:
        return 0.0
    position = index / (total - 1)
    if position < attack and attack > 0:
        return position / attack
    if position > 1.0 - release and release > 0:
        return max(0.0, (1.0 - position) / release)
    return 1.0


def tone(
    frequency: float,
    seconds: float,
    *,
    end_frequency: float | None = None,
    wave_shape: str = "square",
    volume: float = 1.0,
    attack: float = 0.02,
    release: float = 0.25,
    duty: float = 0.5,
) -> array:
    """One note, optionally sweeping from ``frequency`` to ``end_frequency``."""
    total = max(1, int(SAMPLE_RATE * seconds))
    samples = array("h", bytes(total * 2))
    phase = 0.0
    for index in range(total):
        blend = index / max(1, total - 1)
        current = frequency + (end_frequency - frequency) * blend if end_frequency is not None else frequency
        phase += current / SAMPLE_RATE
        cycle = phase % 1.0

        if wave_shape == "square":
            value = 1.0 if cycle < duty else -1.0
        elif wave_shape == "triangle":
            value = 4.0 * abs(cycle - 0.5) - 1.0
        elif wave_shape == "saw":
            value = 2.0 * cycle - 1.0
        elif wave_shape == "noise":
            value = random.uniform(-1.0, 1.0)
        else:
            value = math.sin(2.0 * math.pi * cycle)

        shaped = value * _envelope(index, total, attack, release) * volume * AMPLITUDE
        samples[index] = int(max(-1.0, min(1.0, shaped)) * 32767)
    return samples


def silence(seconds: float) -> array:
    return array("h", bytes(max(0, int(SAMPLE_RATE * seconds)) * 2))


def sequence(*parts: array) -> array:
    """Play parts one after another."""
    out = array("h")
    for part in parts:
        out.extend(part)
    return out


def layer(*parts: array) -> array:
    """Play parts at the same time, summed and clipped."""
    if not parts:
        return array("h")
    length = max(len(part) for part in parts)
    out = array("h", bytes(length * 2))
    for part in parts:
        for index, value in enumerate(part):
            total = out[index] + value
            out[index] = max(-32768, min(32767, total))
    return out


def write_wav(path: str | Path, samples: array) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(samples.tobytes())


def read_wav(path: str | Path) -> array:
    """Load a mono 16-bit WAV, resampling crudely if the rate differs."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())

    if width != 2:
        raise ValueError(f"{path}: only 16-bit audio is supported")

    samples = array("h")
    samples.frombytes(raw)
    if channels > 1:
        # Average the channels down to mono.
        mono = array("h", bytes((len(samples) // channels) * 2))
        for index in range(len(mono)):
            chunk = samples[index * channels : (index + 1) * channels]
            mono[index] = int(sum(chunk) / len(chunk)) if chunk else 0
        samples = mono

    if rate != SAMPLE_RATE and rate > 0:
        ratio = SAMPLE_RATE / rate
        resampled = array("h", bytes(int(len(samples) * ratio) * 2))
        for index in range(len(resampled)):
            source = int(index / ratio)
            resampled[index] = samples[source] if source < len(samples) else 0
        samples = resampled
    return samples


__all__ = [
    "SAMPLE_RATE",
    "tone",
    "silence",
    "sequence",
    "layer",
    "write_wav",
    "read_wav",
]
