from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import spotify_matrix as runtime


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.tetris_service",
    "src.domain.services.runtime_service",
    "src.domain.services.widget_registry_service",
]


def reload_tetris_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    importlib.import_module("src.domain.services.game_service")
    tetris_module = importlib.import_module("src.domain.services.tetris_service")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")
    registry_module = importlib.import_module("src.domain.services.widget_registry_service")
    return config_module, tetris_module, runtime_module, registry_module


def fill_row(game: runtime.TetrisGame, row: int, empty_column: int) -> None:
    for column in range(runtime.TETRIS_COLS):
        game.board[row][column] = "" if column == empty_column else "J"


def place_vertical_i(game: runtime.TetrisGame, column: int) -> None:
    """Stand an I piece up so its single column sits at ``column``."""
    game.piece_type = "I"
    game.rotation = 1
    game.piece_x = column - 2
    game.piece_y = 0


def test_hard_drop_locks_piece_and_clears_full_line():
    game = runtime.TetrisGame(seed=1)
    fill_row(game, runtime.TETRIS_ROWS - 1, 0)
    place_vertical_i(game, 0)

    game.hard_drop()

    assert game.lines == 1
    # The bottom row cleared, so the rest of the I settles one row lower.
    assert game.board[runtime.TETRIS_ROWS - 1][0] == "I"
    assert game.board[runtime.TETRIS_ROWS - 1][1] == ""
    assert game.score >= runtime.TETRIS_LINE_SCORES[1] * game.level


def test_gravity_drops_one_row_per_interval():
    game = runtime.TetrisGame(seed=2)
    start_y = game.piece_y

    game.step(game.drop_interval() * 2.5)

    assert game.piece_y == start_y + 2


def test_lock_delay_gives_the_player_time_to_slide():
    game = runtime.TetrisGame(seed=3)
    while not game._collides(game.piece_x, game.piece_y + 1, game.rotation):
        game.piece_y += 1
    resting_type = game.piece_type

    game.step(runtime.TETRIS_LOCK_DELAY / 2)
    assert game.piece_type == resting_type
    assert all(cell == "" for row in game.board for cell in row)

    game.step(runtime.TETRIS_LOCK_DELAY)
    assert any(cell for row in game.board for cell in row)


def test_move_and_rotate_respect_the_walls():
    game = runtime.TetrisGame(seed=4)
    place_vertical_i(game, 0)
    game.piece_y = 5

    assert game.move(-1, 0) is False
    # Laying the I back down at the left wall only fits after a wall kick.
    assert game.rotate(1) is True
    assert all(0 <= x < runtime.TETRIS_COLS for x, _ in game._cells(game.piece_x, game.piece_y, game.rotation))


def test_hold_swaps_once_per_piece():
    game = runtime.TetrisGame(seed=5)
    first = game.piece_type

    game.hold_piece()
    swapped = game.piece_type

    assert game.hold == first
    assert game.hold_locked is True

    # A second hold before the piece lands is ignored.
    game.hold_piece()
    assert game.piece_type == swapped

    game.hard_drop()
    game.hold_piece()
    assert game.hold != first


def test_game_over_when_the_stack_reaches_the_top():
    game = runtime.TetrisGame(seed=6)
    # Junk up the spawn rows without completing any line.
    for row in range(4):
        for column in range(runtime.TETRIS_COLS - 1):
            game.board[row][column] = "J"

    game.hard_drop()

    assert game.game_over is True
    assert game.snapshot()["gameOver"] is True


def test_drop_button_restarts_after_game_over():
    game = runtime.TetrisGame(seed=7)
    game.game_over = True
    game.score = 999

    # The board holds the final score briefly before a drop deals a new game.
    game.step(1.0)
    game.command("hardDrop")

    assert game.game_over is False
    assert game.score == 0


def test_pause_blocks_movement_and_gravity():
    game = runtime.TetrisGame(seed=8)
    game.command("pause")
    start = (game.piece_x, game.piece_y)

    game.command("left")
    game.step(game.drop_interval() * 3)

    assert (game.piece_x, game.piece_y) == start
    game.command("togglePause")
    assert game.paused is False


def test_snapshot_round_trips_through_the_state_file(tmp_path):
    game = runtime.TetrisGame(seed=9)
    state_path = tmp_path / "state" / "tetris-state.json"

    runtime.write_tetris_state(state_path, game.snapshot())
    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert len(payload["board"]) == runtime.TETRIS_ROWS
    assert all(len(row) == runtime.TETRIS_COLS for row in payload["board"])
    assert payload["updatedAt"] > 0
    assert payload["next"] in runtime.TETRIS_SHAPES


def test_command_queue_only_replays_fresh_commands(tmp_path, monkeypatch):
    _, tetris_module, _, _ = reload_tetris_stack(monkeypatch, tmp_path / "data")
    service = tetris_module.tetris_service

    assert service.queue_command("left") == 1
    assert service.queue_command("rotateCw") == 2

    actions, seq = runtime.read_tetris_commands(service.input_path, 0)
    assert actions == ["left", "rotateCw"]
    assert seq == 2

    repeat, seq = runtime.read_tetris_commands(service.input_path, seq)
    assert repeat == []

    service.queue_command("hardDrop")
    actions, seq = runtime.read_tetris_commands(service.input_path, seq)
    assert actions == ["hardDrop"]
    assert seq == 3


def test_command_queue_recovers_when_the_api_rewinds(tmp_path, monkeypatch):
    _, tetris_module, _, _ = reload_tetris_stack(monkeypatch, tmp_path / "data")
    service = tetris_module.tetris_service
    service.queue_command("left")

    # The runtime has seen a much higher sequence from a previous API process.
    actions, seq = runtime.read_tetris_commands(service.input_path, 500)

    assert actions == ["left"]
    assert seq == 1


def test_queue_keeps_only_the_recent_tail(tmp_path, monkeypatch):
    _, tetris_module, _, _ = reload_tetris_stack(monkeypatch, tmp_path / "data")
    service = tetris_module.tetris_service
    for _ in range(tetris_module.QUEUE_LIMIT + 10):
        service.queue_command("left")

    payload = json.loads(service.input_path.read_text(encoding="utf-8"))

    assert len(payload["commands"]) == tetris_module.QUEUE_LIMIT
    assert payload["seq"] == tetris_module.QUEUE_LIMIT + 10


def test_state_is_stale_when_nothing_is_playing(tmp_path, monkeypatch):
    _, tetris_module, _, _ = reload_tetris_stack(monkeypatch, tmp_path / "data")
    service = tetris_module.tetris_service

    assert service.read_state() is None
    assert service.is_live(None) is False

    runtime.write_tetris_state(service.state_path, runtime.TetrisGame(seed=10).snapshot())
    state = service.read_state()
    assert service.is_live(state) is True

    state.updatedAt -= tetris_module.STALE_SECONDS + 1
    assert service.is_live(state) is False


def test_runtime_args_pass_the_tetris_paths(tmp_path, monkeypatch):
    config_module, tetris_module, runtime_module, _ = reload_tetris_stack(monkeypatch, tmp_path / "data")
    config = config_module.config_service.get_config()
    config.display.mode = "tetris"
    config.tetris.startLevel = 4
    config.tetris.ghost = False
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()

    assert "--tetris-no-ghost" in args
    assert args[args.index("--tetris-start-level") + 1] == "4"
    assert args[args.index("--game-input") + 1] == str(tetris_module.tetris_service.input_path)
    assert args[args.index("--game-state") + 1] == str(tetris_module.tetris_service.state_path)
    assert args[args.index("--display-mode") + 1] == "tetris"


def test_widget_config_and_apply(tmp_path, monkeypatch):
    config_module, _, _, registry_module = reload_tetris_stack(monkeypatch, tmp_path / "data")
    registry_module.runtime_service.apply = lambda: {"stub": True}

    widget = registry_module.widget_registry_service.get_local_widget("core.tetris")
    assert widget is not None
    assert widget.manifest.category == "games"
    assert widget.configurable is True

    saved = registry_module.widget_registry_service.update_widget_config("core.tetris", {"startLevel": 6, "ghost": False})
    assert saved["startLevel"] == 6
    assert saved["ghost"] is False

    registry_module.widget_registry_service.apply_widget("core.tetris")
    assert config_module.config_service.get_config().display.mode == "tetris"


def test_runtime_renders_a_single_tetris_frame(tmp_path):
    parser = runtime.build_parser()
    frame_path = tmp_path / "frame.png"
    state_path = tmp_path / "tetris-state.json"
    args = parser.parse_args(
        [
            "--display-mode", "tetris",
            "--mock-output", str(frame_path),
            "--tetris-state", str(state_path),
            "--once",
        ]
    )
    display = runtime.MockDisplay(frame_path)

    runtime.run_tetris(args, display, 64)

    assert frame_path.exists()
    assert json.loads(state_path.read_text(encoding="utf-8"))["board"]
