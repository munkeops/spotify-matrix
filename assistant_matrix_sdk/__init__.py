"""Public SDK primitives for Assistant Matrix widgets."""

from assistant_matrix_sdk.canvas import MatrixCanvas
from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.context import Asset, Event, WidgetContext
from assistant_matrix_sdk.manifest import WidgetPermission, WidgetPreview, WidgetTrigger
from assistant_matrix_sdk.widget import Widget

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
