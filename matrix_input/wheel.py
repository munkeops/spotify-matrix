"""A radial quick menu, opened by holding the stick or Start.

Wedges are laid out clockwise from the top and picked by pushing the stick
towards one, so choosing is a flick rather than a scroll. The stick's raw
vector comes through on the controller event, which is what makes angular
selection possible on both the analog module and a gamepad's d-pad.
"""

from __future__ import annotations

import math
from typing import Any

from PIL import Image, ImageDraw

from assistant_matrix_sdk.pixels import PANEL, draw_pixel_text, pixel_text_width

CENTRE = (PANEL // 2, PANEL // 2)
OUTER = 30
INNER = 11

#: How far the stick must be pushed before it points at a wedge.
SELECT_DEADZONE = 0.45

BACKDROP = (0, 0, 0)
DIM = 0.14
WEDGE = (26, 34, 58)
WEDGE_EDGE = (52, 66, 104)
SELECTED = (86, 176, 246)
LABEL = (196, 208, 232)
SELECTED_LABEL = (8, 12, 20)
HUB = (12, 16, 28)
HUB_EDGE = (70, 88, 134)
HUB_TEXT = (226, 234, 248)


def wedge_for_vector(x: float, y: float, count: int) -> int | None:
    """Which wedge the stick is pointing at, or None when it is centred.

    Wedge 0 is at the top and they run clockwise, matching how they are drawn.
    """
    if count <= 0:
        return None
    if math.hypot(x, y) < SELECT_DEADZONE:
        return None
    # Screen y grows downward, so negate it to get a normal maths angle, then
    # rotate so that straight up is the middle of wedge 0.
    angle = math.degrees(math.atan2(x, -y)) % 360
    step = 360.0 / count
    return int((angle + step / 2) % 360 // step)


def wedge_bounds(index: int, count: int) -> tuple[float, float]:
    """Start and end angle for a wedge, in PIL's clockwise-from-east degrees."""
    step = 360.0 / count
    # PIL measures from 3 o'clock, so shift by 90 to put wedge 0 at the top.
    middle = index * step - 90.0
    return middle - step / 2, middle + step / 2


def render_wheel(base: Image.Image, items: list[dict[str, Any]], selected: int | None) -> Image.Image:
    """Draw the wheel over ``base``, dimmed so the panel still shows through."""
    frame = base.convert("RGB").copy()
    if frame.size != (PANEL, PANEL):
        frame = frame.resize((PANEL, PANEL), Image.NEAREST)
    frame = Image.blend(Image.new("RGB", (PANEL, PANEL), BACKDROP), frame, DIM)
    draw = ImageDraw.Draw(frame)

    count = len(items)
    if count == 0:
        return frame

    centre_x, centre_y = CENTRE
    box = (centre_x - OUTER, centre_y - OUTER, centre_x + OUTER, centre_y + OUTER)

    for index in range(count):
        start, end = wedge_bounds(index, count)
        is_selected = index == selected
        draw.pieslice(box, start, end, fill=SELECTED if is_selected else WEDGE, outline=WEDGE_EDGE)

    # Labels sit on a ring between the hub and the rim.
    radius = (OUTER + INNER) / 2
    for index, item in enumerate(items):
        step = 360.0 / count
        angle = math.radians(index * step - 90.0)
        label = str(item.get("short", item.get("label", "")))[:5].upper()
        width = pixel_text_width(label, 1)
        x = centre_x + math.cos(angle) * radius - width / 2
        y = centre_y + math.sin(angle) * radius - 2
        draw_pixel_text(draw, int(round(x)), int(round(y)), label, SELECTED_LABEL if index == selected else LABEL, 1)

    # A hub showing what is currently pointed at.
    draw.ellipse((centre_x - INNER, centre_y - INNER, centre_x + INNER, centre_y + INNER), fill=HUB, outline=HUB_EDGE)
    if selected is not None and 0 <= selected < count:
        centre_label = str(items[selected].get("short", items[selected].get("label", "")))[:5].upper()
    else:
        centre_label = "PICK"
    draw_pixel_text(draw, centre_x - pixel_text_width(centre_label, 1) // 2, centre_y - 2, centre_label, HUB_TEXT, 1)
    return frame


__all__ = ["render_wheel", "wedge_for_vector", "wedge_bounds", "SELECT_DEADZONE", "OUTER", "INNER"]
