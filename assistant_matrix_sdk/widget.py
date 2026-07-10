"""Base widget contract."""

from __future__ import annotations

from pathlib import Path

from assistant_matrix_sdk.canvas import MatrixCanvas
from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import WidgetContext


class Widget:
    id = ""
    name = ""
    version = "0.1.0"
    summary = ""
    author = ""
    category = "custom"
    config: list[ConfigField] = []

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
