"""Command REST routes for UI and future agent control."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import CommandRequest, CommandResponse
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service

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
    elif body.command == "set_clock_face":
        if body.value not in {"analog", "digital", "minimal"}:
            raise ValueError("Clock face must be analog, digital, or minimal.")
        config.clock.face = str(body.value)
        config_service.save_config(config)
        runtime = runtime_service.apply()
    elif body.command == "set_brightness":
        value = int(body.value or 0)
        if value < 1 or value > 100:
            raise ValueError("Brightness must be between 1 and 100.")
        config.matrix.brightness = value
        config_service.save_config(config)
        runtime = runtime_service.apply()
    elif body.command == "start_runtime":
        runtime = runtime_service.start()
    elif body.command == "stop_runtime":
        runtime = runtime_service.stop()
    else:
        raise ValueError("Unsupported command.")

    return CommandResponse(ok=True, config=config_service.get_public_config(), runtime=runtime)
