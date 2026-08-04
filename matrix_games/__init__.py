"""Playable games for the Assistant Matrix panel.

Every game subclasses :class:`matrix_games.base.Game` and publishes an encoded
frame, so the API and the web app treat them all identically. Adding a game is
a module here plus one entry in ``GAMES``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from matrix_games.base import GAME_OVER, PAUSED, PLAYING, WON, Game
from matrix_games.breakout import BreakoutGame
from matrix_games.connect_four import ConnectFourGame
from matrix_games.flappy import FlappyGame
from matrix_games.invaders import InvadersGame
from matrix_games.io import read_commands, write_state
from matrix_games.pacman import PacmanGame
from matrix_games.pong import PongGame
from matrix_games.render import PANEL, encode_frame, frame_to_pixels
from matrix_games.snake import SnakeGame
from matrix_games.tetris import TetrisGame, render_tetris_frame, tetris_demo_snapshot

# Universal actions every game understands, on top of its own action list.
COMMON_ACTIONS = ("pause", "resume", "togglePause", "restart")

# Control layouts the web pad and the joystick binding both understand.
DPAD = "dpad"
HORIZONTAL = "horizontal"
VERTICAL = "vertical"
TAP = "tap"
TETRIS_PAD = "tetris"


@dataclass(frozen=True)
class GameSpec:
    game_id: str
    name: str
    summary: str
    factory: Callable[..., Game]
    layout: str
    # Config key in data/config.json and the widget id that runs it.
    config_key: str = ""
    demo: Callable[[], Any] | None = None
    extra_actions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def widget_id(self) -> str:
        return f"core.{self.game_id}"

    @property
    def mode(self) -> str:
        return self.game_id

    @property
    def actions(self) -> tuple[str, ...]:
        return tuple(self.factory.actions) + self.extra_actions + COMMON_ACTIONS  # type: ignore[attr-defined]


GAMES: dict[str, GameSpec] = {
    spec.game_id: spec
    for spec in (
        GameSpec(
            game_id="tetris",
            name="Tetris",
            summary="Stack falling tetrominoes and clear lines.",
            factory=TetrisGame,
            layout=TETRIS_PAD,
            config_key="tetris",
            demo=tetris_demo_snapshot,
        ),
        GameSpec(
            game_id="pacman",
            name="Pac-Man",
            summary="Clear the maze while four ghosts hunt you down.",
            factory=PacmanGame,
            layout=DPAD,
            config_key="pacman",
        ),
        GameSpec(
            game_id="snake",
            name="Snake",
            summary="Eat, grow, and do not bite yourself.",
            factory=SnakeGame,
            layout=DPAD,
            config_key="snake",
        ),
        GameSpec(
            game_id="breakout",
            name="Breakout",
            summary="Bounce the ball and clear every brick.",
            factory=BreakoutGame,
            layout=HORIZONTAL,
            config_key="breakout",
        ),
        GameSpec(
            game_id="invaders",
            name="Space Invaders",
            summary="Hold off descending waves of aliens.",
            factory=InvadersGame,
            layout=HORIZONTAL,
            config_key="invaders",
        ),
        GameSpec(
            game_id="flappy",
            name="Flappy",
            summary="One button, endless pipes.",
            factory=FlappyGame,
            layout=TAP,
            config_key="flappy",
        ),
        GameSpec(
            game_id="pong",
            name="Pong",
            summary="Rally against the computer or a second phone.",
            factory=PongGame,
            layout=VERTICAL,
            config_key="pong",
        ),
        GameSpec(
            game_id="connect4",
            name="Connect Four",
            summary="Line up four discs before your rival does.",
            factory=ConnectFourGame,
            layout=HORIZONTAL,
            config_key="connect4",
        ),
    )
}

GAME_MODES = tuple(GAMES)


def get_spec(game_id: str) -> GameSpec | None:
    return GAMES.get(game_id)


def spec_for_mode(mode: str) -> GameSpec | None:
    return GAMES.get(mode)


def create_game(game_id: str, config: dict[str, Any] | None = None, seed: int | None = None) -> Game:
    spec = GAMES.get(game_id)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    return spec.factory(config or {}, seed)


def demo_game(game_id: str) -> Game:
    """A game posed mid-play, used for preview tiles."""
    spec = GAMES.get(game_id)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    module = __import__(f"matrix_games.{'connect_four' if game_id == 'connect4' else game_id}", fromlist=["demo_snapshot"])
    demo = getattr(module, "demo_snapshot", None)
    if demo is None:
        return spec.factory({}, 1)
    posed = demo()
    return posed if isinstance(posed, Game) else spec.factory({}, 1)


__all__ = [
    "GAMES",
    "GAME_MODES",
    "GameSpec",
    "Game",
    "COMMON_ACTIONS",
    "PLAYING",
    "PAUSED",
    "GAME_OVER",
    "WON",
    "PANEL",
    "create_game",
    "demo_game",
    "get_spec",
    "spec_for_mode",
    "read_commands",
    "write_state",
    "encode_frame",
    "frame_to_pixels",
    "render_tetris_frame",
    "tetris_demo_snapshot",
]
