"""Widget image asset upload and preview routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.domain.models.api_schemas import AssetUploadRequest, AssetUploadResponse
from src.domain.services.asset_service import asset_service

router = APIRouter(tags=["assistant-matrix-assets"])


@router.post("/api/assets/upload", response_model=AssetUploadResponse)
async def upload_asset(body: AssetUploadRequest) -> AssetUploadResponse:
    name = asset_service.save_upload(body.data, body.name)
    return AssetUploadResponse(ok=True, assetPath=name, url=f"/api/assets/{name}")


@router.get("/api/assets/{name}")
async def get_asset(name: str) -> FileResponse:
    path = asset_service.asset_path(name)
    return FileResponse(path, media_type="image/png")
