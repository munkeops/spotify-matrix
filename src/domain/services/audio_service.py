"""Sound settings, and a way to hear whether any of it works.

Game effects are played by the runtime process, because they have to line up
with a frame. This service owns the settings and can play a test sound of its
own, so you can confirm the sound card works before starting a game.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from matrix_audio import AudioEngine, aplay_available, list_output_devices


class AudioService:
    def __init__(self) -> None:
        self._test_engine: AudioEngine | None = None

    def settings(self) -> Any:
        from src.domain.services.config_service import config_service

        return config_service.get_config().audio

    def devices(self) -> list[dict[str, Any]]:
        return list_output_devices()

    def sounds(self) -> list[str]:
        """Effects the active game ships, so the panel can offer a test."""
        from src.domain.services.game_service import game_service

        active = game_service.active_game_id()
        spec = game_service.spec(active) if active else None
        if spec is None:
            specs = list(game_service.specs().values())
            spec = specs[0] if specs else None
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
        }

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
        if not self.settings().enabled:
            return "Turn on game sound to hear effects. Use Test to check the output first."
        return f"Ready, {len(devices)} output(s) available. Test plays a sound straight away."

    def play_test(self, sound: str = "start") -> dict[str, Any]:
        """Play one effect right now, from this process."""
        from src.domain.services.game_service import game_service

        settings = self.settings()
        specs = list(game_service.specs().values())
        if not specs:
            return {"ok": False, "message": "No games installed, so there are no sounds to play."}

        engine = AudioEngine(enabled=True, device=settings.device, volume=int(settings.volume) / 100.0)
        for spec in specs:
            if spec.sounds_dir.is_dir():
                engine.load_directory(spec.sounds_dir)
                break
        engine.start()
        played = engine.play(sound)
        # Replace whatever the last test left running.
        self._stop_previous()
        self._test_engine = engine
        if not played:
            return {"ok": False, "message": f"No sound called {sound}."}
        return {"ok": True, "message": f"Playing {sound}.", "error": engine.error}

    def _stop_previous(self) -> None:
        previous, self._test_engine = self._test_engine, None
        if previous is not None:
            previous.stop()

    def stop(self) -> None:
        self._stop_previous()


audio_service = AudioService()

__all__ = ["AudioService", "audio_service"]
