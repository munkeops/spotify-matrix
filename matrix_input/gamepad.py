"""Bluetooth and USB gamepads, read through Linux evdev.

BlueZ pairs a controller and the kernel exposes it as ``/dev/input/event*``.
This turns those raw events into the same controller events the mini-joystick
produces, so both drive the games through one binding.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from mini_joystick.events import JoystickEvent
from mini_joystick.protocol import Button, ButtonEvent, Direction

# evdev codes, hard-coded so the mapping is testable without the library.
EV_KEY = 0x01
EV_ABS = 0x03

BTN_SOUTH = 0x130   # A on Xbox, cross on PlayStation
BTN_EAST = 0x131    # B / circle
BTN_C = 0x132
BTN_NORTH = 0x133   # Y / triangle
BTN_WEST = 0x134    # X / square
BTN_SELECT = 0x13A
BTN_START = 0x13B
BTN_MODE = 0x13C
BTN_THUMBL = 0x13D
BTN_THUMBR = 0x13E
BTN_TL = 0x136     # left bumper
BTN_TR = 0x137     # right bumper
BTN_TL2 = 0x138    # left trigger, when the pad reports it as a button
BTN_TR2 = 0x139    # right trigger

ABS_X = 0x00
ABS_Y = 0x01
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11

#: Every button a pad reports, each to its own control.
#:
#: These used to collapse onto the module's five: Start, Guide and the left
#: stick click all became OK, Select doubled as Y, and the bumpers and
#: triggers were absent entirely, so a controller was strictly a worse
#: mini-joystick. South stays the primary action because that is where a
#: thumb rests on every pad.
BUTTON_MAP = {
    BTN_SOUTH: Button.A,
    BTN_EAST: Button.B,
    BTN_WEST: Button.C,
    BTN_NORTH: Button.D,
    BTN_C: Button.C,
    BTN_TL: Button.LB,
    BTN_TR: Button.RB,
    BTN_TL2: Button.LT,
    BTN_TR2: Button.RT,
    BTN_START: Button.START,
    BTN_MODE: Button.START,
    BTN_SELECT: Button.SELECT,
    BTN_THUMBL: Button.L3,
    BTN_THUMBR: Button.R3,
}

#: Fraction of an analog axis before it counts as a push.
DEFAULT_DEADZONE = 0.5

# The I2C module's MCU produces auto-repeat and long-press itself. A gamepad
# only reports raw press and release, so the same events are synthesised here
# from held state and time. Without this a held stick moves once and a long
# press never happens, which means no quick wheel from a controller.
REPEAT_DELAY = 0.28
REPEAT_INTERVAL = 0.09
LONG_PRESS_SECONDS = 0.55


@dataclass(frozen=True)
class GamepadInfo:
    path: str
    name: str
    phys: str = ""
    uniq: str = ""

    @property
    def wireless(self) -> bool:
        """Bluetooth pads report a MAC in ``uniq`` and a bluetooth-ish phys."""
        return bool(self.uniq) and ":" in self.uniq


class GamepadMapper:
    """Turns raw evdev codes into controller events.

    Kept free of evdev itself so the mapping can be tested anywhere.
    """

    def __init__(
        self,
        deadzone: float = DEFAULT_DEADZONE,
        *,
        repeat_delay: float = REPEAT_DELAY,
        repeat_interval: float = REPEAT_INTERVAL,
        long_press: float = LONG_PRESS_SECONDS,
    ) -> None:
        self.deadzone = max(0.1, min(0.9, float(deadzone)))
        self.repeat_delay = max(0.0, float(repeat_delay))
        self.repeat_interval = max(0.02, float(repeat_interval))
        self.long_press = max(0.1, float(long_press))
        self._axis_range: dict[int, tuple[float, float]] = {}
        self._direction = Direction.NEUTRAL
        self._axes: dict[int, float] = {ABS_X: 0.0, ABS_Y: 0.0, ABS_HAT0X: 0.0, ABS_HAT0Y: 0.0}
        self._next_repeat = 0.0
        self._held: dict[Button, float] = {}
        self._long_fired: set[Button] = set()

    def configure_axis(self, code: int, minimum: float, maximum: float) -> None:
        """Tell the mapper an axis range, so sticks normalise correctly."""
        if maximum > minimum:
            self._axis_range[code] = (float(minimum), float(maximum))

    def _normalise(self, code: int, value: float) -> float:
        low, high = self._axis_range.get(code, (-1.0, 1.0))
        if high <= low:
            return 0.0
        middle = (high + low) / 2
        span = (high - low) / 2
        return max(-1.0, min(1.0, (float(value) - middle) / span)) if span else 0.0

    def feed(self, event_type: int, code: int, value: int, now: float | None = None) -> list[JoystickEvent]:
        now = time.monotonic() if now is None else now
        if event_type == EV_KEY:
            return self._button(code, value, now)
        if event_type == EV_ABS:
            return self._axis(code, value, now)
        return []

    def tick(self, now: float | None = None) -> list[JoystickEvent]:
        """Events that come from holding rather than from moving.

        Called every poll, so a held direction repeats and a held button
        becomes a long press, matching what the I2C module reports.
        """
        now = time.monotonic() if now is None else now
        events: list[JoystickEvent] = []

        if self._direction != Direction.NEUTRAL and now >= self._next_repeat:
            self._next_repeat = now + self.repeat_interval
            x, y = self._vector()
            events.append(JoystickEvent(kind="direction", direction=self._direction, repeat=True, x=x, y=y))

        for button, since in list(self._held.items()):
            if button not in self._long_fired and now - since >= self.long_press:
                self._long_fired.add(button)
                events.append(JoystickEvent(kind="button", button=button, event=ButtonEvent.LONG_PRESS_START))
        return events

    def _button(self, code: int, value: int, now: float) -> list[JoystickEvent]:
        button = BUTTON_MAP.get(code)
        if button is None:
            return []
        # 1 is press, 2 is auto-repeat from the kernel, 0 is release.
        if value == 0:
            self._held.pop(button, None)
            self._long_fired.discard(button)
            return [JoystickEvent(kind="button", button=button, event=ButtonEvent.PRESS_UP)]
        if value == 1:
            self._held[button] = now
            self._long_fired.discard(button)
            return [JoystickEvent(kind="button", button=button, event=ButtonEvent.PRESS_DOWN)]
        return []

    def _axis(self, code: int, value: int, now: float = 0.0) -> list[JoystickEvent]:
        if code not in self._axes:
            return []
        # Hats are already -1/0/1; sticks need their reported range applied.
        self._axes[code] = float(value) if code in (ABS_HAT0X, ABS_HAT0Y) else self._normalise(code, value)
        direction = self._direction_now()
        if direction == self._direction:
            return []
        self._direction = direction
        # A fresh push waits the initial delay before it starts repeating.
        self._next_repeat = now + self.repeat_delay
        if direction == Direction.NEUTRAL:
            return []
        x, y = self._vector()
        return [JoystickEvent(kind="direction", direction=direction, x=x, y=y)]

    def _vector(self) -> tuple[float, float]:
        """The stick or d-pad as a vector, for angular selection."""
        hat_x, hat_y = self._axes[ABS_HAT0X], self._axes[ABS_HAT0Y]
        if hat_x or hat_y:
            return hat_x, hat_y
        return self._axes[ABS_X], self._axes[ABS_Y]

    def _direction_now(self) -> Direction:
        # The d-pad wins when it is being used, otherwise fall back to the stick.
        x, y = self._vector()
        if max(abs(x), abs(y)) < self.deadzone:
            return Direction.NEUTRAL
        if abs(x) >= abs(y):
            return Direction.RIGHT if x > 0 else Direction.LEFT
        return Direction.DOWN if y > 0 else Direction.UP

    def held_direction(self) -> Direction:
        """The direction currently held, for auto-repeat."""
        return self._direction


def evdev_available() -> bool:
    try:
        import evdev  # noqa: F401
    except ImportError:
        return False
    return True


def list_gamepads() -> list[GamepadInfo]:
    """Input devices that look like a game controller."""
    try:
        import evdev
    except ImportError:
        return []

    found: list[GamepadInfo] = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
        except OSError:
            continue
        try:
            capabilities = device.capabilities()
            keys = set(capabilities.get(EV_KEY, []) or [])
            # A pad is anything reporting a gamepad face button.
            if keys & set(BUTTON_MAP):
                found.append(GamepadInfo(path=path, name=device.name or Path(path).name, phys=device.phys or "", uniq=device.uniq or ""))
        finally:
            device.close()
    return found


def list_input_devices() -> list[dict[str, Any]]:
    """Every evdev device, gamepad or not.

    A controller that connects but presents unexpected button codes is filtered
    out of :func:`list_gamepads`, which looks identical to no controller at all.
    This shows what is actually there.
    """
    try:
        import evdev
    except ImportError:
        return []

    found: list[dict[str, Any]] = []
    for path in evdev.list_devices():
        try:
            device = evdev.InputDevice(path)
        except OSError:
            continue
        try:
            capabilities = device.capabilities()
            keys = sorted(set(capabilities.get(EV_KEY, []) or []))
            axes = sorted({code for code, _ in (capabilities.get(EV_ABS, []) or [])})
            found.append(
                {
                    "path": path,
                    "name": device.name or Path(path).name,
                    "isGamepad": bool(set(keys) & set(BUTTON_MAP)),
                    "buttons": len(keys),
                    "axes": len(axes),
                    # The first few codes are usually enough to spot a pad that
                    # bound to the wrong driver.
                    "sampleKeys": [hex(code) for code in keys[:8]],
                }
            )
        finally:
            device.close()
    return found


class GamepadReader:
    """Reads one evdev device and yields controller events."""

    def __init__(self, path: str, deadzone: float = DEFAULT_DEADZONE) -> None:
        try:
            import evdev
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise RuntimeError(
                "The evdev library is required to read a gamepad. Install it with 'pip install evdev'."
            ) from exc

        self.path = path
        self._device = evdev.InputDevice(path)
        self.name = self._device.name or path
        self.mapper = GamepadMapper(deadzone)
        # Teach the mapper the real axis ranges this pad reports.
        for code, info in self._device.capabilities().get(EV_ABS, []) or []:
            if code in (ABS_X, ABS_Y):
                self.mapper.configure_axis(code, getattr(info, "min", -1), getattr(info, "max", 1))

    def poll(self) -> Iterator[JoystickEvent]:
        """Drain the pad, then add whatever holding it has produced."""
        try:
            while True:
                event = self._device.read_one()
                if event is None:
                    break
                for mapped in self.mapper.feed(event.type, event.code, event.value):
                    yield mapped
        except OSError:
            # The pad went away mid-read; the service will notice and reconnect.
            raise
        yield from self.mapper.tick()

    def close(self) -> None:
        try:
            self._device.close()
        except OSError:  # pragma: no cover
            pass


class FakeGamepad:
    """Scripted pad for tests and development off a Pi."""

    def __init__(self, events: list[tuple[int, int, int]] | None = None, name: str = "Fake Pad") -> None:
        self.queued = list(events or [])
        self.name = name
        self.path = "/dev/input/fake"
        self.mapper = GamepadMapper()
        self.closed = False

    def send(self, event_type: int, code: int, value: int) -> None:
        self.queued.append((event_type, code, value))

    def poll(self, now: float | None = None) -> Iterator[JoystickEvent]:
        pending, self.queued = self.queued, []
        for event_type, code, value in pending:
            yield from self.mapper.feed(event_type, code, value, now)
        yield from self.mapper.tick(now)

    def close(self) -> None:
        self.closed = True


__all__ = [
    "GamepadInfo",
    "GamepadMapper",
    "GamepadReader",
    "FakeGamepad",
    "list_gamepads",
    "list_input_devices",
    "evdev_available",
    "BUTTON_MAP",
    "EV_KEY",
    "EV_ABS",
    "BTN_SOUTH",
    "BTN_EAST",
    "BTN_WEST",
    "BTN_NORTH",
    "BTN_START",
    "ABS_X",
    "ABS_Y",
    "ABS_HAT0X",
    "ABS_HAT0Y",
    "DEFAULT_DEADZONE",
    "REPEAT_DELAY",
    "REPEAT_INTERVAL",
    "LONG_PRESS_SECONDS",
]
