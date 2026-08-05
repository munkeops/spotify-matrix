"""What the mini-joystick's buttons do while it is on device duty."""

from __future__ import annotations

from fastapi import APIRouter

from mini_joystick.bindings import DEFAULT_SYSTEM_BINDINGS, SYSTEM_ACTIONS, SYSTEM_CONTROLS, profile
from mini_joystick.bindings import MODULE
from src.domain.models.api_schemas import SystemControlsResponse, SystemControlsRequest
from src.domain.services.config_service import config_service

router = APIRouter(tags=["assistant-matrix-input"])


def _response() -> SystemControlsResponse:
    saved = config_service.get_config().joystick.systemBindings
    bindings = dict(DEFAULT_SYSTEM_BINDINGS)
    bindings.update({key: value for key, value in saved.items() if value})
    module = profile(MODULE)
    return SystemControlsResponse(
        controls=list(SYSTEM_CONTROLS),
        labels={control: module.label(control) for control in SYSTEM_CONTROLS},
        actions=[{"action": action, "label": label} for action, label in SYSTEM_ACTIONS],
        bindings=bindings,
        defaults=dict(DEFAULT_SYSTEM_BINDINGS),
        customised=sorted(
            control for control, action in bindings.items() if DEFAULT_SYSTEM_BINDINGS.get(control) != action
        ),
    )


@router.get("/api/joystick/system-controls", response_model=SystemControlsResponse)
async def get_system_controls() -> SystemControlsResponse:
    return _response()


@router.post("/api/joystick/system-controls", response_model=SystemControlsResponse)
async def save_system_controls(body: SystemControlsRequest) -> SystemControlsResponse:
    known = {action for action, _ in SYSTEM_ACTIONS}
    unknown_action = sorted(value for value in body.bindings.values() if value not in known)
    if unknown_action:
        raise ValueError(f"Unknown action: {', '.join(unknown_action)}")
    unknown_control = sorted(key for key in body.bindings if key not in SYSTEM_CONTROLS)
    if unknown_control:
        raise ValueError(f"The module has no {', '.join(unknown_control)}")

    config = config_service.get_config()
    config.joystick.systemBindings = dict(body.bindings)
    config_service.save_config(config)
    return _response()


@router.delete("/api/joystick/system-controls", response_model=SystemControlsResponse)
async def reset_system_controls() -> SystemControlsResponse:
    config = config_service.get_config()
    config.joystick.systemBindings = {}
    config_service.save_config(config)
    return _response()
