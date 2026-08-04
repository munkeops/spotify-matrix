"""Re-exports of the SDK game contract."""

from __future__ import annotations

from assistant_matrix_sdk.game import (  # noqa: F401
    GAME_OVER,
    PAUSED,
    PLAYING,
    RESTART_ACTIONS,
    RESTART_GRACE_SECONDS,
    WON,
    Game,
    GameWidget,
)

__all__ = ["Game", "GameWidget", "PLAYING", "PAUSED", "GAME_OVER", "WON", "RESTART_ACTIONS", "RESTART_GRACE_SECONDS"]
