"""Public SDK primitives for Assistant Matrix widgets."""

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import Asset, Event, WidgetContext
from assistant_matrix_sdk.manifest import WidgetPermission, WidgetPreview, WidgetTrigger

__all__ = [
    "Asset",
    "ConfigField",
    "Event",
    "MatrixCanvas",
    "Widget",
    "WidgetContext",
    "WidgetPermission",
    "WidgetPreview",
    "WidgetTrigger",
]


def __getattr__(name: str):
    if name == "MatrixCanvas":
        from assistant_matrix_sdk.canvas import MatrixCanvas

        return MatrixCanvas
    if name == "Widget":
        from assistant_matrix_sdk.widget import Widget

        return Widget
    raise AttributeError(name)
