"""Turn joystick samples into edge-triggered events.

The module reports a level ("A is down") rather than an edge, and the stick is
an analog axis rather than a d-pad. This layer converts both into the discrete
events a menu or a game wants, including press-and-hold auto-repeat.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterator

from mini_joystick.device import JoystickState, MiniJoystick
from mini_joystick.protocol import Button, ButtonEvent, Direction

DEFAULT_POLL_HZ = 30.0
DEFAULT_REPEAT_DELAY = 0.28
DEFAULT_REPEAT_INTERVAL = 0.09


@dataclass(frozen=True)
class JoystickEvent:
    """Something the player did.

    ``kind`` is ``direction`` for a stick push, ``button`` for a button, or
    ``disconnected`` / ``reconnected`` when the module comes and goes.
    """

    kind: str
    direction: Direction = Direction.NEUTRAL
    button: Button | None = None
    event: ButtonEvent = ButtonEvent.NONE
    repeat: bool = False
    #: Raw stick vector for direction events, so a radial menu can use the
    #: angle rather than the four-way direction. Up is negative y.
    x: float = 0.0
    y: float = 0.0

    @property
    def name(self) -> str:
        if self.kind == "direction":
            return self.direction.value
        if self.kind == "button" and self.button is not None:
            return self.button.value
        return self.kind


class JoystickReader:
    """Polls a :class:`MiniJoystick` and yields edges.

    Stateless callers can drive this themselves with :meth:`poll`, passing the
    current time, which is what makes it straightforward to test.
    """

    def __init__(
        self,
        joystick: MiniJoystick,
        *,
        repeat_delay: float = DEFAULT_REPEAT_DELAY,
        repeat_interval: float = DEFAULT_REPEAT_INTERVAL,
    ) -> None:
        self.joystick = joystick
        self.repeat_delay = max(0.0, float(repeat_delay))
        self.repeat_interval = max(0.02, float(repeat_interval))
        self._direction = Direction.NEUTRAL
        self._direction_since = 0.0
        self._next_repeat = 0.0
        self._buttons: dict[Button, ButtonEvent] = {}
        self._connected = True
        self._started = False

    @property
    def connected(self) -> bool:
        """Whether the module answered the last read.

        Events alone cannot say this. The first poll of a healthy module
        deliberately emits nothing - there is no transition to report - so
        anyone watching only events cannot tell a module sitting untouched
        from one that is not there at all.
        """
        return self._connected

    def poll(self, now: float | None = None) -> list[JoystickEvent]:
        """Read once and return the events since the previous read."""
        now = time.monotonic() if now is None else now
        state = self.joystick.read()
        events: list[JoystickEvent] = []

        if state.connected != self._connected or not self._started:
            if self._started or not state.connected:
                events.append(JoystickEvent(kind="reconnected" if state.connected else "disconnected"))
            self._connected = state.connected
        self._started = True
        if not state.connected:
            self._direction = Direction.NEUTRAL
            self._buttons = {}
            return events

        events.extend(self._direction_events(state, now))
        events.extend(self._button_events(state))
        return events

    def _direction_events(self, state: JoystickState, now: float) -> Iterator[JoystickEvent]:
        direction = state.stick.direction(self.joystick.deadzone)
        if direction != self._direction:
            self._direction = direction
            self._direction_since = now
            self._next_repeat = now + self.repeat_delay
            if direction != Direction.NEUTRAL:
                yield JoystickEvent(kind="direction", direction=direction, x=state.stick.x, y=state.stick.y)
            return
        # Held: repeat at a steady rate once the initial delay has passed.
        if direction != Direction.NEUTRAL and now >= self._next_repeat:
            self._next_repeat = now + self.repeat_interval
            yield JoystickEvent(kind="direction", direction=direction, repeat=True, x=state.stick.x, y=state.stick.y)

    def _button_events(self, state: JoystickState) -> Iterator[JoystickEvent]:
        for button in Button:
            event = state.event(button)
            previous = self._buttons.get(button, ButtonEvent.NONE)
            self._buttons[button] = event
            if event == ButtonEvent.NONE or event == previous:
                continue
            yield JoystickEvent(kind="button", button=button, event=event)

    def stream(self, poll_hz: float = DEFAULT_POLL_HZ, stop: Callable[[], bool] | None = None) -> Iterator[JoystickEvent]:
        """Blocking generator of events, for a simple script or a thread."""
        interval = 1.0 / max(1.0, float(poll_hz))
        while stop is None or not stop():
            started = time.monotonic()
            for event in self.poll(started):
                yield event
            time.sleep(max(0.0, interval - (time.monotonic() - started)))


__all__ = [
    "JoystickEvent",
    "JoystickReader",
    "DEFAULT_POLL_HZ",
    "DEFAULT_REPEAT_DELAY",
    "DEFAULT_REPEAT_INTERVAL",
]
