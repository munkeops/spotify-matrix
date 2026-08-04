from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

import matrix_games as mg
from matrix_input.gamepad import (
    BTN_SELECT,
    BTN_THUMBL,
    BTN_THUMBR,
    BTN_TL,
    BTN_TL2,
    BTN_TR,
    BTN_TR2,
    ABS_HAT0X,
    ABS_HAT0Y,
    ABS_X,
    ABS_Y,
    BTN_EAST,
    BTN_NORTH,
    BTN_SOUTH,
    BTN_START,
    BTN_WEST,
    EV_ABS,
    EV_KEY,
    FakeGamepad,
    GamepadMapper,
)
from mini_joystick.bindings import game_action, shell_action
from mini_joystick.protocol import Button, ButtonEvent, Direction

GAMES = mg.discover()


def mapper() -> GamepadMapper:
    pad = GamepadMapper(deadzone=0.5)
    pad.configure_axis(ABS_X, -32768, 32767)
    pad.configure_axis(ABS_Y, -32768, 32767)
    return pad


# --- button mapping ------------------------------------------------------


@pytest.mark.parametrize(
    "code,button",
    [
        (BTN_SOUTH, Button.A),
        (BTN_EAST, Button.B),
        (BTN_WEST, Button.C),
        (BTN_NORTH, Button.D),
        (BTN_START, Button.START),
        (BTN_SELECT, Button.SELECT),
        (BTN_TL, Button.LB),
        (BTN_TR, Button.RB),
        (BTN_TL2, Button.LT),
        (BTN_TR2, Button.RT),
        (BTN_THUMBL, Button.L3),
        (BTN_THUMBR, Button.R3),
    ],
)
def test_every_pad_button_gets_its_own_control(code, button):
    events = mapper().feed(EV_KEY, code, 1)
    assert [(e.button, e.event) for e in events] == [(button, ButtonEvent.PRESS_DOWN)]


def test_release_and_kernel_repeat():
    pad = mapper()
    assert pad.feed(EV_KEY, BTN_SOUTH, 0)[0].event == ButtonEvent.PRESS_UP
    # Value 2 is the kernel auto-repeating; the binding does its own repeat.
    assert pad.feed(EV_KEY, BTN_SOUTH, 2) == []


def test_unknown_buttons_are_ignored():
    assert mapper().feed(EV_KEY, 0x2FF, 1) == []
    assert mapper().feed(0x04, BTN_SOUTH, 1) == [], "only key and abs events matter"


# --- directions ----------------------------------------------------------


@pytest.mark.parametrize(
    "code,value,expected",
    [
        (ABS_HAT0X, 1, Direction.RIGHT),
        (ABS_HAT0X, -1, Direction.LEFT),
        (ABS_HAT0Y, 1, Direction.DOWN),
        (ABS_HAT0Y, -1, Direction.UP),
    ],
)
def test_the_dpad_gives_directions(code, value, expected):
    events = mapper().feed(EV_ABS, code, value)
    assert [e.direction for e in events] == [expected]


def test_the_stick_uses_its_reported_range():
    pad = mapper()
    assert pad.feed(EV_ABS, ABS_X, 32767)[0].direction == Direction.RIGHT
    assert pad.feed(EV_ABS, ABS_X, 0) == [], "returning to centre is not a new direction event"
    assert pad.feed(EV_ABS, ABS_X, -32768)[0].direction == Direction.LEFT


def test_a_resting_stick_is_neutral():
    pad = mapper()
    # Well inside the deadzone.
    assert pad.feed(EV_ABS, ABS_X, 2000) == []
    assert pad.held_direction() == Direction.NEUTRAL


def test_a_direction_fires_once_while_held():
    pad = mapper()
    assert len(pad.feed(EV_ABS, ABS_HAT0X, 1)) == 1
    # The kernel repeats the same value; auto-repeat is the binding's job.
    assert pad.feed(EV_ABS, ABS_HAT0X, 1) == []


def test_the_dpad_wins_over_a_drifting_stick():
    pad = mapper()
    pad.feed(EV_ABS, ABS_X, 32767)
    events = pad.feed(EV_ABS, ABS_HAT0Y, -1)
    assert [e.direction for e in events] == [Direction.UP]


def test_a_diagonal_picks_the_dominant_axis():
    pad = mapper()
    pad.feed(EV_ABS, ABS_Y, 20000)
    events = pad.feed(EV_ABS, ABS_X, 32767)
    assert [e.direction for e in events] == [Direction.RIGHT]


# --- the pad drives games through the shared binding ---------------------


def test_a_pad_press_becomes_a_game_action():
    pad = mapper()
    fire = pad.feed(EV_KEY, BTN_SOUTH, 1)[0]
    left = pad.feed(EV_ABS, ABS_HAT0X, -1)[0]

    assert game_action(fire, set(GAMES["invaders"].actions)) == "fire"
    assert game_action(fire, set(GAMES["tetris"].actions)) == "hardDrop"
    assert game_action(fire, set(GAMES["flappy"].actions)) == "flap"
    assert game_action(left, set(GAMES["pacman"].actions)) == "left"


def test_start_pauses_and_the_pad_walks_plugins():
    pad = mapper()
    start = pad.feed(EV_KEY, BTN_START, 1)[0]
    right = pad.feed(EV_ABS, ABS_HAT0X, 1)[0]

    assert game_action(start, set(GAMES["snake"].actions)) == "togglePause"
    assert shell_action(right).kind == "next"


def test_fake_pad_replays_a_script():
    pad = FakeGamepad([(EV_KEY, BTN_SOUTH, 1), (EV_ABS, ABS_HAT0X, 1)])
    events = list(pad.poll())
    assert [event.kind for event in events] == ["button", "direction"]
    assert list(pad.poll()) == [], "events are drained once"


# --- service -------------------------------------------------------------


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.runtime_service",
    "src.domain.services.widget_registry_service",
    "src.domain.services.joystick_service",
    "src.domain.services.gamepad_service",
]


def reload_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    game_module = importlib.import_module("src.domain.services.game_service")
    importlib.import_module("src.domain.services.joystick_service")
    gamepad_module = importlib.import_module("src.domain.services.gamepad_service")
    return config_module, game_module, gamepad_module


def test_the_pad_drives_the_running_game(tmp_path, monkeypatch):
    config_module, game_module, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.invaders"
    config_module.config_service.save_config(config)

    pad = FakeGamepad([(EV_ABS, ABS_HAT0X, -1), (EV_KEY, BTN_SOUTH, 1)])
    for event in pad.poll():
        gamepad_module.gamepad_service._dispatch(event)

    actions, _ = mg.read_commands(game_module.game_service.input_path("invaders"), 0)
    assert actions == ["left", "fire"]


def test_the_service_reports_what_to_do(tmp_path, monkeypatch):
    _, _, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    state = gamepad_module.gamepad_service.state()

    assert state["enabled"] is False
    assert state["running"] is False
    assert isinstance(state["devices"], list)
    assert state["advice"], "there is always a next step to suggest"


def test_the_thread_starts_and_stops_against_a_fake_pad(tmp_path, monkeypatch):
    config_module, _, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.gamepad.enabled = True
    config_module.config_service.save_config(config)

    service = gamepad_module.gamepad_service
    service.reader_factory = lambda: FakeGamepad(name="Test Pad")
    try:
        assert service.start()["running"] is True
        deadline = __import__("time").monotonic() + 2.0
        while not service.connected and __import__("time").monotonic() < deadline:
            __import__("time").sleep(0.02)
        assert service.connected is True
        assert service.device_name == "Test Pad"
    finally:
        state = service.stop()
    assert state["running"] is False


def test_no_controller_is_not_an_error(tmp_path, monkeypatch):
    config_module, _, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.gamepad.enabled = True
    config_module.config_service.save_config(config)

    service = gamepad_module.gamepad_service
    service.reader_factory = lambda: None
    try:
        service.start()
        __import__("time").sleep(0.2)
        assert service.connected is False
        assert service.running() is True, "it should keep waiting for a pad, not die"
    finally:
        service.stop()


def test_a_paired_pad_with_no_input_device_blames_ertm(monkeypatch):
    """BlueZ connected but no evdev node is the Xbox ERTM signature."""
    import src.domain.services.bluetooth_service as bt_module
    from src.domain.services.gamepad_service import GamepadService

    service = GamepadService()
    monkeypatch.setattr("src.domain.services.gamepad_service.evdev_available", lambda: True)
    monkeypatch.setattr(
        service,
        "_bluetooth_controllers",
        lambda: [{"name": "Xbox Wireless Controller", "connected": True, "role": "controller"}],
    )

    monkeypatch.setattr(bt_module, "ertm_disabled", lambda: False)
    advice = service._advice([])
    assert "ERTM" in advice
    assert "rebuilding the container will not change it" in advice

    # With ERTM already off the problem is elsewhere, so point at the driver
    # and the device node rather than blaming ERTM again.
    monkeypatch.setattr(bt_module, "ertm_disabled", lambda: True)
    advice = service._advice([])
    assert "already off" in advice
    assert "/dev/input/event" in advice
    assert "xpadneo" in advice

    # Not being able to read the setting is not the same as it being fine.
    monkeypatch.setattr(bt_module, "ertm_disabled", lambda: None)
    advice = service._advice([])
    assert "not readable" in advice
    assert "disable_ertm" in advice


def test_no_bluetooth_controller_gives_the_plain_hint(monkeypatch):
    from src.domain.services.gamepad_service import GamepadService

    service = GamepadService()
    monkeypatch.setattr("src.domain.services.gamepad_service.evdev_available", lambda: True)
    monkeypatch.setattr(service, "_bluetooth_controllers", lambda: [])

    assert "pairing mode" in service._advice([])


def test_the_cross_check_survives_bluetooth_being_unavailable(monkeypatch):
    from src.domain.services.gamepad_service import GamepadService

    service = GamepadService()
    monkeypatch.setattr("src.domain.services.gamepad_service.evdev_available", lambda: True)
    monkeypatch.setattr(
        "src.domain.services.bluetooth_service.bluetooth_service.list_devices",
        lambda: (_ for _ in ()).throw(OSError("no bluetoothctl")),
    )

    assert service._advice([]), "a broken bluetooth stack must not break this panel"


# --- holding, which the I2C module gets from its MCU ---------------------


def test_a_held_direction_repeats():
    """Without this a held stick moves once, so Breakout was unplayable."""
    pad = mapper()
    assert [e.direction for e in pad.feed(EV_ABS, ABS_HAT0X, -1, now=0.0)] == [Direction.LEFT]

    assert pad.tick(0.1) == [], "nothing until the initial delay passes"

    first = pad.tick(0.35)
    assert [e.direction for e in first] == [Direction.LEFT]
    assert first[0].repeat is True

    assert pad.tick(0.36) == [], "repeats are spaced, not every poll"
    assert [e.direction for e in pad.tick(0.5)] == [Direction.LEFT]


def test_releasing_stops_the_repeat():
    pad = mapper()
    pad.feed(EV_ABS, ABS_HAT0X, -1, now=0.0)
    pad.tick(0.4)
    pad.feed(EV_ABS, ABS_HAT0X, 0, now=0.5)

    assert pad.tick(1.0) == []


def test_changing_direction_restarts_the_delay():
    pad = mapper()
    pad.feed(EV_ABS, ABS_HAT0X, -1, now=0.0)
    pad.tick(0.4)
    pad.feed(EV_ABS, ABS_HAT0X, 1, now=0.5)

    assert pad.tick(0.55) == [], "a fresh push waits again before repeating"
    assert [e.direction for e in pad.tick(0.85)] == [Direction.RIGHT]


def test_a_held_button_becomes_a_long_press():
    """The quick wheel opens on a long press, which a pad never reported."""
    pad = mapper()
    assert [e.event for e in pad.feed(EV_KEY, BTN_START, 1, now=0.0)] == [ButtonEvent.PRESS_DOWN]

    assert pad.tick(0.2) == []
    assert [e.event for e in pad.tick(0.6)] == [ButtonEvent.LONG_PRESS_START]
    assert pad.tick(1.5) == [], "a long press fires once, not forever"


def test_a_quick_tap_is_not_a_long_press():
    pad = mapper()
    pad.feed(EV_KEY, BTN_START, 1, now=0.0)
    pad.feed(EV_KEY, BTN_START, 0, now=0.1)

    assert pad.tick(2.0) == []


def test_the_same_button_can_be_long_pressed_twice():
    pad = mapper()
    pad.feed(EV_KEY, BTN_START, 1, now=0.0)
    assert pad.tick(0.6)
    pad.feed(EV_KEY, BTN_START, 0, now=0.7)

    pad.feed(EV_KEY, BTN_START, 1, now=1.0)
    assert [e.event for e in pad.tick(1.6)] == [ButtonEvent.LONG_PRESS_START]


def test_a_long_press_opens_the_wheel_from_a_pad(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    config_module, game_module, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.breakout"
    config_module.config_service.save_config(config)

    pad = FakeGamepad([(EV_KEY, BTN_START, 1)])
    for event in pad.poll(now=0.0):
        gamepad_module.gamepad_service._dispatch(event)
    for event in pad.poll(now=1.0):
        gamepad_module.gamepad_service._dispatch(event)

    state = read_shell_state(game_module.game_service.state_dir / "shell.json")
    assert state["wheel"]["open"] is True, "the wheel must open from a controller too"


def test_holding_left_keeps_moving_the_paddle(tmp_path, monkeypatch):
    _, game_module, gamepad_module = reload_stack(monkeypatch, tmp_path / "data")
    config_module = importlib.import_module("src.domain.services.config_service")
    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.breakout"
    config_module.config_service.save_config(config)

    pad = FakeGamepad([(EV_ABS, ABS_HAT0X, -1)])
    for moment in (0.0, 0.35, 0.45, 0.55):
        for event in pad.poll(now=moment):
            gamepad_module.gamepad_service._dispatch(event)

    actions, _ = mg.read_commands(game_module.game_service.input_path("breakout"), 0)
    assert actions.count("left") >= 3, f"a held stick should keep moving, got {actions}"
