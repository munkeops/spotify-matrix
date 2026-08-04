"""The bridge that lets ALSA reach a Bluetooth speaker.

BlueZ can hold an A2DP connection to a speaker, but ALSA knows nothing about
it, so ``aplay -L`` never lists it and the panel has nothing to offer. The
``bluealsa`` daemon is what joins the two: it registers with BlueZ and adds a
``bluealsa`` PCM that plays to whichever device you name.

The Pi is the *source* here - it sends audio to the speaker - which is why
the daemon runs with ``a2dp-source`` rather than the sink profile people
usually reach for first.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

#: The profile that makes the Pi play *to* a speaker.
PROFILES = ("a2dp-source",)

#: Debian named the daemon `bluealsa` up to 3.x and `bluealsad` from 4.x.
BINARIES = ("bluealsad", "bluealsa")

_process: subprocess.Popen | None = None
#: Why the last start attempt failed, so the panel can say rather than guess.
_last_error = ""


def binary() -> str:
    for name in BINARIES:
        found = shutil.which(name)
        if found:
            return found
    return ""


def installed() -> bool:
    return bool(binary())


def running() -> bool:
    """Is a bluealsa daemon up and answering, wherever it lives?

    Asking the daemon is the only reliable test. The recommended setup runs
    it on the Pi rather than in here, and a container cannot see the host's
    processes, so scanning /proc reported "not running" for a daemon that
    was working perfectly well.
    """
    if _process is not None and _process.poll() is None:
        return True
    if _ask_daemon() is not None:
        return True
    try:
        entries = os.listdir("/proc")
    except OSError:
        return False
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/comm", encoding="utf-8", errors="ignore") as handle:
                if handle.read().strip() in BINARIES:
                    return True
        except OSError:
            continue
    return False


def _ask_daemon(timeout: float = 4.0) -> str | None:
    """`bluealsa-aplay -L` output, or None if no daemon answered."""
    binary = shutil.which("bluealsa-aplay")
    if binary is None:
        return None
    try:
        result = subprocess.run([binary, "-L"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    # It exits non-zero when it cannot reach the service; an empty list from a
    # live daemon just means no speaker is connected, which is still running.
    return result.stdout or "" if result.returncode == 0 else None


def pcms() -> list[dict[str, str]]:
    """Connected speakers, as PCM names ALSA can actually open.

    The bare `bluealsa` PCM resolves to 00:00:00:00:00:00, which is not a
    speaker and fails with "PCM not found". These are the real ones.
    """
    listing = _ask_daemon()
    if not listing:
        return []

    found: list[dict[str, str]] = []
    name = ""
    for line in listing.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            name = line.strip()
            if name.startswith("bluealsa:"):
                found.append({"name": name, "description": ""})
            else:
                name = ""
        elif found and name:
            found[-1]["description"] = (found[-1]["description"] + chr(10) + line.strip()).strip()
    # Playback only: a headset also publishes a capture PCM.
    return [pcm for pcm in found if "SOURCE" not in pcm["name"].upper()]


#: What the host needs, when the bus refuses to let the container own the name.
DBUS_ADVICE = (
    "The bluealsa daemon could not claim the name org.bluealsa on the system "
    "bus. The policy allowing that ships inside this container, but the bus "
    "enforcing it runs on the Pi, so it never sees it. Install the bridge on "
    "the Pi itself instead: sudo apt install bluez-alsa-utils && sudo "
    "systemctl enable --now bluealsa"
)


#: The daemon is up but no speaker has handed it an audio transport.
NO_PCM_ADVICE = (
    "The bluealsa bridge is running but no speaker has registered a playback "
    "PCM with it. BlueZ gives the audio connection to whatever was listening "
    "when the speaker connected, so a speaker that was already connected "
    "before the bridge started is not routed through it. Disconnect and "
    "reconnect the speaker - the Bluetooth panel can do both - and it will "
    "appear as an output."
)


def status() -> dict[str, object]:
    """Enough for the panel to say what is wrong, not just that it is."""
    alive = running()
    return {
        "installed": installed(),
        "running": alive,
        "error": _last_error,
        "binary": binary(),
        # How many speakers have actually handed it a playback transport.
        "speakers": len(pcms()) if alive else 0,
    }


def start() -> tuple[bool, str]:
    """Start the bridge if it is not already up.

    Returns whether a bridge is running and something explaining why not.
    Never raises: no sound is a degraded panel, not a failed boot.
    """
    global _process, _last_error

    _last_error = ""
    if running():
        return True, ""
    if not installed():
        _last_error = (
            "bluealsa is not installed, so Bluetooth speakers cannot appear as "
            "audio outputs. Rebuild the container image to add it."
        )
        return False, _last_error
    if running():
        return True, ""

    command = [binary()]
    for profile in PROFILES:
        command += ["-p", profile]
    try:
        _process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        _last_error = f"Could not start bluealsa: {error}"
        return False, _last_error

    # It either registers with BlueZ quickly or it fails outright, usually
    # because the container cannot reach the system D-Bus.
    time.sleep(0.8)
    if _process.poll() is None:
        return True, ""

    detail = ""
    if _process.stderr is not None:
        lines = _process.stderr.read().decode("utf-8", "ignore").strip().splitlines()
        detail = lines[-1] if lines else ""
    _process = None

    # Being refused the name is the one failure with a specific cure, and it
    # is the one that happens, so name it rather than echoing D-Bus at people.
    refused = "name" in detail.lower() and ("own" in detail.lower() or "request" in detail.lower())
    if refused or "org.bluealsa" in detail:
        _last_error = DBUS_ADVICE
    else:
        _last_error = (
            f"bluealsa exited straight away{': ' + detail if detail else ''}. "
            "It needs the host D-Bus socket, which docker-compose maps in as "
            "/var/run/dbus."
        )
    return False, _last_error


def stop() -> None:
    global _process

    if _process is None:
        return
    process, _process = _process, None
    try:
        process.terminate()
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


__all__ = [
    "installed",
    "running",
    "start",
    "stop",
    "status",
    "binary",
    "pcms",
    "PROFILES",
    "BINARIES",
    "DBUS_ADVICE",
]
