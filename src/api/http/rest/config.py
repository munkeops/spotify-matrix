"""Configuration REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import AppConfig
from src.domain.services.config_service import config_service

router = APIRouter(tags=["spotify-matrix-config"])


@router.get("/api/config", response_model=AppConfig)
async def get_config() -> AppConfig:
    return config_service.get_public_config()


@router.post("/api/config", response_model=AppConfig)
async def save_config(body: AppConfig) -> AppConfig:
    return config_service.save_config(body)
