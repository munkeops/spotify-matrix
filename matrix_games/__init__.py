"""Playable games for the Assistant Matrix panel.

Games are not built into the app. Each one is a app package with a
``app.toml`` declaring ``kind = "game"`` and a Python entrypoint exposing a
:class:`assistant_matrix_sdk.game.GameApp` subclass. The ones that ship with
Assistant Matrix live in ``store_apps/``; anything you install lands in
``<data>/apps/packages/`` and is picked up the same way.

Adding a game is dropping in a folder. See ``docs/game-apps.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from assistant_matrix_sdk.game import GAME_OVER, PAUSED, PLAYING, WON, GameApp
from assistant_matrix_sdk.manifest import COMMON_GAME_ACTIONS, GAME_LAYOUTS
from assistant_matrix_sdk.pixels import PANEL, encode_frame, frame_to_pixels
from assistant_matrix_sdk.store import GameStore
from matrix_games.io import read_commands, write_state
from matrix_games.registry import BUNDLED_DIR, GAME_KIND, GameSpec, demo_instance, discover, load_game_class, load_module

# Layout names, re-exported so callers do not reach into the SDK for them.
DPAD, HORIZONTAL, VERTICAL, TAP, TETRIS_PAD = GAME_LAYOUTS

Game = GameApp


def games(installed_dir: Path | None = None) -> dict[str, GameSpec]:
    """Every available game, bundled plus installed."""
    return discover(installed_dir)


def get_spec(game_id: str, installed_dir: Path | None = None) -> GameSpec | None:
    return discover(installed_dir).get(game_id)


def create_game(
    game_id: str,
    config: dict[str, Any] | None = None,
    seed: int | None = None,
    installed_dir: Path | None = None,
    store: GameStore | None = None,
    audio: Any = None,
) -> GameApp:
    spec = get_spec(game_id, installed_dir)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    return spec.create(config, seed, store, audio)


def app_module(game_id: str, installed_dir: Path | None = None):
    """The imported module behind a game, for its constants and helpers."""
    spec = get_spec(game_id, installed_dir)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    return load_module(spec)


def game_class(game_id: str, installed_dir: Path | None = None) -> type[GameApp]:
    spec = get_spec(game_id, installed_dir)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    return spec.load()


def demo_game(game_id: str, installed_dir: Path | None = None) -> GameApp:
    spec = get_spec(game_id, installed_dir)
    if spec is None:
        raise ValueError(f"Unknown game {game_id}.")
    return demo_instance(spec)


class _GameMapping(dict):
    """``GAMES`` reads as a dict but re-scans the app directories on use.

    Keeping it live means installing a game makes it appear without a restart.
    """

    def _refresh(self) -> dict[str, GameSpec]:
        current = discover()
        super().clear()
        super().update(current)
        return current

    def __getitem__(self, key):  # type: ignore[override]
        self._refresh()
        return super().__getitem__(key)

    def __contains__(self, key) -> bool:  # type: ignore[override]
        self._refresh()
        return super().__contains__(key)

    def __iter__(self):  # type: ignore[override]
        self._refresh()
        return super().__iter__()

    def __len__(self) -> int:  # type: ignore[override]
        self._refresh()
        return super().__len__()

    def get(self, key, default=None):  # type: ignore[override]
        self._refresh()
        return super().get(key, default)

    def keys(self):  # type: ignore[override]
        self._refresh()
        return super().keys()

    def values(self):  # type: ignore[override]
        self._refresh()
        return super().values()

    def items(self):  # type: ignore[override]
        self._refresh()
        return super().items()


#: Bundled games, refreshed on access.
GAMES: dict[str, GameSpec] = _GameMapping()


def game_modes() -> tuple[str, ...]:
    return tuple(discover())


__all__ = [
    "GAMES",
    "GameSpec",
    "GameApp",
    "GameStore",
    "Game",
    "BUNDLED_DIR",
    "GAME_KIND",
    "COMMON_GAME_ACTIONS",
    "GAME_LAYOUTS",
    "DPAD",
    "HORIZONTAL",
    "VERTICAL",
    "TAP",
    "TETRIS_PAD",
    "PLAYING",
    "PAUSED",
    "GAME_OVER",
    "WON",
    "PANEL",
    "games",
    "game_modes",
    "get_spec",
    "create_game",
    "demo_game",
    "discover",
    "load_game_class",
    "load_module",
    "app_module",
    "game_class",
    "read_commands",
    "write_state",
    "encode_frame",
    "frame_to_pixels",
]
