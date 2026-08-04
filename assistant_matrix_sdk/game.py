"""The contract every playable matrix game implements.

A game plugin subclasses :class:`GameWidget`, implements ``reset``, ``advance``,
``handle`` and ``render``, and declares the actions it accepts. The host drives
timing and IO, so a game stays pure enough to unit test on its own.
"""

from __future__ import annotations

import random
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.manifest import (
    COMMON_GAME_ACTIONS,
    WidgetPermission,
    WidgetPreview,
    WidgetTrigger,
    build_widget_manifest,
)
from assistant_matrix_sdk.pixels import PANEL, encode_frame

PLAYING = "playing"
PAUSED = "paused"
GAME_OVER = "gameOver"
WON = "won"

# Fire/drop buttons deal a new game once the board is finished, but only after
# this long, so a button press already in flight cannot skip the final score.
RESTART_ACTIONS = ("hardDrop", "softDrop", "fire", "flap", "drop", "start")
RESTART_GRACE_SECONDS = 0.8


class GameWidget:
    """A game the host steps, renders and publishes once per frame.

    Subclasses implement ``reset``, ``advance``, ``handle`` and ``render``.
    ``layout`` tells a controller which pad to draw: ``dpad``, ``horizontal``,
    ``vertical``, ``tap`` or ``tetris``.
    """

    game_id = ""
    id = ""
    name = ""
    summary = ""
    version = "1.0.0"
    author = "Assistant Matrix"
    category = "games"
    license = "MIT"
    matrix_size = "64x64"
    layout = "dpad"
    # Actions accepted beyond the universally handled pause/resume/restart set.
    actions: tuple[str, ...] = ()
    preview_media = WidgetPreview()
    permissions: list[WidgetPermission] = []
    config_fields: list[ConfigField] = []
    triggers: list[WidgetTrigger] = []

    def __init__(self, config: dict[str, Any] | None = None, seed: int | None = None) -> None:
        self.config = config or {}
        self.random = random.Random(seed)
        self.paused = False
        self.game_over = False
        self.won = False
        self.game_over_elapsed = 0.0
        self.reset()

    # --- subclass hooks -------------------------------------------------

    def reset(self) -> None:
        raise NotImplementedError

    def advance(self, elapsed: float) -> None:
        """Move the game on by ``elapsed`` seconds. Never called while paused."""
        raise NotImplementedError

    def handle(self, action: str) -> None:
        """Apply a controller action. Never called while paused or finished."""

    def render(self, size: int = PANEL) -> Image.Image:
        raise NotImplementedError

    def hud(self) -> dict[str, Any]:
        """Label/value pairs the app shows next to the board."""
        return {}

    def extra(self) -> dict[str, Any]:
        """Extra structured fields to publish alongside the frame."""
        return {}

    # --- runtime facing -------------------------------------------------

    def status(self) -> str:
        if self.won:
            return WON
        if self.game_over:
            return GAME_OVER
        if self.paused:
            return PAUSED
        return PLAYING

    def finished(self) -> bool:
        return self.game_over or self.won

    def step(self, elapsed: float) -> None:
        elapsed = max(0.0, elapsed)
        if self.finished():
            self.game_over_elapsed += elapsed
            return
        if self.paused:
            return
        self.advance(elapsed)

    def command(self, action: str) -> None:
        if action == "restart":
            self.restart()
            return
        if action in ("pause", "resume", "togglePause"):
            self.paused = action == "pause" or (action == "togglePause" and not self.paused)
            return
        if self.finished():
            if action in RESTART_ACTIONS and self.game_over_elapsed >= RESTART_GRACE_SECONDS:
                self.restart()
            return
        if self.paused:
            return
        self.handle(action)

    def restart(self) -> None:
        self.paused = False
        self.game_over = False
        self.won = False
        self.game_over_elapsed = 0.0
        self.reset()

    def snapshot(self, image: Image.Image | None = None, size: int = PANEL) -> dict[str, Any]:
        frame = image if image is not None else self.render(size)
        return {
            "game": self.game_id,
            "status": self.status(),
            "hud": self.hud(),
            **encode_frame(frame),
            **self.extra(),
        }


    @classmethod
    def widget_id(cls) -> str:
        return cls.id or f"core.{cls.game_id}"

    @classmethod
    def all_actions(cls) -> tuple[str, ...]:
        """Everything this game accepts, including the universal controls."""
        return tuple(cls.actions) + COMMON_GAME_ACTIONS

    @classmethod
    def manifest(cls, *, entrypoint: str = "") -> dict[str, Any]:
        return build_widget_manifest(
            widget_id=cls.widget_id(),
            name=cls.name,
            version=cls.version,
            summary=cls.summary,
            author=cls.author,
            category=cls.category,
            runtime="python",
            entrypoint=entrypoint,
            matrix_size=cls.matrix_size,
            license=cls.license,
            preview=cls.preview_media,
            permissions=cls.permissions,
            config=cls.config_fields,
            triggers=cls.triggers,
            kind="game",
            layout=cls.layout,
            actions=list(cls.all_actions()),
        )


#: Games were called ``Game`` before the contract moved into the SDK.
Game = GameWidget

__all__ = [
    "GameWidget",
    "Game",
    "PLAYING",
    "PAUSED",
    "GAME_OVER",
    "WON",
    "RESTART_ACTIONS",
    "RESTART_GRACE_SECONDS",
]
