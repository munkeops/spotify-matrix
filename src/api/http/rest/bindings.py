"""Per-game controller binding routes."""

from __future__ import annotations

from fastapi import APIRouter

from mini_joystick.bindings import CONTROLS, default_bindings
from src.domain.models.api_schemas import GameBindingsRequest, GameBindingsResponse
from src.domain.services.config_service import config_service
from src.domain.services.game_service import game_service

router = APIRouter(tags=["assistant-matrix-games"])


def _response(game_id: str) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    actions = list(spec.actions)
    defaults = default_bindings(set(actions))
    saved = config_service.get_config().controller.bindings.get(spec.widget_id, {})
    # Saved values win, but only where the game still declares that action.
    effective = dict(defaults)
    effective.update({key: value for key, value in saved.items() if value in actions or value == "none"})
    return GameBindingsResponse(
        gameId=spec.game_id,
        widgetId=spec.widget_id,
        controls=list(CONTROLS),
        actions=actions,
        bindings=effective,
        defaults=defaults,
    )


@router.get("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def get_game_bindings(game_id: str) -> GameBindingsResponse:
    return _response(game_id)


@router.post("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def save_game_bindings(game_id: str, body: GameBindingsRequest) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    allowed = set(spec.actions) | {"none"}
    invalid = sorted(value for value in body.bindings.values() if value not in allowed)
    if invalid:
        raise ValueError(f"{spec.name} does not accept: {', '.join(invalid)}")
    unknown = sorted(key for key in body.bindings if key not in CONTROLS)
    if unknown:
        raise ValueError(f"Unknown controls: {', '.join(unknown)}")

    config = config_service.get_config()
    bindings = dict(config.controller.bindings)
    bindings[spec.widget_id] = dict(body.bindings)
    config.controller.bindings = bindings
    config_service.save_config(config)
    return _response(game_id)


@router.delete("/api/games/{game_id}/bindings", response_model=GameBindingsResponse)
async def reset_game_bindings(game_id: str) -> GameBindingsResponse:
    spec = game_service.require_spec(game_id)
    config = config_service.get_config()
    bindings = dict(config.controller.bindings)
    bindings.pop(spec.widget_id, None)
    config.controller.bindings = bindings
    config_service.save_config(config)
    return _response(game_id)
