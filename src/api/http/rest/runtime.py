"""Matrix runtime REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import RuntimeActionResponse
from src.domain.services.display_policy_runner_service import display_policy_runner_service
from src.domain.services.runtime_service import runtime_service

router = APIRouter(tags=["spotify-matrix-runtime"])


@router.post("/api/runtime/start", response_model=RuntimeActionResponse)
async def start_runtime() -> RuntimeActionResponse:
    return RuntimeActionResponse(runtime=runtime_service.start())


@router.post("/api/runtime/stop", response_model=RuntimeActionResponse)
async def stop_runtime() -> RuntimeActionResponse:
    display_policy_runner_service.stop()
    return RuntimeActionResponse(runtime=runtime_service.stop())


@router.post("/api/runtime/apply", response_model=RuntimeActionResponse)
async def apply_runtime() -> RuntimeActionResponse:
    return RuntimeActionResponse(runtime=runtime_service.apply())
