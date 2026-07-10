"""Widget store catalog service."""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.domain.models.widget_schemas import StoreWidget, WidgetStoreIndex
from src.domain.services.config_service import config_service
from src.domain.services.widget_registry_service import widget_registry_service


class WidgetStoreService:
    def __init__(self) -> None:
        self.index_path = Path(os.environ.get("ASSISTANT_MATRIX_WIDGET_STORE_INDEX", "configs/widget_store_index.json")).resolve()
        self.installed_path = config_service.data_dir / "widgets" / "installed.json"

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

    def install_widget(self, widget_id: str) -> StoreWidget:
        widget = self.get_widget(widget_id)
        if widget is None:
            raise ValueError(f"Unknown store widget {widget_id}.")
        installed = self.read_installed_widgets()
        by_id = {item.id: item for item in installed}
        by_id[widget.id] = widget
        self._write_installed_widgets(list(by_id.values()))
        widget.installed = True
        return widget

    def read_installed_widgets(self) -> list[StoreWidget]:
        try:
            with self.installed_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError:
            return []
        widgets = payload.get("widgets", payload if isinstance(payload, list) else [])
        return [StoreWidget.model_validate(widget) for widget in widgets]

    def _read_index(self) -> WidgetStoreIndex:
        try:
            with self.index_path.open("r", encoding="utf-8") as file:
                return WidgetStoreIndex.model_validate(json.load(file))
        except FileNotFoundError:
            return WidgetStoreIndex()

    def _write_installed_widgets(self, widgets: list[StoreWidget]) -> None:
        self.installed_path.parent.mkdir(parents=True, exist_ok=True)
        with self.installed_path.open("w", encoding="utf-8") as file:
            json.dump({"schemaVersion": 1, "widgets": [widget.model_dump() for widget in widgets]}, file, indent=2)
            file.write("\n")


widget_store_service = WidgetStoreService()
