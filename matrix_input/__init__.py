"""Input sources that drive the matrix games.

A Bluetooth or USB gamepad read through evdev produces the same controller
events as the I2C mini-joystick, so both go through one binding layer.
"""

from __future__ import annotations

from matrix_input.gamepad import (
    BUTTON_MAP,
    DEFAULT_DEADZONE,
    FakeGamepad,
    GamepadInfo,
    GamepadMapper,
    GamepadReader,
    evdev_available,
    list_gamepads,
)

__all__ = [
    "GamepadInfo",
    "GamepadMapper",
    "GamepadReader",
    "FakeGamepad",
    "list_gamepads",
    "evdev_available",
    "BUTTON_MAP",
    "DEFAULT_DEADZONE",
]
