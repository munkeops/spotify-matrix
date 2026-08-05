"""Command REST routes for UI and future agent control."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import CommandRequest, CommandResponse
from src.domain.services.config_service import config_service
from src.domain.services.display_policy_runner_service import display_policy_runner_service
from src.domain.services.runtime_service import runtime_service
from src.domain.services.app_registry_service import app_registry_service

router = APIRouter(tags=["assistant-matrix-commands"])


@router.post("/api/commands", response_model=CommandResponse)
async def run_command(body: CommandRequest) -> CommandResponse:
    config = config_service.get_config()

    if body.command == "set_mode":
        if body.value not in {"spotify", "clock", "agent", "weather", "testPattern"}:
            raise ValueError("Mode must be spotify, clock, agent, weather, or testPattern.")
        config.display.mode = str(body.value)
        config.runtime.testPattern = body.value == "testPattern"
        config_service.save_config(config)
        runtime = runtime_service.apply()
        matched = None
        app_id = None
    elif body.command == "set_app":
        app_id = str(body.value or "")
        if not app_id:
            raise ValueError("set_app needs a app id value.")
        _, runtime = app_registry_service.apply_app(app_id)
        matched = True
    elif body.command == "set_clock_face":
        if body.value not in {"analog", "digital", "minimal"}:
            raise ValueError("Clock face must be analog, digital, or minimal.")
        config.clock.face = str(body.value)
        config_service.save_config(config)
        runtime = runtime_service.apply()
        matched = None
        app_id = None
    elif body.command == "set_brightness":
        value = int(body.value or 0)
        if value < 1 or value > 100:
            raise ValueError("Brightness must be between 1 and 100.")
        config.matrix.brightness = value
        config_service.save_config(config)
        runtime = runtime_service.apply()
        matched = None
        app_id = None
    elif body.command == "trigger_event":
        event = str(body.value or "")
        if not event:
            raise ValueError("trigger_event needs an event name value.")
        _, runtime, app_id = display_policy_runner_service.trigger_event(event)
        matched = app_id is not None
    elif body.command == "start_runtime":
        runtime = runtime_service.start()
        matched = None
        app_id = None
    elif body.command == "stop_runtime":
        runtime = runtime_service.stop()
        matched = None
        app_id = None
    else:
        raise ValueError("Unsupported command.")

    return CommandResponse(ok=True, config=config_service.get_public_config(), runtime=runtime, matched=matched, appId=app_id)
