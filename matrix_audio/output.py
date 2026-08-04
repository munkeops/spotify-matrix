"""Getting mixed audio out of the Pi.

One long-lived ``aplay`` reading raw PCM from stdin, fed by a thread. That
avoids spawning a process per blip - which is both slow and unable to overlap -
without pulling in a compiled audio binding.

Everything degrades to silence rather than raising: a matrix with no sound card
should still play its games.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from typing import Any

from loguru import logger

from matrix_audio.mixer import Mixer
from matrix_audio.synth import SAMPLE_RATE

#: How much audio to hand the device at a time. Small enough that a blip lands
#: promptly, large enough that the feeder thread is not frantic.
BUFFER_FRAMES = 512


def aplay_available() -> bool:
    return shutil.which("aplay") is not None


def list_output_devices() -> list[dict[str, Any]]:
    """ALSA playback devices, as ``aplay -L`` reports them."""
    binary = shutil.which("aplay")
    if binary is None:
        return []
    try:
        result = subprocess.run([binary, "-L"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []

    devices: list[dict[str, Any]] = []
    name: str | None = None
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            name = line.strip()
            # null is a real ALSA device but never what anyone wants.
            if name and not name.startswith("null"):
                devices.append({"name": name, "description": ""})
            else:
                name = None
        elif devices and name:
            devices[-1]["description"] = (devices[-1]["description"] + " " + line.strip()).strip()
    return devices


class NullOutput:
    """Used when there is no sound card, or audio is switched off."""

    running = False

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    @property
    def error(self) -> str:
        return ""


class AlsaOutput:
    """Feeds a mixer's output into a persistent ``aplay`` process."""

    def __init__(self, mixer: Mixer, device: str = "") -> None:
        self.mixer = mixer
        self.device = device
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _command(self) -> list[str]:
        command = ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1"]
        if self.device:
            command += ["-D", self.device]
        return command + ["-"]

    def start(self) -> None:
        if self.running:
            return
        if not aplay_available():
            self.error = "aplay is not installed, so there is no way to reach the sound card."
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio-out", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._close()

    def _close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.close()
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass

    def _run(self) -> None:
        try:
            self._process = subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            self.error = f"Could not start audio output: {exc}"
            logger.warning("[audio] {}", self.error)
            return

        self.error = ""
        interval = BUFFER_FRAMES / SAMPLE_RATE
        try:
            while not self._stop.is_set():
                process = self._process
                if process is None or process.poll() is not None:
                    # aplay died, usually because the device disappeared.
                    stderr = ""
                    if process is not None and process.stderr:
                        stderr = (process.stderr.read() or b"").decode("utf-8", "replace").strip()
                    self.error = stderr or "Audio output stopped unexpectedly."
                    logger.warning("[audio] {}", self.error)
                    return
                chunk = self.mixer.render(BUFFER_FRAMES)
                try:
                    process.stdin.write(chunk)  # type: ignore[union-attr]
                    process.stdin.flush()  # type: ignore[union-attr]
                except (BrokenPipeError, OSError) as exc:
                    self.error = f"Audio output closed: {exc}"
                    return
                # write() blocks once ALSA's buffer is full, which paces us, but
                # sleep a little anyway so a huge buffer does not spin the CPU.
                self._stop.wait(interval / 2)
        finally:
            self._close()


__all__ = ["AlsaOutput", "NullOutput", "list_output_devices", "aplay_available", "BUFFER_FRAMES"]
