"""One-button flapper for the 64x64 matrix."""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameWidget
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_centered_text, fit_panel, new_frame

BIRD_X = 14
BIRD_SIZE = 5
PIPE_WIDTH = 9
PIPE_SPACING = 34
GROUND_Y = 60

SKY_COLOR = (10, 16, 34)
PIPE_COLOR = (72, 200, 96)
PIPE_LIP_COLOR = (110, 236, 130)
BIRD_COLOR = (250, 208, 60)
BIRD_BEAK = (244, 128, 40)
GROUND_COLOR = (86, 62, 40)
TEXT_COLOR = (226, 234, 248)


class FlappyGame(GameWidget):
    game_id = "flappy"
    name = "Flappy"
    id = "core.flappy"
    summary = "One button, endless pipes."
    layout = "tap"
    config_fields = [
        ConfigField.number("gap", label="Pipe gap", default=20, minimum=14, maximum=30, step=1, help_text="Smaller is harder."),
        ConfigField.number("speed", label="Scroll speed", default=22, minimum=10, maximum=40, step=2),
        ConfigField.number("gravity", label="Gravity", default=110, minimum=40, maximum=200, step=10),
    ]
    actions = ("flap",)

    def reset(self) -> None:
        self.gap = max(14, min(30, int(self.config.get("gap", 20))))
        self.scroll_speed = max(10.0, float(self.config.get("speed", 22)))
        self.gravity = max(40.0, float(self.config.get("gravity", 110)))
        self.flap_velocity = -abs(float(self.config.get("flapVelocity", 38)))
        self.score = 0
        self.best = getattr(self, "best", 0)
        self.started = False
        self.bird_y = float(PANEL // 2)
        self.bird_vy = 0.0
        self.pipes: list[dict[str, Any]] = []
        for index in range(3):
            self.pipes.append(self._new_pipe(PANEL + 6 + index * PIPE_SPACING))

    def _new_pipe(self, x: float) -> dict[str, Any]:
        top = self.random.randint(6, GROUND_Y - self.gap - 8)
        return {"x": x, "top": top, "scored": False}

    def handle(self, action: str) -> None:
        if action != "flap":
            return
        self.started = True
        self.bird_vy = self.flap_velocity

    def advance(self, elapsed: float) -> None:
        if not self.started:
            return
        self.bird_vy += self.gravity * elapsed
        self.bird_y += self.bird_vy * elapsed

        for pipe in self.pipes:
            pipe["x"] -= self.scroll_speed * elapsed
            if not pipe["scored"] and pipe["x"] + PIPE_WIDTH < BIRD_X:
                pipe["scored"] = True
                self.score += 1
                self.best = max(self.best, self.score)
        if self.pipes and self.pipes[0]["x"] + PIPE_WIDTH < 0:
            self.pipes.pop(0)
            # Trail the last pipe, or start past the edge if that was the only one.
            last_x = self.pipes[-1]["x"] if self.pipes else float(PANEL)
            self.pipes.append(self._new_pipe(last_x + PIPE_SPACING))

        if self.bird_y < 0 or self.bird_y + BIRD_SIZE > GROUND_Y:
            self.bird_y = max(0.0, min(float(GROUND_Y - BIRD_SIZE), self.bird_y))
            self.game_over = True
            return
        if self._collides():
            self.game_over = True

    def _collides(self) -> bool:
        for pipe in self.pipes:
            left = pipe["x"]
            right = pipe["x"] + PIPE_WIDTH - 1
            if right < BIRD_X or left > BIRD_X + BIRD_SIZE - 1:
                continue
            if self.bird_y < pipe["top"] or self.bird_y + BIRD_SIZE - 1 > pipe["top"] + self.gap:
                return True
        return False

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Best": self.best}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame(SKY_COLOR)

        for pipe in self.pipes:
            left = int(round(pipe["x"]))
            right = left + PIPE_WIDTH - 1
            if right < 0 or left >= PANEL:
                continue
            top_end = pipe["top"]
            bottom_start = pipe["top"] + self.gap
            draw.rectangle((left, 0, right, top_end - 1), fill=PIPE_COLOR)
            draw.rectangle((left - 1, top_end - 3, right + 1, top_end - 1), fill=PIPE_LIP_COLOR)
            draw.rectangle((left, bottom_start + 1, right, GROUND_Y - 1), fill=PIPE_COLOR)
            draw.rectangle((left - 1, bottom_start + 1, right + 1, bottom_start + 3), fill=PIPE_LIP_COLOR)

        draw.rectangle((0, GROUND_Y, PANEL - 1, PANEL - 1), fill=GROUND_COLOR)

        bird_y = int(round(self.bird_y))
        draw.rectangle((BIRD_X, bird_y, BIRD_X + BIRD_SIZE - 1, bird_y + BIRD_SIZE - 1), fill=BIRD_COLOR)
        draw.point((BIRD_X + BIRD_SIZE, bird_y + 2), fill=BIRD_BEAK)
        draw.point((BIRD_X + 3, bird_y + 1), fill=(20, 20, 30))

        draw_centered_text(draw, 2, str(self.score), TEXT_COLOR, 2)

        if self.game_over:
            draw_banner(draw, ("GAME", "OVER", f"BEST {self.best}"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        elif not self.started:
            draw_banner(draw, ("TAP", "TO FLY"), TEXT_COLOR, top=42)
        return fit_panel(image, size)


def demo_snapshot() -> FlappyGame:
    game = FlappyGame(seed=5)
    game.started = True
    game.score = 7
    game.best = 12
    game.bird_y = 26.0
    game.pipes = [
        {"x": 8.0, "top": 10, "scored": True},
        {"x": 42.0, "top": 24, "scored": False},
    ]
    return game


__all__ = ["FlappyGame", "demo_snapshot"]
