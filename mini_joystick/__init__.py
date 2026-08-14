"""Python SDK for the NULLLAB mini-joystick module.

The module is an I2C device at 0x5A carrying one analog stick and five buttons
(A, B, C, D, and OK under the stick). Its onboard MCU does the debouncing and
reports click, double-click and long-press states, so this SDK is a thin,
well-typed layer over those registers plus the edge detection a UI wants.

    from mini_joystick import MiniJoystick, SMBusTransport, Button

    with MiniJoystick(SMBusTransport(bus=1)) as pad:
        state = pad.read()
        print(state.stick.direction(), state.is_held(Button.A))

Hardware note: the module runs at 5V and its I2C lines idle at 5V, while the
Pi's GPIO is 3.3V tolerant only. Use a bidirectional level shifter on SDA and
SCL. See ``docs/mini-joystick.md``.
"""

from __future__ import annotations

from mini_joystick.device import DEFAULT_DEADZONE, JoystickState, MiniJoystick, Stick
from mini_joystick.events import (
    DEFAULT_POLL_HZ,
    DEFAULT_REPEAT_DELAY,
    DEFAULT_REPEAT_INTERVAL,
    JoystickEvent,
    JoystickReader,
)
from mini_joystick.protocol import (
    AXIS_CENTER,
    AXIS_MAX,
    AXIS_MIN,
    BUTTON_REGISTERS,
    HELD_EVENTS,
    I2C_ADDRESS,
    INVALID,
    Button,
    ButtonEvent,
    Direction,
)
from mini_joystick.transport import (
    FakeTransport,
    SMBusTransport,
    Transport,
    TransportError,
    available_buses,
    scan_bus,
    smbus_available,
)

__version__ = "1.0.0"

__all__ = [
    "MiniJoystick",
    "JoystickState",
    "JoystickReader",
    "JoystickEvent",
    "Stick",
    "Button",
    "ButtonEvent",
    "Direction",
    "Transport",
    "SMBusTransport",
    "FakeTransport",
    "TransportError",
    "available_buses",
    "scan_bus",
    "smbus_available",
    "I2C_ADDRESS",
    "AXIS_MIN",
    "AXIS_CENTER",
    "AXIS_MAX",
    "INVALID",
    "BUTTON_REGISTERS",
    "HELD_EVENTS",
    "DEFAULT_DEADZONE",
    "DEFAULT_POLL_HZ",
    "DEFAULT_REPEAT_DELAY",
    "DEFAULT_REPEAT_INTERVAL",
    "__version__",
]
