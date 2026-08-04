from __future__ import annotations

import importlib
import json
import shutil
import sys
import time
from pathlib import Path

import pytest

import matrix_games as mg
from matrix_games import registry as _registry
from assistant_matrix_sdk import game as base
from assistant_matrix_sdk.pixels import PANEL, frame_to_pixels
from src.utils.frame_codec import decode_frame

# Games live in store_widgets/ as plugins, so the tests load them the same way
# the host does rather than importing modules that no longer exist.
breakout = mg.plugin_module("breakout")
BRICK_COLS, BRICK_ROWS, BreakoutGame = breakout.BRICK_COLS, breakout.BRICK_ROWS, breakout.BreakoutGame

connect_four = mg.plugin_module("connect4")
C4_COLUMNS, C4_ROWS, ConnectFourGame = connect_four.COLUMNS, connect_four.ROWS, connect_four.ConnectFourGame

FlappyGame = mg.game_class("flappy")
InvadersGame = mg.game_class("invaders")
PongGame = mg.game_class("pong")

pacman = mg.plugin_module("pacman")
MAZE, MAZE_COLS, MAZE_ROWS = pacman.MAZE, pacman.COLS, pacman.ROWS
PacmanGame, walkable = pacman.PacmanGame, pacman.walkable

snake = mg.plugin_module("snake")
SNAKE_COLS, SNAKE_ROWS, SnakeGame = snake.COLS, snake.ROWS, snake.SnakeGame

ALL_GAMES = sorted(mg.discover())


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
    actions = [a for a in mg.discover()[game_id].actions if a not in mg.COMMON_GAME_ACTIONS] or ["pause"]
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
    for spec in mg.discover().values():
        assert spec.widget_id == f"core.{spec.game_id}"
        assert set(mg.COMMON_GAME_ACTIONS).issubset(set(spec.actions))
        assert spec.layout in mg.GAME_LAYOUTS
        assert spec.package_dir.joinpath("widget.toml").exists()


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
    config.display.mode = "widget"
    config.display.widgetId = "core.pacman"
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
    assert widget.manifest.kind == "game"

    registry_module.widget_registry_service.apply_widget(f"core.{game_id}")
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "widget"
    assert saved.display.widgetId == f"core.{game_id}"


def test_runtime_passes_the_active_game_queue(tmp_path, monkeypatch):
    config_module, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")

    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.invaders"
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()
    assert args[args.index("--display-mode") + 1] == "widget"
    assert args[args.index("--widget-id") + 1] == "core.invaders"
    assert args[args.index("--game-input") + 1] == str(game_module.game_service.input_path("invaders"))
    assert args[args.index("--game-state") + 1] == str(game_module.game_service.state_path("invaders"))


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_runtime_renders_one_frame_per_game(tmp_path, game_id):
    import spotify_matrix as runtime

    frame_path = tmp_path / f"{game_id}.png"
    state_path = tmp_path / f"{game_id}-state.json"
    args = runtime.build_parser().parse_args(
        [
            "--display-mode", "widget",
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


# --- adding a game plugin ------------------------------------------------


DROP_IN_GAME = '''
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameWidget
from assistant_matrix_sdk.pixels import PANEL, fit_panel, new_frame


class DropInGame(GameWidget):
    game_id = "dropin"
    id = "third.dropin"
    name = "Drop In"
    summary = "A game added without touching the app."
    layout = "horizontal"
    actions = ("left", "right")
    config_fields = [ConfigField.number("size", label="Size", default=4, minimum=1, maximum=9, step=1)]

    def reset(self) -> None:
        self.x = 10
        self.moves = 0

    def handle(self, action: str) -> None:
        self.x += 1 if action == "right" else -1
        self.moves += 1

    def advance(self, elapsed: float) -> None:
        pass

    def hud(self) -> dict[str, Any]:
        return {"Moves": self.moves}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        draw.rectangle((self.x, 30, self.x + 3, 33), fill=(90, 220, 255))
        return fit_panel(image, size)
'''


def install_drop_in_game(packages_dir: Path) -> Path:
    """Author a game package the way a third party would."""
    import importlib.util

    package = packages_dir / "third.dropin"
    (package / "renderer").mkdir(parents=True)
    (package / "renderer" / "__init__.py").write_text("", encoding="utf-8")
    (package / "renderer" / "widget.py").write_text(DROP_IN_GAME, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("drop_in_probe", package / "renderer" / "widget.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["drop_in_probe"] = module
    spec.loader.exec_module(module)
    manifest = module.DropInGame.manifest(entrypoint="renderer.widget:DropInGame")
    widget = manifest["widget"]
    lines = ["[widget]"]
    for key, value in widget.items():
        if isinstance(value, list):
            lines.append(f"{key} = [" + ", ".join(f'"{item}"' for item in value) + "]")
        else:
            lines.append(f'{key} = "{value}"')
    (package / "widget.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return package


def test_a_dropped_in_package_becomes_a_playable_game(tmp_path, monkeypatch):
    config_module, game_module, registry_module = reload_game_stack(monkeypatch, tmp_path / "data")
    packages = tmp_path / "data" / "widgets" / "packages"
    packages.mkdir(parents=True)
    install_drop_in_game(packages)

    # Discovered without any change to the app.
    specs = game_module.game_service.specs()
    assert "dropin" in specs
    spec = specs["dropin"]
    assert spec.bundled is False
    assert spec.layout == "horizontal"
    assert "left" in spec.actions and "restart" in spec.actions

    # Runnable.
    game = spec.create({})
    game.command("right")
    assert game.hud() == {"Moves": 1}
    assert game.render(PANEL).size == (PANEL, PANEL)

    # Listed and configurable like any other plugin.
    registry_module.runtime_service.apply = lambda: {"stub": True}
    widget = registry_module.widget_registry_service.get_local_widget("third.dropin")
    assert widget is not None
    assert widget.manifest.kind == "game"
    assert widget.builtIn is False

    # Applying it points the panel at the package.
    registry_module.widget_registry_service.apply_widget("third.dropin")
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "widget"
    assert saved.display.widgetId == "third.dropin"
    assert game_module.game_service.active_game_id() == "dropin"

    # And it accepts controller input on its own queue.
    game_module.game_service.queue_command("dropin", "left")
    actions, _ = mg.read_commands(game_module.game_service.input_path("dropin"), 0)
    assert actions == ["left"]


def test_an_installed_package_shadows_a_bundled_game(tmp_path, monkeypatch):
    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    packages = tmp_path / "data" / "widgets" / "packages"
    packages.mkdir(parents=True)

    bundled = game_module.game_service.specs()["snake"]
    assert bundled.bundled is True

    shutil.copytree(bundled.package_dir, packages / "core.snake")
    _registry.invalidate_cache()
    replaced = game_module.game_service.specs()["snake"]
    assert replaced.bundled is False, "an installed build must win over the shipped one"


def test_a_broken_package_does_not_break_discovery(tmp_path, monkeypatch):
    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    packages = tmp_path / "data" / "widgets" / "packages"
    (packages / "broken.game").mkdir(parents=True)
    (packages / "broken.game" / "widget.toml").write_text("this is not valid toml {{{", encoding="utf-8")
    (packages / "no.manifest").mkdir(parents=True)

    specs = game_module.game_service.specs()

    assert "snake" in specs, "a bad package must not hide the good ones"
    assert "game" not in specs and "manifest" not in specs


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_runtime_launch_args_point_at_a_real_package(tmp_path, monkeypatch, game_id):
    """The runtime must be handed a directory that actually holds the game.

    Bundled games do not live under the installed packages directory, so a
    launch that assumed they did failed for every shipped game.
    """
    config_module, _, registry_module = reload_game_stack(monkeypatch, tmp_path / "data")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")

    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = f"core.{game_id}"
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()
    widget_dir = Path(args[args.index("--widget-dir") + 1])

    assert widget_dir.is_dir(), f"{game_id}: {widget_dir} does not exist"
    assert (widget_dir / "widget.toml").exists(), f"{game_id}: no manifest at {widget_dir}"


def test_launch_args_prefer_an_installed_build(tmp_path, monkeypatch):
    config_module, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")

    packages = tmp_path / "data" / "widgets" / "packages"
    packages.mkdir(parents=True)
    bundled = game_module.game_service.specs()["snake"].package_dir
    shutil.copytree(bundled, packages / "core.snake")
    _registry.invalidate_cache()

    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.snake"
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()
    widget_dir = Path(args[args.index("--widget-dir") + 1])

    assert widget_dir == packages / "core.snake"


# --- Battleship ---------------------------------------------------------


battleship = mg.plugin_module("battleship")
BattleshipGame = battleship.BattleshipGame
BS_GRID = battleship.GRID


def test_battleship_places_a_full_fleet_without_overlaps():
    game = BattleshipGame(seed=1)
    for fleet in (game.enemy, game.player):
        cells = [cell for ship in fleet.ships for cell in ship.cells]
        assert len(cells) == sum(size for size, _ in battleship.FLEET)
        assert len(set(cells)) == len(cells), "ships must not overlap"
        assert all(0 <= x < BS_GRID and 0 <= y < BS_GRID for x, y in cells)
        assert all(len(ship.cells) == ship.size for ship in fleet.ships)


def test_battleship_ships_never_touch():
    game = BattleshipGame(seed=2)
    for ship in game.enemy.ships:
        halo = {(x + dx, y + dy) for x, y in ship.cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        for other in game.enemy.ships:
            if other is ship:
                continue
            assert not (halo & set(other.cells)), "a one cell gap keeps hunting fair"


def test_battleship_firing_reports_miss_hit_and_sunk():
    game = BattleshipGame(seed=3)
    target = game.enemy.ships[-1]

    empty = next(
        (x, y)
        for x in range(BS_GRID)
        for y in range(BS_GRID)
        if game.enemy.ship_at((x, y)) is None
    )
    assert game.enemy.fire(empty) == "miss"
    assert game.enemy.fire(empty) == "repeat", "firing twice must not count"

    results = [game.enemy.fire(cell) for cell in target.cells]
    assert results[:-1] == ["hit"] * (len(target.cells) - 1)
    assert results[-1] == "sunk"
    assert target.sunk is True


def test_battleship_sinking_every_ship_wins():
    game = BattleshipGame(seed=4)
    for ship in game.enemy.ships:
        for cell in ship.cells:
            if game.finished():
                break
            game.cursor = [cell[0], cell[1]]
            game.command("fire")
            # Let the computer answer, otherwise it is never the player's turn again.
            game.step(1.0)
    assert game.won is True, "perfect shooting should win before the computer does"
    assert game.status() == "won"


def test_battleship_turn_passes_to_the_computer_after_a_shot():
    game = BattleshipGame(seed=5)
    empty = next(
        (x, y)
        for x in range(BS_GRID)
        for y in range(BS_GRID)
        if game.enemy.ship_at((x, y)) is None
    )
    game.cursor = list(empty)
    game.command("fire")
    assert game.turn == "enemy"

    # Input is ignored while the computer is thinking.
    before = list(game.cursor)
    game.command("right")
    assert game.cursor == before

    game.step(1.0)
    assert game.turn == "player"
    assert len(game.player.shots) == 1


def test_battleship_computer_hunts_around_its_hits():
    game = BattleshipGame({"difficulty": "hunt"}, seed=6)
    ship = game.player.ships[0]
    hit = ship.cells[0]

    game.player.fire(hit)
    ship.hits.add(hit)
    x, y = hit
    for step_x, step_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbour = (x + step_x, y + step_y)
        if 0 <= neighbour[0] < BS_GRID and 0 <= neighbour[1] < BS_GRID and neighbour not in game.player.shots:
            game.hunt.append(neighbour)

    target = game._enemy_target()
    assert abs(target[0] - x) + abs(target[1] - y) == 1, "the computer should probe next to its hit"


def test_battleship_never_repeats_a_shot():
    game = BattleshipGame(seed=7)
    for _ in range(BS_GRID * BS_GRID):
        target = game._enemy_target()
        assert target is not None
        assert target not in game.player.shots
        game.player.fire(target)

    # Board exhausted: the computer must hand the turn back, not raise.
    assert game._enemy_target() is None
    game.turn = "enemy"
    game._enemy_fire()
    assert game.turn == "player"


def test_battleship_cursor_wraps_around_the_grid():
    game = BattleshipGame(seed=8)
    game.cursor = [0, 0]
    game.command("left")
    assert game.cursor[0] == BS_GRID - 1
    game.command("up")
    assert game.cursor[1] == BS_GRID - 1


def test_battleship_practice_mode_reveals_the_enemy():
    hidden = BattleshipGame({"revealEnemy": False}, seed=9)
    shown = BattleshipGame({"revealEnemy": True}, seed=9)
    assert hidden.render(PANEL).tobytes() != shown.render(PANEL).tobytes()


def test_an_idle_game_keeps_publishing(tmp_path):
    """A turn based game can sit unchanged; watchers must still see it as live."""
    import spotify_matrix as runtime

    state_path = tmp_path / "idle-state.json"
    frame_path = tmp_path / "idle.png"
    args = runtime.build_parser().parse_args(
        ["--display-mode", "widget", "--mock-output", str(frame_path),
         "--game-state", str(state_path), "--config-path", str(tmp_path / "config.json"), "--once"]
    )

    game = mg.create_game("battleship", {}, seed=1)
    runtime.run_game(args, runtime.MockDisplay(frame_path), 64, game)
    first = json.loads(state_path.read_text(encoding="utf-8"))["updatedAt"]

    # Nothing about the board changes, but the timestamp must still move on.
    time.sleep(0.01)
    runtime.run_game(args, runtime.MockDisplay(frame_path), 64, game)
    second = json.loads(state_path.read_text(encoding="utf-8"))["updatedAt"]

    assert second > first
    assert runtime.GAME_HEARTBEAT_SECONDS <= 2.0, "must be well inside the staleness window"


# --- saved scores --------------------------------------------------------


def test_a_store_without_a_path_stays_in_memory():
    from assistant_matrix_sdk.store import GameStore

    store = GameStore()
    assert store.record_score(10) is True
    assert store.best == 10
    assert store.path is None


def test_scores_survive_a_relaunch(tmp_path):
    from assistant_matrix_sdk.store import GameStore

    path = tmp_path / "flappy.json"
    game = mg.create_game("flappy", {}, seed=1, store=GameStore(path))
    game.score = 12
    game.game_over = True
    game.step(0.1)

    # A fresh process builds a new game object from the same file.
    reloaded = mg.create_game("flappy", {}, seed=1, store=GameStore(path))
    assert reloaded.store.best == 12
    assert reloaded.best == 12, "flappy should show the saved best straight away"


@pytest.mark.parametrize("game_id", ALL_GAMES)
def test_finishing_a_game_records_it_once(tmp_path, game_id):
    from assistant_matrix_sdk.store import GameStore

    store = GameStore(tmp_path / f"{game_id}.json")
    game = mg.create_game(game_id, {}, seed=3, store=store)
    if hasattr(game, "score"):
        game.score = 25
    game.game_over = True

    for _ in range(5):
        game.step(0.1)

    assert store.plays == 1, "stepping past the end must not file the same game again"
    if game.final_score() is not None:
        assert store.best == 25


def test_only_a_better_score_takes_the_top_spot(tmp_path):
    from assistant_matrix_sdk.store import GameStore

    store = GameStore(tmp_path / "snake.json")
    assert store.record_score(10) is True
    assert store.record_score(4) is False
    assert store.record_score(20) is True
    assert store.best == 20
    assert [entry["score"] for entry in store.top()] == [20, 10, 4]
    assert store.plays == 3


def test_the_table_is_capped(tmp_path):
    from assistant_matrix_sdk.store import GameStore, SCORE_HISTORY

    store = GameStore(tmp_path / "capped.json")
    for value in range(SCORE_HISTORY + 8):
        store.record_score(value)

    assert len(store.top()) == SCORE_HISTORY
    assert store.best == SCORE_HISTORY + 7
    assert store.plays == SCORE_HISTORY + 8


def test_restarting_files_each_round_separately(tmp_path):
    from assistant_matrix_sdk.store import GameStore

    store = GameStore(tmp_path / "rounds.json")
    game = mg.create_game("snake", {}, seed=4, store=store)

    for value in (5, 9):
        game.score = value
        game.game_over = True
        game.step(0.1)
        game.step(mg_restart_grace())
        game.command("restart")

    assert store.plays == 2
    assert store.best == 9


def mg_restart_grace() -> float:
    from assistant_matrix_sdk.game import RESTART_GRACE_SECONDS

    return RESTART_GRACE_SECONDS


def test_a_corrupt_score_file_is_ignored(tmp_path):
    from assistant_matrix_sdk.store import GameStore

    path = tmp_path / "broken.json"
    path.write_text("{ not json at all", encoding="utf-8")

    store = GameStore(path)

    assert store.best == 0
    assert store.plays == 0
    store.record_score(7)
    assert GameStore(path).best == 7, "a bad file should be replaced, not fatal"


def test_arbitrary_values_persist(tmp_path):
    from assistant_matrix_sdk.store import GameStore

    path = tmp_path / "values.json"
    store = GameStore(path)
    store.set("level", 4)
    store.update(unlocked=["hard"], nickname="ace")

    reloaded = GameStore(path)
    assert reloaded.get("level") == 4
    assert reloaded.get("unlocked") == ["hard"]
    assert reloaded.get("missing", "fallback") == "fallback"


def test_scores_are_served_and_clearable(tmp_path, monkeypatch):
    from assistant_matrix_sdk.store import GameStore

    _, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    service = game_module.game_service

    GameStore(service.scores_path("snake")).record_score(31)

    assert service.read_scores("snake")["best"] == 31
    assert service.clear_scores("snake")["best"] == 0
    assert service.read_scores("snake")["plays"] == 0


def test_runtime_args_carry_the_score_file(tmp_path, monkeypatch):
    config_module, game_module, _ = reload_game_stack(monkeypatch, tmp_path / "data")
    runtime_module = importlib.import_module("src.domain.services.runtime_service")

    config = config_module.config_service.get_config()
    config.display.mode = "widget"
    config.display.widgetId = "core.flappy"
    config_module.config_service.save_config(config)

    args = runtime_module.runtime_service._args()
    assert args[args.index("--game-scores") + 1] == str(game_module.game_service.scores_path("flappy"))
