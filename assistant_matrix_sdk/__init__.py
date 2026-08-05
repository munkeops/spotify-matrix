"""Public SDK primitives for Assistant Matrix apps and games."""

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import Asset, Event, AppContext
from assistant_matrix_sdk.manifest import AppPermission, AppPreview, AppTrigger

# Apps used to be called widgets. An app written against the old SDK still
# subclasses GameWidget and imports WidgetPreview, and there is no reason to
# break it over a word, so both spellings resolve to the same classes. The
# lazy ones are handled in __getattr__ below.
WidgetContext = AppContext
WidgetPermission = AppPermission
WidgetPreview = AppPreview
WidgetTrigger = AppTrigger

__all__ = [
    "Asset",
    "ConfigField",
    "Event",
    "GameApp",
    "GameStore",
    "SilentAudio",
    "MatrixCanvas",
    "App",
    "AppContext",
    "AppPermission",
    "AppPreview",
    "AppTrigger",
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

#: Names the SDK answered to before apps were called apps.
_LEGACY_NAMES = ("Widget", "WidgetContext", "WidgetPermission", "WidgetPreview", "WidgetTrigger", "GameWidget")


def __getattr__(name: str):
    if name == "MatrixCanvas":
        from assistant_matrix_sdk.canvas import MatrixCanvas

        return MatrixCanvas
    if name in ("App", "Widget"):
        from assistant_matrix_sdk.app import App

        return App
    if name == "SilentAudio":
        from assistant_matrix_sdk.audio import SilentAudio

        return SilentAudio
    if name == "GameStore":
        from assistant_matrix_sdk.store import GameStore

        return GameStore
    if name in ("GameApp", "Game", "GameWidget"):
        from assistant_matrix_sdk.game import GameApp

        return GameApp
    if name in _PIXEL_EXPORTS:
        import assistant_matrix_sdk.pixels as pixels

        return getattr(pixels, name)
    raise AttributeError(name)

__all__ = list(__all__) + list(_LEGACY_NAMES)
