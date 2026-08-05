"""Sound settings, and a way to hear whether any of it works.

Game effects are played by the runtime process, because they have to line up
with a frame. This service owns the settings and can play a test sound of its
own, so you can confirm the sound card works before starting a game.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from matrix_audio import AudioEngine, aplay_available, bluealsa, list_output_devices
from matrix_audio.output import BLUETOOTH


#: How long a test engine may hold the sound card after playing.
#:
#: It has to outlast the effect, and it has to end. Holding aplay open
#: indefinitely means the runtime cannot open the device when a game starts,
#: so one press of Test left every game silent until the API restarted.
TEST_RELEASE_SECONDS = 3.0


class AudioService:
    def __init__(self) -> None:
        self._test_engine: AudioEngine | None = None
        self._release: threading.Timer | None = None

    def settings(self) -> Any:
        from src.domain.services.config_service import config_service

        return config_service.get_config().audio

    def devices(self) -> list[dict[str, Any]]:
        """Outputs that could actually play something.

        The bluealsa PCM is listed by ALSA whenever the app is installed,
        whether or not the daemon behind it is up. Offering it while the
        daemon is down is offering a choice that can only fail, which is
        exactly what it did.
        """
        devices = list_output_devices()
        if bluealsa.running():
            return devices
        return [device for device in devices if device["kind"] != BLUETOOTH]

    def _test_spec(self):
        """The game whose effects the panel offers, and the test plays.

        These must be the same game. They were not, so picking a sound the
        active game ships - flappy's "flap", say - asked a different game's
        directory for it and came back "No sound called flap."
        """
        from src.domain.services.game_service import game_service

        active = game_service.active_game_id()
        spec = game_service.spec(active) if active else None
        if spec is not None and spec.sounds_dir.is_dir():
            return spec
        for candidate in game_service.specs().values():
            if candidate.sounds_dir.is_dir():
                return candidate
        return None

    def sounds(self) -> list[str]:
        """Effects the active game ships, so the panel can offer a test."""
        spec = self._test_spec()
        if spec is None:
            return []
        directory: Path = spec.sounds_dir
        return sorted(path.stem for path in directory.glob("*.wav")) if directory.is_dir() else []

    def state(self) -> dict[str, Any]:
        settings = self.settings()
        devices = self.devices()
        return {
            "enabled": bool(settings.enabled),
            "available": aplay_available(),
            "device": settings.device,
            "volume": int(settings.volume),
            "devices": devices,
            "sounds": self.sounds(),
            "advice": self._advice(devices),
            "bridge": bluealsa.status(),
        }

    def _bluetooth_audio(self) -> list[dict[str, Any]]:
        """Connected Bluetooth devices that are speakers or headphones."""
        from src.domain.services.bluetooth_service import bluetooth_service

        try:
            devices = bluetooth_service.list_devices()
        except Exception:  # the adapter may be missing entirely
            return []
        return [
            device
            for device in devices
            if device.get("connected") and device.get("role") == "audio"
        ]

    def _advice(self, devices: list[dict[str, Any]]) -> str:
        if not aplay_available():
            return (
                "No ALSA tools in the container, so nothing can reach the sound card. "
                "Rebuild the image to install them."
            )
        if not devices:
            return (
                "No audio output found. Check the Pi has one with 'aplay -l', and that "
                "/dev/snd is mapped into the container."
            )
        speakers = self._bluetooth_audio()
        if speakers and not any(device["kind"] == BLUETOOTH for device in devices):
            names = ", ".join(device.get("name") or device.get("mac", "?") for device in speakers)
            if not bluealsa.installed():
                return (
                    f"{names} is connected over Bluetooth but is not an audio output yet. "
                    "Bluetooth audio reaches ALSA through bluealsa, which this image now "
                    "installs - rebuild the container and it will appear in this list."
                )
            if not bluealsa.running():
                return f"{names} is connected, but the bluealsa bridge is not running. {bluealsa.status()['error'] or bluealsa.DBUS_ADVICE}"
            return f"{names} is connected, but not through the bridge. {bluealsa.why_no_speaker()}"
        if not self.settings().enabled:
            return "Turn on game sound to hear effects. Use Test to check the output first."
        wireless = sum(1 for device in devices if device["kind"] == BLUETOOTH)
        if wireless:
            return f"Ready. {wireless} Bluetooth speaker(s) and {len(devices) - wireless} wired output(s)."
        return f"Ready, {len(devices)} output(s) available. Test plays a sound straight away."

    def play_test(self, sound: str = "start") -> dict[str, Any]:
        """Play one effect right now, from this process."""
        from src.domain.services.game_service import game_service

        settings = self.settings()
        specs = list(game_service.specs().values())
        if not specs:
            return {"ok": False, "message": "No games installed, so there are no sounds to play."}

        blocked = self._unusable(settings.device)
        if blocked:
            return {"ok": False, "message": blocked}

        engine = AudioEngine(enabled=True, device=settings.device, volume=int(settings.volume) / 100.0)
        spec = self._test_spec()
        if spec is not None:
            engine.load_directory(spec.sounds_dir)
        engine.start()
        played = engine.play(sound)
        # aplay only fails once it has tried to open the device, which is a
        # moment after the thread starts. Without this wait the panel says
        # "Playing" for a device that rejected the format outright.
        deadline = time.monotonic() + 0.6
        while time.monotonic() < deadline and not engine.error:
            time.sleep(0.05)
        # Replace whatever the last test left running, and make sure this one
        # lets go of the sound card too.
        self._stop_previous()
        self._test_engine = engine
        self._release_later(engine)
        if not played:
            available = ", ".join(self.sounds()[:6]) or "none"
            return {
                "ok": False,
                "message": f"No sound called {sound}. This game has: {available}.",
            }
        if engine.error:
            where = settings.device or "the default output"
            return {
                "ok": False,
                "message": f"Could not play through {where}. {self._explain(engine.error)}",
                "error": engine.error,
            }
        return {"ok": True, "message": f"Playing {sound}.", "error": ""}

    def _unusable(self, device: str) -> str:
        """Why this output cannot play, when we already know.

        Handing it to aplay anyway answers with the ALSA error for the
        all-zeros address, which says nothing about what to do next.
        """
        if not device.startswith("bluealsa"):
            return ""
        if not bluealsa.running():
            return bluealsa.status()["error"] or bluealsa.DBUS_ADVICE  # type: ignore[return-value]
        if not bluealsa.pcms():
            return bluealsa.why_no_speaker()
        return ""

    @staticmethod
    def _explain(error: str) -> str:
        """Say what an ALSA failure means, rather than quoting it.

        aplay reports a page of hardware parameters and a D: trace, and the
        one useful word is buried in it.
        """
        lowered = error.lower()
        if "busy" in lowered:
            return (
                "Something else is using it. A Bluetooth speaker only takes one "
                "stream at a time, so stop the game on the matrix, or wait a "
                "moment if you just pressed Test."
            )
        if "rejected send message" in lowered or "org.freedesktop.dbus.error.accessdenied" in lowered:
            return (
                "The Pi's D-Bus refused the connection to bluealsa, which only "
                "accepts root or the audio group. Run the container as root - "
                'docker-compose sets user: "0:0" for this - or add a policy on '
                "the Pi permitting the user it runs as."
            )
        if "no such device" in lowered or "pcm not found" in lowered:
            return "The output has gone away. Reconnect the speaker and refresh."
        if "channels" in lowered or "sample" in lowered or "rate" in lowered:
            return "The output refused the audio format."
        # Unknown: the last line is usually the actual error.
        lines = [line.strip() for line in error.splitlines() if line.strip()]
        return lines[-1] if lines else error

    def _release_later(self, engine: AudioEngine) -> None:
        """Give the device back once the effect has had time to play."""
        def release() -> None:
            if self._test_engine is engine:
                self._test_engine = None
            engine.stop()

        timer = threading.Timer(TEST_RELEASE_SECONDS, release)
        timer.daemon = True
        self._release = timer
        timer.start()

    def _stop_previous(self) -> None:
        timer, self._release = self._release, None
        if timer is not None:
            timer.cancel()
        previous, self._test_engine = self._test_engine, None
        if previous is not None:
            previous.stop()

    def stop(self) -> None:
        self._stop_previous()


audio_service = AudioService()

__all__ = ["AudioService", "audio_service"]
