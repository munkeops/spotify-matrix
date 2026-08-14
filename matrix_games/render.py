"""Re-exports of the SDK pixel helpers, kept so game modules read naturally."""

from __future__ import annotations

from assistant_matrix_sdk.pixels import (  # noqa: F401
    DIGIT_FONT_3X5,
    PANEL,
    PIXEL_ALPHABET,
    draw_banner,
    draw_centered_text,
    draw_pixel_text,
    encode_frame,
    fit_panel,
    frame_to_pixels,
    new_frame,
    parse_color,
    pixel_text_width,
    shade,
)

__all__ = [
    "DIGIT_FONT_3X5",
    "PANEL",
    "PIXEL_ALPHABET",
    "draw_banner",
    "draw_centered_text",
    "draw_pixel_text",
    "encode_frame",
    "fit_panel",
    "frame_to_pixels",
    "new_frame",
    "parse_color",
    "pixel_text_width",
    "shade",
]
