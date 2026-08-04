"""High level access to the mini-joystick module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from mini_joystick.protocol import (
    AXIS_CENTER,
    AXIS_MAX,
    BUTTON_REGISTERS,
    HELD_EVENTS,
    INVALID,
    REG_LEFT_X,
    REG_LEFT_Y,
    Button,
    ButtonEvent,
    Direction,
)
from mini_joystick.transport import Transport

# Fraction of full deflection before an axis counts as pushed. The sticks rest
# near 128 but rarely exactly on it, so anything smaller chatters.
DEFAULT_DEADZONE = 0.35


@dataclass(frozen=True)
class Stick:
    """One stick sample, normalised to -1.0 … 1.0 with up as negative y.

    ``raw_x``/``raw_y`` are ``None`` when that read failed on the bus.
    """

    x: float
    y: float
    raw_x: int | None
    raw_y: int | None

    @property
    def magnitude(self) -> float:
        return max(abs(self.x), abs(self.y))

    def direction(self, deadzone: float = DEFAULT_DEADZONE) -> Direction:
        """The dominant axis, or NEUTRAL inside the deadzone."""
        if self.magnitude < deadzone:
            return Direction.NEUTRAL
        if abs(self.x) >= abs(self.y):
            return Direction.RIGHT if self.x > 0 else Direction.LEFT
        return Direction.DOWN if self.y > 0 else Direction.UP


@dataclass(frozen=True)
class JoystickState:
    stick: Stick
    buttons: dict[Button, ButtonEvent] = field(default_factory=dict)
    #: False when every register answered 0xFF, which means the module is gone.
    connected: bool = True

    def event(self, button: Button) -> ButtonEvent:
        return self.buttons.get(button, ButtonEvent.NONE)

    def is_held(self, button: Button) -> bool:
        return self.event(button) in HELD_EVENTS

    def clicked(self, button: Button) -> bool:
        return self.event(button) == ButtonEvent.SINGLE_CLICK

    def pressed(self) -> Iterator[Button]:
        for button in BUTTON_REGISTERS:
            if self.is_held(button):
                yield button


def _normalise(raw: int | None) -> float:
    """Map a 0…255 axis byte to -1.0…1.0 with the centre at zero.

    The full byte range is meaningful, so only a failed read (``None``) is
    treated as centred.
    """
    if raw is None:
        return 0.0
    span = AXIS_MAX - AXIS_CENTER
    return max(-1.0, min(1.0, (raw - AXIS_CENTER) / span))


class MiniJoystick:
    """Reads the stick and the five buttons over I2C.

    ``invert_x`` / ``invert_y`` let you match the physical orientation of the
    module once it is screwed into an enclosure.
    """

    def __init__(
        self,
        transport: Transport,
        *,
        deadzone: float = DEFAULT_DEADZONE,
        invert_x: bool = False,
        invert_y: bool = False,
    ) -> None:
        self.transport = transport
        self.deadzone = max(0.05, min(0.9, float(deadzone)))
        self.invert_x = invert_x
        self.invert_y = invert_y

    def read_stick(self) -> Stick:
        raw_x = self.transport.read_register(REG_LEFT_X)
        raw_y = self.transport.read_register(REG_LEFT_Y)
        x = _normalise(raw_x)
        y = _normalise(raw_y)
        return Stick(
            x=-x if self.invert_x else x,
            y=-y if self.invert_y else y,
            raw_x=raw_x,
            raw_y=raw_y,
        )

    def read_button(self, button: Button) -> ButtonEvent:
        value = self.transport.read_register(BUTTON_REGISTERS[button])
        # A failed read and the module's own 0xFF error byte both mean "idle".
        return ButtonEvent.NONE if value is None else ButtonEvent.parse(value)

    def read(self) -> JoystickState:
        """One full sample: both axes and all five buttons."""
        stick = self.read_stick()
        buttons = {button: self.read_button(button) for button in BUTTON_REGISTERS}
        connected = stick.raw_x is not None or stick.raw_y is not None
        return JoystickState(stick=stick, buttons=buttons, connected=connected)

    def direction(self) -> Direction:
        return self.read_stick().direction(self.deadzone)

    def present(self) -> bool:
        """True when the module answers on the bus."""
        return self.transport.read_register(REG_LEFT_X) is not None

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "MiniJoystick":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = ["MiniJoystick", "JoystickState", "Stick", "DEFAULT_DEADZONE"]
