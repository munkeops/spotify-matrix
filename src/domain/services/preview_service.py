"""Render live widget previews using the matrix runtime frame builders."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import spotify_matrix as runtime
from src.domain.services.config_service import config_service

SIZE = 64


class PreviewService:
    def render_data_url(self, widget_id: str, config: dict[str, Any] | None) -> str:
        image = self._frame(widget_id, config or {})
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    def _frame(self, widget_id: str, cfg: dict[str, Any]):
        if widget_id == "core.text":
            return runtime.render_text(
                SIZE,
                str(cfg.get("text", "")),
                runtime.parse_color(cfg.get("color", "#ffffff"), (255, 255, 255)),
                runtime.parse_color(cfg.get("background", "#000000"), (0, 0, 0)),
                family=cfg.get("fontFamily", "pixel"),
                bold=bool(cfg.get("bold", False)),
                italic=bool(cfg.get("italic", False)),
                size_key=cfg.get("fontSize", "medium"),
                align=cfg.get("align", "center"),
                wrap=bool(cfg.get("wrap", False)),
                fit=bool(cfg.get("fit", False)),
            )
        if widget_id == "core.image":
            asset_name = cfg.get("assetPath", "")
            asset_path = str(config_service.data_dir / "widgets" / "assets" / asset_name) if asset_name else ""
            return runtime.render_image_frame(
                SIZE,
                asset_path,
                cfg.get("fit", "contain"),
                runtime.parse_color(cfg.get("background", "#000000"), (0, 0, 0)),
                int(cfg.get("rotate", 0) or 0),
            )
        if widget_id == "core.draw":
            return runtime.render_draw_frame(SIZE, cfg)
        raise ValueError(f"Preview is not available for {widget_id}.")


preview_service = PreviewService()
