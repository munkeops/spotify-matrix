"""Widget registry REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.widget_schemas import LocalWidget, LocalWidgetListResponse, StoreWidget, WidgetApplyRequest, WidgetApplyResponse, WidgetConfigResponse, WidgetConfigUpdateRequest, WidgetInstallRequest, WidgetInstallResponse, WidgetPreviewRequest, WidgetPreviewResponse, WidgetStoreListResponse, WidgetUninstallResponse
from src.domain.services.display_policy_runner_service import display_policy_runner_service
from src.domain.services.preview_service import preview_service
from src.domain.services.runtime_service import runtime_service
from src.domain.services.widget_registry_service import widget_registry_service
from src.domain.services.widget_store_service import widget_store_service

router = APIRouter(tags=["assistant-matrix-widgets"])


@router.get("/api/widgets/store", response_model=WidgetStoreListResponse)
async def list_store_widgets() -> WidgetStoreListResponse:
    index = widget_store_service.list_widgets()
    return WidgetStoreListResponse(schemaVersion=index.schemaVersion, widgets=index.widgets)


@router.get("/api/widgets/store/{widget_id}", response_model=StoreWidget)
async def get_store_widget(widget_id: str) -> StoreWidget:
    widget = widget_store_service.get_widget(widget_id)
    if widget is None:
        raise ValueError(f"Unknown store widget {widget_id}.")
    return widget


@router.post("/api/widgets/install", response_model=WidgetInstallResponse)
async def install_widget(body: WidgetInstallRequest) -> WidgetInstallResponse:
    store_widget = widget_store_service.install_widget(body.widgetId)
    local_widget = widget_registry_service.get_local_widget(store_widget.id)
    if local_widget is None:
        raise ValueError(f"Installed widget {store_widget.id} is unavailable locally.")
    return WidgetInstallResponse(ok=True, widget=local_widget)


@router.post("/api/widgets/preview", response_model=WidgetPreviewResponse)
async def preview_widget(body: WidgetPreviewRequest) -> WidgetPreviewResponse:
    data_url = preview_service.render_data_url(body.widgetId, body.config)
    return WidgetPreviewResponse(ok=True, widgetId=body.widgetId, dataUrl=data_url)


@router.get("/api/widgets/local", response_model=LocalWidgetListResponse)
async def list_local_widgets() -> LocalWidgetListResponse:
    return LocalWidgetListResponse(widgets=widget_registry_service.list_local_widgets())


@router.get("/api/widgets/local/{widget_id}", response_model=LocalWidget)
async def get_local_widget(widget_id: str) -> LocalWidget:
    widget = widget_registry_service.get_local_widget(widget_id)
    if widget is None:
        raise ValueError(f"Unknown widget {widget_id}.")
    return widget


@router.delete("/api/widgets/local/{widget_id}", response_model=WidgetUninstallResponse)
async def uninstall_widget(widget_id: str) -> WidgetUninstallResponse:
    display_policy_runner_service.stop()
    runtime_service.stop()
    widget_store_service.uninstall_widget(widget_id)
    return WidgetUninstallResponse(ok=True, widgetId=widget_id)


@router.get("/api/widgets/local/{widget_id}/config", response_model=WidgetConfigResponse)
async def get_widget_config(widget_id: str) -> WidgetConfigResponse:
    return WidgetConfigResponse(widgetId=widget_id, config=widget_registry_service.get_widget_config(widget_id))


@router.post("/api/widgets/local/{widget_id}/config", response_model=WidgetConfigResponse)
async def update_widget_config(widget_id: str, body: WidgetConfigUpdateRequest) -> WidgetConfigResponse:
    return WidgetConfigResponse(widgetId=widget_id, config=widget_registry_service.update_widget_config(widget_id, body.config))


@router.post("/api/widgets/local/{widget_id}/apply", response_model=WidgetApplyResponse)
async def apply_widget(widget_id: str, body: WidgetApplyRequest) -> WidgetApplyResponse:
    display_policy_runner_service.stop()
    widget, runtime = widget_registry_service.apply_widget(widget_id, body.config)
    if widget is None:
        raise ValueError(f"Unknown widget {widget_id}.")
    return WidgetApplyResponse(ok=True, widget=widget, runtime=runtime)
