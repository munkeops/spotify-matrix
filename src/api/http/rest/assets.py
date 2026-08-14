"""App image asset upload, gallery, and preview routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.domain.models.api_schemas import AssetListResponse, AssetUploadRequest, AssetUploadResponse
from src.domain.services.asset_service import asset_service

router = APIRouter(tags=["assistant-matrix-assets"])

_MEDIA_TYPES = {".png": "image/png", ".gif": "image/gif", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@router.post("/api/assets/upload", response_model=AssetUploadResponse)
async def upload_asset(body: AssetUploadRequest) -> AssetUploadResponse:
    name = asset_service.save_upload(body.data, body.name)
    return AssetUploadResponse(ok=True, assetPath=name, url=f"/api/assets/{name}")


@router.get("/api/assets", response_model=AssetListResponse)
async def list_assets() -> AssetListResponse:
    return AssetListResponse(assets=asset_service.list_assets())


@router.get("/api/assets/{name}")
async def get_asset(name: str) -> FileResponse:
    path = asset_service.asset_path(name)
    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


@router.delete("/api/assets/{name}", response_model=AssetListResponse)
async def delete_asset(name: str) -> AssetListResponse:
    asset_service.delete_asset(name)
    return AssetListResponse(assets=asset_service.list_assets())
