"""Manifest helpers for store-ready apps."""

from __future__ import annotations

from pathlib import Path

#: The manifest filename. `widget.toml` was the old spelling and is still
#: read, so an app installed before the rename keeps working untouched.
MANIFEST_NAME = "app.toml"
LEGACY_MANIFEST_NAME = "widget.toml"

#: The table inside it. Same story: `[widget]` still parses.
MANIFEST_SECTION = "app"
LEGACY_MANIFEST_SECTION = "widget"


def manifest_path(package_dir: Path | str) -> Path:
    """The manifest in this package, whichever spelling it uses."""
    package_dir = Path(package_dir)
    current = package_dir / MANIFEST_NAME
    if current.exists():
        return current
    legacy = package_dir / LEGACY_MANIFEST_NAME
    return legacy if legacy.exists() else current


def manifest_section(data: dict) -> dict:
    """The app table out of a parsed manifest, old spelling included."""
    section = data.get(MANIFEST_SECTION)
    if not isinstance(section, dict):
        section = data.get(LEGACY_MANIFEST_SECTION)
    return section if isinstance(section, dict) else {}

from dataclasses import dataclass
from typing import Any, Literal

from assistant_matrix_sdk.config import ConfigField


AppCategory = Literal["media", "time", "assistant", "information", "diagnostics", "games", "custom"]
AppKind = Literal["app", "game"]

#: Control layouts a game can ask a controller to render.
GAME_LAYOUTS = ("dpad", "horizontal", "vertical", "tap", "tetris")

#: Directions each layout puts a button behind, mirroring the web pad. A game
#: declaring a direction its layout does not draw is a control the player has
#: no way to press, which is how Road Rash shipped without a throttle. Keep
#: this in step with GamePad.tsx.
LAYOUT_DIRECTIONS: dict[str, frozenset[str]] = {
    "dpad": frozenset({"up", "down", "left", "right"}),
    "horizontal": frozenset({"up", "down", "left", "right"}),
    "vertical": frozenset({"up", "down", "p2Up", "p2Down"}),
    "tap": frozenset(),
    "tetris": frozenset({"up", "down", "left", "right"}),
}

#: Controls every game understands regardless of what else it declares.
COMMON_GAME_ACTIONS = ("pause", "resume", "togglePause", "restart")


@dataclass(frozen=True)
class AppPreview:
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
class AppPermission:
    name: str
    reason: str

    def to_manifest(self) -> dict[str, str]:
        return {"name": self.name, "reason": self.reason}


@dataclass(frozen=True)
class AppTrigger:
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


def build_app_manifest(
    *,
    app_id: str,
    name: str,
    version: str,
    summary: str,
    author: str = "Assistant Matrix",
    category: AppCategory = "custom",
    runtime: str = "python",
    entrypoint: str = "",
    matrix_size: str = "64x64",
    license: str = "MIT",
    preview: AppPreview | None = None,
    permissions: list[AppPermission] | None = None,
    config: list[ConfigField] | None = None,
    triggers: list[AppTrigger] | None = None,
    kind: AppKind = "app",
    layout: str = "",
    actions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical app.toml-compatible manifest shape.

    ``kind="game"`` marks a package the host should drive with a controller;
    ``layout`` and ``actions`` tell that controller what pad to draw.
    """

    app: dict[str, Any] = {
        "id": app_id,
        "name": name,
        "version": version,
        "summary": summary,
        "author": author,
        "category": category,
        "runtime": runtime,
        "entrypoint": entrypoint,
        "matrix_size": matrix_size,
        "license": license,
        "kind": kind,
    }
    if kind == "game":
        app["layout"] = layout or "dpad"
        app["actions"] = list(actions or [])
    return {
        "app": app,
        "preview": (preview or AppPreview()).to_manifest(),
        "permissions": [permission.to_manifest() for permission in permissions or []],
        "config": [field.to_manifest() for field in config or []],
        "triggers": [trigger.to_manifest() for trigger in triggers or []],
    }


# The names these had before apps were called apps.
#
# Kept on the module as well as the package, because importing
# straight from the module is just as common as importing from the
# package, and both used to work.
WidgetPermission = AppPermission
WidgetPreview = AppPreview
WidgetTrigger = AppTrigger
