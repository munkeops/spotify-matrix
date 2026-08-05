"""Connect Four for the 64x64 matrix, hot seat or against the computer."""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_centered_text, fit_panel, new_frame

COLUMNS = 7
ROWS = 6
CELL = 8
BOARD_LEFT = (PANEL - COLUMNS * CELL) // 2
BOARD_TOP = 14
DISC_RADIUS = 3
DROP_SPEED = 90.0

BOARD_COLOR = (28, 46, 110)
HOLE_COLOR = (6, 8, 16)
RED = (240, 78, 88)
YELLOW = (246, 206, 66)
TEXT_COLOR = (200, 212, 232)
WIN_COLOR = (255, 255, 255)

PLAYER_COLORS = {1: RED, 2: YELLOW}
PLAYER_NAMES = {1: "RED", 2: "YELLOW"}


class ConnectFourGame(GameApp):
    game_id = "connect4"
    name = "Connect Four"
    id = "core.connect4"
    summary = "Line up four discs before your rival does."
    layout = "horizontal"
    config_fields = [
        ConfigField.select("opponent", [("Second player", "human"), ("Computer", "ai")], label="Opponent"),
    ]
    actions = ("left", "right", "drop")

    def reset(self) -> None:
        self.opponent = str(self.config.get("opponent", "human"))
        self.board = [[0] * COLUMNS for _ in range(ROWS)]
        self.player = 1
        self.cursor = COLUMNS // 2
        self.winner = 0
        self.win_cells: list[tuple[int, int]] = []
        self.falling: dict[str, Any] | None = None
        self.ai_timer = 0.0

    # --- rules ----------------------------------------------------------

    def _landing_row(self, column: int) -> int | None:
        for row in range(ROWS - 1, -1, -1):
            if self.board[row][column] == 0:
                return row
        return None

    def _winning_cells(self, row: int, column: int, player: int) -> list[tuple[int, int]]:
        for step_x, step_y in ((1, 0), (0, 1), (1, 1), (1, -1)):
            line = [(row, column)]
            for direction in (1, -1):
                next_row = row + step_y * direction
                next_column = column + step_x * direction
                while 0 <= next_row < ROWS and 0 <= next_column < COLUMNS and self.board[next_row][next_column] == player:
                    line.append((next_row, next_column))
                    next_row += step_y * direction
                    next_column += step_x * direction
            if len(line) >= 4:
                return line
        return []

    def _settle(self, row: int, column: int, player: int) -> None:
        self.board[row][column] = player
        cells = self._winning_cells(row, column, player)
        if cells:
            self.audio.play("win")
            self.winner = player
            self.win_cells = cells
            self.won = True
            return
        if all(self.board[0][index] != 0 for index in range(COLUMNS)):
            self.game_over = True
            return
        self.player = 2 if player == 1 else 1

    def _drop(self, column: int) -> None:
        if self.falling is not None:
            return
        row = self._landing_row(column)
        if row is None:
            return
        self.audio.play("drop")
        self.falling = {
            "column": column,
            "row": row,
            "player": self.player,
            "y": float(BOARD_TOP - CELL),
            "target": float(BOARD_TOP + row * CELL),
        }

    # --- input and stepping ---------------------------------------------

    def handle(self, action: str) -> None:
        if self.falling is not None:
            return
        if self.opponent == "ai" and self.player == 2:
            return
        if action == "left":
            self.audio.play("move", 0.5)
            self.cursor = (self.cursor - 1) % COLUMNS
        elif action == "right":
            self.cursor = (self.cursor + 1) % COLUMNS
        elif action == "drop":
            self._drop(self.cursor)

    def advance(self, elapsed: float) -> None:
        if self.falling is not None:
            self.falling["y"] += DROP_SPEED * elapsed
            if self.falling["y"] >= self.falling["target"]:
                landed = self.falling
                self.falling = None
                self._settle(int(landed["row"]), int(landed["column"]), int(landed["player"]))
            return
        if self.opponent == "ai" and self.player == 2 and not self.finished():
            self.ai_timer += elapsed
            if self.ai_timer >= 0.6:
                self.ai_timer = 0.0
                self.cursor = self._ai_column()
                self._drop(self.cursor)

    def _ai_column(self) -> int:
        playable = [column for column in range(COLUMNS) if self._landing_row(column) is not None]
        # Take the win, otherwise block, otherwise lean towards the middle.
        for player in (2, 1):
            for column in playable:
                row = self._landing_row(column)
                if row is None:
                    continue
                self.board[row][column] = player
                winning = bool(self._winning_cells(row, column, player))
                self.board[row][column] = 0
                if winning:
                    return column
        weighted = sorted(playable, key=lambda column: abs(column - COLUMNS // 2))
        best = weighted[: max(1, len(weighted) // 2)]
        return self.random.choice(best)

    def hud(self) -> dict[str, Any]:
        if self.winner:
            return {"Winner": PLAYER_NAMES[self.winner]}
        if self.game_over:
            return {"Result": "Draw"}
        return {"Turn": PLAYER_NAMES[self.player], "Mode": "vs CPU" if self.opponent == "ai" else "2 player"}

    def extra(self) -> dict[str, Any]:
        return {"turn": self.player, "twoPlayer": self.opponent == "human"}

    # --- drawing ---------------------------------------------------------

    def _disc(self, draw, x: int, y: int, color: tuple[int, int, int]) -> None:
        center_x = x + CELL // 2
        center_y = y + CELL // 2
        draw.ellipse((center_x - DISC_RADIUS, center_y - DISC_RADIUS, center_x + DISC_RADIUS, center_y + DISC_RADIUS), fill=color)

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()

        if self.winner:
            draw_centered_text(draw, 1, f"{PLAYER_NAMES[self.winner]} WINS", PLAYER_COLORS[self.winner], 1)
        elif self.game_over:
            draw_centered_text(draw, 1, "DRAW", TEXT_COLOR, 1)
        else:
            draw_centered_text(draw, 1, f"{PLAYER_NAMES[self.player]} TURN", PLAYER_COLORS[self.player], 1)

        if not self.finished() and self.falling is None:
            cursor_x = BOARD_LEFT + self.cursor * CELL
            self._disc(draw, cursor_x, BOARD_TOP - CELL + 1, PLAYER_COLORS[self.player])
            draw.line((cursor_x + 1, BOARD_TOP - 2, cursor_x + CELL - 2, BOARD_TOP - 2), fill=PLAYER_COLORS[self.player])

        draw.rectangle((BOARD_LEFT, BOARD_TOP, BOARD_LEFT + COLUMNS * CELL - 1, BOARD_TOP + ROWS * CELL - 1), fill=BOARD_COLOR)
        for row in range(ROWS):
            for column in range(COLUMNS):
                x = BOARD_LEFT + column * CELL
                y = BOARD_TOP + row * CELL
                value = self.board[row][column]
                if value:
                    highlight = (row, column) in self.win_cells
                    self._disc(draw, x, y, WIN_COLOR if highlight else PLAYER_COLORS[value])
                else:
                    self._disc(draw, x, y, HOLE_COLOR)

        if self.falling is not None:
            x = BOARD_LEFT + int(self.falling["column"]) * CELL
            self._disc(draw, x, int(self.falling["y"]), PLAYER_COLORS[int(self.falling["player"])])

        if self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        return fit_panel(image, size)


def demo_snapshot() -> ConnectFourGame:
    game = ConnectFourGame(seed=11)
    moves = [(3, 1), (3, 2), (4, 1), (2, 2), (4, 2), (5, 1)]
    for column, player in moves:
        row = game._landing_row(column)
        if row is not None:
            game.board[row][column] = player
    game.cursor = 4
    return game


__all__ = ["ConnectFourGame", "demo_snapshot"]
