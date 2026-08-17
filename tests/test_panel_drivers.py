"""Panel wiring drivers.

The pin numbers here are checked against hzeller/rpi-rgb-led-matrix's own
lib/hardware-mapping.c, because a settings page that draws a pin table is
only useful if the table is the one the code drives.
"""

import pytest

from matrix_display import drivers


def test_direct_wiring_matches_the_libraries_regular_mapping():
    """Taken from lib/hardware-mapping.c, "regular"."""
    assert drivers.DIRECT.hardware_mapping == "regular"
    assert drivers.DIRECT.pins == {
        "R1": 11, "G1": 27, "B1": 7,
        "R2": 8, "G2": 9, "B2": 10,
        "A": 22, "B": 23, "C": 24, "D": 25, "E": 15,
        "CLK": 17, "LAT": 4, "OE": 18,
    }


def test_the_hat_matches_the_libraries_adafruit_mapping():
    assert drivers.ADAFRUIT_HAT.pins == {
        "R1": 5, "G1": 13, "B1": 6,
        "R2": 12, "G2": 16, "B2": 23,
        "A": 22, "B": 26, "C": 27, "D": 20, "E": 24,
        "CLK": 17, "LAT": 21, "OE": 4,
    }


def test_the_pwm_mod_only_moves_output_enable():
    """That single wire is the whole modification, and the whole benefit."""
    plain = drivers.ADAFRUIT_HAT.pins
    modified = drivers.ADAFRUIT_HAT_PWM.pins

    differences = {pin for pin in plain if plain[pin] != modified[pin]}

    assert differences == {"OE"}
    assert modified["OE"] == 18


@pytest.mark.parametrize("driver", drivers.DRIVERS, ids=lambda d: d.id)
def test_every_driver_wires_every_signal(driver):
    """A 64x64 panel needs all fourteen, E included."""
    assert set(driver.pins) == set(drivers.PIN_ORDER)


@pytest.mark.parametrize("driver", drivers.DRIVERS, ids=lambda d: d.id)
def test_pulsing_follows_where_output_enable_lands(driver):
    """The Pi's pulse generator drives GPIO 18 and nothing else, so this is
    not a preference: it is a consequence of the wiring."""
    assert driver.no_hardware_pulse is (driver.pins["OE"] != 18)


@pytest.mark.parametrize("driver", drivers.DRIVERS, ids=lambda d: d.id)
def test_no_two_signals_share_a_pin(driver):
    assert len(set(driver.pins.values())) == len(driver.pins)


def test_direct_wiring_starts_at_the_slowdown_a_pi_4_needs():
    """A clean direct connection is not a faster one. The library picks 2 on
    a Pi 4 for itself (options-initialize.cc), and starting below that gave
    a shaking picture on hardware that the standalone demo drove fine."""
    assert drivers.DIRECT.gpio_slowdown >= 2


def test_a_driver_carries_only_the_three_settings_that_follow_from_wiring():
    """Rows, brightness and rotation belong to the panel, not to how it is
    plugged in, and must survive switching between them."""
    assert set(drivers.settings("direct")) == {"hardwareMapping", "gpioSlowdown", "noHardwarePulse"}


def test_switching_drivers_changes_the_mapping_and_the_pulsing():
    hat = drivers.settings("adafruit-hat")
    direct = drivers.settings("direct")

    assert hat["hardwareMapping"] == "adafruit-hat" and hat["noHardwarePulse"] is True
    assert direct["hardwareMapping"] == "regular" and direct["noHardwarePulse"] is False


def test_an_unknown_driver_rewrites_nothing():
    """Including "custom": someone hand-tuning an odd panel keeps their
    values, rather than having a driver nobody chose applied over them."""
    assert drivers.settings("custom") == {}
    assert drivers.settings("nonsense") == {}
    assert drivers.get("custom") is None


def test_the_active_driver_is_read_back_from_the_mapping():
    """No second copy of the choice to fall out of step with the settings."""
    for driver in drivers.DRIVERS:
        assert drivers.detect(driver.hardware_mapping) == driver.id
    assert drivers.detect("regular-pi1") == drivers.CUSTOM
    assert drivers.detect("") == drivers.CUSTOM


def test_tuning_the_slowdown_does_not_make_a_panel_custom():
    """Slowdown is meant to be adjusted; a panel does not stop being
    directly wired because someone raised it by one."""
    assert drivers.detect(drivers.DIRECT.hardware_mapping) == "direct"


def test_changing_driver_restarts_the_runtime():
    """Every setting a driver writes is a constructor argument to the panel;
    saving one without a restart would move the setting and not the matrix."""
    from src.api.http.rest.config import RESTART_ON_CHANGE

    assert set(drivers.settings("direct")) <= set(RESTART_ON_CHANGE)


def test_the_image_ships_every_top_level_package():
    """A package the API imports but the Dockerfile does not copy works
    everywhere except the thing that runs on the Pi."""
    from pathlib import Path

    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    packages = [
        path.parent.name
        for path in Path(".").glob("matrix_*/__init__.py")
    ]

    assert packages, "found no matrix_* packages to check"
    for package in packages:
        assert f"COPY {package} ./{package}" in dockerfile, f"{package} is missing from the image"


def test_the_settings_page_offers_the_drivers_the_server_defines():
    """The picker must not carry its own copy of the pin tables."""
    from pathlib import Path

    component = Path("web/src/components/DriverSelect.tsx").read_text(encoding="utf-8")

    assert "getMatrixDrivers" in component, "the definitions are fetched"
    for driver in drivers.DRIVERS:
        # The library's mapping names appearing here would mean a second
        # copy of the definitions, free to drift from the server's.
        assert driver.hardware_mapping not in component


def test_an_optional_service_cannot_block_the_default_stack():
    """Compose interpolates the whole file before it filters profiles, so a
    required variable on a profiled service fails every build and every up
    for people who never asked for that service."""
    from pathlib import Path

    lines = Path("docker-compose.yml").read_text(encoding="utf-8").splitlines()
    # Comments are free to mention the syntax; compose only reads the rest.
    settings = [line for line in lines if not line.lstrip().startswith("#")]

    offenders = [line.strip() for line in settings if ":?" in line]

    assert not offenders, f"a required variable breaks compose for everyone: {offenders}"


def test_the_app_list_does_not_render_a_frame_per_card():
    """Previewing every app on the page meant a config fetch and a full
    frame rendered on the Pi for each one, on every refresh - competing for
    the CPU that clocks the panel, which is visible as a shaking picture."""
    from pathlib import Path

    for page in ("web/src/pages/Apps.tsx", "web/src/components/AppConfigDrawer.tsx"):
        source = Path(page).read_text(encoding="utf-8")
        assert "previewApp(" not in source, f"{page} renders frames on the Pi to draw itself"


def test_the_timing_knobs_reach_the_runtime():
    """A setting the panel page offers but the runtime never passes is a
    dial wired to nothing."""
    from pathlib import Path

    runtime = Path("src/domain/services/runtime_service.py").read_text(encoding="utf-8")
    script = Path("spotify_matrix.py").read_text(encoding="utf-8")

    for flag, option in (
        ("--pwm-lsb-nanoseconds", "pwm_lsb_nanoseconds"),
        ("--pwm-dither-bits", "pwm_dither_bits"),
        ("--panel-type", "panel_type"),
    ):
        assert flag in runtime, f"{flag} is never passed to the runtime"
        assert f"options.{option}" in script, f"{option} never reaches the panel driver"


def test_the_timing_knobs_restart_the_matrix():
    """They are constructor arguments like the rest; saving one without a
    restart moves the setting and not the panel."""
    from src.api.http.rest.config import RESTART_ON_CHANGE

    assert {"pwmLsbNanoseconds", "pwmDitherBits", "panelType"} <= set(RESTART_ON_CHANGE)


def test_an_idle_module_is_not_reported_as_missing():
    """The first poll of a healthy module emits no event - there is no
    transition to report - so a service watching only events called a
    working joystick disconnected until someone pressed something."""
    from mini_joystick.events import JoystickReader

    from mini_joystick.device import JoystickState, Stick

    class Idle:
        """A module sitting centred, answering the bus, untouched."""

        deadzone = 0.3

        def read(self):
            return JoystickState(stick=Stick(x=0.0, y=0.0, raw_x=128, raw_y=128), connected=True)

    reader = JoystickReader(Idle())

    assert reader.poll(0.0) == [], "a healthy first read reports no transition"
    assert reader.connected is True, "but it knows the module answered"


def test_switching_wiring_remembers_what_the_old_one_was_tuned_to():
    """Tuning a panel takes measurement and patience, and it is specific to
    how the panel is plugged in. Losing it on every swap would mean finding
    it again each time."""
    hat = {
        "hardwareMapping": "adafruit-hat-pwm", "gpioSlowdown": 2, "noHardwarePulse": False,
        "pwmBits": 10, "pwmDitherBits": 1, "pwmLsbNanoseconds": 130,
        "limitRefreshRateHz": 250, "panelType": "", "brightness": 65, "rotation": 270,
    }

    moved = drivers.switch(hat, "direct")

    assert moved["hardwareMapping"] == "regular"
    assert moved["profiles"]["adafruit-hat-pwm"]["limitRefreshRateHz"] == 250
    assert moved["profiles"]["adafruit-hat-pwm"]["pwmDitherBits"] == 1

    back = drivers.switch(moved, "adafruit-hat-pwm")

    assert back["hardwareMapping"] == "adafruit-hat-pwm"
    assert back["limitRefreshRateHz"] == 250, "the tuning came back"
    assert back["pwmDitherBits"] == 1


def test_a_swap_leaves_the_panel_and_its_content_alone():
    """Rows, brightness and rotation describe the panel and what is on it,
    not the board underneath, and must survive changing boards."""
    before = {
        "hardwareMapping": "regular", "gpioSlowdown": 3, "noHardwarePulse": False,
        "rows": 64, "cols": 64, "brightness": 42, "rotation": 270,
    }

    after = drivers.switch(before, "adafruit-hat")

    assert (after["brightness"], after["rotation"], after["rows"]) == (42, 270, 64)
    assert not set(drivers.PROFILE_FIELDS) & {"rows", "cols", "brightness", "rotation"}


def test_a_wiring_never_used_starts_from_its_own_values():
    before = {"hardwareMapping": "regular", "gpioSlowdown": 3, "noHardwarePulse": False}

    after = drivers.switch(before, "adafruit-hat")

    assert after["noHardwarePulse"] is True, "the HAT cannot pulse in hardware"
    assert after["gpioSlowdown"] == drivers.ADAFRUIT_HAT.gpio_slowdown


def test_switching_is_one_call_not_a_page_assembling_settings():
    """A half-applied wiring - a HAT's mapping with a directly wired panel's
    timing - drives nothing correctly, so it must not be possible to save
    one without the others."""
    from pathlib import Path

    component = Path("web/src/components/DriverSelect.tsx").read_text(encoding="utf-8")

    assert "switchMatrixDriver" in component
