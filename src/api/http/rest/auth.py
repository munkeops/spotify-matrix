"""Spotify OAuth pairing REST routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from src.domain.models.api_schemas import AuthSessionResponse, AuthSessionSecrets, TokenRequest, TokenSaveResponse
from src.domain.services.auth_service import auth_service
from src.domain.services.config_service import config_service

router = APIRouter(tags=["spotify-matrix-auth"])


@router.post("/api/auth/session", response_model=AuthSessionResponse)
async def create_auth_session() -> AuthSessionResponse:
    return auth_service.create_pairing_session()


@router.get("/api/auth/login")
async def login_with_spotify() -> RedirectResponse:
    return RedirectResponse(auth_service.create_authorization_url())


@router.get("/api/auth/callback", response_class=HTMLResponse)
async def spotify_auth_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> HTMLResponse:
    if error:
        return HTMLResponse(f"<h1>Spotify authorization failed</h1><p>{error}</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h1>Spotify authorization failed</h1><p>Missing code or state.</p>", status_code=400)
    auth_service.complete_authorization(code=code, state=state)
    return HTMLResponse("<h1>Spotify Matrix is paired.</h1><p>You can close this tab and return to the setup UI.</p>")


@router.get("/api/auth/session/{pairing_token}", response_model=AuthSessionSecrets)
async def get_auth_session(pairing_token: str) -> AuthSessionSecrets:
    return auth_service.get_pairing_session(pairing_token)


@router.post("/api/token", response_model=TokenSaveResponse)
async def save_token(body: TokenRequest) -> TokenSaveResponse:
    auth_service.validate_pairing_token(body.pairingToken)
    status = config_service.save_token(body.token.model_dump())
    auth_service.consume_pairing_token(body.pairingToken)
    return TokenSaveResponse(ok=True, token=status)
