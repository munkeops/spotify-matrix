"""Widget store catalog service."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.domain.models.widget_schemas import StoreWidget, WidgetStoreIndex
from src.domain.services.widget_registry_service import widget_registry_service


class WidgetStoreService:
    def __init__(self) -> None:
        self.index_path = Path(os.environ.get("ASSISTANT_MATRIX_WIDGET_STORE_INDEX", "configs/widget_store_index.json")).resolve()

    def list_widgets(self) -> WidgetStoreIndex:
        index = self._read_index()
        installed_ids = {widget.manifest.id for widget in widget_registry_service.list_local_widgets()}
        for widget in index.widgets:
            widget.installed = widget.id in installed_ids
        return index

    def get_widget(self, widget_id: str) -> StoreWidget | None:
        for widget in self.list_widgets().widgets:
            if widget.id == widget_id:
                return widget
        return None

    def _read_index(self) -> WidgetStoreIndex:
        try:
            with self.index_path.open("r", encoding="utf-8") as file:
                return WidgetStoreIndex.model_validate(json.load(file))
        except FileNotFoundError:
            return WidgetStoreIndex()


widget_store_service = WidgetStoreService()
