"""Pixel drawing primitives for 64x64 matrix apps and games.

Everything here is plain Pillow work with no dependency on the host app, so a
app can import it and draw exactly the way the built-in games do.
"""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageColor, ImageDraw

PANEL = 64

DIGIT_FONT_3X5 = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "-": ("000", "000", "111", "000", "000"),
    ".": ("000", "000", "000", "000", "010"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "110", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    ":": ("000", "010", "000", "010", "000"),
    "!": ("010", "010", "010", "000", "010"),
    "?": ("111", "001", "010", "000", "010"),
    ",": ("000", "000", "000", "010", "100"),
    "'": ("010", "010", "000", "000", "000"),
    "/": ("001", "001", "010", "100", "100"),
    "+": ("000", "010", "111", "010", "000"),
    "(": ("001", "010", "010", "010", "001"),
    ")": ("100", "010", "010", "010", "100"),
    "&": ("010", "101", "010", "101", "011"),
    "#": ("101", "111", "101", "111", "101"),
    "%": ("101", "001", "010", "100", "101"),
    "*": ("000", "101", "010", "101", "000"),
}


def draw_pixel_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 2) -> None:
    cursor = x
    for char in text:
        glyph = DIGIT_FONT_3X5.get(char.upper())
        if char == " ":
            cursor += 2 * scale
            continue
        if not glyph:
            draw.text((cursor, y), char, fill=color)
            cursor += 6
            continue
        for row, pattern in enumerate(glyph):
            for col, pixel in enumerate(pattern):
                if pixel == "1":
                    draw.rectangle(
                        (
                            cursor + col * scale,
                            y + row * scale,
                            cursor + (col + 1) * scale - 1,
                            y + (row + 1) * scale - 1,
                        ),
                        fill=color,
                    )
        cursor += 4 * scale


def pixel_text_width(text: str, scale: int = 2) -> int:
    width = 0
    for char in text:
        if char == " ":
            width += 2 * scale
        elif char.upper() in DIGIT_FONT_3X5:
            width += 4 * scale
        else:
            width += 6
    return max(0, width - scale)


def parse_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return fallback
    try:
        color = ImageColor.getrgb(value)
    except ValueError:
        return fallback
    return color[:3]


def draw_centered_text(draw: ImageDraw.ImageDraw, y: int, text: str, color: tuple[int, int, int], scale: int = 1, width: int = PANEL, left: int = 0) -> None:
    draw_pixel_text(draw, left + (width - pixel_text_width(text, scale)) // 2, y, text, color, scale)


def draw_banner(draw: ImageDraw.ImageDraw, lines: tuple[str, ...], color: tuple[int, int, int], *, top: int | None = None, width: int = PANEL, left: int = 0, border: tuple[int, int, int] = (60, 66, 90)) -> None:
    """Dark plate with centered lines, used for pause and game-over states."""
    height = len(lines) * 7
    start = (PANEL - height) // 2 if top is None else top
    draw.rectangle((left + 2, start - 3, left + width - 3, start + height + 1), fill=(0, 0, 0), outline=border)
    for index, line in enumerate(lines):
        draw_centered_text(draw, start + index * 7, line, color, 1, width, left)


def new_frame(background: tuple[int, int, int] = (0, 0, 0)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (PANEL, PANEL), background)
    return image, ImageDraw.Draw(image)


def fit_panel(image: Image.Image, size: int) -> Image.Image:
    """Games draw at 64x64; scale only when the panel is a different size."""
    return image if size == PANEL else image.resize((size, size), Image.NEAREST)


def shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)  # type: ignore[return-value]


# Base62 keeps the encoded frame compact enough to poll a few times a second.
PIXEL_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def frame_to_pixels(image: Image.Image) -> tuple[list[str], list[str]]:
    """Encode a rendered frame as a colour palette plus one string per row.

    The web app renders this directly, so every game gets a live mirror of the
    real panel without a bespoke component per game.
    """
    image = image.convert("RGB")
    width, height = image.size
    data = list(image.getdata())
    palette: dict[tuple[int, int, int], int] = {}
    rows: list[str] = []
    for y in range(height):
        chars: list[str] = []
        for x in range(width):
            color = data[y * width + x]
            index = palette.get(color)
            if index is None:
                if len(palette) >= len(PIXEL_ALPHABET):
                    index = 0
                else:
                    index = len(palette)
                    palette[color] = index
            chars.append(PIXEL_ALPHABET[index])
        rows.append("".join(chars))
    colors = ["#%02x%02x%02x" % color for color in palette]
    return colors, rows


def encode_frame(image: Image.Image) -> dict[str, Any]:
    palette, pixels = frame_to_pixels(image)
    return {"palette": palette, "pixels": pixels}
