"""Tetris controller REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import TetrisInputRequest, TetrisInputResponse, TetrisStateResponse
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service
from src.domain.services.tetris_service import tetris_service

router = APIRouter(tags=["assistant-matrix-tetris"])


@router.post("/api/tetris/input", response_model=TetrisInputResponse)
async def send_tetris_input(body: TetrisInputRequest) -> TetrisInputResponse:
    seq = tetris_service.queue_command(body.action)
    return TetrisInputResponse(ok=True, seq=seq, action=body.action)


@router.get("/api/tetris/state", response_model=TetrisStateResponse)
async def get_tetris_state() -> TetrisStateResponse:
    state = tetris_service.read_state()
    config = config_service.get_config()
    return TetrisStateResponse(
        live=tetris_service.is_live(state),
        running=runtime_service.state().running,
        active=config.display.mode == "tetris" and not config.runtime.testPattern,
        state=state,
    )
