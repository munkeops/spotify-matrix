"""Snake for the 64x64 matrix."""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame, shade

CELL = 3
COLS = 21
ROWS = 19
ORIGIN = (0, 6)

HEAD_COLOR = (150, 245, 120)
BODY_COLOR = (60, 200, 90)
FOOD_COLOR = (240, 80, 80)
WALL_COLOR = (40, 46, 62)
TEXT_COLOR = (200, 212, 232)

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class SnakeGame(GameApp):
    game_id = "snake"
    name = "Snake"
    id = "core.snake"
    summary = "Eat, grow, and do not bite yourself."
    layout = "dpad"
    config_fields = [
        ConfigField.number("speed", label="Starting speed", default=6, minimum=2, maximum=14, step=1, help_text="Cells per second. Speeds up as you eat."),
        ConfigField.boolean("walls", label="Walls are deadly", default=True, help_text="Turn off to wrap around the edges instead."),
    ]
    actions = ("up", "down", "left", "right")

    def reset(self) -> None:
        self.walls = bool(self.config.get("walls", True))
        self.base_speed = max(2.0, float(self.config.get("speed", 6)))
        middle = ROWS // 2
        self.body = [(4, middle), (3, middle), (2, middle)]
        self.direction = (1, 0)
        self.pending: list[tuple[int, int]] = []
        self.grow = 0
        self.score = 0
        self.move_timer = 0.0
        self.food = self._place_food()

    def _place_food(self) -> tuple[int, int]:
        occupied = set(self.body)
        free = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in occupied]
        return self.random.choice(free) if free else (0, 0)

    def speed(self) -> float:
        return min(18.0, self.base_speed + self.score * 0.35)

    def handle(self, action: str) -> None:
        step = DIRECTIONS.get(action)
        if step is None:
            return
        # Queue turns so a fast double tap around a corner is not swallowed.
        last = self.pending[-1] if self.pending else self.direction
        if (step[0], step[1]) == (-last[0], -last[1]) or step == last:
            return
        if len(self.pending) < 2:
            self.pending.append(step)
            self.audio.play("turn", 0.4)

    def advance(self, elapsed: float) -> None:
        self.move_timer += elapsed
        interval = 1.0 / self.speed()
        while self.move_timer >= interval and not self.finished():
            self.move_timer -= interval
            self._move()
            interval = 1.0 / self.speed()

    def _move(self) -> None:
        if self.pending:
            self.direction = self.pending.pop(0)
        head_x, head_y = self.body[0]
        next_x = head_x + self.direction[0]
        next_y = head_y + self.direction[1]

        if not (0 <= next_x < COLS and 0 <= next_y < ROWS):
            if self.walls:
                self.game_over = True
                self.audio.play("crash")
                return
            next_x %= COLS
            next_y %= ROWS

        # The tail vacates this move unless the snake is growing into it.
        body = self.body if self.grow else self.body[:-1]
        if (next_x, next_y) in body:
            self.game_over = True
            self.audio.play("crash")
            return

        self.body.insert(0, (next_x, next_y))
        if self.grow:
            self.grow -= 1
        else:
            self.body.pop()

        if (next_x, next_y) == self.food:
            self.audio.play("eat")
            self.score += 1
            self.grow += 2
            if len(self.body) + self.grow >= COLS * ROWS:
                self.won = True
                return
            self.food = self._place_food()

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Best": max(self.store.best, self.score), "Length": len(self.body)}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        origin_x, origin_y = ORIGIN
        width = COLS * CELL
        height = ROWS * CELL

        draw_pixel_text(draw, 1, 0, f"SCORE {self.score}", TEXT_COLOR, 1)
        draw.rectangle((origin_x, origin_y - 1, origin_x + width - 1, origin_y + height), outline=WALL_COLOR)

        food_x = origin_x + self.food[0] * CELL
        food_y = origin_y + self.food[1] * CELL
        draw.rectangle((food_x, food_y, food_x + CELL - 1, food_y + CELL - 1), fill=FOOD_COLOR)

        for index, (cell_x, cell_y) in enumerate(self.body):
            x = origin_x + cell_x * CELL
            y = origin_y + cell_y * CELL
            if index == 0:
                color = HEAD_COLOR
            else:
                # Fade the tail slightly so the direction of travel reads at a glance.
                color = shade(BODY_COLOR, max(0.45, 1.0 - index * 0.03))
            draw.rectangle((x, y, x + CELL - 1, y + CELL - 1), fill=color)

        if self.won:
            draw_banner(draw, ("YOU", "WIN"), HEAD_COLOR)
        elif self.game_over:
            draw_banner(draw, ("GAME", "OVER", f"{self.score}"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        return fit_panel(image, size)


def demo_snapshot() -> SnakeGame:
    game = SnakeGame(seed=4)
    game.body = [(10, 9), (9, 9), (8, 9), (7, 9), (7, 10), (7, 11), (6, 11)]
    game.food = (14, 6)
    game.score = 4
    return game


__all__ = ["SnakeGame", "demo_snapshot"]
