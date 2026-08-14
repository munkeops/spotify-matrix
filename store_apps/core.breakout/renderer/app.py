"""Breakout for the 64x64 matrix."""

from __future__ import annotations

import math
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame, shade

BRICK_COLS = 10
BRICK_ROWS = 5
BRICK_WIDTH = 6
BRICK_HEIGHT = 3
BRICK_LEFT = 2
BRICK_TOP = 10
# Flush, like the arcade. A one pixel gap between rows reads as a seam where
# two bricks meet at a corner, but in continuous coordinates it is a two unit
# channel - exactly the width of the ball, which could thread it diagonally.
BRICK_GAP_Y = 0

FIELD_TOP = 8
PADDLE_Y = 58
PADDLE_HEIGHT = 2
BALL_SIZE = 2

# Ten layouts, cycled with a rebuilt wall each time round. "#" is a brick,
# "=" takes two hits, "." is a gap. Each row is BRICK_COLS wide.
LEVELS = (
    ("##########", "##########", "##########", "##########", "##########"),
    ("#.#.#.#.#.", ".#.#.#.#.#", "#.#.#.#.#.", ".#.#.#.#.#", "#.#.#.#.#."),
    ("....##....", "...####...", "..######..", ".########.", "##########"),
    ("##########", "#........#", "#.######.#", "#........#", "##########"),
    ("=========="  , "##########", "..######..", "##########", "=========="),
    ("#........#", ".#......#.", "..#....#..", "...#..#...", "....##...."),
    ("##..##..##", "##..##..##", "..######..", "##..##..##", "##..##..##"),
    ("=#=#=#=#=#", "#=#=#=#=#=", "=#=#=#=#=#", "#=#=#=#=#=", "=#=#=#=#=#"),
    (".########.", "#.#....#.#", "#..####..#", "#.#....#.#", ".########."),
    ("==========", "==========", "##########", "==========", "=========="),
)

ROW_COLORS = [(238, 74, 84), (244, 148, 44), (240, 206, 46), (72, 214, 96), (74, 158, 240)]
ROW_POINTS = [50, 40, 30, 20, 10]
PADDLE_COLOR = (210, 220, 240)
# A brick that still needs another hit is drawn washed out.
TOUGH_TINT = 0.55
BALL_COLOR = (255, 255, 255)
TEXT_COLOR = (170, 182, 206)
FRAME_COLOR = (40, 46, 62)


class BreakoutGame(GameApp):
    game_id = "breakout"
    name = "Breakout"
    id = "core.breakout"
    summary = "Bounce the ball and clear every brick."
    layout = "horizontal"
    config_fields = [
        ConfigField.number("paddleWidth", label="Paddle width", default=12, minimum=6, maximum=20, step=1),
        ConfigField.number("ballSpeed", label="Ball speed", default=34, minimum=18, maximum=60, step=2),
        ConfigField.number("lives", label="Lives", default=3, minimum=1, maximum=5, step=1),
    ]
    actions = ("left", "right", "fire")

    def reset(self) -> None:
        self.paddle_width = max(6, min(20, int(self.config.get("paddleWidth", 12))))
        self.base_speed = max(18.0, float(self.config.get("ballSpeed", 34)))
        self.lives = max(1, int(self.config.get("lives", 3)))
        self.score = 0
        self.level = 1
        self._build_level()

    def level_pattern(self) -> tuple[str, ...]:
        """The brick pattern for this level, cycling once they run out."""
        return LEVELS[(self.level - 1) % len(LEVELS)]

    def _build_level(self) -> None:
        rows = self.level_pattern()
        # 0 is empty, 1 needs one hit, 2 needs two.
        self.bricks = [
            [2 if cell == chr(61) else 1 if cell == chr(35) else 0 for cell in rows[row]]
            for row in range(BRICK_ROWS)
        ]
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
            self.audio.play("launch")
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
            self.audio.play("wall", 0.5)
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
                self.audio.play("paddle")

        if self.ball_y > PANEL:
            self.lives -= 1
            self.audio.play("lose_life")
            if self.lives <= 0:
                self.game_over = True
                self.audio.play("game_over")
            else:
                self._serve()

    def _brick_rect(self, row: int, column: int) -> tuple[int, int, int, int]:
        left = BRICK_LEFT + column * BRICK_WIDTH
        top = BRICK_TOP + row * (BRICK_HEIGHT + BRICK_GAP_Y)
        return left, top, left + BRICK_WIDTH - 1, top + BRICK_HEIGHT - 1

    def _overlaps(self, left: int, top: int, right: int, bottom: int) -> bool:
        """Do the ball and a brick share any space at all?

        The pixel at ``right`` covers up to ``right + 1`` in continuous
        coordinates, so testing ``ball_x <= right`` makes the brick a whole
        unit narrower and shorter than it is drawn. Two bricks meeting at a
        corner then leave a slot the ball fits through exactly, which is the
        corner it was slipping past.
        """
        return (
            self.ball_x < right + 1
            and left < self.ball_x + BALL_SIZE
            and self.ball_y < bottom + 1
            and top < self.ball_y + BALL_SIZE
        )

    def _penetration(self, left: int, top: int, right: int, bottom: int) -> tuple[float, float]:
        """How far the ball has sunk into a brick along each axis."""
        width, height = right - left + 1, bottom - top + 1
        ball_x = self.ball_x + BALL_SIZE / 2
        ball_y = self.ball_y + BALL_SIZE / 2
        depth_x = (width + BALL_SIZE) / 2 - abs(ball_x - (left + width / 2))
        depth_y = (height + BALL_SIZE) / 2 - abs(ball_y - (top + height / 2))
        return depth_x, depth_y

    def _hit_bricks(self) -> None:
        """Resolve against every brick the ball is touching, not just one.

        Two things were wrong. The bounce axis came from comparing the
        distance to the brick's centre, which weighs a horizontal gap against
        a vertical one on a brick twice as wide as it is tall, so a hit on the
        top face could read as a hit on the side. And only the first
        overlapping brick was resolved, so at the corner where two bricks meet
        the ball turned away from one while still inside the other, and the
        next step turned it back - straight through the seam.

        Overlap depth is the comparison that holds whatever shape the brick
        is, each axis turns at most once however many bricks are involved,
        and the ball is pushed clear so it cannot resolve twice against the
        same brick.
        """
        hits = []
        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLS):
                if not self.bricks[row][column]:
                    continue
                rect = self._brick_rect(row, column)
                if self._overlaps(*rect):
                    hits.append((row, column, rect))
        if not hits:
            return

        flip_x = flip_y = False
        push_x = push_y = 0.0
        cracked = destroyed = False

        for row, column, rect in hits:
            depth_x, depth_y = self._penetration(*rect)
            left, top, right, bottom = rect
            ball_x = self.ball_x + BALL_SIZE / 2
            ball_y = self.ball_y + BALL_SIZE / 2
            # An exact corner has equal depths and turns the ball on both.
            if depth_y <= depth_x:
                flip_y = True
                away = depth_y if ball_y > top + (bottom - top + 1) / 2 else -depth_y
                push_y = away if abs(away) > abs(push_y) else push_y
            if depth_x <= depth_y:
                flip_x = True
                away = depth_x if ball_x > left + (right - left + 1) / 2 else -depth_x
                push_x = away if abs(away) > abs(push_x) else push_x

            self.bricks[row][column] -= 1
            if self.bricks[row][column] > 0:
                cracked = True
            else:
                destroyed = True
                self.score += ROW_POINTS[row]

        if flip_x:
            self.ball_vx = -self.ball_vx
            self.ball_x += push_x
        if flip_y:
            self.ball_vy = -self.ball_vy
            self.ball_y += push_y

        self.audio.play("brick" if destroyed else "wall")
        if destroyed and not any(any(brick_row) for brick_row in self.bricks):
            self.level += 1
            self._build_level()
            self.audio.play("start")

    def hud(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Best": max(self.store.best, self.score),
            "Lives": max(0, self.lives),
            "Level": f"{self.level}/{len(LEVELS)}",
        }

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        draw_pixel_text(draw, 1, 1, f"{self.score}", TEXT_COLOR, 1)
        for life in range(max(0, self.lives)):
            draw.rectangle((PANEL - 4 - life * 5, 2, PANEL - 2 - life * 5, 3), fill=PADDLE_COLOR)
        draw.line((0, FIELD_TOP - 1, PANEL - 1, FIELD_TOP - 1), fill=FRAME_COLOR)

        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLS):
                strength = self.bricks[row][column]
                if strength:
                    left, top, right, bottom = self._brick_rect(row, column)
                    color = ROW_COLORS[row] if strength == 1 else shade(ROW_COLORS[row], TOUGH_TINT)
                    draw.rectangle((left, top, right - 1, bottom), fill=color)

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
        game.bricks[0][column] = 0 if column % 3 == 0 else 1
        game.bricks[1][column] = 0 if column % 4 == 1 else 1
    game.score = 320
    game.ball_x = 30
    game.ball_y = 40
    game.launched = True
    return game


__all__ = ["BreakoutGame", "demo_snapshot"]
