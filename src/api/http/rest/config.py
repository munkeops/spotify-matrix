"""Configuration REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.domain.models.api_schemas import AppConfig, ImageUploadResponse
from src.domain.services.config_service import config_service

router = APIRouter(tags=["spotify-matrix-config"])


@router.get("/api/config", response_model=AppConfig)
async def get_config() -> AppConfig:
    return config_service.get_public_config()


@router.post("/api/config", response_model=AppConfig)
async def save_config(body: AppConfig) -> AppConfig:
    return config_service.save_config(body)


@router.post("/api/display/image", response_model=ImageUploadResponse)
async def upload_display_image(request: Request) -> ImageUploadResponse:
    content = await request.body()
    if not content:
        raise ValueError("Upload body is empty.")
    return ImageUploadResponse(imagePath=config_service.save_display_image(content))
