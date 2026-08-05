"""Background joystick controller for the matrix.

Polls the mini-joystick on its own thread. While a game is on the panel the
stick and buttons drive that game through the same command queue the web pad
uses; otherwise they shuffle through the installed apps.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from loguru import logger

from mini_joystick import (
    Button,
    ButtonEvent,
    FakeTransport,
    JoystickReader,
    MiniJoystick,
    SMBusTransport,
    Transport,
    TransportError,
)
from mini_joystick.bindings import DEFAULT_PROFILE, GAMEPAD, MODULE, ShellAction, game_action, shell_action
from mini_joystick.transport import available_buses, scan_bus, smbus_available
from src.domain.services.config_service import config_service
from src.domain.services.game_service import game_service

POLL_HZ = float(os.environ.get("ASSISTANT_MATRIX_JOYSTICK_POLL_HZ", "30"))
RECONNECT_SECONDS = 5.0

# Percentage points per button press.
BRIGHTNESS_STEP = 10
#: Never dim below something you can still read the panel by.
#:
#: The floor was 5, which is close enough to off that the matrix looks
#: broken - and since the level persists, a few too many presses on dimmer
#: left the panel dark through a reboot, with the way back up being a button
#: you cannot see to find.
BRIGHTNESS_MIN = 20
BRIGHTNESS_MAX = 100

# Wheel entries. `action` is handled below; `short` is what fits a wedge.
WHEEL_IN_GAME = (
    {"action": "togglePause", "label": "Pause", "short": "PAUSE"},
    {"action": "restart", "label": "Restart", "short": "RESET"},
    {"action": "exitGame", "label": "Exit", "short": "EXIT"},
    {"action": "brightnessDown", "label": "Dimmer", "short": "DIM"},
    {"action": "openMenu", "label": "Apps", "short": "PLUG"},
    {"action": "brightnessUp", "label": "Brighter", "short": "BRIGHT"},
)

WHEEL_SHELL = (
    {"action": "openMenu", "label": "Apps", "short": "PLUG"},
    {"action": "brightnessUp", "label": "Brighter", "short": "BRIGHT"},
    {"action": "power", "label": "Power", "short": "POWER"},
    {"action": "brightnessDown", "label": "Dimmer", "short": "DIM"},
)

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
        self._wheel_open = False
        self._device = DEFAULT_PROFILE
        self._brightness_nonce = 0
        self._wheel_items: list = []
        self._wheel_selected = None
        self._last_non_game = ""
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
            "role": str(settings.role or "system"),
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

    def dispatch_event(self, event, device: str = MODULE) -> None:
        """Route one controller event, from ``device``.

        The device decides which binding profile applies, so the module's
        five buttons and a pad's thirteen can mean different things in the
        same game.
        """
        self._device = device
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

        if self._wheel_open:
            self._dispatch_wheel(event)
            return
        if self._wheel_opens(event):
            self._open_wheel(bool(active))
            return

        # The module is bolted to the matrix; a gamepad is what you play with.
        # Left on system duty it never touches the game, so you can open the
        # wheel, switch app or change brightness mid-game without putting the
        # controller down.
        if active and self._plays_games(event):
            self._dispatch_game(active, event)
        else:
            self._dispatch_shell(event)

    def _plays_games(self, event) -> bool:
        """May the device this event came from drive the running game?"""
        if getattr(self, "_device", MODULE) != MODULE:
            return True
        return config_service.get_config().joystick.role == "player"

    def _wheel_opens(self, event) -> bool:
        """Holding OK is the way in, from a game or the shell alike."""
        return (
            event.kind == "button"
            and event.button in (Button.OK, Button.START)
            and event.event == ButtonEvent.LONG_PRESS_START
        )

    def _open_wheel(self, in_game: bool) -> None:
        self._wheel_items = [dict(item) for item in (WHEEL_IN_GAME if in_game else WHEEL_SHELL)]
        self._wheel_selected = None
        self._wheel_open = True
        self._menu_open = False
        self._publish_shell()
        self._record("wheel:open")

    def _close_wheel(self) -> None:
        self._wheel_open = False
        self._wheel_selected = None
        self._publish_shell()

    def _dispatch_wheel(self, event) -> None:
        from matrix_input.wheel import wedge_for_vector

        if event.kind == "direction":
            selected = wedge_for_vector(event.x, event.y, len(self._wheel_items))
            if selected != self._wheel_selected:
                self._wheel_selected = selected
                self._publish_shell()
            return
        if event.kind != "button" or event.button is None:
            return
        if event.event not in (ButtonEvent.PRESS_DOWN, ButtonEvent.SINGLE_CLICK, ButtonEvent.PRESS_UP):
            return
        if event.button in (Button.B, Button.D):
            self._close_wheel()
            return
        if event.button not in (Button.OK, Button.A, Button.START):
            return
        # Releasing the hold, or clicking, takes whatever is pointed at.
        chosen = self._wheel_selected
        self._close_wheel()
        if chosen is not None and 0 <= chosen < len(self._wheel_items):
            self._run_wheel_action(str(self._wheel_items[chosen].get("action", "")))

    def _run_wheel_action(self, action: str) -> None:
        active = game_service.active_game_id()
        if action == "brightnessUp":
            self._adjust_brightness(BRIGHTNESS_STEP)
        elif action == "brightnessDown":
            self._adjust_brightness(-BRIGHTNESS_STEP)
        elif action == "openMenu":
            self._open_menu()
        elif action == "exitGame":
            self._exit_game()
        elif action == "power":
            self._toggle_power()
        elif active and action:
            game_service.queue_command(active, action)
            self._record(f"{active}:{action}")

    def _exit_game(self) -> None:
        """Leave a game for whatever was on the panel before it."""
        apps = self._apps()
        if not apps:
            return
        target = self._last_non_game
        available = {app.manifest.id for app in apps}
        if target not in available:
            target = next(
                (w.manifest.id for w in apps if w.manifest.kind != "game"),
                apps[0].manifest.id,
            )
        self._apply_app(target)

    def _toggle_power(self) -> None:
        from src.domain.services.runtime_service import runtime_service

        if runtime_service.state().running:
            runtime_service.stop()
        else:
            runtime_service.start()
        self._record("power")

    def _game_bindings(self, app_id: str) -> dict:
        device = getattr(self, "_device", DEFAULT_PROFILE)
        saved = config_service.get_config().controller.profiles.get(device, {})
        return dict(saved.get(app_id, {}))

    def _dispatch_game(self, game_id: str, event) -> None:
        spec = game_service.spec(game_id)
        if spec is None:
            return
        action = game_action(event, set(spec.actions), self._game_bindings(spec.app_id))
        if not action:
            return
        game_service.queue_command(game_id, action)
        self._record(f"{game_id}:{action}")

    def _apps(self) -> list:
        from src.domain.services.app_registry_service import app_registry_service

        return [app for app in app_registry_service.list_local_apps() if app.enabled]

    def _publish_shell(self, brightness: int | None = None) -> None:
        """Tell the runtime what to draw, and how bright to be."""
        from matrix_input.shell import write_shell_state
        from src.domain.services.game_service import game_service

        config = config_service.get_config()
        apps = self._apps() if self._menu_open else []
        items = [
            {"id": app.manifest.id, "name": app.manifest.name, "active": app.active}
            for app in apps
        ]
        self._shell_seq += 1
        write_shell_state(
            game_service.state_dir / "shell.json",
            {
                "seq": self._shell_seq,
                "brightness": int(brightness if brightness is not None else config.matrix.brightness),
                # Changes on every brightness press, including one that is
                # already at the limit, so the runtime can show the bar.
                "brightnessSeq": self._brightness_nonce,
                "menu": {"open": self._menu_open, "cursor": self._cursor, "items": items},
                "wheel": {
                    "open": self._wheel_open,
                    "selected": self._wheel_selected,
                    "items": list(self._wheel_items),
                },
            },
        )

    def publish_brightness(self, level: int) -> None:
        """Push a level at the running panel without restarting it.

        The binding takes brightness live, so a change made in Settings
        should land as fast as one made on the joystick.
        """
        self._brightness_nonce += 1
        self._publish_shell(int(level))

    def _adjust_brightness(self, delta: int) -> None:
        config = config_service.get_config()
        level = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, int(config.matrix.brightness) + delta))
        # Bump on every press, not only on a change, so the bar still appears
        # at the ends of the range. Without it, pressing brighter at full
        # brightness did nothing whatsoever and read as a broken button.
        self._brightness_nonce += 1
        if level != config.matrix.brightness:
            config.matrix.brightness = level
            config_service.save_config(config)
        # Published, not restarted: the panel picks it up live.
        self._publish_shell(level)
        self._record(f"brightness:{level}")

    def _open_menu(self) -> None:
        apps = self._apps()
        if not apps:
            return
        ids = [app.manifest.id for app in apps]
        active = next((index for index, app in enumerate(apps) if app.active), 0)
        self._cursor = active if 0 <= active < len(ids) else 0
        self._menu_open = True
        self._publish_shell()
        self._record("menu:open")

    def _close_menu(self) -> None:
        self._menu_open = False
        self._publish_shell()
        self._record("menu:close")

    def _move_cursor(self, step: int) -> None:
        apps = self._apps()
        if not apps:
            return
        self._cursor = (self._cursor + step) % len(apps)
        self._publish_shell()

    def _select_from_menu(self) -> None:
        apps = self._apps()
        if not apps:
            return
        app_id = apps[self._cursor % len(apps)].manifest.id
        # Close first: applying restarts the runtime, which drops the overlay.
        self._menu_open = False
        self._publish_shell()
        self._apply_app(app_id)

    def menu_state(self) -> dict:
        apps = self._apps() if self._menu_open else []
        return {
            "open": self._menu_open,
            "cursor": self._cursor,
            "items": [{"id": w.manifest.id, "name": w.manifest.name, "active": w.active} for w in apps],
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
        apps = self._apps()
        if not apps:
            return
        ids = [app.manifest.id for app in apps]
        active_id = next((app.manifest.id for app in apps if app.active), "")
        # Resync only when something else moved the panel, so repeated pushes
        # keep walking the list instead of bouncing off the active app.
        if active_id and active_id != self._last_active:
            self._last_active = active_id
            if active_id in ids:
                self._cursor = ids.index(active_id)
        self._cursor %= len(ids)

        if action.kind in ("next", "previous"):
            step = 1 if action.kind == "next" else -1
            self._cursor = (self._cursor + step) % len(ids)
            self._apply_app(ids[self._cursor])
        elif action.kind == "apply":
            self._apply_app(ids[self._cursor % len(ids)])
        elif action.kind == "open" and action.value in ids:
            self._cursor = ids.index(action.value)
            self._apply_app(action.value)
        elif action.kind == "power":
            from src.domain.services.runtime_service import runtime_service

            if runtime_service.state().running:
                runtime_service.stop()
            else:
                runtime_service.start()
            self._record("power")

    def _apply_app(self, app_id: str) -> None:
        from src.domain.services.app_registry_service import app_registry_service

        spec = game_service.spec(app_id.replace("core.", "", 1))
        if spec is None or spec.app_id != app_id:
            self._last_non_game = app_id
        try:
            app_registry_service.apply_app(app_id)
            self._record(f"apply:{app_id}")
        except Exception as exc:
            self.last_error = str(exc)
            logger.warning("[joystick] could not apply {}: {}", app_id, exc)

    def _record(self, action: str) -> None:
        self.last_action = action
        self.last_action_at = time.time()


joystick_service = JoystickService()

__all__ = ["JoystickService", "joystick_service", "FakeTransport", "Button", "ShellAction"]
