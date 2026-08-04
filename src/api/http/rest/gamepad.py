"""Game controller REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import GamepadConfigRequest, GamepadStateResponse
from src.domain.services.config_service import config_service
from src.domain.services.gamepad_service import gamepad_service

router = APIRouter(tags=["assistant-matrix-gamepad"])


@router.get("/api/gamepad", response_model=GamepadStateResponse)
async def get_gamepad_state() -> GamepadStateResponse:
    """Controllers the kernel can see, and what to do if there are none."""
    return GamepadStateResponse(**gamepad_service.state())


@router.post("/api/gamepad/config", response_model=GamepadStateResponse)
async def save_gamepad_config(body: GamepadConfigRequest) -> GamepadStateResponse:
    config = config_service.get_config()
    payload = config.gamepad.model_dump()
    payload.update(body.config)
    config.gamepad = type(config.gamepad).model_validate(payload)
    config_service.save_config(config)
    # Re-open so a changed device or deadzone takes effect immediately.
    gamepad_service.apply()
    return GamepadStateResponse(**gamepad_service.state())
