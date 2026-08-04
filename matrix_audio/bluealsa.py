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

_process: subprocess.Popen | None = None


def installed() -> bool:
    return shutil.which("bluealsa") is not None


def running() -> bool:
    """Is a bluealsa daemon already up, ours or the host's?

    Reading /proc avoids depending on pgrep, which the image does not have.
    """
    if _process is not None and _process.poll() is None:
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
                if handle.read().strip() == "bluealsa":
                    return True
        except OSError:
            continue
    return False


def start() -> tuple[bool, str]:
    """Start the bridge if it is not already up.

    Returns whether a bridge is running and something explaining why not.
    Never raises: no sound is a degraded panel, not a failed boot.
    """
    global _process

    if not installed():
        return False, (
            "bluealsa is not installed, so Bluetooth speakers cannot appear as "
            "audio outputs. Rebuild the container image to add it."
        )
    if running():
        return True, ""

    binary = shutil.which("bluealsa")
    command = [binary]
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
        return False, f"Could not start bluealsa: {error}"

    # It either registers with BlueZ quickly or it fails outright, usually
    # because the container cannot reach the system D-Bus.
    time.sleep(0.6)
    if _process.poll() is not None:
        detail = ""
        if _process.stderr is not None:
            detail = _process.stderr.read().decode("utf-8", "ignore").strip().splitlines()[-1:] or [""]
            detail = detail[0]
        _process = None
        return False, (
            f"bluealsa exited straight away{': ' + detail if detail else ''}. "
            "It needs the host D-Bus socket, which docker-compose maps in as "
            "/var/run/dbus."
        )
    return True, ""


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


__all__ = ["installed", "running", "start", "stop", "PROFILES"]
