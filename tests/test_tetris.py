"""Tetris gameplay rules.

Tetris is a game app like every other, so the queue, registry and runtime
plumbing are covered generically in ``test_games.py``. What stays here is the
behaviour specific to Tetris, plus the Tetris-only API that predates the
shared games layer.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import matrix_games as mg

tetris = mg.app_module("tetris")

TetrisGame = tetris.TetrisGame
TETRIS_COLS = tetris.TETRIS_COLS
TETRIS_ROWS = tetris.TETRIS_ROWS
TETRIS_SHAPES = tetris.TETRIS_SHAPES
TETRIS_LINE_SCORES = tetris.TETRIS_LINE_SCORES
TETRIS_LOCK_DELAY = tetris.TETRIS_LOCK_DELAY

SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.tetris_service",
]


def reload_tetris_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    importlib.import_module("src.domain.services.config_service")
    importlib.import_module("src.domain.services.game_service")
    return importlib.import_module("src.domain.services.tetris_service")


def fill_row(game, row: int, empty_column: int) -> None:
    for column in range(TETRIS_COLS):
        game.board[row][column] = "" if column == empty_column else "J"


def place_vertical_i(game, column: int) -> None:
    """Stand an I piece up so its single column sits at ``column``."""
    game.piece_type = "I"
    game.rotation = 1
    game.piece_x = column - 2
    game.piece_y = 0


def test_hard_drop_locks_piece_and_clears_full_line():
    game = TetrisGame(seed=1)
    fill_row(game, TETRIS_ROWS - 1, 0)
    place_vertical_i(game, 0)

    game.hard_drop()

    assert game.lines == 1
    # The bottom row cleared, so the rest of the I settles one row lower.
    assert game.board[TETRIS_ROWS - 1][0] == "I"
    assert game.board[TETRIS_ROWS - 1][1] == ""
    assert game.score >= TETRIS_LINE_SCORES[1] * game.level


def test_gravity_drops_one_row_per_interval():
    game = TetrisGame(seed=2)
    start_y = game.piece_y

    game.step(game.drop_interval() * 2.5)

    assert game.piece_y == start_y + 2


def test_lock_delay_gives_the_player_time_to_slide():
    game = TetrisGame(seed=3)
    while not game._collides(game.piece_x, game.piece_y + 1, game.rotation):
        game.piece_y += 1
    resting_type = game.piece_type

    game.step(TETRIS_LOCK_DELAY / 2)
    assert game.piece_type == resting_type
    assert all(cell == "" for row in game.board for cell in row)

    game.step(TETRIS_LOCK_DELAY)
    assert any(cell for row in game.board for cell in row)


def test_move_and_rotate_respect_the_walls():
    game = TetrisGame(seed=4)
    place_vertical_i(game, 0)
    game.piece_y = 5

    assert game.move(-1, 0) is False
    # Laying the I back down at the left wall only fits after a wall kick.
    assert game.rotate(1) is True
    assert all(0 <= x < TETRIS_COLS for x, _ in game._cells(game.piece_x, game.piece_y, game.rotation))


def test_hold_swaps_once_per_piece():
    game = TetrisGame(seed=5)
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
    game = TetrisGame(seed=6)
    # Junk up the spawn rows without completing any line.
    for row in range(4):
        for column in range(TETRIS_COLS - 1):
            game.board[row][column] = "J"

    game.hard_drop()

    assert game.game_over is True
    assert game.board_snapshot()["gameOver"] is True


def test_levels_speed_up_as_lines_clear():
    game = TetrisGame(seed=7)
    slow = game.drop_interval()
    game.lines = 20
    game.level = game.start_level + game.lines // 10

    assert game.drop_interval() < slow


def test_ghost_piece_can_be_turned_off():
    with_ghost = TetrisGame({"ghost": True}, seed=8)
    without = TetrisGame({"ghost": False}, seed=8)

    assert with_ghost.board_snapshot()["ghost"]
    assert without.board_snapshot()["ghost"] == []


def test_board_snapshot_shape():
    snapshot = TetrisGame(seed=9).board_snapshot()

    assert len(snapshot["board"]) == TETRIS_ROWS
    assert all(len(row) == TETRIS_COLS for row in snapshot["board"])
    assert snapshot["next"] in TETRIS_SHAPES


def test_tetris_api_still_reads_the_structured_board(tmp_path, monkeypatch):
    """The Tetris-only routes predate the shared games layer and must keep working."""
    tetris_module = reload_tetris_stack(monkeypatch, tmp_path / "data")
    service = tetris_module.tetris_service

    assert service.read_state() is None
    assert service.queue_command("left") == 1

    mg.write_state(service.state_path, TetrisGame(seed=10).snapshot())

    state = service.read_state()
    assert state is not None
    assert service.is_live(state) is True
    assert len(state.board) == TETRIS_ROWS
    assert state.next in TETRIS_SHAPES

    state.updatedAt -= tetris_module.STALE_SECONDS + 1
    assert service.is_live(state) is False
