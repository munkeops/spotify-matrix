"""Manifest helpers for store-ready widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from assistant_matrix_sdk.config import ConfigField


WidgetCategory = Literal["media", "time", "assistant", "information", "diagnostics", "games", "custom"]


@dataclass(frozen=True)
class WidgetPreview:
    card_gif: str = "previews/card.gif"
    matrix_png: str = "previews/matrix-64.png"
    description: str = ""

    def to_manifest(self) -> dict[str, str]:
        return {
            "card_gif": self.card_gif,
            "matrix_png": self.matrix_png,
            "description": self.description,
        }


@dataclass(frozen=True)
class WidgetPermission:
    name: str
    reason: str

    def to_manifest(self) -> dict[str, str]:
        return {"name": self.name, "reason": self.reason}


@dataclass(frozen=True)
class WidgetTrigger:
    event: str
    default_enabled: bool = False
    priority: int = 0
    min_duration_seconds: int = 0

    def to_manifest(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "default_enabled": self.default_enabled,
            "priority": self.priority,
            "min_duration_seconds": self.min_duration_seconds,
        }


def build_widget_manifest(
    *,
    widget_id: str,
    name: str,
    version: str,
    summary: str,
    author: str = "Assistant Matrix",
    category: WidgetCategory = "custom",
    runtime: str = "python",
    entrypoint: str = "",
    matrix_size: str = "64x64",
    license: str = "MIT",
    preview: WidgetPreview | None = None,
    permissions: list[WidgetPermission] | None = None,
    config: list[ConfigField] | None = None,
    triggers: list[WidgetTrigger] | None = None,
) -> dict[str, Any]:
    """Build the canonical widget.toml-compatible manifest shape."""

    return {
        "widget": {
            "id": widget_id,
            "name": name,
            "version": version,
            "summary": summary,
            "author": author,
            "category": category,
            "runtime": runtime,
            "entrypoint": entrypoint,
            "matrix_size": matrix_size,
            "license": license,
        },
        "preview": (preview or WidgetPreview()).to_manifest(),
        "permissions": [permission.to_manifest() for permission in permissions or []],
        "config": [field.to_manifest() for field in config or []],
        "triggers": [trigger.to_manifest() for trigger in triggers or []],
    }
