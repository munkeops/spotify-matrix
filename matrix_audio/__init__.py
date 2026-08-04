"""Audio for the matrix: a small mixer, an ALSA output, and a chiptune synth.

The engine is what a game talks to. It owns a mixer and an output, so a plugin
just says ``self.audio.play("blip")`` and never learns whether a sound card
exists. When there is none, every call is a no-op.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from matrix_audio.mixer import MAX_VOICES, Mixer
from matrix_audio import bluealsa
from matrix_audio.output import AlsaOutput, NullOutput, aplay_available, list_output_devices
from matrix_audio.synth import SAMPLE_RATE, read_wav, write_wav


class AudioEngine:
    """A mixer plus an output, with a safe do-nothing mode."""

    def __init__(self, *, enabled: bool = True, device: str = "", volume: float = 0.8) -> None:
        self.mixer = Mixer(volume=volume)
        self.enabled = bool(enabled)
        self.device = device
        self._output: Any = NullOutput()

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        if not self.enabled:
            return
        self._output = AlsaOutput(self.mixer, self.device)
        self._output.start()

    def stop(self) -> None:
        self._output.stop()
        self._output = NullOutput()
        self.mixer.stop_all()

    @property
    def running(self) -> bool:
        return bool(getattr(self._output, "running", False))

    @property
    def error(self) -> str:
        return str(getattr(self._output, "error", "") or "")

    # --- use -------------------------------------------------------------

    def load_directory(self, directory: Path, prefix: str = "") -> list[str]:
        return self.mixer.load_directory(Path(directory), prefix)

    def play(self, name: str, volume: float = 1.0) -> bool:
        """Play a loaded effect. Never raises, so a game can call it freely."""
        if not self.enabled:
            return False
        return self.mixer.play(name, volume)

    def set_volume(self, volume: float) -> None:
        self.mixer.volume = max(0.0, min(1.0, float(volume)))

    def known(self) -> list[str]:
        return self.mixer.known()


class SilentAudio:
    """What a game gets when nothing has given it a real engine."""

    enabled = False
    running = False
    error = ""

    def play(self, name: str, volume: float = 1.0) -> bool:
        return False

    def known(self) -> list[str]:
        return []

    def load_directory(self, directory: Path, prefix: str = "") -> list[str]:
        return []


__all__ = [
    "bluealsa",
    "AudioEngine",
    "SilentAudio",
    "Mixer",
    "AlsaOutput",
    "NullOutput",
    "list_output_devices",
    "aplay_available",
    "read_wav",
    "write_wav",
    "SAMPLE_RATE",
    "MAX_VOICES",
]
