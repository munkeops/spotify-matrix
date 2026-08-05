"""Game controller REST routes shared by every matrix game."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import (
    GameInputRequest,
    GameInputResponse,
    GameListResponse,
    GameStateResponse,
    GameSummary,
)
from src.domain.services.game_service import game_service
from src.domain.services.runtime_service import runtime_service

router = APIRouter(tags=["assistant-matrix-games"])


@router.get("/api/games", response_model=GameListResponse)
async def list_games() -> GameListResponse:
    active = game_service.active_game_id()
    games = [
        GameSummary(
            id=spec.game_id,
            name=spec.name,
            summary=spec.summary,
            appId=spec.app_id,
            layout=spec.layout,
            actions=list(spec.actions),
            active=spec.game_id == active,
        )
        for spec in sorted(game_service.specs().values(), key=lambda spec: spec.name)
    ]
    return GameListResponse(games=games, activeGameId=active, running=runtime_service.state().running)


@router.post("/api/games/{game_id}/input", response_model=GameInputResponse)
async def send_game_input(game_id: str, body: GameInputRequest) -> GameInputResponse:
    seq = game_service.queue_command(game_id, body.action)
    return GameInputResponse(ok=True, gameId=game_id, seq=seq, action=body.action)


@router.get("/api/games/{game_id}/state", response_model=GameStateResponse)
async def get_game_state(game_id: str) -> GameStateResponse:
    state = game_service.read_state(game_id)
    return GameStateResponse(
        gameId=game_id,
        live=game_service.is_live(state),
        running=runtime_service.state().running,
        active=game_service.active_game_id() == game_id,
        state=state,
    )
