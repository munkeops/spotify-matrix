"""Mini-joystick REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import JoystickConfigRequest, JoystickStateResponse
from src.domain.services.config_service import config_service
from src.domain.services.joystick_service import joystick_service

router = APIRouter(tags=["assistant-matrix-joystick"])


@router.get("/api/joystick", response_model=JoystickStateResponse)
async def get_joystick_state() -> JoystickStateResponse:
    return JoystickStateResponse(**joystick_service.state())


@router.post("/api/joystick/config", response_model=JoystickStateResponse)
async def save_joystick_config(body: JoystickConfigRequest) -> JoystickStateResponse:
    config = config_service.get_config()
    payload = config.joystick.model_dump()
    payload.update(body.config)
    config.joystick = type(config.joystick).model_validate(payload)
    config_service.save_config(config)
    # Re-open the bus so a changed address or deadzone takes effect immediately.
    joystick_service.apply()
    return JoystickStateResponse(**joystick_service.state())


@router.post("/api/joystick/start", response_model=JoystickStateResponse)
async def start_joystick() -> JoystickStateResponse:
    return JoystickStateResponse(**joystick_service.start())


@router.post("/api/joystick/stop", response_model=JoystickStateResponse)
async def stop_joystick() -> JoystickStateResponse:
    return JoystickStateResponse(**joystick_service.stop())
