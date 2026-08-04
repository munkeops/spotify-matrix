"""Audio settings routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.domain.models.api_schemas import AudioConfigRequest, AudioStateResponse, AudioTestRequest
from src.domain.services.audio_service import audio_service
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service

router = APIRouter(tags=["assistant-matrix-audio"])


@router.get("/api/audio", response_model=AudioStateResponse)
async def get_audio_state() -> AudioStateResponse:
    return AudioStateResponse(**audio_service.state())


@router.post("/api/audio/config", response_model=AudioStateResponse)
async def save_audio_config(body: AudioConfigRequest) -> AudioStateResponse:
    config = config_service.get_config()
    payload = config.audio.model_dump()
    payload.update(body.config)
    config.audio = type(config.audio).model_validate(payload)
    config_service.save_config(config)
    # The runtime opens the sound card at launch, so restart it if one is up.
    if runtime_service.state().running:
        runtime_service.apply()
    return AudioStateResponse(**audio_service.state())


@router.post("/api/audio/test")
async def test_audio(body: AudioTestRequest) -> dict[str, Any]:
    """Play one effect immediately, to prove the output works."""
    return audio_service.play_test(body.sound)
