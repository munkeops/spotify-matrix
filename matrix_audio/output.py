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


# `aplay -L` lists every way of reaching every card: the card itself, the
# rate-converting wrapper, the mixing wrapper, and an alias or two. They are
# not four speakers, and offering them as four choices is how the panel ended
# up unreadable. These are the plumbing.
#:
#: Matched against the part before the colon, because several also appear
#: bare: `aplay -L` lists both `sysdefault` and `sysdefault:CARD=x`, and only
#: the second was being filtered.
PLUMBING = frozenset(
    {"plughw", "sysdefault", "dmix", "dsnoop", "front", "iec958", "spdif", "hdmi", "surround"}
)


def _is_plumbing(name: str) -> bool:
    base = name.split(":", 1)[0]
    return base in PLUMBING or base.startswith("surround")


def _bluetooth_address(name: str) -> str:
    """The speaker's address out of a bluealsa PCM name, if it names one."""
    for part in name.split(","):
        key, _, value = part.partition("=")
        if key.strip().upper().endswith("DEV"):
            return value.strip()
    return ""

#: Rough kind for each device, used to sort and to label.
BLUETOOTH, HEADPHONES, HDMI, USB, DEFAULT, OTHER = (
    "bluetooth",
    "headphones",
    "hdmi",
    "usb",
    "default",
    "other",
)

ORDER = {BLUETOOTH: 0, HEADPHONES: 1, USB: 2, HDMI: 3, DEFAULT: 4, OTHER: 5}


def _classify(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if name.startswith("bluealsa") or "bluetooth" in text:
        return BLUETOOTH
    if name in ("default", "pulse", "pipewire"):
        return DEFAULT
    if "hdmi" in text:
        return HDMI
    if "usb" in text:
        return USB
    if "headphone" in text or "headset" in text or "analog" in text or "3.5" in text:
        return HEADPHONES
    return OTHER


def _label(name: str, description: str, kind: str) -> str:
    """A name someone would recognise, rather than an ALSA PCM string."""
    if kind == DEFAULT:
        return "System default"
    first = description.splitlines()[0].strip() if description else ""
    if kind == BLUETOOTH:
        # bluealsa:DEV=F4:6A:D7:..,PROFILE=a2dp -> the speaker's own name if
        # the description carries it, otherwise the address.
        # bluealsa describes a speaker as "JBL Flip 5, trusted, A2DP"; only
        # the first part is its name.
        speaker = first.split(",", 1)[0].strip()
        if speaker and not speaker.lower().startswith("bluetooth"):
            return speaker
        address = _bluetooth_address(name)
        return f"Bluetooth speaker {address}".strip() if address else "Bluetooth speaker"
    if kind == HDMI:
        # vc4hdmi0 / vc4hdmi1 are the Pi's two HDMI ports.
        for port in ("hdmi0", "hdmi1"):
            if port in name.lower():
                return f"HDMI {int(port[-1]) + 1}"
        return "HDMI"
    return first or name


def list_output_devices(include_plumbing: bool = False) -> list[dict[str, Any]]:
    """Playback devices, named the way a person would name them.

    ``aplay -L`` is the source, but its output is deduplicated by card and
    given a readable label. Pass ``include_plumbing`` to get the raw list
    back for the cases where someone really does want ``dmix``.
    """
    raw = _raw_output_devices()
    if not raw:
        return []

    devices: list[dict[str, Any]] = []
    seen_cards: set[str] = set()
    for entry in raw:
        name = entry["name"]
        description = entry["description"]
        plumbing = _is_plumbing(name)
        if plumbing and not include_plumbing:
            continue

        kind = _classify(name, description)
        # One entry per card: `hw:CARD=x` and `default:CARD=x` are one speaker.
        if kind == BLUETOOTH:
            # bluealsa lists a bare alias as well as one PCM per speaker.
            card = _bluetooth_address(name) or "any"
        elif "CARD=" in name:
            card = name.split("CARD=", 1)[1].split(",")[0]
        else:
            card = name
        key = f"{kind}:{card}"
        if not plumbing and key in seen_cards:
            continue
        seen_cards.add(key)

        devices.append(
            {
                "name": name,
                "description": description,
                "label": _label(name, description, kind),
                "kind": kind,
                "plumbing": plumbing,
            }
        )

    # The bare `bluealsa` alias means "whichever speaker"; once a real one is
    # listed it is a confusing duplicate of it.
    named = {
        device["name"]
        for device in devices
        if device["kind"] == BLUETOOTH and _bluetooth_address(device["name"])
    }
    if named:
        devices = [
            device
            for device in devices
            if device["kind"] != BLUETOOTH or _bluetooth_address(device["name"])
        ]

    devices.sort(key=lambda device: (ORDER.get(device["kind"], 9), device["label"]))
    return devices


def _raw_output_devices() -> list[dict[str, Any]]:
    """ALSA playback devices, exactly as ``aplay -L`` reports them."""
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
            devices[-1]["description"] = (devices[-1]["description"] + "\n" + line.strip()).strip()
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
