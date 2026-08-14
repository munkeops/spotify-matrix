"""Wire protocol for the NULLLAB mini-joystick module.

Transcribed from the vendor's Arduino library (``JoystickHandle.h`` /
``JoystickHandle.cpp``, release V1.0.0 of nulllaborg/mini-joystick-module).
Every constant here mirrors that source; nothing is inferred.
"""

from __future__ import annotations

from enum import Enum, IntEnum

#: Fixed 7-bit I2C address of the module.
I2C_ADDRESS = 0x5A

#: Analog axes. The board carries one stick; the right-hand registers are
#: defined by the vendor library but unused on this hardware.
REG_LEFT_X = 0x10
REG_LEFT_Y = 0x11
REG_RIGHT_X = 0x12
REG_RIGHT_Y = 0x13

#: One register per button. Note the ordering is not alphabetical.
REG_BUTTON_OK = 0x20
REG_BUTTON_C = 0x21
REG_BUTTON_A = 0x22
REG_BUTTON_B = 0x23
REG_BUTTON_D = 0x24

#: Axis values span the full byte with the stick centred at 128.
AXIS_MIN = 0
AXIS_CENTER = 128
AXIS_MAX = 255

#: The module answers 0xFF when a register read fails.
INVALID = 0xFF


class Button(str, Enum):
    """Every button any supported input can report.

    The first five are the mini-joystick module's silkscreen, and they are
    all it ever sends. A gamepad reports those plus the shoulders, triggers
    and the rest; keeping one enum means one binding vocabulary, and a
    profile decides which of these a given device actually offers.
    """

    A = "a"
    B = "b"
    C = "c"
    D = "d"
    OK = "ok"

    # Gamepad only. The module has no register for any of these.
    LB = "lb"
    RB = "rb"
    LT = "lt"
    RT = "rt"
    START = "start"
    SELECT = "select"
    L3 = "l3"
    R3 = "r3"
    #: The Guide/PS button. A dedicated way into the menu, so a stick nudge
    #: does not have to be one.
    HOME = "home"


BUTTON_REGISTERS: dict[Button, int] = {
    Button.A: REG_BUTTON_A,
    Button.B: REG_BUTTON_B,
    Button.C: REG_BUTTON_C,
    Button.D: REG_BUTTON_D,
    Button.OK: REG_BUTTON_OK,
}


class ButtonEvent(IntEnum):
    """Button states reported by the module's onboard MCU."""

    PRESS_DOWN = 0
    PRESS_UP = 1
    PRESS_REPEAT = 2
    SINGLE_CLICK = 3
    DOUBLE_CLICK = 4
    LONG_PRESS_START = 5
    LONG_PRESS_HOLD = 6
    NONE = 8

    @classmethod
    def parse(cls, value: int) -> "ButtonEvent":
        try:
            return cls(value)
        except ValueError:
            # Anything unexpected, including the 0xFF error byte, reads as idle.
            return cls.NONE


#: Events that mean the button is physically down right now.
HELD_EVENTS = frozenset(
    {
        ButtonEvent.PRESS_DOWN,
        ButtonEvent.PRESS_REPEAT,
        ButtonEvent.LONG_PRESS_START,
        ButtonEvent.LONG_PRESS_HOLD,
    }
)


class Direction(str, Enum):
    NEUTRAL = "neutral"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


__all__ = [
    "I2C_ADDRESS",
    "REG_LEFT_X",
    "REG_LEFT_Y",
    "REG_RIGHT_X",
    "REG_RIGHT_Y",
    "REG_BUTTON_A",
    "REG_BUTTON_B",
    "REG_BUTTON_C",
    "REG_BUTTON_D",
    "REG_BUTTON_OK",
    "AXIS_MIN",
    "AXIS_CENTER",
    "AXIS_MAX",
    "INVALID",
    "Button",
    "ButtonEvent",
    "BUTTON_REGISTERS",
    "HELD_EVENTS",
    "Direction",
]
