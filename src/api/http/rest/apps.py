"""App registry REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.app_schemas import LocalApp, LocalAppListResponse, StoreApp, AppApplyRequest, AppApplyResponse, AppConfigResponse, AppConfigUpdateRequest, AppInstallRequest, AppInstallResponse, AppPreviewRequest, AppPreviewResponse, AppStoreListResponse, AppUninstallResponse
from src.domain.services.display_policy_runner_service import display_policy_runner_service
from src.domain.services.preview_service import preview_service
from src.domain.services.runtime_service import runtime_service
from src.domain.services.app_registry_service import app_registry_service
from src.domain.services.app_store_service import app_store_service

router = APIRouter(tags=["assistant-matrix-apps"])


@router.get("/api/apps/store", response_model=AppStoreListResponse)
async def list_store_apps() -> AppStoreListResponse:
    index = app_store_service.list_apps()
    return AppStoreListResponse(schemaVersion=index.schemaVersion, apps=index.apps)


@router.get("/api/apps/store/{app_id}", response_model=StoreApp)
async def get_store_app(app_id: str) -> StoreApp:
    app = app_store_service.get_app(app_id)
    if app is None:
        raise ValueError(f"Unknown store app {app_id}.")
    return app


@router.post("/api/apps/install", response_model=AppInstallResponse)
async def install_app(body: AppInstallRequest) -> AppInstallResponse:
    store_app = app_store_service.install_app(body.appId)
    local_app = app_registry_service.get_local_app(store_app.id)
    if local_app is None:
        raise ValueError(f"Installed app {store_app.id} is unavailable locally.")
    return AppInstallResponse(ok=True, app=local_app)


@router.post("/api/apps/preview", response_model=AppPreviewResponse)
async def preview_app(body: AppPreviewRequest) -> AppPreviewResponse:
    data_url = preview_service.render_data_url(body.appId, body.config)
    return AppPreviewResponse(ok=True, appId=body.appId, dataUrl=data_url)


@router.get("/api/apps/local", response_model=LocalAppListResponse)
async def list_local_apps() -> LocalAppListResponse:
    return LocalAppListResponse(apps=app_registry_service.list_local_apps())


@router.get("/api/apps/local/{app_id}", response_model=LocalApp)
async def get_local_app(app_id: str) -> LocalApp:
    app = app_registry_service.get_local_app(app_id)
    if app is None:
        raise ValueError(f"Unknown app {app_id}.")
    return app


@router.delete("/api/apps/local/{app_id}", response_model=AppUninstallResponse)
async def uninstall_app(app_id: str) -> AppUninstallResponse:
    display_policy_runner_service.stop()
    runtime_service.stop()
    app_store_service.uninstall_app(app_id)
    return AppUninstallResponse(ok=True, appId=app_id)


@router.get("/api/apps/local/{app_id}/config", response_model=AppConfigResponse)
async def get_app_config(app_id: str) -> AppConfigResponse:
    return AppConfigResponse(appId=app_id, config=app_registry_service.get_app_config(app_id))


@router.post("/api/apps/local/{app_id}/config", response_model=AppConfigResponse)
async def update_app_config(app_id: str, body: AppConfigUpdateRequest) -> AppConfigResponse:
    return AppConfigResponse(appId=app_id, config=app_registry_service.update_app_config(app_id, body.config))


@router.post("/api/apps/local/{app_id}/apply", response_model=AppApplyResponse)
async def apply_app(app_id: str, body: AppApplyRequest) -> AppApplyResponse:
    display_policy_runner_service.stop()
    app, runtime = app_registry_service.apply_app(app_id, body.config)
    if app is None:
        raise ValueError(f"Unknown app {app_id}.")
    return AppApplyResponse(ok=True, app=app, runtime=runtime)
