"""Display policy REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.widget_schemas import DisplayPolicyApplyResponse, DisplayPolicyResponse, DisplayPolicyRuntimeState, DisplayPolicyUpdateRequest
from src.domain.services.display_policy_service import display_policy_service
from src.domain.services.display_policy_runner_service import display_policy_runner_service

router = APIRouter(tags=["assistant-matrix-display"])


@router.get("/api/display/policy", response_model=DisplayPolicyResponse)
async def get_display_policy() -> DisplayPolicyResponse:
    return DisplayPolicyResponse(policy=display_policy_service.get_policy())


@router.post("/api/display/policy", response_model=DisplayPolicyResponse)
async def update_display_policy(body: DisplayPolicyUpdateRequest) -> DisplayPolicyResponse:
    return DisplayPolicyResponse(policy=display_policy_service.save_policy(body.policy))


@router.get("/api/display/policy/state", response_model=DisplayPolicyRuntimeState)
async def get_display_policy_state() -> DisplayPolicyRuntimeState:
    return display_policy_runner_service.state()


@router.post("/api/display/policy/apply", response_model=DisplayPolicyApplyResponse)
async def apply_display_policy() -> DisplayPolicyApplyResponse:
    policy = display_policy_service.get_policy()
    state, runtime = display_policy_runner_service.apply_policy(policy)
    return DisplayPolicyApplyResponse(ok=True, policy=policy, state=state, runtime=runtime)


@router.post("/api/display/policy/stop", response_model=DisplayPolicyRuntimeState)
async def stop_display_policy() -> DisplayPolicyRuntimeState:
    return display_policy_runner_service.stop()
