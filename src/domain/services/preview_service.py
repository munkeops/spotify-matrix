"""Render live app previews using the matrix runtime frame builders."""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from typing import Any

import spotify_matrix as runtime
from src.domain.services.config_service import config_service
from src.utils.frame_codec import decode_frame
from matrix_games.registry import demo_instance
from src.domain.services.game_service import game_service

SIZE = 64


class PreviewService:
    def render_data_url(self, app_id: str, config: dict[str, Any] | None) -> str:
        image = self._frame(app_id, config or {})
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    def _frame(self, app_id: str, cfg: dict[str, Any]):
        if app_id == "core.text":
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
        if app_id == "core.image":
            asset_name = cfg.get("assetPath", "")
            asset_path = str(config_service.data_dir / "apps" / "assets" / asset_name) if asset_name else ""
            return runtime.render_image_frame(
                SIZE,
                asset_path,
                cfg.get("fit", "contain"),
                runtime.parse_color(cfg.get("background", "#000000"), (0, 0, 0)),
                int(cfg.get("rotate", 0) or 0),
            )
        if app_id == "core.draw":
            return runtime.render_draw_frame(SIZE, cfg)
        if app_id == "core.clock":
            return runtime.render_clock(SIZE, datetime.now(), cfg.get("face", "analog"), bool(cfg.get("use24Hour", False)), bool(cfg.get("showSeconds", False)))
        if app_id == "core.agent":
            return runtime.render_agent_face(SIZE, 0, cfg.get("faceStyle", "classic"), cfg.get("animationSpeed", "normal"))
        game_spec = next((spec for spec in game_service.specs().values() if spec.app_id == app_id), None)
        if game_spec is not None:
            return self._game_frame(game_spec)
        if app_id == "core.testPattern":
            return runtime.render_test_pattern(SIZE, 0)
        if app_id == "core.spotify":
            return runtime.render_record(runtime.demo_album_art(96), 20, SIZE)
        if app_id == "core.weather":
            state = runtime.WeatherState(
                label=cfg.get("label", "Local weather"),
                temperature=72, apparent_temperature=74, uv_index=4, aqi=38, wind_speed=8,
                weather_code=0, summary="Sunny",
            )
            return runtime.render_weather_quad(state, 0, SIZE, cfg.get("temperatureUnit", "fahrenheit"))
        if app_id == "core.slideshow":
            items = cfg.get("items", [])
            asset_path = str(config_service.data_dir / "apps" / "assets" / items[0]) if items else ""
            return runtime.render_image_frame(
                SIZE,
                asset_path,
                cfg.get("fit", "cover"),
                runtime.parse_color(cfg.get("background", "#000000"), (0, 0, 0)),
                int(cfg.get("rotate", 0) or 0),
            )
        raise ValueError(f"Preview is not available for {app_id}.")

    def _game_frame(self, spec):
        # Mirror the real panel while a game is running, otherwise pose a demo board.
        state = game_service.read_state(spec.game_id)
        if game_service.is_live(state) and state is not None and state.pixels:
            return decode_frame(state.palette, state.pixels, SIZE)
        return demo_instance(spec).render(SIZE)


preview_service = PreviewService()
