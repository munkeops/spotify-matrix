"""Public SDK primitives for Assistant Matrix widgets and games."""

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import Asset, Event, WidgetContext
from assistant_matrix_sdk.manifest import WidgetPermission, WidgetPreview, WidgetTrigger

__all__ = [
    "Asset",
    "ConfigField",
    "Event",
    "GameWidget",
    "GameStore",
    "MatrixCanvas",
    "Widget",
    "WidgetContext",
    "WidgetPermission",
    "WidgetPreview",
    "WidgetTrigger",
    # Pixel helpers, so a game draws the way the built-ins do.
    "PANEL",
    "draw_banner",
    "draw_centered_text",
    "draw_pixel_text",
    "encode_frame",
    "fit_panel",
    "new_frame",
    "parse_color",
    "pixel_text_width",
    "shade",
]

_PIXEL_EXPORTS = {
    "PANEL",
    "draw_banner",
    "draw_centered_text",
    "draw_pixel_text",
    "encode_frame",
    "fit_panel",
    "new_frame",
    "parse_color",
    "pixel_text_width",
    "shade",
}


def __getattr__(name: str):
    if name == "MatrixCanvas":
        from assistant_matrix_sdk.canvas import MatrixCanvas

        return MatrixCanvas
    if name == "Widget":
        from assistant_matrix_sdk.widget import Widget

        return Widget
    if name == "GameStore":
        from assistant_matrix_sdk.store import GameStore

        return GameStore
    if name in ("GameWidget", "Game"):
        from assistant_matrix_sdk.game import GameWidget

        return GameWidget
    if name in _PIXEL_EXPORTS:
        import assistant_matrix_sdk.pixels as pixels

        return getattr(pixels, name)
    raise AttributeError(name)
