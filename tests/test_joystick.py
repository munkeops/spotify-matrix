from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from matrix_games import GAMES
from mini_joystick import (
    AXIS_CENTER,
    AXIS_MAX,
    AXIS_MIN,
    BUTTON_REGISTERS,
    INVALID,
    Button,
    ButtonEvent,
    Direction,
    FakeTransport,
    JoystickReader,
    MiniJoystick,
)
from mini_joystick.bindings import ShellAction, game_action, shell_action
from mini_joystick.events import JoystickEvent
from mini_joystick.protocol import I2C_ADDRESS, REG_LEFT_X, REG_LEFT_Y


def make(stick: tuple[int, int] = (AXIS_CENTER, AXIS_CENTER), **buttons: int) -> tuple[MiniJoystick, FakeTransport]:
    transport = FakeTransport({REG_LEFT_X: stick[0], REG_LEFT_Y: stick[1]})
    for button, register in BUTTON_REGISTERS.items():
        transport.set(register, buttons.get(button.value, ButtonEvent.NONE))
    return MiniJoystick(transport), transport


# --- protocol -----------------------------------------------------------


def test_registers_match_the_vendor_library():
    # Guards against a typo silently pointing at the wrong button.
    assert I2C_ADDRESS == 0x5A
    assert (REG_LEFT_X, REG_LEFT_Y) == (0x10, 0x11)
    assert BUTTON_REGISTERS[Button.OK] == 0x20
    assert BUTTON_REGISTERS[Button.C] == 0x21
    assert BUTTON_REGISTERS[Button.A] == 0x22
    assert BUTTON_REGISTERS[Button.B] == 0x23
    assert BUTTON_REGISTERS[Button.D] == 0x24


def test_unknown_button_values_read_as_idle():
    assert ButtonEvent.parse(0) == ButtonEvent.PRESS_DOWN
    assert ButtonEvent.parse(4) == ButtonEvent.DOUBLE_CLICK
    assert ButtonEvent.parse(INVALID) == ButtonEvent.NONE
    assert ButtonEvent.parse(99) == ButtonEvent.NONE


# --- device -------------------------------------------------------------


def test_centred_stick_is_neutral():
    pad, _ = make()
    stick = pad.read_stick()
    assert stick.x == 0.0 and stick.y == 0.0
    assert stick.direction() == Direction.NEUTRAL


@pytest.mark.parametrize(
    "raw,expected",
    [
        ((AXIS_MIN, AXIS_CENTER), Direction.LEFT),
        ((AXIS_MAX, AXIS_CENTER), Direction.RIGHT),
        ((AXIS_CENTER, AXIS_MIN), Direction.UP),
        ((AXIS_CENTER, AXIS_MAX), Direction.DOWN),
    ],
)
def test_stick_directions(raw, expected):
    pad, _ = make(raw)
    assert pad.read_stick().direction() == expected


def test_deadzone_ignores_a_lazy_stick():
    pad, _ = make((AXIS_CENTER + 20, AXIS_CENTER))
    assert pad.read_stick().direction(0.35) == Direction.NEUTRAL
    assert pad.read_stick().direction(0.1) == Direction.RIGHT


def test_axes_can_be_inverted_for_mounting():
    transport = FakeTransport({REG_LEFT_X: AXIS_MAX, REG_LEFT_Y: AXIS_CENTER})
    pad = MiniJoystick(transport, invert_x=True)
    assert pad.read_stick().direction() == Direction.LEFT


def test_dominant_axis_wins_on_a_diagonal():
    pad, _ = make((AXIS_MAX, AXIS_CENTER + 40))
    assert pad.read_stick().direction() == Direction.RIGHT


def test_reads_every_button_in_one_sample():
    pad, transport = make(a=int(ButtonEvent.PRESS_DOWN), d=int(ButtonEvent.SINGLE_CLICK))
    state = pad.read()

    assert state.is_held(Button.A) is True
    assert state.clicked(Button.D) is True
    assert state.is_held(Button.B) is False
    assert list(state.pressed()) == [Button.A]
    # Two axis reads plus one per button.
    assert len(transport.reads) == 2 + len(BUTTON_REGISTERS)


def test_a_missing_module_reports_disconnected():
    transport = FakeTransport()
    pad = MiniJoystick(transport)
    state = pad.read()
    assert state.connected is False
    assert pad.present() is False


def test_a_single_bad_read_does_not_raise():
    pad, transport = make((AXIS_MAX, AXIS_CENTER))
    transport.fail_on = {BUTTON_REGISTERS[Button.A]}
    state = pad.read()
    assert state.event(Button.A) == ButtonEvent.NONE
    assert state.connected is True


def test_close_releases_the_bus():
    pad, transport = make()
    with pad:
        pass
    assert transport.closed is True


# --- event reader -------------------------------------------------------


def test_direction_fires_once_then_repeats():
    pad, transport = make()
    reader = JoystickReader(pad, repeat_delay=0.3, repeat_interval=0.1)
    assert reader.poll(0.0) == []

    transport.set(REG_LEFT_X, AXIS_MAX)
    first = reader.poll(1.0)
    assert [e.direction for e in first] == [Direction.RIGHT]
    assert first[0].repeat is False

    # Held but still inside the initial delay.
    assert reader.poll(1.1) == []
    repeat = reader.poll(1.35)
    assert repeat and repeat[0].repeat is True

    transport.set(REG_LEFT_X, AXIS_CENTER)
    assert reader.poll(1.5) == []


def test_buttons_only_fire_on_a_change():
    pad, transport = make()
    reader = JoystickReader(pad)
    reader.poll(0.0)

    transport.set(BUTTON_REGISTERS[Button.A], int(ButtonEvent.PRESS_DOWN))
    events = [e for e in reader.poll(0.1) if e.kind == "button"]
    assert [(e.button, e.event) for e in events] == [(Button.A, ButtonEvent.PRESS_DOWN)]

    # Same level on the next poll is not a new edge.
    assert [e for e in reader.poll(0.2) if e.kind == "button"] == []

    transport.set(BUTTON_REGISTERS[Button.A], int(ButtonEvent.PRESS_UP))
    events = [e for e in reader.poll(0.3) if e.kind == "button"]
    assert [e.event for e in events] == [ButtonEvent.PRESS_UP]


def test_disconnect_and_reconnect_are_reported():
    pad, transport = make()
    reader = JoystickReader(pad)
    reader.poll(0.0)

    transport.registers.clear()
    assert [e.kind for e in reader.poll(0.1)] == ["disconnected"]
    assert reader.poll(0.2) == []

    transport.set(REG_LEFT_X, AXIS_CENTER)
    transport.set(REG_LEFT_Y, AXIS_CENTER)
    assert [e.kind for e in reader.poll(0.3)] == ["reconnected"]


# --- bindings -----------------------------------------------------------


def direction_event(direction: Direction, repeat: bool = False) -> JoystickEvent:
    return JoystickEvent(kind="direction", direction=direction, repeat=repeat)


def button_event(button: Button, event: ButtonEvent = ButtonEvent.PRESS_DOWN) -> JoystickEvent:
    return JoystickEvent(kind="button", button=button, event=event)


def test_dpad_games_take_the_stick_verbatim():
    actions = set(GAMES["pacman"].actions)
    for direction in (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT):
        assert game_action(direction_event(direction), actions) == direction.value


def test_stick_up_rotates_in_tetris():
    actions = set(GAMES["tetris"].actions)
    assert game_action(direction_event(Direction.UP), actions) == "rotateCw"
    assert game_action(direction_event(Direction.DOWN), actions) == "softDrop"
    assert game_action(direction_event(Direction.LEFT), actions) == "left"


def test_stick_up_flaps_in_a_one_button_game():
    actions = set(GAMES["flappy"].actions)
    assert game_action(direction_event(Direction.UP), actions) == "flap"


def test_only_movement_auto_repeats():
    tetris = set(GAMES["tetris"].actions)
    assert game_action(direction_event(Direction.LEFT, repeat=True), tetris) == "left"
    assert game_action(direction_event(Direction.DOWN, repeat=True), tetris) == "softDrop"
    # A held stick must not spin the piece or spam hard drops.
    assert game_action(direction_event(Direction.UP, repeat=True), tetris) == ""
    assert game_action(direction_event(Direction.UP, repeat=True), set(GAMES["flappy"].actions)) == ""


def test_face_buttons_map_to_each_game():
    assert game_action(button_event(Button.A), set(GAMES["tetris"].actions)) == "hardDrop"
    assert game_action(button_event(Button.B), set(GAMES["tetris"].actions)) == "rotateCcw"
    assert game_action(button_event(Button.A), set(GAMES["invaders"].actions)) == "fire"
    assert game_action(button_event(Button.A), set(GAMES["connect4"].actions)) == "drop"
    assert game_action(button_event(Button.A), set(GAMES["flappy"].actions)) == "flap"


def test_ok_pauses_and_long_press_restarts():
    actions = set(GAMES["snake"].actions)
    assert game_action(button_event(Button.OK, ButtonEvent.PRESS_DOWN), actions) == "togglePause"
    assert game_action(button_event(Button.OK, ButtonEvent.LONG_PRESS_START), actions) == "restart"


def test_restart_needs_a_long_press_on_d():
    actions = set(GAMES["snake"].actions)
    assert game_action(button_event(Button.D, ButtonEvent.SINGLE_CLICK), actions) == ""
    assert game_action(button_event(Button.D, ButtonEvent.LONG_PRESS_START), actions) == "restart"


def test_release_events_do_nothing():
    actions = set(GAMES["tetris"].actions)
    assert game_action(button_event(Button.A, ButtonEvent.PRESS_UP), actions) == ""


def test_shell_stick_walks_the_plugin_list():
    assert shell_action(direction_event(Direction.RIGHT)) == ShellAction(kind="next")
    assert shell_action(direction_event(Direction.DOWN)) == ShellAction(kind="next")
    assert shell_action(direction_event(Direction.LEFT)) == ShellAction(kind="previous")
    assert shell_action(direction_event(Direction.NEUTRAL)) is None


def test_shell_ok_applies_and_long_d_powers():
    assert shell_action(button_event(Button.OK, ButtonEvent.SINGLE_CLICK)).kind == "apply"
    assert shell_action(button_event(Button.D, ButtonEvent.LONG_PRESS_START)).kind == "power"
    assert shell_action(button_event(Button.OK, ButtonEvent.PRESS_DOWN)) is None


# --- service ------------------------------------------------------------


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.runtime_service",
    "src.domain.services.widget_registry_service",
    "src.domain.services.joystick_service",
]


def reload_joystick_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    game_module = importlib.import_module("src.domain.services.game_service")
    joystick_module = importlib.import_module("src.domain.services.joystick_service")
    registry_module = importlib.import_module("src.domain.services.widget_registry_service")
    return config_module, game_module, joystick_module, registry_module


def test_service_drives_the_active_game(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service._dispatch(direction_event(Direction.UP))
    service._dispatch(button_event(Button.OK, ButtonEvent.PRESS_DOWN))

    from matrix_games import read_commands

    actions, _ = read_commands(game_module.game_service.input_path("snake"), 0)
    assert actions == ["up", "togglePause"]
    assert service.last_action == "snake:togglePause"


def test_service_switches_plugins_when_no_game_runs(tmp_path, monkeypatch):
    config_module, _, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.widget_registry_service.apply_widget = lambda widget_id, values=None: (applied.append(widget_id), (None, None))[1]

    service = joystick_module.joystick_service
    service._dispatch(direction_event(Direction.RIGHT))
    service._dispatch(direction_event(Direction.RIGHT))

    assert len(applied) == 2
    assert applied[0] != applied[1], "each push moves to a different plugin"
    assert config_module.config_service.get_config().display.mode == "spotify"


def test_service_reports_its_state(tmp_path, monkeypatch):
    _, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service

    state = service.state()
    assert state["enabled"] is False
    assert state["running"] is False
    assert state["address"] == I2C_ADDRESS

    service._dispatch(JoystickEvent(kind="disconnected"))
    assert service.connected is False
    service._dispatch(JoystickEvent(kind="reconnected"))
    assert service.connected is True


def test_service_thread_starts_and_stops_against_a_fake_bus(tmp_path, monkeypatch):
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.joystick.enabled = True
    config_module.config_service.save_config(config)

    transport = FakeTransport({REG_LEFT_X: AXIS_CENTER, REG_LEFT_Y: AXIS_CENTER})
    service = joystick_module.joystick_service
    service.transport_factory = lambda: transport

    try:
        state = service.start()
        assert state["running"] is True
        deadline = __import__("time").monotonic() + 2.0
        while not transport.reads and __import__("time").monotonic() < deadline:
            __import__("time").sleep(0.02)
        assert transport.reads, "the polling thread should be reading the bus"
    finally:
        state = service.stop()
    assert state["running"] is False
