"""Persistent configuration and token storage for Spotify Matrix."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from configs import base_config
from src.domain.models.api_schemas import AppConfig, TokenStatus


class ConfigService:
    def __init__(self) -> None:
        paths = base_config["paths"]
        self.data_dir = Path(os.environ.get("SPOTIFY_MATRIX_DATA_DIR", paths["data_dir"])).resolve()
        self.config_path = Path(os.environ.get("SPOTIFY_MATRIX_CONFIG", self.data_dir / paths["config_file"])).resolve()
        self.token_path = Path(os.environ.get("SPOTIFY_TOKEN_CACHE", self.data_dir / paths["token_file"])).resolve()

    def get_config(self) -> AppConfig:
        payload = self._read_json(self.config_path, {})
        return AppConfig.model_validate(payload)

    def get_public_config(self) -> AppConfig:
        config = self.get_config()
        if config.spotify.clientSecret:
            config.spotify.clientSecret = "********"
        return config

    def save_config(self, config: AppConfig) -> AppConfig:
        current = self.get_config()
        if config.spotify.clientSecret == "********":
            config.spotify.clientSecret = current.spotify.clientSecret
        self._write_json(self.config_path, config.model_dump())
        return self.get_public_config()

    def token_status(self) -> TokenStatus:
        token = self._read_json(self.token_path, None)
        if not token:
            return TokenStatus(present=False, hasRefreshToken=False)
        return TokenStatus(
            present=True,
            hasRefreshToken=bool(token.get("refresh_token")),
            expiresAt=token.get("expires_at"),
        )

    def save_token(self, token: dict[str, Any]) -> TokenStatus:
        token = {
            **token,
            "expires_at": time.time() + int(token.get("expires_in", 3600)) - 60,
        }
        self._write_json(self.token_path, token)
        return self.token_status()

    def missing_values(self, config: AppConfig) -> list[str]:
        missing = []
        if config.display.mode == "weather":
            has_coordinates = config.weather.latitude is not None and config.weather.longitude is not None
            if not config.weather.postalCode and not has_coordinates:
                missing.append("Weather ZIP/postal code or coordinates")
            return missing
        if config.display.mode != "spotify":
            return missing
        if not config.spotify.clientId:
            missing.append("Spotify Client ID")
        if not config.spotify.clientSecret:
            missing.append("Spotify Client Secret")
        if not self.token_status().hasRefreshToken:
            missing.append("Spotify refresh token")
        return missing

    def _read_json(self, path: Path, fallback: Any) -> Any:
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return fallback

    def _write_json(self, path: Path, value: Any) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(value, file, indent=2)
            file.write("\n")


config_service = ConfigService()
