from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

import matrix_games as mg

GAMES = mg.discover()
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


def _queued(path, last=0):
    """Actions from the queue, dropping the seat most tests do not care about."""
    commands, seq = mg.read_commands(path, last)
    return [action for action, _ in commands], seq



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


def test_shell_stick_walks_the_app_list():
    assert shell_action(direction_event(Direction.RIGHT)) == ShellAction(kind="next")
    assert shell_action(direction_event(Direction.DOWN)) == ShellAction(kind="next")
    assert shell_action(direction_event(Direction.LEFT)) == ShellAction(kind="previous")
    assert shell_action(direction_event(Direction.NEUTRAL)) is None


def test_shell_ok_opens_the_menu_and_long_d_powers():
    assert shell_action(button_event(Button.OK, ButtonEvent.SINGLE_CLICK)).kind == "openMenu"
    assert shell_action(button_event(Button.OK, ButtonEvent.PRESS_DOWN)).kind == "openMenu"
    assert shell_action(button_event(Button.D, ButtonEvent.LONG_PRESS_START)).kind == "power"
    assert shell_action(button_event(Button.A)).kind == "brightnessUp"
    assert shell_action(button_event(Button.B)).kind == "brightnessDown"


def test_shell_menu_navigates_without_applying():
    # With the menu up the stick only moves a highlight.
    assert shell_action(direction_event(Direction.DOWN), True).kind == "cursorNext"
    assert shell_action(direction_event(Direction.UP), True).kind == "cursorPrevious"
    assert shell_action(button_event(Button.OK), True).kind == "select"
    assert shell_action(button_event(Button.B), True).kind == "closeMenu"
    # Brightness is not reachable while picking, so a press cannot dim by mistake.
    assert shell_action(button_event(Button.A), True).kind == "select"


# --- service ------------------------------------------------------------


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.runtime_service",
    "src.domain.services.app_registry_service",
    "src.domain.services.joystick_service",
]


def reload_joystick_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    game_module = importlib.import_module("src.domain.services.game_service")
    joystick_module = importlib.import_module("src.domain.services.joystick_service")
    registry_module = importlib.import_module("src.domain.services.app_registry_service")
    return config_module, game_module, joystick_module, registry_module


def test_service_drives_the_active_game(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config.joystick.role = "player"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service._dispatch(direction_event(Direction.UP))
    service._dispatch(button_event(Button.OK, ButtonEvent.PRESS_DOWN))

    actions, _ = _queued(game_module.game_service.input_path("snake"))
    assert actions == ["up", "togglePause"]
    assert service.last_action == "snake:togglePause"


def test_service_switches_apps_when_no_game_runs(tmp_path, monkeypatch):
    config_module, _, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    service = joystick_module.joystick_service
    service._dispatch(direction_event(Direction.RIGHT))
    service._dispatch(direction_event(Direction.RIGHT))

    assert len(applied) == 2
    assert applied[0] != applied[1], "each push moves to a different app"
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


# --- the on-panel shell menu ---------------------------------------------


def test_the_menu_opens_moves_and_selects(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    config_module, game_module, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    service = joystick_module.joystick_service
    shell_path = game_module.game_service.state_dir / "shell.json"

    # Clicking the stick opens the menu rather than applying anything.
    service._dispatch(button_event(Button.OK, ButtonEvent.SINGLE_CLICK))
    state = read_shell_state(shell_path)
    assert state["menu"]["open"] is True
    assert state["menu"]["items"], "the menu lists the installed apps"
    assert applied == [], "opening the menu must not change the panel"

    # The stick moves a highlight, still without applying.
    start = read_shell_state(shell_path)["menu"]["cursor"]
    service._dispatch(direction_event(Direction.DOWN))
    service._dispatch(direction_event(Direction.DOWN))
    moved = read_shell_state(shell_path)["menu"]["cursor"]
    assert moved != start
    assert applied == []

    # Clicking again picks the highlighted one and closes.
    service._dispatch(button_event(Button.OK, ButtonEvent.SINGLE_CLICK))
    assert len(applied) == 1
    closed = read_shell_state(shell_path)
    assert closed["menu"]["open"] is False
    assert applied[0] == closed["menu"].get("selected", applied[0])


def test_the_menu_can_be_cancelled(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    _, game_module, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    service = joystick_module.joystick_service
    service._dispatch(button_event(Button.OK, ButtonEvent.SINGLE_CLICK))
    service._dispatch(button_event(Button.B, ButtonEvent.SINGLE_CLICK))

    assert read_shell_state(game_module.game_service.state_dir / "shell.json")["menu"]["open"] is False
    assert applied == [], "cancelling changes nothing"


def test_buttons_step_brightness_without_a_restart(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    shell_path = game_module.game_service.state_dir / "shell.json"

    config = config_module.config_service.get_config()
    config.matrix.brightness = 50
    config_module.config_service.save_config(config)

    service._dispatch(button_event(Button.A, ButtonEvent.SINGLE_CLICK))
    assert config_module.config_service.get_config().matrix.brightness == 50 + joystick_module.BRIGHTNESS_STEP
    # Published for the runtime to pick up live, not applied by restarting.
    assert read_shell_state(shell_path)["brightness"] == 50 + joystick_module.BRIGHTNESS_STEP

    service._dispatch(button_event(Button.B, ButtonEvent.SINGLE_CLICK))
    assert config_module.config_service.get_config().matrix.brightness == 50


def test_brightness_stops_at_the_limits(tmp_path, monkeypatch):
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service

    for _ in range(30):
        service._dispatch(button_event(Button.A, ButtonEvent.SINGLE_CLICK))
    assert config_module.config_service.get_config().matrix.brightness == joystick_module.BRIGHTNESS_MAX

    for _ in range(30):
        service._dispatch(button_event(Button.B, ButtonEvent.SINGLE_CLICK))
    assert config_module.config_service.get_config().matrix.brightness == joystick_module.BRIGHTNESS_MIN


def test_the_module_reaches_the_menu_while_a_game_runs(tmp_path, monkeypatch):
    """The module is device control: it must work without putting the pad
    down, which is the whole point of having it bolted to the matrix."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service._dispatch(button_event(Button.OK, ButtonEvent.SINGLE_CLICK))

    assert service._menu_open, "the menu opened over the running game"
    actions, _ = _queued(game_module.game_service.input_path("snake"), 0)
    assert actions == [], "and the game saw nothing from the module"


def test_the_module_can_still_be_made_a_game_controller(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config.joystick.role = "player"
    config_module.config_service.save_config(config)

    joystick_module.joystick_service._dispatch(button_event(Button.OK, ButtonEvent.SINGLE_CLICK))

    actions, _ = _queued(game_module.game_service.input_path("snake"), 0)
    assert actions == ["togglePause"]


def test_a_gamepad_still_plays_while_the_module_runs_the_system(tmp_path, monkeypatch):
    """The two devices do different jobs at the same time."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service.dispatch_event(direction_event(Direction.UP), device="gamepad")
    service.dispatch_event(button_event(Button.OK, ButtonEvent.SINGLE_CLICK), device="module")

    actions, _ = _queued(game_module.game_service.input_path("snake"), 0)
    assert actions == ["up"], "the pad played, the module did not"
    assert service._menu_open


def test_the_menu_scrolls_to_keep_the_cursor_visible():
    from matrix_input.shell import VISIBLE_ROWS, visible_window

    assert visible_window(0, 3) == (0, 3), "a short list never scrolls"
    start, end = visible_window(0, 20)
    assert (start, end) == (0, VISIBLE_ROWS)
    start, end = visible_window(19, 20)
    assert end == 20 and start == 20 - VISIBLE_ROWS
    start, end = visible_window(10, 20)
    assert start <= 10 < end


# --- the radial wheel ----------------------------------------------------


def long_press(button: Button = Button.OK) -> JoystickEvent:
    return JoystickEvent(kind="button", button=button, event=ButtonEvent.LONG_PRESS_START)


def stick(x: float, y: float) -> JoystickEvent:
    direction = Direction.UP if y < 0 else Direction.DOWN if y > 0 else Direction.RIGHT if x > 0 else Direction.LEFT
    return JoystickEvent(kind="direction", direction=direction, x=x, y=y)


def test_the_wheel_picks_by_angle():
    from matrix_input.wheel import wedge_for_vector

    # Six wedges, zero at the top, running clockwise.
    assert wedge_for_vector(0, -1, 6) == 0
    assert wedge_for_vector(0, 1, 6) == 3
    assert wedge_for_vector(0, 0, 6) is None, "a centred stick points at nothing"
    # Four wedges line up with the compass points.
    assert wedge_for_vector(0, -1, 4) == 0
    assert wedge_for_vector(1, 0, 4) == 1
    assert wedge_for_vector(0, 1, 4) == 2
    assert wedge_for_vector(-1, 0, 4) == 3


def test_holding_ok_opens_the_wheel_over_a_game(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    shell_path = game_module.game_service.state_dir / "shell.json"

    service._dispatch(long_press())
    wheel = read_shell_state(shell_path)["wheel"]
    assert wheel["open"] is True
    assert [item["action"] for item in wheel["items"]] == [item["action"] for item in joystick_module.WHEEL_IN_GAME]

    # Pushing the stick highlights a wedge without doing anything.
    service._dispatch(stick(0, -1))
    assert read_shell_state(shell_path)["wheel"]["selected"] == 0
    actions, _ = _queued(game_module.game_service.input_path("snake"), 0)
    assert actions == [], "browsing the wheel must not reach the game"


def test_the_wheel_sends_the_chosen_action(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service._dispatch(long_press())
    service._dispatch(stick(0, -1))          # wedge 0 is Pause
    service._dispatch(button_event(Button.OK, ButtonEvent.PRESS_UP))

    actions, _ = _queued(game_module.game_service.input_path("snake"), 0)
    assert actions == ["togglePause"]
    assert read_shell_state(game_module.game_service.state_dir / "shell.json")["wheel"]["open"] is False


def test_the_wheel_can_be_cancelled(tmp_path, monkeypatch):
    from matrix_input.shell import read_shell_state

    _, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service

    service._dispatch(long_press())
    service._dispatch(stick(0, -1))
    service._dispatch(button_event(Button.B, ButtonEvent.SINGLE_CLICK))

    assert read_shell_state(game_module.game_service.state_dir / "shell.json")["wheel"]["open"] is False


def test_releasing_on_nothing_does_nothing(tmp_path, monkeypatch):
    _, game_module, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    service = joystick_module.joystick_service
    service._dispatch(long_press())
    # Never pushed the stick, so nothing is selected.
    service._dispatch(button_event(Button.OK, ButtonEvent.PRESS_UP))

    assert applied == []


def test_exit_game_returns_to_the_previous_app(tmp_path, monkeypatch):
    config_module, _, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    service = joystick_module.joystick_service
    # Arrive at a game from the clock.
    service._apply_app("core.clock")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service._run_wheel_action("exitGame")

    assert applied[-1] == "core.clock"


def test_exit_falls_back_to_a_non_game(tmp_path, monkeypatch):
    config_module, _, joystick_module, registry_module = reload_joystick_stack(monkeypatch, tmp_path / "data")
    applied: list[str] = []
    registry_module.app_registry_service.apply_app = lambda app_id, values=None: (applied.append(app_id), (None, None))[1]

    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    joystick_module.joystick_service._run_wheel_action("exitGame")

    assert applied, "there is always somewhere to go back to"
    assert not applied[-1].startswith("core.snake")


# --- per game bindings ---------------------------------------------------


def test_defaults_only_use_actions_a_game_declares():
    from mini_joystick.bindings import default_bindings

    for spec in mg.discover().values():
        actions = set(spec.actions)
        for control, action in default_bindings(actions).items():
            assert action in actions, f"{spec.game_id}: {control} bound to unknown {action}"


def test_an_override_replaces_the_default():
    tetris = set(GAMES["tetris"].actions)
    press_a = button_event(Button.A)

    assert game_action(press_a, tetris) == "hardDrop"
    assert game_action(press_a, tetris, {"a": "hold"}) == "hold"


def test_an_override_a_game_rejects_is_ignored():
    flappy = set(GAMES["flappy"].actions)
    press_a = button_event(Button.A)

    # Flappy has no hold, so the binding falls back rather than sending junk.
    assert game_action(press_a, flappy, {"a": "hold"}) == "flap"


def test_a_control_can_be_unbound():
    tetris = set(GAMES["tetris"].actions)
    assert game_action(button_event(Button.A), tetris, {"a": "none"}) == ""


def test_overrides_still_respect_auto_repeat():
    tetris = set(GAMES["tetris"].actions)
    held = direction_event(Direction.UP, repeat=True)
    # Rebinding up to a rotate must not let a held stick spin the piece.
    assert game_action(held, tetris, {"up": "rotateCw"}) == ""
    assert game_action(direction_event(Direction.UP), tetris, {"up": "rotateCw"}) == "rotateCw"


def test_the_service_uses_saved_bindings(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.tetris"
    config.joystick.role = "player"
    config.controller.profiles = {"module": {"core.tetris": {"a": "hold"}}}
    config_module.config_service.save_config(config)

    joystick_module.joystick_service.dispatch_event(button_event(Button.A), device="module")

    actions, _ = _queued(game_module.game_service.input_path("tetris"), 0)
    assert actions == ["hold"]


def test_each_device_keeps_its_own_bindings(tmp_path, monkeypatch):
    """Rebinding A on the pad must not rebind A on the module."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.tetris"
    config.joystick.role = "player"
    config.controller.profiles = {
        "module": {"core.tetris": {"a": "hold"}},
        "gamepad": {"core.tetris": {"a": "rotateCcw"}},
    }
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service.dispatch_event(button_event(Button.A), device="module")
    service.dispatch_event(button_event(Button.A), device="gamepad")

    actions, _ = _queued(game_module.game_service.input_path("tetris"), 0)
    assert actions == ["hold", "rotateCcw"]


# --- per-device binding profiles -----------------------------------------


def test_each_device_offers_the_controls_it_actually_has():
    from mini_joystick.bindings import GAMEPAD, MODULE, PROFILES

    module = PROFILES[MODULE].controls
    gamepad = PROFILES[GAMEPAD].controls

    assert set(module) < set(gamepad), "a pad is a superset of the module"
    for control in ("lb", "rb", "lt", "rt", "start", "select"):
        assert control in gamepad and control not in module


def test_the_same_control_is_labelled_for_the_device_in_hand():
    """Control "c" is silkscreened C on the module and printed X on a pad."""
    from mini_joystick.bindings import GAMEPAD, MODULE, profile

    assert profile(MODULE).label("c") == "C"
    assert profile(GAMEPAD).label("c") == "X"
    assert profile(MODULE).label("ok") != profile(GAMEPAD).label("ok")


def test_defaults_use_a_pads_spare_buttons():
    from mini_joystick.bindings import GAMEPAD, MODULE, default_bindings

    actions = set(mg.game_class("tetris").all_actions())
    module = default_bindings(actions, MODULE)
    gamepad = default_bindings(actions, GAMEPAD)

    assert set(module) < set(gamepad)
    assert gamepad["lb"] == "rotateCcw" and gamepad["rb"] == "rotateCw"
    assert gamepad["start"] == "togglePause"
    # A control the device does not have never gets a default.
    assert "lb" not in module


def test_defaults_never_offer_an_action_the_game_does_not_have():
    from mini_joystick.bindings import PROFILES, default_bindings

    for game_id in sorted(mg.discover()):
        actions = set(mg.game_class(game_id).all_actions())
        for name in PROFILES:
            for control, action in default_bindings(actions, name).items():
                assert action in actions, f"{game_id}/{name}: {control} -> {action}"


def test_old_configs_keep_their_bindings_on_both_devices():
    """The single mapping applied to both, so neither should lose it."""
    from src.domain.services.config_service import migrate_config

    payload, changed = migrate_config(
        {"controller": {"bindings": {"core.tetris": {"a": "hold"}}}, "display": {"mode": "spotify"}}
    )

    assert changed
    assert "bindings" not in payload["controller"]
    assert payload["controller"]["profiles"]["module"]["core.tetris"] == {"a": "hold"}
    assert payload["controller"]["profiles"]["gamepad"]["core.tetris"] == {"a": "hold"}


def test_brightness_gives_feedback_at_the_top_of_the_range(tmp_path, monkeypatch):
    """Pressing brighter at full brightness published nothing, and the
    runtime only draws the bar when something changes, so the button looked
    broken rather than already at the limit."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = joystick_module.BRIGHTNESS_MAX
    config_module.config_service.save_config(config)

    before = service._brightness_nonce
    service._adjust_brightness(joystick_module.BRIGHTNESS_STEP)

    assert service._brightness_nonce > before, "the press is published even when clamped"
    assert config_module.config_service.get_config().matrix.brightness == joystick_module.BRIGHTNESS_MAX


def test_brightness_goes_back_up_after_coming_down(tmp_path, monkeypatch):
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = 60
    config_module.config_service.save_config(config)

    service._adjust_brightness(-joystick_module.BRIGHTNESS_STEP)
    assert config_module.config_service.get_config().matrix.brightness == 50
    service._adjust_brightness(joystick_module.BRIGHTNESS_STEP)
    assert config_module.config_service.get_config().matrix.brightness == 60


def test_both_brightness_buttons_work_end_to_end(tmp_path, monkeypatch):
    """Through the whole dispatch path, not just the setter: A is brighter,
    B is dimmer, and each must move the saved level."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = 50
    config_module.config_service.save_config(config)

    service._dispatch(button_event(Button.A, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().matrix.brightness == 60, "A did not brighten"

    service._dispatch(button_event(Button.B, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().matrix.brightness == 50, "B did not dim"


def test_brightness_climbs_all_the_way_from_the_floor(tmp_path, monkeypatch):
    """Repeated dimming persists to config, so getting back up has to work."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = joystick_module.BRIGHTNESS_MIN
    config_module.config_service.save_config(config)

    for _ in range(20):
        service._dispatch(button_event(Button.A, ButtonEvent.PRESS_DOWN))

    assert config_module.config_service.get_config().matrix.brightness == joystick_module.BRIGHTNESS_MAX


def test_the_panel_cannot_be_dimmed_into_darkness(tmp_path, monkeypatch):
    """The floor was 5, which looks broken. Settings can still set any value
    deliberately; this only bounds what the dimmer button can reach."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service

    for _ in range(30):
        service._dispatch(button_event(Button.B, ButtonEvent.PRESS_DOWN))

    level = config_module.config_service.get_config().matrix.brightness
    assert level == joystick_module.BRIGHTNESS_MIN >= 20, f"dimmed to {level}"


def test_saving_brightness_in_settings_reaches_the_panel(tmp_path, monkeypatch):
    """Saving config used to write the file and stop there, so changing
    brightness in Settings moved the number and not the matrix."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    import asyncio
    import importlib

    sys.modules.pop("src.api.http.rest.config", None)
    routes = importlib.import_module("src.api.http.rest.config")

    config = config_module.config_service.get_config()
    config.matrix.brightness = 40
    config_module.config_service.save_config(config)

    published: list[int] = []
    monkeypatch.setattr(joystick_module.joystick_service, "publish_brightness", published.append)
    monkeypatch.setattr(routes, "config_service", config_module.config_service)

    updated = config_module.config_service.get_config().model_copy(deep=True)
    updated.matrix.brightness = 100
    asyncio.run(routes.save_config(updated))

    assert published == [100], "the running panel was told"


def test_saving_a_driver_setting_restarts_the_runtime(tmp_path, monkeypatch):
    """pwmBits and friends are constructor arguments; only a restart takes
    them, and saving silently did neither."""
    config_module, _, _, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    import asyncio
    import importlib

    sys.modules.pop("src.api.http.rest.config", None)
    routes = importlib.import_module("src.api.http.rest.config")
    monkeypatch.setattr(routes, "config_service", config_module.config_service)

    applied: list[bool] = []
    from src.domain.services import runtime_service as runtime_module

    monkeypatch.setattr(runtime_module.runtime_service, "apply", lambda: applied.append(True))

    updated = config_module.config_service.get_config().model_copy(deep=True)
    updated.matrix.pwmBits = 8
    asyncio.run(routes.save_config(updated))

    assert applied, "the runtime was restarted for a driver change"


def test_system_buttons_can_be_rebound(tmp_path, monkeypatch):
    """Which button sits where under a thumb is not something the silkscreen
    order knows, so brightness up and down landed on buttons that are not a
    pair and could not be swapped."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = 50
    config.joystick.systemBindings = {"a": "brightnessDown", "b": "brightnessUp"}
    config_module.config_service.save_config(config)

    service._dispatch(button_event(Button.A, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().matrix.brightness == 40, "A now dims"

    service._dispatch(button_event(Button.B, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().matrix.brightness == 50, "B now brightens"


def test_volume_can_be_driven_from_the_module(tmp_path, monkeypatch):
    """There was no way to change volume from the device at all."""
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.audio.volume = 50
    config_module.config_service.save_config(config)

    service._dispatch(button_event(Button.C, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().audio.volume == 60

    service._dispatch(button_event(Button.D, ButtonEvent.PRESS_DOWN))
    assert config_module.config_service.get_config().audio.volume == 50


def test_an_unbound_control_does_nothing(tmp_path, monkeypatch):
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    service = joystick_module.joystick_service
    config = config_module.config_service.get_config()
    config.matrix.brightness = 50
    config.joystick.systemBindings = {"a": "none"}
    config_module.config_service.save_config(config)

    service._dispatch(button_event(Button.A, ButtonEvent.PRESS_DOWN))

    assert config_module.config_service.get_config().matrix.brightness == 50


def test_the_system_controls_route_round_trips(tmp_path, monkeypatch):
    import asyncio
    import importlib

    config_module, _, _, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    sys.modules.pop("src.api.http.rest.system_controls", None)
    routes = importlib.import_module("src.api.http.rest.system_controls")
    monkeypatch.setattr(routes, "config_service", config_module.config_service)

    swapped = asyncio.run(
        routes.save_system_controls(routes.SystemControlsRequest(bindings={"a": "brightnessDown", "b": "brightnessUp"}))
    )
    assert swapped.bindings["a"] == "brightnessDown"
    assert set(swapped.customised) == {"a", "b"}

    back = asyncio.run(routes.reset_system_controls())
    assert back.bindings == back.defaults and back.customised == []


def test_the_system_controls_route_refuses_nonsense(tmp_path, monkeypatch):
    import asyncio
    import importlib

    config_module, _, _, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    sys.modules.pop("src.api.http.rest.system_controls", None)
    routes = importlib.import_module("src.api.http.rest.system_controls")
    monkeypatch.setattr(routes, "config_service", config_module.config_service)

    with pytest.raises(ValueError):
        asyncio.run(routes.save_system_controls(routes.SystemControlsRequest(bindings={"a": "selfDestruct"})))
    with pytest.raises(ValueError):
        asyncio.run(routes.save_system_controls(routes.SystemControlsRequest(bindings={"z": "brightnessUp"})))


def test_the_stick_cannot_swap_the_app_out_from_under_a_game(tmp_path, monkeypatch):
    """Nudging left while playing switched apps, because with the menu closed
    a push is a shortcut for "next app" - which is fine on an idle panel and
    not fine mid-game."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    applied: list[str] = []
    monkeypatch.setattr(service, "_apply_app", applied.append)

    for _ in range(4):
        service._dispatch(direction_event(Direction.LEFT))
        service._dispatch(direction_event(Direction.RIGHT))

    assert applied == [], "the running game stayed on the panel"


def test_the_stick_still_walks_apps_on_an_idle_panel(tmp_path, monkeypatch):
    config_module, _, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "clock"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    applied: list[str] = []
    monkeypatch.setattr(service, "_apply_app", applied.append)

    service._dispatch(direction_event(Direction.RIGHT))

    assert applied, "with nothing playing the shortcut is still useful"


def test_home_opens_the_menu_from_a_pad_mid_game(tmp_path, monkeypatch):
    """A dedicated button beats a stick nudge, and it must not reach the
    game the way every other pad button does."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = "core.snake"
    config_module.config_service.save_config(config)

    service = joystick_module.joystick_service
    service.dispatch_event(button_event(Button.HOME, ButtonEvent.PRESS_DOWN), device="gamepad")

    assert service._menu_open
    actions, _ = _queued(game_module.game_service.input_path("snake"))
    assert actions == [], "Home never reaches the game"


def test_home_closes_the_menu_again():
    from mini_joystick.bindings import shell_action

    event = button_event(Button.HOME, ButtonEvent.PRESS_DOWN)

    assert shell_action(event, False).kind == "openMenu"
    assert shell_action(event, True).kind == "closeMenu"


def _seat_game(config_module, game_module, app_id="core.pong"):
    config = config_module.config_service.get_config()
    config.display.mode = "app"
    config.display.appId = app_id
    config.joystick.role = "player"
    config_module.config_service.save_config(config)


def test_two_controllers_take_two_seats(tmp_path, monkeypatch):
    """The second pad drives player two, which is the whole point: both send
    plain "up" and the seat says whose paddle moves."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    _seat_game(config_module, game_module)
    service = joystick_module.joystick_service

    service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event4")
    service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event5")

    commands, _ = mg.read_commands(game_module.game_service.input_path("pong"), 0)
    assert [player for _, player in commands] == [0, 1]


def test_a_device_keeps_its_seat(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    _seat_game(config_module, game_module)
    service = joystick_module.joystick_service

    for _ in range(3):
        service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event5")
        service.dispatch_event(direction_event(Direction.DOWN), device="gamepad", device_id="/dev/input/event4")

    commands, _ = mg.read_commands(game_module.game_service.input_path("pong"), 0)
    seats = {}
    for action, player in commands:
        seats.setdefault(action, set()).add(player)
    assert all(len(players) == 1 for players in seats.values()), "a device does not wander between seats"


def test_a_third_controller_does_not_steal_a_paddle(tmp_path, monkeypatch):
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    _seat_game(config_module, game_module)
    service = joystick_module.joystick_service

    for path in ("/dev/input/event4", "/dev/input/event5", "/dev/input/event6"):
        service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id=path)

    commands, _ = mg.read_commands(game_module.game_service.input_path("pong"), 0)
    assert [player for _, player in commands] == [0, 1], "the third was ignored, not seated"


def test_a_single_player_game_lets_every_controller_play(tmp_path, monkeypatch):
    """With one player there is nothing to tell apart, so seating the first
    device would lock the others out."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    _seat_game(config_module, game_module, "core.snake")
    service = joystick_module.joystick_service

    service.dispatch_event(direction_event(Direction.UP), device="module")
    service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event4")

    commands, _ = mg.read_commands(game_module.game_service.input_path("snake"), 0)
    assert [player for _, player in commands] == [0, 0]


def test_seats_are_forgotten_when_the_game_changes(tmp_path, monkeypatch):
    """Seat two of Pong means nothing in Tron."""
    config_module, game_module, joystick_module, _ = reload_joystick_stack(monkeypatch, tmp_path / "data")
    _seat_game(config_module, game_module)
    service = joystick_module.joystick_service

    service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event5")
    assert service.seats.occupied()

    _seat_game(config_module, game_module, "core.tron")
    service.dispatch_event(direction_event(Direction.UP), device="gamepad", device_id="/dev/input/event4")

    seated = service.seats.occupied()
    assert list(seated) == [0], "the new game starts from an empty board"
