"""Software mixer for short sound effects.

Several blips can land in the same frame — a Pac-Man pellet while a ghost turns
blue — so effects are summed into one stream rather than fighting over the
device. Rendering is a pure function of the active voices, which is what makes
the audio engine testable without a sound card.
"""

from __future__ import annotations

import threading
from array import array
from dataclasses import dataclass, field
from pathlib import Path

from matrix_audio.synth import SAMPLE_RATE, read_wav

#: Beyond this, extra sounds are dropped rather than turning into mud.
MAX_VOICES = 8


@dataclass
class Voice:
    samples: array
    position: int = 0
    volume: float = 1.0

    @property
    def finished(self) -> bool:
        return self.position >= len(self.samples)


@dataclass
class Mixer:
    """Holds loaded effects and whatever is currently sounding."""

    volume: float = 0.8
    sounds: dict[str, array] = field(default_factory=dict)
    voices: list[Voice] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # --- library ---------------------------------------------------------

    def load(self, name: str, samples: array) -> None:
        with self._lock:
            self.sounds[name] = samples

    def load_directory(self, directory: Path, prefix: str = "") -> list[str]:
        """Load every WAV in a directory, named after the file stem."""
        loaded: list[str] = []
        if not directory.is_dir():
            return loaded
        for path in sorted(directory.glob("*.wav")):
            try:
                self.load(f"{prefix}{path.stem}", read_wav(path))
                loaded.append(f"{prefix}{path.stem}")
            except Exception:
                # A broken effect should cost you that sound, not the game.
                # wave raises its own error type, so catch broadly on purpose.
                continue
        return loaded

    def known(self) -> list[str]:
        with self._lock:
            return sorted(self.sounds)

    # --- playback --------------------------------------------------------

    def play(self, name: str, volume: float = 1.0) -> bool:
        """Start a sound. Returns False when it is unknown or the mixer is full."""
        with self._lock:
            samples = self.sounds.get(name)
            if samples is None:
                return False
            self.voices = [voice for voice in self.voices if not voice.finished]
            if len(self.voices) >= MAX_VOICES:
                return False
            self.voices.append(Voice(samples=samples, volume=max(0.0, min(1.0, volume))))
            return True

    def stop_all(self) -> None:
        with self._lock:
            self.voices = []

    @property
    def active(self) -> int:
        with self._lock:
            return sum(1 for voice in self.voices if not voice.finished)

    def render(self, frames: int) -> bytes:
        """Mix the next ``frames`` samples. Silence when nothing is playing."""
        if frames <= 0:
            return b""
        with self._lock:
            voices = [voice for voice in self.voices if not voice.finished]
            self.voices = voices
            master = max(0.0, min(1.0, self.volume))
            if not voices or master <= 0.0:
                # Advance nothing: silence costs one allocation.
                return bytes(frames * 2)

            out = array("h", bytes(frames * 2))
            for voice in voices:
                samples = voice.samples
                start = voice.position
                count = min(frames, len(samples) - start)
                for index in range(count):
                    total = out[index] + int(samples[start + index] * voice.volume * master)
                    out[index] = max(-32768, min(32767, total))
                voice.position += count
            return out.tobytes()


__all__ = ["Mixer", "Voice", "MAX_VOICES", "SAMPLE_RATE"]
