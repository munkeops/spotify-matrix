"""The contract every playable matrix game implements.

A game app subclasses :class:`GameApp`, implements ``reset``, ``advance``,
``handle`` and ``render``, and declares the actions it accepts. The host drives
timing and IO, so a game stays pure enough to unit test on its own.
"""

from __future__ import annotations

import random
from typing import Any

from PIL import Image

from assistant_matrix_sdk.audio import Audio, SilentAudio
from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.manifest import (
    COMMON_GAME_ACTIONS,
    AppPermission,
    AppPreview,
    AppTrigger,
    build_app_manifest,
)
from assistant_matrix_sdk.pixels import PANEL, encode_frame
from assistant_matrix_sdk.store import GameStore

PLAYING = "playing"
PAUSED = "paused"
GAME_OVER = "gameOver"
WON = "won"

# Fire/drop buttons deal a new game once the board is finished, but only after
# this long, so a button press already in flight cannot skip the final score.
RESTART_ACTIONS = ("hardDrop", "softDrop", "fire", "flap", "drop", "start")
RESTART_GRACE_SECONDS = 0.8


class GameApp:
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
    #: How many people can play: a count, or (minimum, maximum).
    #:
    #: A game that takes more than one gets its actions tagged with the seat
    #: they came from, so every player sends plain "up" rather than the game
    #: inventing a "p2Up". Seats are filled by using a controller, so a second
    #: pad joins by pressing something.
    players: int | tuple[int, int] = 1
    preview_media = AppPreview()
    permissions: list[AppPermission] = []
    config_fields: list[ConfigField] = []
    triggers: list[AppTrigger] = []

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        seed: int | None = None,
        store: GameStore | None = None,
        audio: Audio | None = None,
    ) -> None:
        self.config = config or {}
        self.random = random.Random(seed)
        # Set before reset() so a game can make a noise as it starts.
        # Silent unless the host hands over a real engine.
        self.audio: Audio = audio if audio is not None else SilentAudio()
        # Set before reset() so a game can read its saved best straight away.
        # Without a path this is in memory, which is what tests and previews get.
        self.store = store if store is not None else GameStore()
        self.paused = False
        self.game_over = False
        self.won = False
        self.game_over_elapsed = 0.0
        self._scored = False
        self.reset()

    # --- subclass hooks -------------------------------------------------

    def reset(self) -> None:
        raise NotImplementedError

    def advance(self, elapsed: float) -> None:
        """Move the game on by ``elapsed`` seconds. Never called while paused."""
        raise NotImplementedError

    def handle(self, action: str, player: int = 0) -> None:
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
            # File the score once, the moment the game ends.
            self._record_final_score()
            self.game_over_elapsed += elapsed
            return
        if self.paused:
            return
        self.advance(elapsed)

    @classmethod
    def player_range(cls) -> tuple[int, int]:
        """Minimum and maximum players, however ``players`` was written."""
        declared = cls.players
        if isinstance(declared, (tuple, list)) and len(declared) == 2:
            low, high = int(declared[0]), int(declared[1])
        else:
            low = high = int(declared)  # type: ignore[arg-type]
        low = max(1, low)
        return low, max(low, high)

    @classmethod
    def max_players(cls) -> int:
        return cls.player_range()[1]

    @classmethod
    def _handle_takes_player(cls) -> bool:
        """Does this game's ``handle`` want to know who pressed the button?

        Most do not, and should not have to grow a parameter they ignore, so
        the seat is only passed to the ones that ask for it.
        """
        cached = cls.__dict__.get("_handle_player_cache")
        if cached is None:
            import inspect

            try:
                parameters = inspect.signature(cls.handle).parameters
            except (TypeError, ValueError):
                cached = False
            else:
                cached = "player" in parameters
            cls._handle_player_cache = cached  # type: ignore[attr-defined]
        return bool(cached)

    def command(self, action: str, player: int = 0) -> None:
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
        if self._handle_takes_player():
            self.handle(action, player=player)
        else:
            self.handle(action)

    def final_score(self) -> int | None:
        """The number worth remembering, or None for a game without a score.

        Defaults to a ``score`` attribute, so most games need do nothing.
        """
        score = getattr(self, "score", None)
        return int(score) if isinstance(score, (int, float)) else None

    def _record_final_score(self) -> None:
        if self._scored:
            return
        self._scored = True
        score = self.final_score()
        if score is None:
            self.store.record_play()
        else:
            self.store.record_score(score)

    def restart(self) -> None:
        self.paused = False
        self.game_over = False
        self.won = False
        self.game_over_elapsed = 0.0
        self._scored = False
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
    def app_id(cls) -> str:
        return cls.id or f"core.{cls.game_id}"

    @classmethod
    def all_actions(cls) -> tuple[str, ...]:
        """Everything this game accepts, including the universal controls."""
        return tuple(cls.actions) + COMMON_GAME_ACTIONS

    @classmethod
    def manifest(cls, *, entrypoint: str = "") -> dict[str, Any]:
        return build_app_manifest(
            app_id=cls.app_id(),
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
Game = GameApp

__all__ = [
    "GameWidget",
    "GameApp",
    "Game",
    "PLAYING",
    "PAUSED",
    "GAME_OVER",
    "WON",
    "RESTART_ACTIONS",
    "RESTART_GRACE_SECONDS",
]


# The names these had before apps were called apps.
#
# Kept on the module as well as the package, because importing
# straight from the module is just as common as importing from the
# package, and both used to work.
GameWidget = GameApp
