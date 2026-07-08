"""Persistent configuration and token storage for Spotify Matrix."""

from __future__ import annotations

import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

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
        if config.runtime.testPattern:
            return missing
        if config.runtime.displayMode == "spotify":
            if not config.spotify.clientId:
                missing.append("Spotify Client ID")
            if not config.spotify.clientSecret:
                missing.append("Spotify Client Secret")
            if not self.token_status().hasRefreshToken:
                missing.append("Spotify refresh token")
        if config.runtime.displayMode == "image" and not config.runtime.imagePath:
            missing.append("Uploaded image")
        return missing

    def save_display_image(self, content: bytes) -> str:
        try:
            image = Image.open(BytesIO(content)).convert("RGB")
        except Exception as exc:
            raise ValueError("Upload must be a readable image file.") from exc

        target = self.data_dir / "uploaded_image.png"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        image.save(target)

        config = self.get_config()
        config.runtime.imagePath = str(target)
        config.runtime.displayMode = "image"
        self.save_config(config)
        return str(target)

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
