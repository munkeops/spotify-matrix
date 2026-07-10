"""Display policy REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.widget_schemas import DisplayPolicyResponse, DisplayPolicyUpdateRequest
from src.domain.services.display_policy_service import display_policy_service

router = APIRouter(tags=["assistant-matrix-display"])


@router.get("/api/display/policy", response_model=DisplayPolicyResponse)
async def get_display_policy() -> DisplayPolicyResponse:
    return DisplayPolicyResponse(policy=display_policy_service.get_policy())


@router.post("/api/display/policy", response_model=DisplayPolicyResponse)
async def update_display_policy(body: DisplayPolicyUpdateRequest) -> DisplayPolicyResponse:
    return DisplayPolicyResponse(policy=display_policy_service.save_policy(body.policy))
