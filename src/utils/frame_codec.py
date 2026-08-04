"""Rebuild a panel image from the palette/row encoding games publish."""

from __future__ import annotations

from PIL import Image

from matrix_games.render import PIXEL_ALPHABET


def decode_frame(palette: list[str], pixels: list[str], size: int = 64) -> Image.Image:
    colors = [_rgb(value) for value in palette] or [(0, 0, 0)]
    height = len(pixels)
    width = max((len(row) for row in pixels), default=0)
    if not height or not width:
        return Image.new("RGB", (size, size), (0, 0, 0))

    image = Image.new("RGB", (width, height), colors[0])
    image.putdata(
        [
            colors[_index(row[x])] if x < len(row) and _index(row[x]) < len(colors) else colors[0]
            for row in pixels
            for x in range(width)
        ]
    )
    return image if (width, height) == (size, size) else image.resize((size, size), Image.NEAREST)


def _index(char: str) -> int:
    position = PIXEL_ALPHABET.find(char)
    return position if position >= 0 else 0


def _rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return (0, 0, 0)


__all__ = ["decode_frame"]
