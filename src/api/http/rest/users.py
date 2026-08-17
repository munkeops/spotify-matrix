"""Profile routes: who is using this unit."""

from __future__ import annotations

from fastapi import APIRouter

from matrix_users import ProfileError
from src.domain.models.api_schemas import (
    UserCreateRequest,
    UserProfile,
    UserSignInRequest,
    UsersResponse,
    UserUpdateRequest,
)
from src.domain.services.user_service import user_service

router = APIRouter(tags=["assistant-matrix-users"])


def _fail(error: ProfileError) -> None:
    """Profile errors are things the person can fix, so they read as 400."""
    raise ValueError(str(error))


@router.get("/api/users", response_model=UsersResponse)
async def list_users() -> UsersResponse:
    return UsersResponse(**user_service.state())


@router.post("/api/users", response_model=UserProfile)
async def create_user(body: UserCreateRequest) -> UserProfile:
    try:
        return UserProfile(**user_service.create(body.name, body.pin))
    except ProfileError as error:
        _fail(error)


@router.post("/api/users/{profile_id}", response_model=UserProfile)
async def update_user(profile_id: str, body: UserUpdateRequest) -> UserProfile:
    try:
        return UserProfile(**user_service.update(profile_id, body.model_dump(exclude_unset=True)))
    except ProfileError as error:
        _fail(error)


@router.delete("/api/users/{profile_id}", response_model=UsersResponse)
async def delete_user(profile_id: str) -> UsersResponse:
    try:
        return UsersResponse(**user_service.delete(profile_id))
    except ProfileError as error:
        _fail(error)


@router.post("/api/users/{profile_id}/sign-in", response_model=UsersResponse)
async def sign_in(profile_id: str, body: UserSignInRequest) -> UsersResponse:
    try:
        return UsersResponse(**user_service.sign_in(profile_id, body.pin))
    except ProfileError as error:
        _fail(error)
