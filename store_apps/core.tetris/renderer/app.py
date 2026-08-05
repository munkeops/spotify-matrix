"""Tetris for the 64x64 matrix."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_pixel_text, fit_panel, new_frame, pixel_text_width

TETRIS_COLS = 10
TETRIS_ROWS = 20
TETRIS_CELL = 3
TETRIS_ORIGIN = (1, 2)
TETRIS_PANEL_X = 34

# Each piece is a rotation box size plus the filled cells inside that box.
TETRIS_SHAPES: dict[str, tuple[int, tuple[tuple[int, int], ...]]] = {
    "I": (4, ((0, 1), (1, 1), (2, 1), (3, 1))),
    "O": (2, ((0, 0), (1, 0), (0, 1), (1, 1))),
    "T": (3, ((1, 0), (0, 1), (1, 1), (2, 1))),
    "S": (3, ((1, 0), (2, 0), (0, 1), (1, 1))),
    "Z": (3, ((0, 0), (1, 0), (1, 1), (2, 1))),
    "J": (3, ((0, 0), (0, 1), (1, 1), (2, 1))),
    "L": (3, ((2, 0), (0, 1), (1, 1), (2, 1))),
}

TETRIS_COLORS = {
    "I": (0, 214, 228),
    "O": (240, 206, 46),
    "T": (176, 84, 232),
    "S": (72, 214, 96),
    "Z": (238, 74, 84),
    "J": (74, 118, 240),
    "L": (244, 148, 44),
}

TETRIS_KICKS = ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1))
TETRIS_LINE_SCORES = (0, 100, 300, 500, 800)
TETRIS_LOCK_DELAY = 0.45
TETRIS_LOCK_RESET_LIMIT = 12
TETRIS_FRAME_COLOR = (36, 40, 58)
TETRIS_LABEL_COLOR = (120, 132, 156)
TETRIS_VALUE_COLOR = (226, 234, 248)


def tetris_cells(piece_type: str, rotation: int) -> tuple[tuple[int, int], ...]:
    box, cells = TETRIS_SHAPES[piece_type]
    result = cells
    for _ in range(rotation % 4):
        result = tuple((box - 1 - y, x) for x, y in result)
    return result


class TetrisGame(GameApp):
    game_id = "tetris"
    name = "Tetris"
    id = "core.tetris"
    summary = "Stack falling tetrominoes and clear lines."
    layout = "tetris"
    config_fields = [
        ConfigField.number("startLevel", label="Starting level", default=1, minimum=1, maximum=15, step=1, help_text="Higher levels start with faster gravity."),
        ConfigField.boolean("ghost", label="Show landing preview", default=True),
        ConfigField.number("autoRestartSeconds", label="Auto restart seconds", default=0, minimum=0, maximum=120, step=1, help_text="Seconds to wait after game over before dealing a new board. 0 waits for the restart button."),
    ]
    actions = ("left", "right", "softDrop", "hardDrop", "rotateCw", "rotateCcw", "hold")

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        seed: int | None = None,
        store: Any = None,
        audio: Any = None,
        *,
        start_level: int | None = None,
        ghost: bool | None = None,
    ) -> None:
        config = dict(config or {})
        if start_level is not None:
            config["startLevel"] = start_level
        if ghost is not None:
            config["ghost"] = ghost
        super().__init__(config, seed, store, audio)

    def reset(self) -> None:
        self.start_level = max(1, min(15, int(self.config.get("startLevel", 1) or 1)))
        self.ghost = bool(self.config.get("ghost", True))
        self.board: list[list[str]] = [[""] * TETRIS_COLS for _ in range(TETRIS_ROWS)]
        self.bag: list[str] = []
        self.score = 0
        self.lines = 0
        self.level = self.start_level
        self.hold = ""
        self.hold_locked = False
        self.drop_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.piece_type = ""
        self.rotation = 0
        self.piece_x = 0
        self.piece_y = 0
        self.next_type = self._take()
        self._spawn()

    def _take(self) -> str:
        if not self.bag:
            self.bag = list(TETRIS_SHAPES)
            self.random.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self, piece_type: str = "") -> None:
        self.piece_type = piece_type or self.next_type
        if not piece_type:
            self.next_type = self._take()
        self.rotation = 0
        self.piece_x = (TETRIS_COLS - TETRIS_SHAPES[self.piece_type][0]) // 2
        self.piece_y = 0
        self.drop_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        if self._collides(self.piece_x, self.piece_y, self.rotation):
            self.game_over = True
            self.audio.play("game_over")

    def _cells(self, x: int, y: int, rotation: int) -> list[tuple[int, int]]:
        return [(x + cell_x, y + cell_y) for cell_x, cell_y in tetris_cells(self.piece_type, rotation)]

    def _collides(self, x: int, y: int, rotation: int) -> bool:
        for cell_x, cell_y in self._cells(x, y, rotation):
            if cell_x < 0 or cell_x >= TETRIS_COLS or cell_y >= TETRIS_ROWS:
                return True
            if cell_y >= 0 and self.board[cell_y][cell_x]:
                return True
        return False

    def _reset_lock_delay(self) -> None:
        if self.lock_timer > 0 and self.lock_resets < TETRIS_LOCK_RESET_LIMIT:
            self.lock_timer = 0.0
            self.lock_resets += 1

    def move(self, dx: int, dy: int) -> bool:
        if self.finished() or self.paused:
            return False
        if self._collides(self.piece_x + dx, self.piece_y + dy, self.rotation):
            return False
        self.piece_x += dx
        self.piece_y += dy
        self._reset_lock_delay()
        if dx:
            self.audio.play("move")
        return True

    def rotate(self, direction: int) -> bool:
        if self.finished() or self.paused:
            return False
        rotation = (self.rotation + direction) % 4
        for dx, dy in TETRIS_KICKS:
            if not self._collides(self.piece_x + dx, self.piece_y + dy, rotation):
                self.piece_x += dx
                self.piece_y += dy
                self.rotation = rotation
                self._reset_lock_delay()
                self.audio.play("rotate")
                return True
        return False

    def soft_drop(self) -> None:
        if self.move(0, 1):
            self.score += 1
            self.drop_timer = 0.0

    def hard_drop(self) -> None:
        if self.finished() or self.paused:
            return
        distance = 0
        while not self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.piece_y += 1
            distance += 1
        self.score += distance * 2
        self._lock()

    def hold_piece(self) -> None:
        if self.finished() or self.paused or self.hold_locked:
            return
        held = self.hold
        self.hold = self.piece_type
        if held:
            self._spawn(held)
        else:
            self._spawn()
        self.hold_locked = True
        self.audio.play("hold")

    def landing_y(self) -> int:
        y = self.piece_y
        while not self._collides(self.piece_x, y + 1, self.rotation):
            y += 1
        return y

    def _lock(self) -> None:
        for cell_x, cell_y in self._cells(self.piece_x, self.piece_y, self.rotation):
            if 0 <= cell_y < TETRIS_ROWS and 0 <= cell_x < TETRIS_COLS:
                self.board[cell_y][cell_x] = self.piece_type
        cleared = self._clear_lines()
        self.audio.play("line" if cleared else "lock")
        if cleared == 4:
            self.audio.play("tetris")
        if cleared:
            self.lines += cleared
            self.score += TETRIS_LINE_SCORES[cleared] * self.level
            self.level = self.start_level + self.lines // 10
        self.hold_locked = False
        self._spawn()

    def _clear_lines(self) -> int:
        kept = [row for row in self.board if not all(row)]
        cleared = TETRIS_ROWS - len(kept)
        if cleared:
            self.board = [[""] * TETRIS_COLS for _ in range(cleared)] + kept
        return cleared

    def drop_interval(self) -> float:
        return max(0.06, 0.80 - (self.level - 1) * 0.06)

    def advance(self, elapsed: float) -> None:
        if self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.lock_timer += elapsed
            if self.lock_timer >= TETRIS_LOCK_DELAY:
                self._lock()
            return
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.drop_timer += elapsed
        interval = self.drop_interval()
        while self.drop_timer >= interval and not self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.piece_y += 1
            self.drop_timer -= interval

    def handle(self, action: str) -> None:
        if action == "left":
            self.move(-1, 0)
        elif action == "right":
            self.move(1, 0)
        elif action == "softDrop":
            self.soft_drop()
        elif action == "hardDrop":
            self.hard_drop()
        elif action == "rotateCw":
            self.rotate(1)
        elif action == "rotateCcw":
            self.rotate(-1)
        elif action == "hold":
            self.hold_piece()

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Best": max(self.store.best, self.score), "Lines": self.lines, "Level": self.level}

    def board_snapshot(self) -> dict[str, Any]:
        """Structured board state, kept for the Tetris specific API and preview."""
        active = [] if self.game_over else [[x, y] for x, y in self._cells(self.piece_x, self.piece_y, self.rotation)]
        ghost: list[list[int]] = []
        if self.ghost and not self.game_over and not self.paused:
            landing = self.landing_y()
            if landing != self.piece_y:
                ghost = [[x, y] for x, y in self._cells(self.piece_x, landing, self.rotation)]
        return {
            "board": ["".join(cell or "." for cell in row) for row in self.board],
            "active": active,
            "activeType": "" if self.game_over else self.piece_type,
            "ghost": ghost,
            "next": self.next_type,
            "hold": self.hold,
            "holdLocked": self.hold_locked,
            "score": self.score,
            "lines": self.lines,
            "level": self.level,
            "gameOver": self.game_over,
            "paused": self.paused,
        }

    def extra(self) -> dict[str, Any]:
        return self.board_snapshot()

    def render(self, size: int = PANEL) -> Image.Image:
        return render_tetris_frame(size, self.board_snapshot())


def demo_snapshot() -> TetrisGame:
    """A board posed mid-game, used for the preview tile."""
    game = TetrisGame(seed=7)
    game.board[19] = ["J", "J", "L", "L", "O", "O", "S", "S", "Z", ""]
    game.board[18] = ["J", "", "", "L", "O", "O", "", "S", "Z", ""]
    game.board[17] = ["", "", "", "L", "", "", "", "", "Z", ""]
    game.piece_type = "T"
    game.next_type = "I"
    game.hold = "L"
    game.piece_x = 3
    game.piece_y = 6
    game.score = 2400
    game.lines = 12
    game.level = 2
    return game


def tetris_demo_snapshot() -> dict[str, Any]:
    """Structured version of the posed board, for the Tetris specific preview."""
    return demo_snapshot().board_snapshot()


def _tetris_block(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int]) -> None:
    draw.rectangle((x, y, x + TETRIS_CELL - 1, y + TETRIS_CELL - 1), fill=color)
    draw.point((x, y), fill=tuple(min(255, channel + 60) for channel in color))


def _tetris_mini_piece(draw: ImageDraw.ImageDraw, x: int, y: int, piece_type: str, cell: int = 2, area: int = 8) -> None:
    if piece_type not in TETRIS_SHAPES:
        return
    cells = TETRIS_SHAPES[piece_type][1]
    min_x = min(cell_x for cell_x, _ in cells)
    min_y = min(cell_y for _, cell_y in cells)
    span_x = max(cell_x for cell_x, _ in cells) - min_x + 1
    span_y = max(cell_y for _, cell_y in cells) - min_y + 1
    start_x = x + (area - span_x * cell) // 2
    start_y = y + (area - span_y * cell) // 2
    color = TETRIS_COLORS[piece_type]
    for cell_x, cell_y in cells:
        left = start_x + (cell_x - min_x) * cell
        top = start_y + (cell_y - min_y) * cell
        draw.rectangle((left, top, left + cell - 1, top + cell - 1), fill=color)


def tetris_score_text(value: int) -> str:
    value = max(0, int(value))
    return str(value) if value < 100000 else f"{value // 1000}K"


def _render_tetris_panel(draw: ImageDraw.ImageDraw, snapshot: dict[str, Any]) -> None:
    x = TETRIS_PANEL_X
    draw_pixel_text(draw, x, 1, "NEXT", TETRIS_LABEL_COLOR, 1)
    _tetris_mini_piece(draw, x + 2, 8, str(snapshot.get("next", "")))
    draw_pixel_text(draw, x, 18, "HOLD", TETRIS_LABEL_COLOR, 1)
    _tetris_mini_piece(draw, x + 2, 25, str(snapshot.get("hold", "")))
    draw_pixel_text(draw, x, 35, "SCORE", TETRIS_LABEL_COLOR, 1)
    draw_pixel_text(draw, x, 41, tetris_score_text(snapshot.get("score", 0)), TETRIS_VALUE_COLOR, 1)
    draw_pixel_text(draw, x, 49, "LINES", TETRIS_LABEL_COLOR, 1)
    draw_pixel_text(draw, x, 55, str(max(0, int(snapshot.get("lines", 0)))), TETRIS_VALUE_COLOR, 1)
    level = min(99, max(1, int(snapshot.get("level", 1))))
    draw_pixel_text(draw, x + 16, 55, f"L{level}", TETRIS_LABEL_COLOR, 1)


def _tetris_overlay(draw: ImageDraw.ImageDraw, lines: tuple[str, ...], width: int, height: int) -> None:
    origin_x, origin_y = TETRIS_ORIGIN
    top = origin_y + height // 2 - (len(lines) * 7) // 2
    draw.rectangle((origin_x, top - 3, origin_x + width - 1, top + len(lines) * 7 + 1), fill=(0, 0, 0), outline=TETRIS_FRAME_COLOR)
    for index, line in enumerate(lines):
        draw_pixel_text(draw, origin_x + (width - pixel_text_width(line, 1)) // 2, top + index * 7, line, TETRIS_VALUE_COLOR, 1)


def render_tetris_frame(size: int, snapshot: dict[str, Any]) -> Image.Image:
    image, draw = new_frame()
    origin_x, origin_y = TETRIS_ORIGIN
    width = TETRIS_COLS * TETRIS_CELL
    height = TETRIS_ROWS * TETRIS_CELL
    draw.rectangle((origin_x - 1, origin_y - 1, origin_x + width, origin_y + height), outline=TETRIS_FRAME_COLOR)

    for row_index, row in enumerate(snapshot.get("board", [])):
        for col_index, cell in enumerate(row):
            if cell != ".":
                _tetris_block(draw, origin_x + col_index * TETRIS_CELL, origin_y + row_index * TETRIS_CELL, TETRIS_COLORS.get(cell, TETRIS_VALUE_COLOR))

    active_color = TETRIS_COLORS.get(str(snapshot.get("activeType", "")), TETRIS_VALUE_COLOR)
    ghost_color = tuple(channel // 4 for channel in active_color)
    for cell_x, cell_y in snapshot.get("ghost", []):
        if cell_y >= 0:
            left = origin_x + cell_x * TETRIS_CELL
            top = origin_y + cell_y * TETRIS_CELL
            draw.rectangle((left, top, left + TETRIS_CELL - 1, top + TETRIS_CELL - 1), fill=ghost_color)
    for cell_x, cell_y in snapshot.get("active", []):
        if cell_y >= 0:
            _tetris_block(draw, origin_x + cell_x * TETRIS_CELL, origin_y + cell_y * TETRIS_CELL, active_color)

    _render_tetris_panel(draw, snapshot)

    if snapshot.get("gameOver"):
        _tetris_overlay(draw, ("GAME", "OVER"), width, height)
    elif snapshot.get("paused"):
        _tetris_overlay(draw, ("PAUSED",), width, height)

    return fit_panel(image, size)


__all__ = [
    "TetrisGame",
    "render_tetris_frame",
    "tetris_demo_snapshot",
    "tetris_cells",
    "tetris_score_text",
    "TETRIS_COLS",
    "TETRIS_ROWS",
    "TETRIS_CELL",
    "TETRIS_SHAPES",
    "TETRIS_COLORS",
    "TETRIS_KICKS",
    "TETRIS_LINE_SCORES",
    "TETRIS_LOCK_DELAY",
    "TETRIS_LOCK_RESET_LIMIT",
]
