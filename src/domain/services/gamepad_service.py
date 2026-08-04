"""Bluetooth and USB gamepad controller.

BlueZ pairs the pad and the kernel exposes it as an input device; this polls it
and pushes the resulting actions through the same binding the mini-joystick
uses, so a controller drives the games and the plugin list identically.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from loguru import logger

from matrix_input.gamepad import GamepadReader, evdev_available, list_gamepads, list_input_devices
from src.domain.services.config_service import config_service

POLL_HZ = float(os.environ.get("ASSISTANT_MATRIX_GAMEPAD_POLL_HZ", "60"))
RECONNECT_SECONDS = 3.0


class GamepadService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.connected = False
        self.device_name = ""
        self.last_error = ""
        # Injected by the tests; production opens a real evdev device.
        self.reader_factory = None

    def settings(self) -> Any:
        return config_service.get_config().gamepad

    def enabled(self) -> bool:
        return bool(self.settings().enabled)

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def devices(self) -> list[dict[str, Any]]:
        return [{"path": pad.path, "name": pad.name, "wireless": pad.wireless} for pad in list_gamepads()]

    def state(self) -> dict[str, Any]:
        settings = self.settings()
        pads = self.devices()
        return {
            "enabled": bool(settings.enabled),
            "running": self.running(),
            "connected": self.connected,
            "libraryInstalled": evdev_available(),
            "device": settings.device,
            "deviceName": self.device_name,
            "devices": pads,
            "inputDevices": list_input_devices(),
            "lastError": self.last_error,
            "advice": self._advice(pads),
        }

    def _bluetooth_controllers(self) -> list[dict[str, Any]]:
        """Controllers BlueZ believes are connected, for cross-checking."""
        try:
            from src.domain.services.bluetooth_service import bluetooth_service

            return [
                device
                for device in bluetooth_service.list_devices()
                if device.get("connected") and device.get("role") == "controller"
            ]
        except Exception:
            return []

    def _advice(self, pads: list[dict[str, Any]]) -> str:
        if not evdev_available():
            return "The evdev library is missing. Rebuild the container so gamepad support is installed."
        if not pads:
            # Bluetooth saying "connected" while no input device exists is the
            # signature of a pad that paired but never finished linking.
            # A pad bound to the wrong driver is present but unrecognised,
            # which otherwise looks exactly like nothing being connected.
            others = [device for device in list_input_devices() if not device["isGamepad"]]
            candidates = [
                device for device in others
                if any(word in device["name"].lower() for word in ("xbox", "controller", "gamepad", "pad"))
            ]
            if candidates:
                found = candidates[0]
                return (
                    f"{found['name']} is connected as an input device but does not report gamepad buttons "
                    f"({found['buttons']} keys, {found['axes']} axes), so the kernel bound it to the wrong "
                    "driver. For an Xbox pad install xpadneo on the Pi, or connect it by USB to check the "
                    "rest of the chain works."
                )

            paired = self._bluetooth_controllers()
            if paired:
                from src.domain.services.bluetooth_service import ERTM_HELP, ertm_disabled

                name = paired[0].get("name", "The controller")
                ertm = ertm_disabled()
                if ertm is False:
                    return (
                        f"{name} is paired but the kernel created no input device, and Bluetooth ERTM is on. "
                        f"That combination is what stops an Xbox pad connecting. {ERTM_HELP} "
                        "This is a setting on the Pi itself, so rebuilding the container will not change it."
                    )
                if ertm is None:
                    # Unknown is not the same as fine, and saying so sends you
                    # off re-pairing a controller that is already connected.
                    return (
                        f"{name} shows as connected but the kernel created no input device, and the ERTM "
                        "setting is not readable from in here. Check on the Pi with: "
                        "cat /sys/module/bluetooth/parameters/disable_ertm (want Y), and whether the device "
                        "node exists at all with: ls -l /dev/input/event*"
                    )
                return (
                    f"{name} is connected and ERTM is already off, but no input device exists. Check on the "
                    "Pi whether the kernel made one: ls -l /dev/input/event* and "
                    "grep -i -A5 xbox /proc/bus/input/devices. If the Pi has it but this list is empty, the "
                    "container is not seeing /dev/input. If the Pi does not have it either, the pad needs a "
                    "driver: install xpadneo."
                )
            return (
                "No controller found. Put the pad in pairing mode, pair it under Settings -> Bluetooth, "
                "and it will appear here. A USB pad works too."
            )
        if self.connected:
            return f"Reading {self.device_name}."
        if not self.enabled():
            return "A controller is available. Turn on 'Use a game controller' to start reading it."
        return "A controller is present but not being read yet; it should connect within a few seconds."

    # --- lifecycle -------------------------------------------------------

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.running():
                return self.state()
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="gamepad", daemon=True)
            self._thread.start()
        return self.state()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop.set()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self.connected = False
        return self.state()

    def apply(self) -> dict[str, Any]:
        """Start or stop to match the saved config."""
        if self.enabled():
            if self.running():
                self.stop()
            return self.start()
        return self.stop()

    # --- polling ---------------------------------------------------------

    def _open(self):
        if self.reader_factory is not None:
            return self.reader_factory()
        settings = self.settings()
        wanted = str(settings.device or "").strip()
        pads = list_gamepads()
        if not pads:
            return None
        chosen = next((pad for pad in pads if pad.path == wanted), None) if wanted else None
        # No preference means take the first pad, which is what one controller means.
        pad = chosen or pads[0]
        return GamepadReader(pad.path, deadzone=float(settings.deadzone))

    def _run(self) -> None:
        interval = 1.0 / max(1.0, POLL_HZ)
        while not self._stop.is_set():
            reader = None
            try:
                reader = self._open()
            except Exception as exc:
                self.last_error = str(exc)
                logger.warning("[gamepad] could not open controller: {}", exc)

            if reader is None:
                self.connected = False
                if self._stop.wait(RECONNECT_SECONDS):
                    return
                continue

            self.device_name = getattr(reader, "name", "")
            self.connected = True
            self.last_error = ""
            logger.info("[gamepad] reading {}", self.device_name)
            try:
                while not self._stop.is_set():
                    started = time.monotonic()
                    for event in reader.poll():
                        self._dispatch(event)
                    self._stop.wait(max(0.0, interval - (time.monotonic() - started)))
            except Exception as exc:
                # A pad that goes out of range raises on read, so reconnect.
                self.last_error = str(exc)
                logger.info("[gamepad] {} disconnected: {}", self.device_name, exc)
            finally:
                self.connected = False
                try:
                    reader.close()
                except Exception:
                    pass
            if not self._stop.is_set():
                self._stop.wait(RECONNECT_SECONDS)

    def _dispatch(self, event) -> None:
        # Shared with the mini-joystick so both controllers behave identically.
        from src.domain.services.joystick_service import joystick_service

        from mini_joystick.bindings import GAMEPAD

        joystick_service.dispatch_event(event, device=GAMEPAD)


gamepad_service = GamepadService()

__all__ = ["GamepadService", "gamepad_service"]
