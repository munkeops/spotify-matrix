"""Pairing-token service for laptop OAuth helper."""

from __future__ import annotations

import base64
import secrets
import os
import time
import urllib.parse
import urllib.request
import json

from configs import base_config
from src.domain.models.api_schemas import AuthSessionResponse, AuthSessionSecrets
from src.domain.services.config_service import config_service

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


class AuthService:
    def __init__(self) -> None:
        self._sessions: dict[str, float] = {}
        self._oauth_states: dict[str, float] = {}

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

    def create_authorization_url(self) -> str:
        config = config_service.get_config()
        missing = []
        if not config.spotify.clientId:
            missing.append("Spotify Client ID")
        if not config.spotify.clientSecret:
            missing.append("Spotify Client Secret")
        if not config.spotify.redirectUri:
            missing.append("Spotify Redirect URI")
        if missing:
            raise ValueError(f"Missing {', '.join(missing)}")

        self._cleanup()
        state = secrets.token_urlsafe(18)
        ttl = int(base_config["runtime"]["pairing_ttl_s"])
        self._oauth_states[state] = time.time() + ttl
        query = urllib.parse.urlencode(
            {
                "client_id": config.spotify.clientId,
                "response_type": "code",
                "redirect_uri": config.spotify.redirectUri,
                "scope": str(base_config["spotify"]["scope"]),
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def complete_authorization(self, code: str, state: str) -> None:
        self._cleanup()
        if state not in self._oauth_states:
            raise ValueError("Spotify authorization session expired or did not match.")

        config = config_service.get_config()
        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.spotify.redirectUri,
            }
        ).encode("utf-8")
        auth = base64.b64encode(f"{config.spotify.clientId}:{config.spotify.clientSecret}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            TOKEN_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            token = json.loads(response.read().decode("utf-8"))

        config_service.save_token(token)
        self._oauth_states.pop(state, None)

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
        expired_states = [state for state, expires_at in self._oauth_states.items() if expires_at <= now]
        for state in expired_states:
            self._oauth_states.pop(state, None)


auth_service = AuthService()
