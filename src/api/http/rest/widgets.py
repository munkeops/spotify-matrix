"""Widget registry REST routes."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.widget_schemas import LocalWidget, LocalWidgetListResponse
from src.domain.services.widget_registry_service import widget_registry_service

router = APIRouter(tags=["assistant-matrix-widgets"])


@router.get("/api/widgets/local", response_model=LocalWidgetListResponse)
async def list_local_widgets() -> LocalWidgetListResponse:
    return LocalWidgetListResponse(widgets=widget_registry_service.list_local_widgets())


@router.get("/api/widgets/local/{widget_id}", response_model=LocalWidget)
async def get_local_widget(widget_id: str) -> LocalWidget:
    widget = widget_registry_service.get_local_widget(widget_id)
    if widget is None:
        raise ValueError(f"Unknown widget {widget_id}.")
    return widget
