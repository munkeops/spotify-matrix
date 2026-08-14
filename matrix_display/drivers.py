"""How the panel is wired to the Pi.

The underlying library already speaks several wirings; what was missing was
any way to choose one, or to tell from the settings page which one you are
looking at. A driver here is a named wiring - the GPIO mapping plus the two
timing settings that follow from it - so moving the same install between a
Pi with an Adafruit HAT and a Pi wired straight to the header is picking a
name rather than remembering three numbers.

Only three settings belong to a driver. Everything else about the panel
(rows, columns, brightness, rotation, chain) is about the panel itself and
survives a change of wiring untouched.

The pin tables are BCM numbers, taken from the library's own
lib/hardware-mapping.c so that what the settings page draws is what the
code actually drives. For the HAT they are informational - the board does
that wiring for you - and for direct wiring they are the thing you follow
with jumper wires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Chosen when the settings do not match any driver we know, which is what
#: someone hand-tuning an unusual panel ends up with. Never applied over
#: anyone's values.
CUSTOM = "custom"


@dataclass(frozen=True)
class Driver:
    """One way of wiring a panel to the Pi."""

    id: str
    name: str
    summary: str
    #: The library's name for this wiring, passed through as-is.
    hardware_mapping: str
    #: A starting point, not a law. Higher is slower and steadier; the right
    #: value depends on the Pi, the cable length and the panel.
    gpio_slowdown: int
    #: True where the wiring cannot use the Pi's hardware pulse generator,
    #: which costs a lot of refresh and is the usual reason a panel looks dim.
    no_hardware_pulse: bool
    #: Signal name to BCM pin.
    pins: dict[str, int] = field(default_factory=dict)
    notes: str = ""


#: Signal order for display: colour first, then address lines, then timing.
#: Reading down this list is the order you would wire it in.
PIN_ORDER = (
    "R1", "G1", "B1", "R2", "G2", "B2",
    "A", "B", "C", "D", "E",
    "CLK", "LAT", "OE",
)

_REGULAR_PINS = {
    "R1": 11, "G1": 27, "B1": 7,
    "R2": 8, "G2": 9, "B2": 10,
    "A": 22, "B": 23, "C": 24, "D": 25, "E": 15,
    "CLK": 17, "LAT": 4, "OE": 18,
}

_HAT_PINS = {
    "R1": 5, "G1": 13, "B1": 6,
    "R2": 12, "G2": 16, "B2": 23,
    "A": 22, "B": 26, "C": 27, "D": 20, "E": 24,
    "CLK": 17, "LAT": 21, "OE": 4,
}

DIRECT = Driver(
    id="direct",
    name="Direct wiring",
    summary="Panel wired straight to the Pi's header, no HAT.",
    hardware_mapping="regular",
    # Nothing sits between the Pi and the panel, so the signal is clean and
    # the default rate usually holds. Raise it if the picture glitches.
    gpio_slowdown=1,
    # OE lands on GPIO 18, which can be driven by the hardware pulse
    # generator, so the panel gets the refresh it is capable of.
    no_hardware_pulse=False,
    pins=dict(_REGULAR_PINS),
    notes=(
        "E on GPIO 15 is what a 64x64 panel needs and a 32 row panel does not. "
        "Turn the Pi's onboard audio off (dtparam=audio=off) and blacklist "
        "snd_bcm2835: it holds the same hardware the panel needs for timing."
    ),
)

ADAFRUIT_HAT = Driver(
    id="adafruit-hat",
    name="Adafruit HAT",
    summary="The HAT or Bonnet as sold, without modification.",
    hardware_mapping="adafruit-hat",
    gpio_slowdown=4,
    # OE is on GPIO 4 on this board, which the pulse generator cannot reach.
    no_hardware_pulse=True,
    pins=dict(_HAT_PINS),
    notes=(
        "The board does the wiring, so these pins are for reference. Hardware "
        "pulsing is unavailable here, which caps the refresh rate: the panel "
        "will look dimmer than the same one wired directly."
    ),
)

ADAFRUIT_HAT_PWM = Driver(
    id="adafruit-hat-pwm",
    name="Adafruit HAT (PWM mod)",
    summary="The HAT with GPIO 4 bridged to GPIO 18.",
    hardware_mapping="adafruit-hat-pwm",
    gpio_slowdown=4,
    no_hardware_pulse=False,
    pins={**_HAT_PINS, "OE": 18},
    notes=(
        "Solder a wire between GPIO 4 and GPIO 18 on the HAT, then pick this. "
        "It moves OE onto a pin the hardware pulse generator can drive, which "
        "is the single biggest brightness win available to a HAT."
    ),
)

DRIVERS: tuple[Driver, ...] = (DIRECT, ADAFRUIT_HAT, ADAFRUIT_HAT_PWM)


def get(driver_id: str) -> Driver | None:
    for driver in DRIVERS:
        if driver.id == driver_id:
            return driver
    return None


def settings(driver_id: str) -> dict[str, Any]:
    """The matrix settings this driver implies, ready to merge into config.

    Empty for an unknown id, including "custom": a driver nobody selected
    must never quietly rewrite someone's tuning.
    """
    driver = get(driver_id)
    if driver is None:
        return {}
    return {
        "hardwareMapping": driver.hardware_mapping,
        "gpioSlowdown": driver.gpio_slowdown,
        "noHardwarePulse": driver.no_hardware_pulse,
    }


def detect(hardware_mapping: str) -> str:
    """Which driver these settings describe, or "custom".

    Matched on the mapping alone. Slowdown and pulsing are tuning that
    people are meant to adjust, and a panel does not stop being directly
    wired because someone raised its slowdown by one.
    """
    for driver in DRIVERS:
        if driver.hardware_mapping == (hardware_mapping or "").strip():
            return driver.id
    return CUSTOM
