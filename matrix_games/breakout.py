"""Breakout for the 64x64 matrix."""

from __future__ import annotations

import math
from typing import Any

from PIL import Image

from matrix_games.base import Game
from matrix_games.render import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

BRICK_COLS = 10
BRICK_ROWS = 5
BRICK_WIDTH = 6
BRICK_HEIGHT = 3
BRICK_LEFT = 2
BRICK_TOP = 10
BRICK_GAP_Y = 1

FIELD_TOP = 8
PADDLE_Y = 58
PADDLE_HEIGHT = 2
BALL_SIZE = 2

ROW_COLORS = [(238, 74, 84), (244, 148, 44), (240, 206, 46), (72, 214, 96), (74, 158, 240)]
ROW_POINTS = [50, 40, 30, 20, 10]
PADDLE_COLOR = (210, 220, 240)
BALL_COLOR = (255, 255, 255)
TEXT_COLOR = (170, 182, 206)
FRAME_COLOR = (40, 46, 62)


class BreakoutGame(Game):
    game_id = "breakout"
    name = "Breakout"
    actions = ("left", "right", "fire")

    def reset(self) -> None:
        self.paddle_width = max(6, min(20, int(self.config.get("paddleWidth", 12))))
        self.base_speed = max(18.0, float(self.config.get("ballSpeed", 34)))
        self.lives = max(1, int(self.config.get("lives", 3)))
        self.score = 0
        self.level = 1
        self._build_level()

    def _build_level(self) -> None:
        self.bricks = [[True] * BRICK_COLS for _ in range(BRICK_ROWS)]
        self.paddle_x = (PANEL - self.paddle_width) / 2
        self._serve()

    def _serve(self) -> None:
        self.launched = False
        self.ball_x = self.paddle_x + self.paddle_width / 2
        self.ball_y = PADDLE_Y - BALL_SIZE
        self.ball_vx = 0.0
        self.ball_vy = 0.0

    def speed(self) -> float:
        return self.base_speed * (1.0 + (self.level - 1) * 0.12)

    def handle(self, action: str) -> None:
        if action == "left":
            self.paddle_x = max(1.0, self.paddle_x - 3)
        elif action == "right":
            self.paddle_x = min(PANEL - 1 - self.paddle_width, self.paddle_x + 3)
        elif action == "fire" and not self.launched:
            angle = math.radians(self.random.uniform(-35, 35))
            self.ball_vx = math.sin(angle) * self.speed()
            self.ball_vy = -math.cos(angle) * self.speed()
            self.launched = True
        if not self.launched:
            self.ball_x = self.paddle_x + self.paddle_width / 2

    def advance(self, elapsed: float) -> None:
        if not self.launched:
            return
        # Sub-step so a fast ball cannot tunnel through a brick or the paddle.
        steps = max(1, int(self.speed() * elapsed / 1.5) + 1)
        for _ in range(steps):
            self._advance_ball(elapsed / steps)
            if self.finished() or not self.launched:
                return

    def _advance_ball(self, elapsed: float) -> None:
        self.ball_x += self.ball_vx * elapsed
        self.ball_y += self.ball_vy * elapsed

        if self.ball_x <= 1:
            self.ball_x = 1
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x >= PANEL - 1 - BALL_SIZE:
            self.ball_x = PANEL - 1 - BALL_SIZE
            self.ball_vx = -abs(self.ball_vx)
        if self.ball_y <= FIELD_TOP:
            self.ball_y = FIELD_TOP
            self.ball_vy = abs(self.ball_vy)

        self._hit_bricks()

        if self.ball_vy > 0 and PADDLE_Y - BALL_SIZE <= self.ball_y <= PADDLE_Y + PADDLE_HEIGHT:
            if self.paddle_x - 1 <= self.ball_x + BALL_SIZE / 2 <= self.paddle_x + self.paddle_width + 1:
                offset = (self.ball_x + BALL_SIZE / 2 - (self.paddle_x + self.paddle_width / 2)) / (self.paddle_width / 2)
                angle = math.radians(max(-60.0, min(60.0, offset * 60)))
                self.ball_vx = math.sin(angle) * self.speed()
                self.ball_vy = -abs(math.cos(angle) * self.speed())
                self.ball_y = PADDLE_Y - BALL_SIZE

        if self.ball_y > PANEL:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over = True
            else:
                self._serve()

    def _brick_rect(self, row: int, column: int) -> tuple[int, int, int, int]:
        left = BRICK_LEFT + column * BRICK_WIDTH
        top = BRICK_TOP + row * (BRICK_HEIGHT + BRICK_GAP_Y)
        return left, top, left + BRICK_WIDTH - 1, top + BRICK_HEIGHT - 1

    def _hit_bricks(self) -> None:
        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLS):
                if not self.bricks[row][column]:
                    continue
                left, top, right, bottom = self._brick_rect(row, column)
                if left <= self.ball_x + BALL_SIZE - 1 and self.ball_x <= right and top <= self.ball_y + BALL_SIZE - 1 and self.ball_y <= bottom:
                    self.bricks[row][column] = False
                    self.score += ROW_POINTS[row]
                    # Bounce off whichever face the ball was closest to.
                    if abs((self.ball_y + BALL_SIZE / 2) - (top + BRICK_HEIGHT / 2)) > abs((self.ball_x + BALL_SIZE / 2) - (left + BRICK_WIDTH / 2)):
                        self.ball_vy = -self.ball_vy
                    else:
                        self.ball_vx = -self.ball_vx
                    if not any(any(brick_row) for brick_row in self.bricks):
                        self.level += 1
                        self._build_level()
                    return

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Lives": max(0, self.lives), "Level": self.level}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        draw_pixel_text(draw, 1, 1, f"{self.score}", TEXT_COLOR, 1)
        for life in range(max(0, self.lives)):
            draw.rectangle((PANEL - 4 - life * 5, 2, PANEL - 2 - life * 5, 3), fill=PADDLE_COLOR)
        draw.line((0, FIELD_TOP - 1, PANEL - 1, FIELD_TOP - 1), fill=FRAME_COLOR)

        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLS):
                if self.bricks[row][column]:
                    left, top, right, bottom = self._brick_rect(row, column)
                    draw.rectangle((left, top, right - 1, bottom), fill=ROW_COLORS[row])

        draw.rectangle(
            (int(self.paddle_x), PADDLE_Y, int(self.paddle_x) + self.paddle_width - 1, PADDLE_Y + PADDLE_HEIGHT - 1),
            fill=PADDLE_COLOR,
        )
        draw.rectangle(
            (int(self.ball_x), int(self.ball_y), int(self.ball_x) + BALL_SIZE - 1, int(self.ball_y) + BALL_SIZE - 1),
            fill=BALL_COLOR,
        )

        if self.game_over:
            draw_banner(draw, ("GAME", "OVER", f"{self.score}"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        elif not self.launched:
            draw_banner(draw, ("PRESS", "FIRE"), TEXT_COLOR, top=40)
        return fit_panel(image, size)


def demo_snapshot() -> BreakoutGame:
    game = BreakoutGame(seed=2)
    for column in range(BRICK_COLS):
        game.bricks[0][column] = column % 3 != 0
        game.bricks[1][column] = column % 4 != 1
    game.score = 320
    game.ball_x = 30
    game.ball_y = 40
    game.launched = True
    return game


__all__ = ["BreakoutGame", "demo_snapshot"]
