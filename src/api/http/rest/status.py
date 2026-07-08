"""Status REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import StatusResponse
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service

router = APIRouter(tags=["spotify-matrix-status"])


@router.get("/api/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    config = config_service.get_config()
    missing = config_service.missing_values(config)
    return StatusResponse(
        configured=not missing,
        missing=missing,
        token=config_service.token_status(),
        runtime=runtime_service.state(),
        dataDir=str(config_service.data_dir),
    )
