"""Pong for the 64x64 matrix, against the computer or a second phone."""

from __future__ import annotations

import math
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameWidget
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame, pixel_text_width

PADDLE_WIDTH = 2
PADDLE_HEIGHT = 12
BALL_SIZE = 2
LEFT_X = 2
RIGHT_X = PANEL - 2 - PADDLE_WIDTH
FIELD_TOP = 9

LEFT_COLOR = (96, 200, 255)
RIGHT_COLOR = (255, 140, 120)
BALL_COLOR = (255, 255, 255)
NET_COLOR = (48, 54, 74)
TEXT_COLOR = (196, 208, 230)


class PongGame(GameWidget):
    game_id = "pong"
    name = "Pong"
    id = "core.pong"
    summary = "Rally against the computer or a second phone."
    layout = "vertical"
    config_fields = [
        ConfigField.select("opponent", [("Computer", "ai"), ("Second player", "human")], label="Opponent", help_text="Second player uses the P2 buttons, so two phones can share one panel."),
        ConfigField.number("target", label="Play to", default=7, minimum=1, maximum=21, step=1),
        ConfigField.number("aiSpeed", label="Computer speed", default=34, minimum=10, maximum=60, step=2),
        ConfigField.number("ballSpeed", label="Ball speed", default=32, minimum=18, maximum=60, step=2),
    ]
    actions = ("up", "down", "p2Up", "p2Down")

    def reset(self) -> None:
        self.target = max(1, min(21, int(self.config.get("target", 7))))
        self.opponent = str(self.config.get("opponent", "ai"))
        self.ai_speed = max(10.0, float(self.config.get("aiSpeed", 34)))
        self.base_speed = max(18.0, float(self.config.get("ballSpeed", 32)))
        self.left_y = (PANEL - PADDLE_HEIGHT) / 2
        self.right_y = (PANEL - PADDLE_HEIGHT) / 2
        self.left_score = 0
        self.right_score = 0
        self.winner = ""
        self._serve(1)

    def _serve(self, direction: int) -> None:
        self.ball_x = PANEL / 2 - BALL_SIZE / 2
        self.ball_y = self.random.uniform(FIELD_TOP + 6, PANEL - 10)
        angle = math.radians(self.random.uniform(-30, 30))
        self.rally = 0
        self.ball_vx = direction * math.cos(angle) * self.base_speed
        self.ball_vy = math.sin(angle) * self.base_speed

    def speed(self) -> float:
        return self.base_speed * (1.0 + min(0.9, self.rally * 0.06))

    def handle(self, action: str) -> None:
        step = 4.0
        if action == "up":
            self.left_y = max(FIELD_TOP, self.left_y - step)
        elif action == "down":
            self.left_y = min(PANEL - PADDLE_HEIGHT, self.left_y + step)
        elif action == "p2Up" and self.opponent == "human":
            self.right_y = max(FIELD_TOP, self.right_y - step)
        elif action == "p2Down" and self.opponent == "human":
            self.right_y = min(PANEL - PADDLE_HEIGHT, self.right_y + step)

    def advance(self, elapsed: float) -> None:
        if self.opponent != "human":
            self._move_ai(elapsed)

        steps = max(1, int(self.speed() * elapsed / 1.5) + 1)
        for _ in range(steps):
            self._advance_ball(elapsed / steps)
            if self.finished():
                return

    def _move_ai(self, elapsed: float) -> None:
        target = self.ball_y + BALL_SIZE / 2 - PADDLE_HEIGHT / 2
        # Only chase once the ball is heading this way, so the AI is beatable.
        if self.ball_vx <= 0:
            target = (PANEL - PADDLE_HEIGHT) / 2
        delta = target - self.right_y
        move = min(abs(delta), self.ai_speed * elapsed)
        self.right_y += math.copysign(move, delta)
        self.right_y = max(FIELD_TOP, min(PANEL - PADDLE_HEIGHT, self.right_y))

    def _advance_ball(self, elapsed: float) -> None:
        self.ball_x += self.ball_vx * elapsed
        self.ball_y += self.ball_vy * elapsed

        if self.ball_y <= FIELD_TOP:
            self.ball_y = FIELD_TOP
            self.ball_vy = abs(self.ball_vy)
        elif self.ball_y >= PANEL - BALL_SIZE:
            self.ball_y = PANEL - BALL_SIZE
            self.ball_vy = -abs(self.ball_vy)

        if self.ball_vx < 0 and LEFT_X <= self.ball_x <= LEFT_X + PADDLE_WIDTH:
            if self.left_y - 1 <= self.ball_y + BALL_SIZE / 2 <= self.left_y + PADDLE_HEIGHT + 1:
                self._bounce(self.left_y, 1)
        elif self.ball_vx > 0 and RIGHT_X - BALL_SIZE <= self.ball_x <= RIGHT_X + PADDLE_WIDTH:
            if self.right_y - 1 <= self.ball_y + BALL_SIZE / 2 <= self.right_y + PADDLE_HEIGHT + 1:
                self._bounce(self.right_y, -1)

        if self.ball_x < -BALL_SIZE:
            self.right_score += 1
            self._finish_point(-1)
        elif self.ball_x > PANEL:
            self.left_score += 1
            self._finish_point(1)

    def _bounce(self, paddle_y: float, direction: int) -> None:
        self.rally += 1
        offset = (self.ball_y + BALL_SIZE / 2 - (paddle_y + PADDLE_HEIGHT / 2)) / (PADDLE_HEIGHT / 2)
        angle = math.radians(max(-55.0, min(55.0, offset * 55)))
        speed = self.speed()
        self.ball_vx = direction * abs(math.cos(angle)) * speed
        self.ball_vy = math.sin(angle) * speed
        self.ball_x = (LEFT_X + PADDLE_WIDTH) if direction > 0 else (RIGHT_X - BALL_SIZE)

    def _finish_point(self, direction: int) -> None:
        if self.left_score >= self.target or self.right_score >= self.target:
            self.winner = "left" if self.left_score > self.right_score else "right"
            self.won = True
            return
        self._serve(direction)

    def hud(self) -> dict[str, Any]:
        return {"You": self.left_score, "Rival": self.right_score, "First to": self.target}

    def extra(self) -> dict[str, Any]:
        return {"twoPlayer": self.opponent == "human"}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        for y in range(FIELD_TOP, PANEL, 4):
            draw.point((PANEL // 2, y), fill=NET_COLOR)

        left_text = str(self.left_score)
        draw_pixel_text(draw, PANEL // 2 - 4 - pixel_text_width(left_text, 1), 1, left_text, LEFT_COLOR, 1)
        draw_pixel_text(draw, PANEL // 2 + 4, 1, str(self.right_score), RIGHT_COLOR, 1)
        draw.line((0, FIELD_TOP - 2, PANEL - 1, FIELD_TOP - 2), fill=NET_COLOR)

        draw.rectangle((LEFT_X, int(self.left_y), LEFT_X + PADDLE_WIDTH - 1, int(self.left_y) + PADDLE_HEIGHT - 1), fill=LEFT_COLOR)
        draw.rectangle((RIGHT_X, int(self.right_y), RIGHT_X + PADDLE_WIDTH - 1, int(self.right_y) + PADDLE_HEIGHT - 1), fill=RIGHT_COLOR)
        draw.rectangle((int(self.ball_x), int(self.ball_y), int(self.ball_x) + BALL_SIZE - 1, int(self.ball_y) + BALL_SIZE - 1), fill=BALL_COLOR)

        if self.won:
            draw_banner(draw, ("YOU WIN",) if self.winner == "left" else ("RIVAL", "WINS"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        return fit_panel(image, size)


def demo_snapshot() -> PongGame:
    game = PongGame(seed=6)
    game.left_score = 3
    game.right_score = 4
    game.left_y = 22
    game.right_y = 34
    game.ball_x = 28
    game.ball_y = 30
    return game


__all__ = ["PongGame", "demo_snapshot"]
