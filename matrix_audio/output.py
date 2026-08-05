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

#: How much audio the sound card may hold, in milliseconds.
#:
#: Left to itself ALSA picked half a second, and since the mixer feeds
#: silence continuously, a new effect queued behind all of it - a game sound
#: arriving up to 500ms after the frame that caused it. This is the ceiling
#: on how late an effect can be, so it wants to be small; too small and the
#: feeder cannot keep up and the output crackles.
DEFAULT_BUFFER_MS = 120


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
    raw = _raw_output_devices() + _bluetooth_pcms()
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

    # `aplay -L` always offers a bare `bluealsa`, but it resolves to
    # 00:00:00:00:00:00 rather than to any speaker, so opening it can only
    # ever fail with "PCM not found". Only the daemon's own list is real.
    devices = [
        device
        for device in devices
        if device["kind"] != BLUETOOTH or _bluetooth_address(device["name"])
    ]

    devices.sort(key=lambda device: (ORDER.get(device["kind"], 9), device["label"]))
    return devices


def plug_device(device: str) -> str:
    """Wrap a device so ALSA converts our stream to whatever it wants.

    The mixer renders 22050Hz mono, which a sound card is free to refuse.
    HDMI happens to accept it; the bluealsa PCM does not, because A2DP is
    44100Hz stereo - so a Bluetooth speaker connected perfectly well and
    then played nothing. ALSA's `plug` app does that conversion.

    The braces form is deliberate. A bluealsa name is
    `bluealsa:DEV=...,PROFILE=a2dp`, and plain `plug:` + that would have
    ALSA read `PROFILE=a2dp` as an argument to plug rather than to
    bluealsa; naming the slave explicitly keeps it whole.
    """
    if not device or device.startswith("plug"):
        return device
    return 'plug:{SLAVE="' + device + '"}'


def _bluetooth_pcms() -> list[dict[str, Any]]:
    """Speakers the bluealsa daemon knows about.

    `aplay -L` only lists the bare `bluealsa` alias, which resolves to
    00:00:00:00:00:00 and fails with "PCM not found". The daemon is the only
    thing that knows which speakers are actually connected.
    """
    try:
        from matrix_audio import bluealsa

        return [dict(pcm) for pcm in bluealsa.pcms()]
    except Exception:
        return []


def resolve_device(device: str) -> str:
    """Turn a saved choice into a PCM that can be opened right now.

    A speaker's PCM name contains its address, so it changes with the
    hardware. Someone who picked the bare `bluealsa` alias - or picked a
    speaker that has since been swapped - gets whichever one is connected
    rather than the all-zeros address that alias means.
    """
    if not device.startswith("bluealsa"):
        return device
    try:
        from matrix_audio import bluealsa

        available = [pcm["name"] for pcm in bluealsa.pcms()]
    except Exception:
        return device
    if not available or device in available:
        return device
    # Prefer music over a headset's telephony profile.
    music = [name for name in available if "PROFILE=a2dp" in name]
    return (music or available)[0]


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

    def __init__(self, mixer: Mixer, device: str = "", buffer_ms: int = DEFAULT_BUFFER_MS) -> None:
        self.mixer = mixer
        self.device = device
        self.buffer_ms = max(30, int(buffer_ms))
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _command(self) -> list[str]:
        buffer_us = self.buffer_ms * 1000
        command = [
            "aplay",
            "-q",
            "-t",
            "raw",
            "-f",
            "S16_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            "1",
            "--buffer-time",
            str(buffer_us),
            # Four periods to a buffer: enough for the feeder to stay ahead
            # without adding latency of its own.
            "--period-time",
            str(max(5000, buffer_us // 4)),
        ]
        # Always name a device, so the default gets converted too. Leaving it
        # off sent 22050Hz mono straight at whatever `default` is, and HDMI
        # refuses that with "Unknown error 524".
        command += ["-D", plug_device(resolve_device(self.device or "default"))]
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
