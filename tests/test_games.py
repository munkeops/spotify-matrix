from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

import matrix_games as mg
from matrix_games import base
from matrix_games.breakout import BRICK_COLS, BRICK_ROWS, BreakoutGame
from matrix_games.connect_four import COLUMNS as C4_COLUMNS, ROWS as C4_ROWS, ConnectFourGame
from matrix_games.flappy import FlappyGame
from matrix_games.invaders import InvadersGame
from matrix_games.pacman import COLS as MAZE_COLS, MAZE, ROWS as MAZE_ROWS, PacmanGame, walkable
from matrix_games.pong import PongGame
from matrix_games.render import PANEL, frame_to_pixels
from matrix_games.snake import COLS as SNAKE_COLS, ROWS as SNAKE_ROWS, SnakeGame
from src.utils.frame_codec import decode_frame

ALL_GAMES = sorted(mg.GAMES)


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.game_service",
    "src.domain.services.runtime_service",
    "src.domain.services.widget_registry_service",
]


def reload_game_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    game_module = importlib.import_module("src.domain.services.game_service")
    registry_module = importlib.import_module("src.domain.services.widget_registry_service")
    return config_module, game_module, registry_module


# --- shared layer -------------------------------------------------------


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_every_game_survives_a_long_random_session(game_id):
    game = mg.create_game(game_id, {}, seed=5)
    actions = list(mg.GAMES[game_id].factory.actions) or ["pause"]
    for tick in range(600):
        game.command(actions[tick % len(actions)])
        game.step(0.05)
    frame = game.render(PANEL)
    assert frame.size == (PANEL, PANEL)
    assert game.status() in ("playing", "paused", "gameOver", "won")


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_snapshot_encodes_a_full_panel(game_id):
    game = mg.demo_game(game_id)
    snapshot = game.snapshot()
    assert snapshot["game"] == game_id
    assert len(snapshot["pixels"]) == PANEL
    assert all(len(row) == PANEL for row in snapshot["pixels"])
    assert snapshot["palette"], "a rendered frame always has at least one colour"
    assert isinstance(snapshot["hud"], dict)


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_frame_encoding_round_trips_losslessly(game_id):
    original = mg.demo_game(game_id).render(PANEL).convert("RGB")
    palette, pixels = frame_to_pixels(original)
    restored = decode_frame(palette, pixels, PANEL)
    assert list(original.getdata()) == list(restored.getdata())


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_pause_freezes_the_game(game_id):
    game = mg.create_game(game_id, {}, seed=2)
    game.command("pause")
    before = game.render(PANEL).tobytes()
    for _ in range(40):
        game.step(0.05)
    assert game.paused is True
    assert game.render(PANEL).tobytes() == before
    game.command("togglePause")
    assert game.paused is False


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_restart_clears_progress(game_id):
    game = mg.create_game(game_id, {}, seed=3)
    for _ in range(100):
        game.step(0.05)
    game.game_over = True
    game.command("restart")
    assert game.game_over is False
    assert game.paused is False
    assert game.game_over_elapsed == 0.0


def test_unknown_game_is_rejected():
    with pytest.raises(ValueError):
        mg.create_game("solitaire")


def test_every_spec_declares_its_common_actions():
    for spec in mg.GAMES.values():
        assert spec.widget_id == f"core.{spec.game_id}"
        assert set(mg.COMMON_ACTIONS).issubset(set(spec.actions))
        assert spec.layout in (mg.DPAD, mg.HORIZONTAL, mg.VERTICAL, mg.TAP, mg.TETRIS_PAD)


# --- Pac-Man ------------------------------------------------------------


def test_pacman_maze_is_fully_connected():
    from collections import deque

    start = (13, 22)
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for step_x, step_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_x, next_y = (x + step_x) % MAZE_COLS, y + step_y
            if 0 <= next_y < MAZE_ROWS and walkable(next_x, next_y) and (next_x, next_y) not in seen:
                seen.add((next_x, next_y))
                queue.append((next_x, next_y))
    pellets = {(x, y) for y in range(MAZE_ROWS) for x in range(MAZE_COLS) if MAZE[y][x] in ".o"}
    assert pellets and pellets <= seen, "every pellet must be reachable from the start tile"


def test_pacman_eats_along_a_corridor():
    game = PacmanGame(seed=1)
    game.ready_timer = 0.0
    for _ in range(120):
        game.step(0.05)
    assert game.score > 0
    assert game.eaten_pellets
    assert game.pac_x < 13, "holding left should travel left"


def test_pacman_stops_at_a_wall():
    game = PacmanGame(seed=1)
    game.ready_timer = 0.0
    for _ in range(400):
        game.step(0.05)
    tile_x, tile_y = int(round(game.pac_x)) % MAZE_COLS, int(round(game.pac_y))
    assert walkable(tile_x, tile_y), "Pac-Man must never come to rest inside a wall"


def test_pacman_turn_is_buffered_until_the_junction():
    game = PacmanGame(seed=2)
    game.ready_timer = 0.0
    for _ in range(40):
        game.step(0.05)
    game.command("up")
    for _ in range(40):
        game.step(0.05)
    assert game.direction == (0, -1)


def test_power_pellet_frightens_every_ghost():
    game = PacmanGame(seed=3)
    game.ready_timer = 0.0
    game.pac_x, game.pac_y = 1.0, 3.0
    game._eat()
    assert game.fright_timer > 0
    assert all(ghost.frightened for ghost in game.ghosts)
    assert game.score == 50


def test_eating_a_frightened_ghost_scores_the_chain():
    game = PacmanGame(seed=4)
    game.ready_timer = 0.0
    ghost = game.ghosts[0]
    ghost.state = "maze"
    ghost.frightened = True
    ghost.x, ghost.y = game.pac_x, game.pac_y
    game._check_collisions()
    assert ghost.eaten is True
    assert game.score == 200
    assert game.lives == 3


def test_touching_a_hunting_ghost_costs_a_life():
    game = PacmanGame(seed=5)
    game.ready_timer = 0.0
    ghost = game.ghosts[0]
    ghost.state = "maze"
    ghost.frightened = False
    ghost.x, ghost.y = game.pac_x, game.pac_y
    game._check_collisions()
    assert game.lives == 2
    assert game.death_timer > 0


def test_pacman_game_over_on_the_last_life():
    game = PacmanGame({"lives": 1}, seed=6)
    game.ready_timer = 0.0
    ghost = game.ghosts[0]
    ghost.state = "maze"
    ghost.x, ghost.y = game.pac_x, game.pac_y
    game._check_collisions()
    while game.death_timer > 0:
        game.step(0.1)
    assert game.game_over is True


def test_clearing_the_maze_advances_the_level():
    game = PacmanGame(seed=7)
    game.eaten_pellets = set(list(game.pellets)[:-1])
    last = list(game.pellets)[-1]
    game.pac_x, game.pac_y = float(last[0]), float(last[1])
    game._eat()
    assert game.level == 2
    assert game.eaten_pellets == set()


# --- Snake --------------------------------------------------------------


def test_snake_grows_when_it_eats():
    game = SnakeGame(seed=1)
    head_x, head_y = game.body[0]
    game.food = (head_x + 1, head_y)
    length = len(game.body)
    game._move()
    for _ in range(3):
        game._move()
    assert game.score == 1
    assert len(game.body) > length


def test_snake_dies_against_the_wall():
    game = SnakeGame({"walls": True}, seed=2)
    game.body = [(SNAKE_COLS - 1, 5), (SNAKE_COLS - 2, 5)]
    game.direction = (1, 0)
    game._move()
    assert game.game_over is True


def test_snake_wraps_when_walls_are_off():
    game = SnakeGame({"walls": False}, seed=3)
    game.body = [(SNAKE_COLS - 1, 5), (SNAKE_COLS - 2, 5)]
    game.direction = (1, 0)
    game._move()
    assert game.game_over is False
    assert game.body[0][0] == 0


def test_snake_cannot_reverse_into_itself():
    game = SnakeGame(seed=4)
    game.direction = (1, 0)
    game.handle("left")
    assert game.pending == []


def test_snake_dies_on_its_own_body():
    game = SnakeGame(seed=5)
    game.body = [(5, 5), (6, 5), (6, 6), (5, 6), (4, 6)]
    game.direction = (0, 1)
    game._move()
    assert game.game_over is True


# --- Breakout -----------------------------------------------------------


def test_breakout_serves_from_the_paddle():
    game = BreakoutGame(seed=1)
    assert game.launched is False
    game.handle("fire")
    assert game.launched is True
    assert game.ball_vy < 0, "the ball must leave the paddle upwards"


def test_breakout_loses_a_life_below_the_floor():
    game = BreakoutGame(seed=2)
    game.handle("fire")
    game.ball_y = PANEL + 2
    game._advance_ball(0.01)
    assert game.lives == 2
    assert game.launched is False


def test_breakout_clearing_every_brick_starts_a_new_level():
    game = BreakoutGame(seed=3)
    game.bricks = [[False] * BRICK_COLS for _ in range(BRICK_ROWS)]
    game.bricks[0][0] = True
    left, top, _, _ = game._brick_rect(0, 0)
    game.ball_x, game.ball_y = float(left), float(top)
    game.handle("fire")
    game._hit_bricks()
    assert game.level == 2
    assert any(any(row) for row in game.bricks)


def test_breakout_paddle_stays_on_screen():
    game = BreakoutGame(seed=4)
    for _ in range(60):
        game.handle("left")
    assert game.paddle_x >= 1
    for _ in range(120):
        game.handle("right")
    assert game.paddle_x + game.paddle_width <= PANEL - 1


# --- Flappy -------------------------------------------------------------


def test_flappy_waits_for_the_first_flap():
    game = FlappyGame(seed=1)
    start = game.bird_y
    for _ in range(20):
        game.step(0.05)
    assert game.bird_y == start
    game.command("flap")
    game.step(0.05)
    assert game.bird_y != start


def test_flappy_scores_when_a_pipe_passes():
    game = FlappyGame(seed=2)
    game.command("flap")
    game.pipes = [{"x": 2.0, "top": 20, "scored": False}]
    game.bird_y = 25.0
    game.bird_vy = 0.0

    game.step(0.05)

    assert game.score == 1
    assert game.game_over is False


def test_flappy_ceiling_ends_the_run():
    game = FlappyGame(seed=6)
    game.command("flap")
    # Flapping every frame climbs into the ceiling, exactly as it should.
    for _ in range(40):
        if game.game_over:
            break
        game.command("flap")
        game.step(0.05)
    assert game.game_over is True


def test_flappy_dies_on_the_ground():
    game = FlappyGame(seed=3)
    game.command("flap")
    game.bird_y = 100.0
    game.step(0.05)
    assert game.game_over is True


def test_flappy_remembers_the_best_score():
    game = FlappyGame(seed=4)
    game.score = 9
    game.best = 9
    game.restart()
    assert game.best == 9
    assert game.score == 0


# --- Pong ---------------------------------------------------------------


def test_pong_scores_when_the_ball_leaves_the_court():
    game = PongGame(seed=1)
    game.ball_x = -10
    game._advance_ball(0.01)
    assert game.right_score == 1


def test_pong_reaching_the_target_wins():
    game = PongGame({"target": 1}, seed=2)
    game.ball_x = PANEL + 5
    game._advance_ball(0.01)
    assert game.won is True
    assert game.winner == "left"


def test_pong_second_player_only_moves_in_two_player_mode():
    solo = PongGame({"opponent": "ai"}, seed=3)
    start = solo.right_y
    solo.handle("p2Up")
    assert solo.right_y == start

    duo = PongGame({"opponent": "human"}, seed=3)
    duo.right_y = 30
    duo.handle("p2Up")
    assert duo.right_y < 30
    assert duo.extra()["twoPlayer"] is True


def test_pong_paddles_stay_in_the_court():
    game = PongGame(seed=4)
    for _ in range(60):
        game.handle("up")
    assert game.left_y >= 9
    for _ in range(120):
        game.handle("down")
    assert game.left_y + 12 <= PANEL


# --- Space Invaders -----------------------------------------------------


def test_invaders_bullet_kills_and_scores():
    game = InvadersGame(seed=1)
    left, top, _, _ = game._invader_rect(4, 0)
    game.bullet = [left + 1, top + 1]
    game._advance_bullet(0.01)
    assert game.alive[4][0] is False
    assert game.score > 0
    assert game.bullet is None


def test_invaders_only_one_bullet_at_a_time():
    game = InvadersGame(seed=2)
    game.handle("fire")
    first = list(game.bullet or [])
    game.handle("fire")
    assert game.bullet == first


def test_invaders_clearing_a_wave_advances():
    game = InvadersGame(seed=3)
    game.alive = [[False] * 8 for _ in range(5)]
    game.alive[0][0] = True
    left, top, _, _ = game._invader_rect(0, 0)
    game.bullet = [left + 1, top + 1]
    game._advance_bullet(0.01)
    assert game.wave == 2
    assert sum(1 for row in game.alive for cell in row if cell) == 40


def test_invaders_bomb_costs_a_life():
    game = InvadersGame(seed=4)
    game.bombs = [[float(game.ship_x + 3), 57.0]]
    game._advance_bombs(0.01)
    assert game.lives == 2


def test_invaders_reaching_the_ship_ends_the_game():
    game = InvadersGame(seed=5)
    game.fleet_y = 60.0
    game.step_timer = 10.0
    game._advance_fleet(0.05)
    assert game.game_over is True


# --- Connect Four -------------------------------------------------------


def settle(game: ConnectFourGame, column: int) -> None:
    game.cursor = column
    game.handle("drop")
    for _ in range(40):
        game.step(0.05)
        if game.falling is None:
            return


def test_connect_four_stacks_discs_from_the_bottom():
    game = ConnectFourGame({"opponent": "human"}, seed=1)
    settle(game, 3)
    assert game.board[C4_ROWS - 1][3] != 0
    settle(game, 3)
    assert game.board[C4_ROWS - 2][3] != 0


def test_connect_four_detects_a_horizontal_win():
    game = ConnectFourGame({"opponent": "human"}, seed=2)
    for column in range(3):
        settle(game, column)  # red builds along the bottom
        settle(game, 6)       # yellow stacks harmlessly on the right
    settle(game, 3)
    assert game.winner == 1
    assert game.won is True
    assert len(game.win_cells) >= 4


def test_connect_four_full_board_is_a_draw():
    game = ConnectFourGame({"opponent": "human"}, seed=3)
    # Fill without ever making four in a row.
    pattern = [1, 1, 2, 2, 1, 1, 2, 2]
    for column in range(C4_COLUMNS):
        for row in range(C4_ROWS):
            game.board[C4_ROWS - 1 - row][column] = pattern[(row + column * 2) % len(pattern)]
    game.board[0][0] = 0
    game.player = 1
    settle(game, 0)
    assert game.game_over is True
    assert game.winner == 0


def test_connect_four_ai_blocks_an_open_three():
    game = ConnectFourGame({"opponent": "ai"}, seed=4)
    for column in range(3):
        game.board[C4_ROWS - 1][column] = 1
    game.player = 2
    assert game._ai_column() == 3


def test_connect_four_ignores_input_while_a_disc_falls():
    game = ConnectFourGame({"opponent": "human"}, seed=5)
    game.cursor = 2
    game.handle("drop")
    assert game.falling is not None
    game.handle("right")
    assert game.cursor == 2


# --- service and registry ------------------------------------------------


def test_queue_and_state_are_per_game(tmp_path, monkeypatch):
    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    service = game_module.game_service

    assert service.queue_command("snake", "up") == 1
    assert service.queue_command("pacman", "left") == 1
    assert service.input_path("snake") != service.input_path("pacman")

    actions, seq = mg.read_commands(service.input_path("snake"), 0)
    assert actions == ["up"]
    other, _ = mg.read_commands(service.input_path("pacman"), 0)
    assert other == ["left"]

    service.queue_command("snake", "down")
    fresh, _ = mg.read_commands(service.input_path("snake"), seq)
    assert fresh == ["down"]


def test_service_rejects_unknown_games(tmp_path, monkeypatch):
    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    with pytest.raises(ValueError):
        game_module.game_service.queue_command("solitaire", "left")


def test_active_game_follows_the_display_mode(tmp_path, monkeypatch):
    config_module, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    assert game_module.game_service.active_game_id() == ""

    config = config_module.config_service.get_config()
    config.display.mode = "pacman"
    config_module.config_service.save_config(config)
    assert game_module.game_service.active_game_id() == "pacman"

    config.runtime.testPattern = True
    config_module.config_service.save_config(config)
    assert game_module.game_service.active_game_id() == ""


def test_published_state_is_stale_when_nothing_plays(tmp_path, monkeypatch):
    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    service = game_module.game_service

    assert service.read_state("snake") is None
    mg.write_state(service.state_path("snake"), mg.demo_game("snake").snapshot())
    state = service.read_state("snake")
    assert service.is_live(state) is True
    assert len(state.pixels) == PANEL

    state.updatedAt -= game_module.STALE_SECONDS + 1
    assert service.is_live(state) is False


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_each_game_is_a_configurable_widget(tmp_path, monkeypatch, game_id):
    config_module, _, registry_module = reload_game_stack(monkeypatch, tmp_path / "data")
    registry_module.runtime_service.apply = lambda: {"stub": True}

    widget = registry_module.widget_registry_service.get_local_widget(f"core.{game_id}")
    assert widget is not None
    assert widget.manifest.category == "games"

    registry_module.widget_registry_service.apply_widget(f"core.{game_id}")
    assert config_module.config_service.get_config().display.mode == game_id


def test_runtime_passes_the_active_game_queue(tmp_path, monkeypatch):
    config_module, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")

    config = config_module.config_service.get_config()
    config.display.mode = "invaders"
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()
    assert args[args.index("--display-mode") + 1] == "invaders"
    assert args[args.index("--game-input") + 1] == str(game_module.game_service.input_path("invaders"))
    assert args[args.index("--game-state") + 1] == str(game_module.game_service.state_path("invaders"))


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_runtime_renders_one_frame_per_game(tmp_path, game_id):
    import spotify_matrix as runtime

    frame_path = tmp_path / f"{game_id}.png"
    state_path = tmp_path / f"{game_id}-state.json"
    args = runtime.build_parser().parse_args(
        [
            "--display-mode", game_id,
            "--mock-output", str(frame_path),
            "--game-state", str(state_path),
            "--config-path", str(tmp_path / "config.json"),
            "--once",
        ]
    )
    runtime.run_game(args, runtime.MockDisplay(frame_path), 64, game_id)

    assert frame_path.exists()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["game"] == game_id
    assert len(payload["pixels"]) == PANEL
    assert payload["updatedAt"] > 0


def test_restart_button_waits_out_the_grace_period():
    game = mg.create_game("snake", {}, seed=1)
    game.game_over = True

    # A press already in flight must not skip past the final score.
    game.command("hardDrop")
    assert game.game_over is True

    game.step(base.RESTART_GRACE_SECONDS)
    game.command("hardDrop")
    assert game.game_over is False
    assert game.status() == base.PLAYING
