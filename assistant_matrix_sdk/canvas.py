"""64x64 matrix drawing helper for widget authors."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageColor, ImageDraw


class MatrixCanvas:
    def __init__(self, width: int = 64, height: int = 64, background: str | tuple[int, int, int] = "#000000") -> None:
        self.width = width
        self.height = height
        self.image = Image.new("RGB", (width, height), self._color(background))
        self._draw = ImageDraw.Draw(self.image)

    def clear(self, color: str | tuple[int, int, int] = "#000000") -> None:
        self._draw.rectangle((0, 0, self.width, self.height), fill=self._color(color))

    def background(self, color: str | tuple[int, int, int]) -> None:
        self.clear(color)

    def text(self, x: int, y: int, value: object, color: str | tuple[int, int, int] = "#ffffff") -> None:
        self._draw.text((x, y), str(value), fill=self._color(color))

    def rect(self, x: int, y: int, width: int, height: int, color: str | tuple[int, int, int], *, outline: str | tuple[int, int, int] | None = None) -> None:
        self._draw.rectangle((x, y, x + width - 1, y + height - 1), fill=self._color(color), outline=self._color(outline) if outline else None)

    def circle(self, x: int, y: int, radius: int, color: str | tuple[int, int, int], *, outline: str | tuple[int, int, int] | None = None) -> None:
        self._draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=self._color(color), outline=self._color(outline) if outline else None)

    def line(self, x1: int, y1: int, x2: int, y2: int, color: str | tuple[int, int, int], *, width: int = 1) -> None:
        self._draw.line((x1, y1, x2, y2), fill=self._color(color), width=width)

    def image_file(self, path: str | Path, x: int = 0, y: int = 0, size: int | tuple[int, int] | None = None) -> None:
        source = Image.open(path).convert("RGB")
        if isinstance(size, int):
            source = source.resize((size, size))
        elif size is not None:
            source = source.resize(size)
        self.image.paste(source, (x, y))

    def frame(self) -> Image.Image:
        return self.image.copy()

    def save(self, path: str | Path) -> None:
        self.image.save(path)

    def _color(self, value: str | tuple[int, int, int] | None) -> tuple[int, int, int] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return value
        return ImageColor.getrgb(value)
