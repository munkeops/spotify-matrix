"""The on-panel shell: a app menu and live brightness, driven by a controller.

The controller is read in the API process but the panel is drawn by the runtime
process, so the two talk through one small JSON file. The API owns the menu
state; the runtime draws it over whatever is already on screen and applies
brightness without restarting.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from assistant_matrix_sdk.pixels import PANEL, draw_centered_text, draw_pixel_text, pixel_text_width

# How many app rows fit under the title.
VISIBLE_ROWS = 5
ROW_HEIGHT = 8
TITLE_Y = 2
LIST_TOP = 13

BACKDROP = (0, 0, 0)
DIM = 0.18
FRAME = (60, 74, 120)
TITLE = (150, 168, 210)
ITEM = (196, 208, 232)
SELECTED_TEXT = (10, 12, 20)
SELECTED_BG = (120, 200, 255)
ACTIVE_DOT = (110, 240, 150)
HINT = (110, 124, 152)


def default_state() -> dict[str, Any]:
    return {
        "seq": 0,
        "brightness": 0,
        "menu": {"open": False, "cursor": 0, "items": []},
        "wheel": {"open": False, "selected": None, "items": []},
    }


def read_shell_state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return default_state()
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return default_state()
    if not isinstance(payload, dict):
        return default_state()
    menu = payload.get("menu")
    if not isinstance(menu, dict):
        menu = {}
    items = [item for item in menu.get("items", []) if isinstance(item, dict) and item.get("id")]
    wheel = payload.get("wheel")
    if not isinstance(wheel, dict):
        wheel = {}
    wheel_items = [item for item in wheel.get("items", []) if isinstance(item, dict)]
    selected = wheel.get("selected")
    return {
        "seq": int(payload.get("seq", 0) or 0),
        "brightness": int(payload.get("brightness", 0) or 0),
        "menu": {
            "open": bool(menu.get("open", False)),
            "cursor": max(0, int(menu.get("cursor", 0) or 0)),
            "items": items,
        },
        "wheel": {
            "open": bool(wheel.get("open", False)),
            "selected": int(selected) if isinstance(selected, (int, float)) else None,
            "items": wheel_items,
        },
    }


def write_shell_state(path: Path | None, state: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(state, file)
        for _ in range(3):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                # Windows refuses the swap while the runtime has it open.
                time.sleep(0.01)
        with path.open("w", encoding="utf-8") as file:
            json.dump(state, file)
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass


def visible_window(cursor: int, total: int, rows: int = VISIBLE_ROWS) -> tuple[int, int]:
    """Scroll the list so the cursor stays on screen with context around it."""
    if total <= rows:
        return 0, total
    start = max(0, min(cursor - rows // 2, total - rows))
    return start, start + rows


def render_menu(base: Image.Image, menu: dict[str, Any]) -> Image.Image:
    """Draw the app menu over ``base``, dimmed so the panel stays visible."""
    frame = base.convert("RGB").copy()
    if frame.size != (PANEL, PANEL):
        frame = frame.resize((PANEL, PANEL), Image.NEAREST)
    frame = Image.blend(Image.new("RGB", (PANEL, PANEL), BACKDROP), frame, DIM)
    draw = ImageDraw.Draw(frame)

    items = menu.get("items", [])
    cursor = max(0, min(int(menu.get("cursor", 0)), max(0, len(items) - 1)))

    draw.rectangle((0, 0, PANEL - 1, PANEL - 1), outline=FRAME)
    draw_centered_text(draw, TITLE_Y, "APPS", TITLE, 1)
    draw.line((3, TITLE_Y + 7, PANEL - 4, TITLE_Y + 7), fill=FRAME)
    # Rows run 13..50, leaving the bottom strip for the hint.

    if not items:
        draw_centered_text(draw, 26, "NONE", ITEM, 1)
        return frame

    start, end = visible_window(cursor, len(items))
    for row, item in enumerate(items[start:end]):
        index = start + row
        y = LIST_TOP + row * ROW_HEIGHT
        selected = index == cursor
        label = str(item.get("name", item.get("id", "")))[:11].upper()
        if selected:
            draw.rectangle((2, y - 2, PANEL - 3, y + 6), fill=SELECTED_BG)
        draw_pixel_text(draw, 5, y, label, SELECTED_TEXT if selected else ITEM, 1)
        if item.get("active"):
            draw.rectangle((PANEL - 7, y + 1, PANEL - 5, y + 3), fill=SELECTED_TEXT if selected else ACTIVE_DOT)

    # Arrows when the list runs past the window.
    if start > 0:
        draw_pixel_text(draw, PANEL - 7, TITLE_Y, "^", HINT, 1)
    if end < len(items):
        draw_pixel_text(draw, PANEL - 7, PANEL - 7, "V", HINT, 1)

    hint = "OK PICK"
    draw_pixel_text(draw, (PANEL - pixel_text_width(hint, 1)) // 2, PANEL - 7, hint, HINT, 1)
    return frame


def render_brightness(base: Image.Image, level: int) -> Image.Image:
    """A brief bar so a brightness change is visible on the panel."""
    frame = base.convert("RGB").copy()
    if frame.size != (PANEL, PANEL):
        frame = frame.resize((PANEL, PANEL), Image.NEAREST)
    draw = ImageDraw.Draw(frame)
    level = max(0, min(100, int(level)))

    top = PANEL - 14
    draw.rectangle((6, top, PANEL - 7, top + 9), fill=(0, 0, 0), outline=FRAME)
    filled = int((PANEL - 16) * level / 100)
    if filled > 0:
        draw.rectangle((8, top + 3, 8 + filled, top + 6), fill=SELECTED_BG)
    label = f"{level}"
    draw_pixel_text(draw, PANEL - 8 - pixel_text_width(label, 1), top - 8, label, ITEM, 1)
    return frame


__all__ = [
    "read_shell_state",
    "write_shell_state",
    "default_state",
    "render_menu",
    "render_brightness",
    "visible_window",
    "VISIBLE_ROWS",
]
