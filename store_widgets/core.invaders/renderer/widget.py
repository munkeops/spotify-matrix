"""Space Invaders for the 64x64 matrix."""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameWidget
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

COLUMNS = 8
ROWS = 5
STEP_X = 7
STEP_Y = 6
FLEET_LEFT = 4
FLEET_TOP = 11

SHIP_Y = 57
SHIP_WIDTH = 7
SHIP_HEIGHT = 4
SHIP_SPEED = 3

BULLET_SPEED = 70.0
BOMB_SPEED = 26.0
MAX_BOMBS = 3

# Two animation frames per invader family, drawn as 6x4 pixel sprites.
SPRITES = [
    [("..##..", ".####.", "##..##", ".#..#."), ("..##..", ".####.", "##..##", "#....#")],
    [(".####.", "######", "#.##.#", "#....#"), (".####.", "######", "#.##.#", ".#..#.")],
    [("#.##.#", "######", ".####.", ".#..#."), ("#.##.#", "######", ".####.", "#....#")],
]
SHIP_SPRITE = ("...#...", "..###..", "#######", "#######")

ROW_SPRITE = [0, 1, 1, 2, 2]
ROW_COLOR = [(120, 230, 255), (200, 140, 255), (200, 140, 255), (110, 240, 140), (110, 240, 140)]
ROW_POINTS = [30, 20, 20, 10, 10]

SHIP_COLOR = (120, 240, 150)
BULLET_COLOR = (255, 255, 255)
BOMB_COLOR = (255, 140, 90)
TEXT_COLOR = (196, 208, 230)
FLOOR_COLOR = (40, 46, 62)


class InvadersGame(GameWidget):
    game_id = "invaders"
    name = "Space Invaders"
    id = "core.invaders"
    summary = "Hold off descending waves of aliens."
    layout = "horizontal"
    config_fields = [
        ConfigField.number("lives", label="Lives", default=3, minimum=1, maximum=5, step=1),
    ]
    actions = ("left", "right", "fire")

    def reset(self) -> None:
        self.lives = max(1, int(self.config.get("lives", 3)))
        self.score = 0
        self.wave = 1
        self.ship_x = (PANEL - SHIP_WIDTH) // 2
        self._build_wave()

    def _build_wave(self) -> None:
        self.alive = [[True] * COLUMNS for _ in range(ROWS)]
        self.fleet_x = float(FLEET_LEFT)
        self.fleet_y = float(FLEET_TOP + min(6, (self.wave - 1) * 2))
        self.fleet_direction = 1
        self.step_timer = 0.0
        self.animation = 0
        self.bullet: list[float] | None = None
        self.bombs: list[list[float]] = []
        self.bomb_timer = 0.0

    def _alive_count(self) -> int:
        return sum(1 for row in self.alive for cell in row if cell)

    def step_interval(self) -> float:
        remaining = self._alive_count()
        total = ROWS * COLUMNS
        pace = 0.62 * (remaining / total) + 0.07
        return max(0.05, pace / (1.0 + (self.wave - 1) * 0.15))

    def handle(self, action: str) -> None:
        if action == "left":
            self.ship_x = max(1, self.ship_x - SHIP_SPEED)
        elif action == "right":
            self.ship_x = min(PANEL - 1 - SHIP_WIDTH, self.ship_x + SHIP_SPEED)
        elif action == "fire" and self.bullet is None:
            self.bullet = [self.ship_x + SHIP_WIDTH // 2, float(SHIP_Y - 3)]

    def advance(self, elapsed: float) -> None:
        self._advance_fleet(elapsed)
        self._advance_bullet(elapsed)
        self._advance_bombs(elapsed)

    def _advance_fleet(self, elapsed: float) -> None:
        self.step_timer += elapsed
        interval = self.step_interval()
        while self.step_timer >= interval and not self.finished():
            self.step_timer -= interval
            self.animation ^= 1
            columns = [column for column in range(COLUMNS) if any(self.alive[row][column] for row in range(ROWS))]
            if not columns:
                return
            left = self.fleet_x + min(columns) * STEP_X
            right = self.fleet_x + max(columns) * STEP_X + 6
            if (self.fleet_direction > 0 and right >= PANEL - 2) or (self.fleet_direction < 0 and left <= 2):
                self.fleet_direction *= -1
                self.fleet_y += 3
            else:
                self.fleet_x += self.fleet_direction * 2
            if self._lowest_row_bottom() >= SHIP_Y:
                self.game_over = True
                return

    def _lowest_row_bottom(self) -> float:
        for row in range(ROWS - 1, -1, -1):
            if any(self.alive[row]):
                return self.fleet_y + row * STEP_Y + 4
        return 0.0

    def _invader_rect(self, row: int, column: int) -> tuple[float, float, float, float]:
        left = self.fleet_x + column * STEP_X
        top = self.fleet_y + row * STEP_Y
        return left, top, left + 5, top + 3

    def _advance_bullet(self, elapsed: float) -> None:
        if self.bullet is None:
            return
        self.bullet[1] -= BULLET_SPEED * elapsed
        if self.bullet[1] < 0:
            self.bullet = None
            return
        bullet_x, bullet_y = self.bullet
        for row in range(ROWS):
            for column in range(COLUMNS):
                if not self.alive[row][column]:
                    continue
                left, top, right, bottom = self._invader_rect(row, column)
                if left <= bullet_x <= right and top <= bullet_y <= bottom + 2:
                    self.alive[row][column] = False
                    self.score += ROW_POINTS[row] * self.wave
                    self.bullet = None
                    if self._alive_count() == 0:
                        self.wave += 1
                        self._build_wave()
                    return

    def _advance_bombs(self, elapsed: float) -> None:
        self.bomb_timer += elapsed
        drop_every = max(0.4, 1.6 - self.wave * 0.15)
        if self.bomb_timer >= drop_every and len(self.bombs) < MAX_BOMBS:
            self.bomb_timer = 0.0
            shooters = [
                (row, column)
                for column in range(COLUMNS)
                for row in range(ROWS - 1, -1, -1)
                if self.alive[row][column]
            ]
            if shooters:
                row, column = self.random.choice(shooters)
                left, _, right, bottom = self._invader_rect(row, column)
                self.bombs.append([(left + right) / 2, bottom + 1])

        for bomb in list(self.bombs):
            bomb[1] += BOMB_SPEED * elapsed
            if bomb[1] >= PANEL:
                self.bombs.remove(bomb)
                continue
            if SHIP_Y <= bomb[1] <= SHIP_Y + SHIP_HEIGHT and self.ship_x <= bomb[0] <= self.ship_x + SHIP_WIDTH:
                self.bombs.remove(bomb)
                self._hit()

    def _hit(self) -> None:
        self.lives -= 1
        self.bullet = None
        self.bombs = []
        self.ship_x = (PANEL - SHIP_WIDTH) // 2
        if self.lives <= 0:
            self.game_over = True

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Lives": max(0, self.lives), "Wave": self.wave}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        draw_pixel_text(draw, 1, 1, f"{self.score}", TEXT_COLOR, 1)
        for life in range(max(0, self.lives - 1)):
            draw.rectangle((PANEL - 4 - life * 4, 1, PANEL - 3 - life * 4, 3), fill=SHIP_COLOR)
        draw.line((0, 7, PANEL - 1, 7), fill=FLOOR_COLOR)

        for row in range(ROWS):
            sprite = SPRITES[ROW_SPRITE[row]][self.animation]
            color = ROW_COLOR[row]
            for column in range(COLUMNS):
                if not self.alive[row][column]:
                    continue
                left, top, _, _ = self._invader_rect(row, column)
                for offset_y, line in enumerate(sprite):
                    for offset_x, pixel in enumerate(line):
                        if pixel == "#":
                            draw.point((int(left) + offset_x, int(top) + offset_y), fill=color)

        for offset_y, line in enumerate(SHIP_SPRITE):
            for offset_x, pixel in enumerate(line):
                if pixel == "#":
                    draw.point((self.ship_x + offset_x, SHIP_Y + offset_y), fill=SHIP_COLOR)

        if self.bullet is not None:
            x, y = int(self.bullet[0]), int(self.bullet[1])
            draw.line((x, y, x, y + 2), fill=BULLET_COLOR)
        for bomb in self.bombs:
            x, y = int(bomb[0]), int(bomb[1])
            draw.line((x, y, x, y + 2), fill=BOMB_COLOR)

        if self.game_over:
            draw_banner(draw, ("GAME", "OVER", f"{self.score}"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        return fit_panel(image, size)


def demo_snapshot() -> InvadersGame:
    game = InvadersGame(seed=8)
    game.score = 640
    game.wave = 2
    for column in range(COLUMNS):
        game.alive[4][column] = column % 3 != 0
        game.alive[3][column] = column % 4 != 2
    game.bullet = [30.0, 40.0]
    game.bombs = [[16.0, 34.0]]
    return game


__all__ = ["InvadersGame", "demo_snapshot"]
