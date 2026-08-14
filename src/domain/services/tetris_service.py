"""Tetris view over the shared game bridge.

Kept so the original ``/api/tetris/*`` routes and their structured board state
keep working now that every game shares :mod:`game_service`.
"""

from __future__ import annotations

from pathlib import Path

from src.domain.models.api_schemas import TetrisState
from src.domain.services.game_service import QUEUE_LIMIT, STALE_SECONDS, game_service

GAME_ID = "tetris"

__all__ = ["QUEUE_LIMIT", "STALE_SECONDS", "TetrisService", "tetris_service"]


class TetrisService:
    @property
    def state_dir(self) -> Path:
        return game_service.state_dir

    @property
    def input_path(self) -> Path:
        return game_service.input_path(GAME_ID)

    @property
    def state_path(self) -> Path:
        return game_service.state_path(GAME_ID)

    def queue_command(self, action: str) -> int:
        return game_service.queue_command(GAME_ID, action)

    def read_state(self) -> TetrisState | None:
        payload = game_service.read_raw_state(GAME_ID)
        if not payload:
            return None
        return TetrisState.model_validate(payload)

    def is_live(self, state: TetrisState | None) -> bool:
        if state is None or not state.updatedAt:
            return False
        import time

        return (time.time() - state.updatedAt) <= STALE_SECONDS


tetris_service = TetrisService()
