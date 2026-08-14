"""2048 for the 64x64 matrix.

Push the board in a direction, everything slides that way, and equal tiles
merge into their sum. A new tile appears wherever there is room. Reach 2048
to win; fill the board with no move left and it is over.

Turn based and four inputs, which makes it the one game here that plays as
well on the matrix's own joystick as on a controller.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

SIZE = 4
#: Four tiles and the gaps between them have to fit inside 64 with a header
#: above: 4 * (13 + 1) is 56, which leaves room for both.
CELL = 13
GAP = 1
ORIGIN = (4, 7)

BACKGROUND = (14, 16, 22)
EMPTY = (34, 38, 48)
TEXT = (222, 228, 244)
DIM = (126, 136, 162)

#: Colour per value, in powers of two from 2. Later tiles glow warmer, so how
#: far along you are reads from across the room.
TILE_COLORS = {
    2: (60, 74, 96),
    4: (70, 96, 120),
    8: (66, 130, 140),
    16: (70, 160, 130),
    32: (96, 180, 100),
    64: (150, 190, 80),
    128: (210, 190, 70),
    256: (230, 160, 60),
    512: (240, 120, 60),
    1024: (240, 90, 90),
    2048: (250, 220, 110),
}
BEYOND = (255, 255, 255)

#: What each value is written as. Four digits will not fit a 13 pixel tile,
#: so the thousands are written short - which is also how people say them.
LABELS = {
    2: "2",
    4: "4",
    8: "8",
    16: "16",
    32: "32",
    64: "64",
    128: "128",
    256: "256",
    512: "512",
    1024: "1K",
    2048: "2K",
    4096: "4K",
    8192: "8K",
}


class Game2048(GameApp):
    game_id = "2048"
    id = "core.2048"
    name = "2048"
    summary = "Slide the board, merge matching tiles, reach 2048."
    layout = "dpad"
    actions = ("up", "down", "left", "right")
    config_fields = [
        ConfigField.number("target", label="Win at", default=2048, minimum=64, maximum=8192, step=64),
        ConfigField.boolean("fours", label="Spawn fours", default=True, help_text="One tile in ten arrives as a 4."),
    ]

    def reset(self) -> None:
        self.target = max(8, int(self.config.get("target", 2048)))
        self.spawn_fours = bool(self.config.get("fours", True))

        self.grid = [[0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.moves = 0
        self.best_tile = 0
        self.last_gain = 0
        self._spawn()
        self._spawn()

    # --- board -----------------------------------------------------------

    def _free(self) -> list[tuple[int, int]]:
        return [(r, c) for r in range(SIZE) for c in range(SIZE) if not self.grid[r][c]]

    def _spawn(self) -> None:
        free = self._free()
        if not free:
            return
        row, column = self.random.choice(free)
        self.grid[row][column] = 4 if self.spawn_fours and self.random.random() < 0.1 else 2

    @staticmethod
    def _slide(line: list[int]) -> tuple[list[int], int]:
        """Collapse one row towards its start, returning it and what it scored.

        A tile that has just merged cannot merge again in the same move,
        which is why this walks the row rather than looping until nothing
        changes: 2 2 4 goes to 4 4, not to 8.
        """
        packed = [value for value in line if value]
        result: list[int] = []
        gained = 0
        index = 0
        while index < len(packed):
            if index + 1 < len(packed) and packed[index] == packed[index + 1]:
                merged = packed[index] * 2
                result.append(merged)
                gained += merged
                index += 2
            else:
                result.append(packed[index])
                index += 1
        return result + [0] * (SIZE - len(result)), gained

    def _lines(self, action: str) -> list[list[tuple[int, int]]]:
        """Board coordinates in the order they collapse for this push."""
        if action == "left":
            return [[(r, c) for c in range(SIZE)] for r in range(SIZE)]
        if action == "right":
            return [[(r, c) for c in reversed(range(SIZE))] for r in range(SIZE)]
        if action == "up":
            return [[(r, c) for r in range(SIZE)] for c in range(SIZE)]
        return [[(r, c) for r in reversed(range(SIZE))] for c in range(SIZE)]

    def push(self, action: str) -> bool:
        """Apply a move. False when nothing on the board could shift."""
        moved = False
        gained = 0
        for line in self._lines(action):
            values = [self.grid[r][c] for r, c in line]
            collapsed, scored = self._slide(values)
            gained += scored
            if collapsed != values:
                moved = True
                for (r, c), value in zip(line, collapsed):
                    self.grid[r][c] = value
        if moved:
            self.score += gained
            self.last_gain = gained
            self.moves += 1
        return moved

    def can_move(self) -> bool:
        if self._free():
            return True
        for row in range(SIZE):
            for column in range(SIZE):
                value = self.grid[row][column]
                if row + 1 < SIZE and self.grid[row + 1][column] == value:
                    return True
                if column + 1 < SIZE and self.grid[row][column + 1] == value:
                    return True
        return False

    # --- play ------------------------------------------------------------

    def handle(self, action: str) -> None:
        if action not in self.actions:
            return
        if not self.push(action):
            self.audio.play("blocked", 0.4)
            return

        self._spawn()
        self.best_tile = max(max(row) for row in self.grid)
        self.audio.play("merge" if self.last_gain else "slide")

        if self.best_tile >= self.target and not self.won:
            self.won = True
            self.audio.play("win")
            return
        if not self.can_move():
            self.game_over = True
            self.audio.play("game_over")

    def advance(self, elapsed: float) -> None:
        """Nothing moves on its own; the board waits for you."""

    # --- reporting -------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Best": max(self.store.best, self.score),
            "Tile": self.best_tile,
            "Moves": self.moves,
        }

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame(BACKGROUND)
        origin_x, origin_y = ORIGIN

        draw_pixel_text(draw, 1, 1, f"{self.score:06d}", TEXT, 1)
        draw_pixel_text(draw, PANEL - 24, 1, f"{self.best_tile}", DIM, 1)

        for row in range(SIZE):
            for column in range(SIZE):
                left = origin_x + column * (CELL + GAP)
                top = origin_y + row * (CELL + GAP)
                value = self.grid[row][column]
                draw.rectangle(
                    (left, top, left + CELL - 1, top + CELL - 1),
                    fill=TILE_COLORS.get(value, BEYOND) if value else EMPTY,
                )
                if not value:
                    continue
                label = LABELS.get(value) or f"{value // 1024}K"
                width = len(label) * 4 - 1
                draw_pixel_text(
                    draw,
                    left + (CELL - width) // 2,
                    top + (CELL - 5) // 2,
                    label,
                    (18, 20, 26) if value >= 128 else TEXT,
                    1,
                )

        if self.won:
            draw_banner(draw, (str(self.target),), TEXT)
        elif self.game_over:
            draw_banner(draw, ("NO", "MOVES"), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        return fit_panel(image, size)


def demo_snapshot() -> Game2048:
    game = Game2048(seed=3)
    game.grid = [
        [2, 8, 32, 2],
        [4, 64, 128, 16],
        [16, 256, 8, 4],
        [2, 4, 2, 8],
    ]
    game.score = 3120
    game.best_tile = 256
    game.moves = 84
    return game
