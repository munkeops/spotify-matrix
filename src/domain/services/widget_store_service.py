"""Widget store catalog service."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import hashlib
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
        self._install_archive_if_available(widget)
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

    def _install_archive_if_available(self, widget: StoreWidget) -> None:
        if not widget.archiveUrl:
            return
        try:
            archive_path = self._resolve_archive(widget.archiveUrl)
        except Exception:
            return
        if widget.sha256:
            digest = self._sha256(archive_path)
            if digest.lower() != widget.sha256.lower():
                raise ValueError(f"Archive checksum mismatch for {widget.id}.")
        package_dir = config_service.data_dir / "widgets" / "packages" / widget.id
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_dir = Path(temp_dir) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            self._safe_extract(archive_path, extract_dir)
            if package_dir.exists():
                shutil.rmtree(package_dir)
            package_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(extract_dir, package_dir)

    def _resolve_archive(self, archive_url: str) -> Path:
        parsed = urllib.parse.urlparse(archive_url)
        if parsed.scheme in {"http", "https"}:
            cache_dir = config_service.data_dir / "widgets" / "downloads"
            cache_dir.mkdir(parents=True, exist_ok=True)
            target = cache_dir / Path(parsed.path).name
            urllib.request.urlretrieve(archive_url, target)
            return target
        if parsed.scheme == "file":
            return Path(urllib.request.url2pathname(parsed.path))
        path = Path(archive_url)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _safe_extract(self, archive_path: Path, target_dir: Path) -> None:
        target_root = target_dir.resolve()
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                destination = (target_dir / member.name).resolve()
                try:
                    destination.relative_to(target_root)
                except ValueError:
                    raise ValueError(f"Unsafe archive path {member.name}.")
            archive.extractall(target_dir)


widget_store_service = WidgetStoreService()
