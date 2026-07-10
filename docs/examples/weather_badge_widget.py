"""Example Assistant Matrix widget using the SDK."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from assistant_matrix_sdk import ConfigField, MatrixCanvas, Widget, WidgetContext, WidgetPermission, WidgetPreview, WidgetTrigger


class WeatherBadgeWidget(Widget):
    id = "example.weather-badge"
    name = "Weather Badge"
    version = "0.1.0"
    summary = "Tiny weather-style badge for SDK preview."
    author = "Assistant Matrix"
    category = "information"
    preview_media = WidgetPreview(description="Simple matrix weather badge preview.")
    permissions = [
        WidgetPermission("network", "Future versions may fetch live weather data."),
    ]

    config = [
        ConfigField.string("label", label="Label", default="HOME"),
        ConfigField.number("temperature", label="Temperature", default=72),
        ConfigField.select("condition", ["sunny", "rain", "cloud"], label="Condition", default="sunny"),
    ]
    triggers = [
        WidgetTrigger("schedule.rotation", default_enabled=True, priority=20),
    ]

    def render(self, canvas: MatrixCanvas, context: WidgetContext) -> None:
        label = str(context.config.get("label", "HOME"))[:6].upper()
        temperature = context.config.get("temperature", 72)
        condition = context.config.get("condition", "sunny")

        canvas.background("#08101c")
        canvas.rect(0, 0, 64, 16, "#203a5f")
        canvas.text(4, 4, label, "#ffffff")
        canvas.text(8, 24, f"{temperature}F", "#ffd66b")

        if condition == "rain":
            canvas.circle(48, 22, 7, "#9fb3c8")
            for offset in (0, 6, 12):
                canvas.line(42 + offset, 34, 39 + offset, 42, "#5fc8ff")
        elif condition == "cloud":
            canvas.circle(45, 28, 7, "#bfc7cf")
            canvas.circle(53, 28, 8, "#d5dbe0")
            canvas.rect(40, 30, 20, 8, "#c8d0d6")
        else:
            canvas.circle(49, 31, 9, "#ffd64f")
            for x1, y1, x2, y2 in ((49, 15, 49, 9), (49, 47, 49, 53), (33, 31, 27, 31), (65, 31, 59, 31)):
                canvas.line(x1, y1, x2, y2, "#ffd64f")


if __name__ == "__main__":
    widget = WeatherBadgeWidget()
    widget.preview(
        "weather_badge_preview.png",
        WidgetContext(config={"label": "HOME", "temperature": 72, "condition": "sunny"}),
    )
