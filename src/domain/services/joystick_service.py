"""Background joystick controller for the matrix.

Polls the mini-joystick on its own thread. While a game is on the panel the
stick and buttons drive that game through the same command queue the web pad
uses; otherwise they shuffle through the installed plugins.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from loguru import logger

from mini_joystick import (
    Button,
    FakeTransport,
    JoystickReader,
    MiniJoystick,
    SMBusTransport,
    Transport,
    TransportError,
)
from mini_joystick.bindings import ShellAction, game_action, shell_action
from mini_joystick.transport import available_buses, scan_bus, smbus_available
from src.domain.services.config_service import config_service
from src.domain.services.game_service import game_service

POLL_HZ = float(os.environ.get("ASSISTANT_MATRIX_JOYSTICK_POLL_HZ", "30"))
RECONNECT_SECONDS = 5.0

# Percentage points per button press.
BRIGHTNESS_STEP = 10
BRIGHTNESS_MIN = 5
BRIGHTNESS_MAX = 100

# Buses the kernel creates for other hardware. i2c-20/21 are the HDMI DDC
# channels on a Pi 4, i2c-10/11 come from the RP1 on a Pi 5, and i2c-0 is the
# HAT ID EEPROM. None of them reach the GPIO header, so seeing only these means
# the header bus has not been enabled rather than that the wiring is wrong.
NON_GPIO_BUSES = {0, 10, 11, 20, 21, 22}

GPIO_BUS_HELP = (
    "Enable it with 'sudo raspi-config' (Interface Options -> I2C), or add 'dtparam=i2c_arm=on' to "
    "/boot/firmware/config.txt, then reboot. This is a boot-time setting, so it cannot be turned on "
    "from this app and a reboot is required."
)


class JoystickService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.connected = False
        self.last_error = ""
        self.last_action = ""
        self.last_action_at = 0.0
        self.events_seen = 0
        self._cursor = 0
        self._last_active = ""
        self._menu_open = False
        self._shell_seq = 0
        # Injected by the tests; production builds one from config.
        self.transport_factory = None

    # --- lifecycle -------------------------------------------------------

    def settings(self) -> Any:
        return config_service.get_config().joystick

    def enabled(self) -> bool:
        return bool(self.settings().enabled)

    def state(self) -> dict[str, Any]:
        settings = self.settings()
        return {
            "enabled": bool(settings.enabled),
            "running": self.running(),
            "connected": self.connected,
            "bus": settings.bus,
            "address": settings.address,
            "lastError": self.last_error,
            "lastAction": self.last_action,
            "lastActionAt": self.last_action_at,
            "eventsSeen": self.events_seen,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Probe every I2C bus so a wiring problem is visible, not guesswork."""
        settings = self.settings()
        address = int(settings.address)
        installed = smbus_available()
        buses: list[dict[str, Any]] = []
        detected = False

        for bus in available_buses():
            entry: dict[str, Any] = {"bus": bus, "addresses": [], "joystickFound": False, "error": ""}
            try:
                found = scan_bus(bus)
                entry["addresses"] = [f"0x{value:02x}" for value in found]
                entry["joystickFound"] = address in found
                detected = detected or entry["joystickFound"]
            except Exception as exc:
                entry["error"] = str(exc)
            buses.append(entry)

        return {
            "libraryInstalled": installed,
            "buses": buses,
            "configuredBus": int(settings.bus),
            "configuredAddress": f"0x{address:02x}",
            "detected": detected,
            "advice": self._advice(installed, buses, detected, int(settings.bus), address),
        }

    def _advice(self, installed: bool, buses: list[dict[str, Any]], detected: bool, bus: int, address: int) -> str:
        if not installed:
            return (
                "The smbus2 library is missing. Rebuild the container, or install it with "
                "'pip install smbus2'."
            )
        if not buses:
            return (
                "No /dev/i2c-* device is visible. On the Pi: enable I2C with 'sudo raspi-config' "
                "(Interface Options -> I2C), check 'dtparam=i2c_arm=on' is in /boot/firmware/config.txt, "
                "then REBOOT - the device node only appears after a reboot. Confirm with 'ls /dev/i2c-*' "
                "on the host. In Docker, privileged mode shares the host /dev, so if the host has the "
                "node and the container does not, recreate the container."
            )
        if detected:
            found_on = [entry["bus"] for entry in buses if entry["joystickFound"]]
            if bus in found_on:
                return "The module is responding. If input still does nothing, enable the joystick above."
            return f"The module answered on bus {found_on[0]}, but the app is set to bus {bus}. Change the bus here."

        gpio_buses = [entry for entry in buses if entry["bus"] not in NON_GPIO_BUSES]
        if not gpio_buses:
            others = ", ".join(str(entry["bus"]) for entry in buses)
            return (
                f"Only non-GPIO buses are present ({others}). Those belong to HDMI and onboard hardware, "
                f"not the pin header, so the module cannot be on one. The GPIO bus is not enabled yet. "
                f"{GPIO_BUS_HELP} Then look for /dev/i2c-1."
            )

        seen = sorted({addr for entry in gpio_buses for addr in entry["addresses"]})
        if seen:
            return (
                f"The GPIO bus works and sees {', '.join(seen)}, but nothing at 0x{address:02x}. "
                "Check the module has 5V power and that SDA and SCL are not swapped."
            )
        return (
            "The GPIO bus is present but empty. Wire SDA to GPIO 2 (physical pin 3) and SCL to GPIO 3 "
            "(physical pin 5), power the module from 5V, and use a level shifter on both lines."
        )

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.running():
                return self.state()
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="mini-joystick", daemon=True)
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

    def _build_transport(self) -> Transport:
        if self.transport_factory is not None:
            return self.transport_factory()
        settings = self.settings()
        return SMBusTransport(bus=int(settings.bus), address=int(settings.address), combined=bool(settings.combinedRead))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                transport = self._build_transport()
            except TransportError as exc:
                self.last_error = str(exc)
                self.connected = False
                logger.warning("[joystick] {}", exc)
                if self._stop.wait(RECONNECT_SECONDS):
                    return
                continue

            settings = self.settings()
            joystick = MiniJoystick(
                transport,
                deadzone=float(settings.deadzone),
                invert_x=bool(settings.invertX),
                invert_y=bool(settings.invertY),
            )
            reader = JoystickReader(joystick, repeat_delay=float(settings.repeatDelay), repeat_interval=float(settings.repeatInterval))
            self.last_error = ""
            interval = 1.0 / max(1.0, POLL_HZ)
            try:
                while not self._stop.is_set():
                    started = time.monotonic()
                    for event in reader.poll(started):
                        self._dispatch(event)
                    self._stop.wait(max(0.0, interval - (time.monotonic() - started)))
            except Exception as exc:  # keep the thread alive across bus glitches
                self.last_error = str(exc)
                logger.exception("[joystick] polling failed")
            finally:
                joystick.close()
                self.connected = False
            if not self._stop.is_set():
                self._stop.wait(RECONNECT_SECONDS)

    def dispatch_event(self, event) -> None:
        """Route one controller event. Shared by the joystick and any gamepad."""
        self._dispatch(event)

    def _dispatch(self, event) -> None:
        if event.kind == "disconnected":
            self.connected = False
            logger.info("[joystick] module not responding")
            return
        if event.kind == "reconnected":
            self.connected = True
            logger.info("[joystick] module connected")
            return

        self.connected = True
        self.events_seen += 1
        active = game_service.active_game_id()
        if active:
            self._dispatch_game(active, event)
        else:
            self._dispatch_shell(event)

    def _dispatch_game(self, game_id: str, event) -> None:
        spec = game_service.spec(game_id)
        if spec is None:
            return
        action = game_action(event, set(spec.actions))
        if not action:
            return
        game_service.queue_command(game_id, action)
        self._record(f"{game_id}:{action}")

    def _widgets(self) -> list:
        from src.domain.services.widget_registry_service import widget_registry_service

        return [widget for widget in widget_registry_service.list_local_widgets() if widget.enabled]

    def _publish_shell(self, brightness: int | None = None) -> None:
        """Tell the runtime what to draw, and how bright to be."""
        from matrix_input.shell import write_shell_state
        from src.domain.services.game_service import game_service

        config = config_service.get_config()
        widgets = self._widgets() if self._menu_open else []
        items = [
            {"id": widget.manifest.id, "name": widget.manifest.name, "active": widget.active}
            for widget in widgets
        ]
        self._shell_seq += 1
        write_shell_state(
            game_service.state_dir / "shell.json",
            {
                "seq": self._shell_seq,
                "brightness": int(brightness if brightness is not None else config.matrix.brightness),
                "menu": {"open": self._menu_open, "cursor": self._cursor, "items": items},
            },
        )

    def _adjust_brightness(self, delta: int) -> None:
        config = config_service.get_config()
        level = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, int(config.matrix.brightness) + delta))
        if level == config.matrix.brightness:
            return
        config.matrix.brightness = level
        config_service.save_config(config)
        # Published, not restarted: the panel picks it up live.
        self._publish_shell(level)
        self._record(f"brightness:{level}")

    def _open_menu(self) -> None:
        widgets = self._widgets()
        if not widgets:
            return
        ids = [widget.manifest.id for widget in widgets]
        active = next((index for index, widget in enumerate(widgets) if widget.active), 0)
        self._cursor = active if 0 <= active < len(ids) else 0
        self._menu_open = True
        self._publish_shell()
        self._record("menu:open")

    def _close_menu(self) -> None:
        self._menu_open = False
        self._publish_shell()
        self._record("menu:close")

    def _move_cursor(self, step: int) -> None:
        widgets = self._widgets()
        if not widgets:
            return
        self._cursor = (self._cursor + step) % len(widgets)
        self._publish_shell()

    def _select_from_menu(self) -> None:
        widgets = self._widgets()
        if not widgets:
            return
        widget_id = widgets[self._cursor % len(widgets)].manifest.id
        # Close first: applying restarts the runtime, which drops the overlay.
        self._menu_open = False
        self._publish_shell()
        self._apply_widget(widget_id)

    def menu_state(self) -> dict:
        widgets = self._widgets() if self._menu_open else []
        return {
            "open": self._menu_open,
            "cursor": self._cursor,
            "items": [{"id": w.manifest.id, "name": w.manifest.name, "active": w.active} for w in widgets],
        }

    def _dispatch_shell(self, event) -> None:
        action = shell_action(event, self._menu_open)
        if action is None:
            return

        if action.kind == "openMenu":
            self._open_menu()
            return
        if action.kind == "closeMenu":
            self._close_menu()
            return
        if action.kind == "cursorNext":
            self._move_cursor(1)
            return
        if action.kind == "cursorPrevious":
            self._move_cursor(-1)
            return
        if action.kind == "select":
            self._select_from_menu()
            return
        if action.kind == "brightnessUp":
            self._adjust_brightness(BRIGHTNESS_STEP)
            return
        if action.kind == "brightnessDown":
            self._adjust_brightness(-BRIGHTNESS_STEP)
            return
        widgets = self._widgets()
        if not widgets:
            return
        ids = [widget.manifest.id for widget in widgets]
        active_id = next((widget.manifest.id for widget in widgets if widget.active), "")
        # Resync only when something else moved the panel, so repeated pushes
        # keep walking the list instead of bouncing off the active widget.
        if active_id and active_id != self._last_active:
            self._last_active = active_id
            if active_id in ids:
                self._cursor = ids.index(active_id)
        self._cursor %= len(ids)

        if action.kind in ("next", "previous"):
            step = 1 if action.kind == "next" else -1
            self._cursor = (self._cursor + step) % len(ids)
            self._apply_widget(ids[self._cursor])
        elif action.kind == "apply":
            self._apply_widget(ids[self._cursor % len(ids)])
        elif action.kind == "open" and action.value in ids:
            self._cursor = ids.index(action.value)
            self._apply_widget(action.value)
        elif action.kind == "power":
            from src.domain.services.runtime_service import runtime_service

            if runtime_service.state().running:
                runtime_service.stop()
            else:
                runtime_service.start()
            self._record("power")

    def _apply_widget(self, widget_id: str) -> None:
        from src.domain.services.widget_registry_service import widget_registry_service

        try:
            widget_registry_service.apply_widget(widget_id)
            self._record(f"apply:{widget_id}")
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("[joystick] could not apply {}: {}", widget_id, exc)

    def _record(self, action: str) -> None:
        self.last_action = action
        self.last_action_at = time.time()


joystick_service = JoystickService()

__all__ = ["JoystickService", "joystick_service", "FakeTransport", "Button", "ShellAction"]
