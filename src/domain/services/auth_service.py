"""Pairing-token service for laptop OAuth helper."""

from __future__ import annotations

import secrets
import os
import time

from configs import base_config
from src.domain.models.api_schemas import AuthSessionResponse, AuthSessionSecrets
from src.domain.services.config_service import config_service


class AuthService:
    def __init__(self) -> None:
        self._sessions: dict[str, float] = {}

    def create_pairing_session(self) -> AuthSessionResponse:
        config = config_service.get_config()
        missing = []
        if not config.spotify.clientId:
            missing.append("Spotify Client ID")
        if not config.spotify.clientSecret:
            missing.append("Spotify Client Secret")
        if missing:
            raise ValueError(f"Missing {', '.join(missing)}")

        self._cleanup()
        token = secrets.token_urlsafe(18)
        ttl = int(base_config["runtime"]["pairing_ttl_s"])
        self._sessions[token] = time.time() + ttl
        port = int(os.environ.get("PORT", str(base_config["http"]["port"])))
        return AuthSessionResponse(
            pairingToken=token,
            expiresInSeconds=ttl,
            command=f"python scripts/oauth_helper.py --pi http://<pi-host>:{port} --pairing-token {token}",
        )

    def get_pairing_session(self, token: str) -> AuthSessionSecrets:
        self.validate_pairing_token(token)
        config = config_service.get_config()
        return AuthSessionSecrets(
            clientId=config.spotify.clientId,
            clientSecret=config.spotify.clientSecret,
            scope=str(base_config["spotify"]["scope"]),
        )

    def validate_pairing_token(self, token: str) -> None:
        self._cleanup()
        if token not in self._sessions:
            raise ValueError("Pairing session expired or not found.")

    def consume_pairing_token(self, token: str) -> None:
        self._sessions.pop(token, None)

    def _cleanup(self) -> None:
        now = time.time()
        expired = [token for token, expires_at in self._sessions.items() if expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)


auth_service = AuthService()
