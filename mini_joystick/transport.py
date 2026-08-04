"""I2C transports for the mini-joystick module.

The vendor library writes the register byte, ends the transmission, then issues
a separate read. :class:`SMBusTransport` reproduces that exact pair by default
so the module's MCU sees the transaction shape it was written for.
"""

from __future__ import annotations

import errno
import threading
from typing import Protocol

from mini_joystick.protocol import I2C_ADDRESS


class TransportError(RuntimeError):
    """Raised when the bus is unusable, as opposed to a single bad read."""


def _open_error(bus: int, exc: OSError) -> str:
    """Say what actually went wrong, because the fixes are entirely different."""
    if exc.errno == errno.ENOENT:
        return (
            f"I2C bus {bus} does not exist (/dev/i2c-{bus} is missing). Enable I2C with "
            "'sudo raspi-config' (Interface Options -> I2C), make sure 'dtparam=i2c_arm=on' is in "
            "/boot/firmware/config.txt, then REBOOT - the device node only appears after a reboot. "
            "Verify with 'ls /dev/i2c-*' on the host."
        )
    if exc.errno in (errno.EACCES, errno.EPERM):
        return (
            f"Permission denied opening I2C bus {bus}. Add the user to the i2c group "
            "('sudo usermod -aG i2c $USER' then log out and back in), or run the container privileged."
        )
    return f"Could not open I2C bus {bus}: {exc}"


class Transport(Protocol):
    """Anything that can read one register byte from the module.

    Returns ``None`` when the read itself failed, which is distinct from a
    valid 0xFF byte. The axes use the full 0-255 range, so a sentinel value
    would swallow full deflection.
    """

    def read_register(self, register: int) -> int | None: ...

    def close(self) -> None: ...


class SMBusTransport:
    """Talks to the module over a Linux I2C bus via ``smbus2``.

    ``combined`` selects the transaction shape:

    * ``False`` (default) mirrors the Arduino library — write the register,
      STOP, then read a byte. Safest, because it is what the vendor firmware
      is known to answer.
    * ``True`` uses a repeated START (``read_byte_data``). One transaction
      instead of two, but only correct if the firmware tolerates it.
    """

    def __init__(self, bus: int = 1, address: int = I2C_ADDRESS, *, combined: bool = False) -> None:
        try:
            from smbus2 import SMBus
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise TransportError(
                "smbus2 is required to talk to the mini-joystick. "
                "Install it with 'pip install smbus2' and enable I2C with 'sudo raspi-config'."
            ) from exc

        self.address = address
        self.combined = combined
        self._lock = threading.Lock()
        try:
            self._bus = SMBus(bus)
        except OSError as exc:  # pragma: no cover - depends on the host
            raise TransportError(_open_error(bus, exc)) from exc

    def read_register(self, register: int) -> int | None:
        with self._lock:
            try:
                if self.combined:
                    return int(self._bus.read_byte_data(self.address, register)) & 0xFF
                self._bus.write_byte(self.address, register)
                return int(self._bus.read_byte(self.address)) & 0xFF
            except OSError:
                # A NAK or a bus blip. None, not 0xFF, so a full-deflection
                # axis reading of 255 is never mistaken for a failure.
                return None

    def close(self) -> None:
        with self._lock:
            try:
                self._bus.close()
            except OSError:  # pragma: no cover - nothing useful to do
                pass


class FakeTransport:
    """In-memory transport used by the tests and for development off-Pi."""

    def __init__(self, registers: dict[int, int] | None = None) -> None:
        self.registers: dict[int, int] = dict(registers or {})
        self.reads: list[int] = []
        self.closed = False
        self.fail_on: set[int] = set()

    def read_register(self, register: int) -> int | None:
        self.reads.append(register)
        if register in self.fail_on or register not in self.registers:
            return None
        return self.registers[register] & 0xFF

    def set(self, register: int, value: int) -> None:
        self.registers[register] = value & 0xFF

    def close(self) -> None:
        self.closed = True


__all__ = [
    "Transport",
    "TransportError",
    "SMBusTransport",
    "FakeTransport",
    "smbus_available",
    "available_buses",
    "scan_bus",
]


def smbus_available() -> bool:
    """Whether the I2C library is installed at all."""
    try:
        import smbus2  # noqa: F401
    except ImportError:
        return False
    return True


def available_buses() -> list[int]:
    """Bus numbers the kernel is exposing, from /dev/i2c-*."""
    from pathlib import Path

    buses: list[int] = []
    for node in Path("/dev").glob("i2c-*"):
        suffix = node.name.split("-", 1)[-1]
        if suffix.isdigit():
            buses.append(int(suffix))
    return sorted(buses)


def scan_bus(bus: int) -> list[int]:
    """Addresses that answer on a bus, like ``i2cdetect -y <bus>``.

    Raises :class:`TransportError` when the bus cannot be opened at all, which
    is a different problem from an empty bus.
    """
    try:
        from smbus2 import SMBus
    except ImportError as exc:
        raise TransportError("smbus2 is not installed, so the I2C bus cannot be scanned.") from exc

    try:
        handle = SMBus(bus)
    except OSError as exc:
        raise TransportError(f"Could not open I2C bus {bus}: {exc}") from exc

    found: list[int] = []
    try:
        for address in range(0x03, 0x78):
            try:
                handle.read_byte(address)
            except OSError:
                continue
            found.append(address)
    finally:
        handle.close()
    return found
