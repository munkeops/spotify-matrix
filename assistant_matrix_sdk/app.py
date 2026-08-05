"""Base app contract."""

from __future__ import annotations

from pathlib import Path

from assistant_matrix_sdk.canvas import MatrixCanvas
from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import AppContext
from assistant_matrix_sdk.manifest import AppPermission, AppPreview, AppTrigger, build_app_manifest


class App:
    id = ""
    name = ""
    version = "0.1.0"
    summary = ""
    author = ""
    category = "custom"
    runtime = "python"
    matrix_size = "64x64"
    license = "MIT"
    preview_media = AppPreview()
    permissions: list[AppPermission] = []
    config: list[ConfigField] = []
    triggers: list[AppTrigger] = []

    def setup(self, context: AppContext) -> None:
        return None

    def render(self, canvas: MatrixCanvas, context: AppContext) -> None:
        raise NotImplementedError("Apps must implement render(canvas, context).")

    def teardown(self, context: AppContext) -> None:
        return None

    def preview(self, path: str | Path, context: AppContext | None = None, *, size: int = 64) -> None:
        canvas = MatrixCanvas(size, size)
        self.render(canvas, context or AppContext())
        canvas.save(path)

    @classmethod
    def manifest_config(cls) -> list[dict[str, object]]:
        return [field.to_manifest() for field in cls.config]

    @classmethod
    def manifest(cls, *, entrypoint: str = "") -> dict[str, object]:
        return build_app_manifest(
            app_id=cls.id,
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


# The names these had before apps were called apps.
#
# Kept on the module as well as the package, because importing
# straight from the module is just as common as importing from the
# package, and both used to work.
Widget = App
