"""High score routes for game plugins."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import GameScoresResponse
from src.domain.services.game_service import game_service

router = APIRouter(tags=["assistant-matrix-games"])


@router.get("/api/games/{game_id}/scores", response_model=GameScoresResponse)
async def get_game_scores(game_id: str) -> GameScoresResponse:
    game_service.require_spec(game_id)
    return GameScoresResponse(gameId=game_id, **game_service.read_scores(game_id))


@router.delete("/api/games/{game_id}/scores", response_model=GameScoresResponse)
async def clear_game_scores(game_id: str) -> GameScoresResponse:
    game_service.require_spec(game_id)
    return GameScoresResponse(gameId=game_id, **game_service.clear_scores(game_id))
