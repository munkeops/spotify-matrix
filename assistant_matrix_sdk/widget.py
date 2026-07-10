"""Base widget contract."""

from __future__ import annotations

from pathlib import Path

from assistant_matrix_sdk.canvas import MatrixCanvas
from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import WidgetContext
from assistant_matrix_sdk.manifest import WidgetPermission, WidgetPreview, WidgetTrigger, build_widget_manifest


class Widget:
    id = ""
    name = ""
    version = "0.1.0"
    summary = ""
    author = ""
    category = "custom"
    runtime = "python"
    matrix_size = "64x64"
    license = "MIT"
    preview_media = WidgetPreview()
    permissions: list[WidgetPermission] = []
    config: list[ConfigField] = []
    triggers: list[WidgetTrigger] = []

    def setup(self, context: WidgetContext) -> None:
        return None

    def render(self, canvas: MatrixCanvas, context: WidgetContext) -> None:
        raise NotImplementedError("Widgets must implement render(canvas, context).")

    def teardown(self, context: WidgetContext) -> None:
        return None

    def preview(self, path: str | Path, context: WidgetContext | None = None, *, size: int = 64) -> None:
        canvas = MatrixCanvas(size, size)
        self.render(canvas, context or WidgetContext())
        canvas.save(path)

    @classmethod
    def manifest_config(cls) -> list[dict[str, object]]:
        return [field.to_manifest() for field in cls.config]

    @classmethod
    def manifest(cls, *, entrypoint: str = "") -> dict[str, object]:
        return build_widget_manifest(
            widget_id=cls.id,
            name=cls.name,
            version=cls.version,
            summary=cls.summary,
            author=cls.author or "Assistant Matrix",
            category=cls.category,
            runtime=cls.runtime,
            entrypoint=entrypoint,
            matrix_size=cls.matrix_size,
            license=cls.license,
            preview=cls.preview_media,
            permissions=cls.permissions,
            config=cls.config,
            triggers=cls.triggers,
        )
