"""Centipede for the 64x64 matrix.

A centipede winds down through a mushroom field. Shoot a segment and it dies
leaving a mushroom behind, and the centipede splits in two at that point -
so clearing one is a race against making the field harder to shoot through.

Everything lives on a 21x21 grid of 3 pixel cells, which is the largest that
leaves a mushroom looking like a mushroom.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

CELL = 3
COLS = 21
ROWS = 18
ORIGIN = (1, 9)
#: Rows at the bottom the player may move within, as in the arcade.
PLAYER_ROWS = 5

MUSHROOM_HITS = 4

BACKGROUND = (8, 10, 16)
MUSHROOM = ((120, 200, 120), (150, 190, 90), (200, 170, 80), (220, 120, 120))
POISON = (230, 90, 90)
BODY = (110, 220, 140)
HEAD = (240, 240, 120)
PLAYER = (120, 210, 255)
SHOT = (255, 245, 200)
TEXT = (214, 222, 240)
DIM = (120, 132, 160)


class Segment:
    __slots__ = ("x", "y", "direction", "descending", "head")

    def __init__(self, x: int, y: int, direction: int, head: bool = False) -> None:
        self.x = x
        self.y = y
        self.direction = direction
        self.descending = 0
        self.head = head


class CentipedeGame(GameApp):
    game_id = "centipede"
    id = "core.centipede"
    name = "Centipede"
    summary = "Shoot it apart before it reaches you. Every hit leaves a mushroom."
    layout = "dpad"
    actions = ("left", "right", "up", "down", "fire")
    config_fields = [
        ConfigField.number("lives", label="Lives", default=3, minimum=1, maximum=5, step=1),
        ConfigField.number("length", label="Centipede length", default=10, minimum=4, maximum=16, step=1),
        ConfigField.number("mushrooms", label="Mushrooms", default=28, minimum=0, maximum=60, step=4),
        ConfigField.number("speed", label="Speed", default=8, minimum=3, maximum=16, step=1, help_text="Steps a second. Rises each wave."),
    ]

    def reset(self) -> None:
        self.max_lives = max(1, int(self.config.get("lives", 3)))
        self.length = max(2, int(self.config.get("length", 10)))
        self.mushroom_count = max(0, int(self.config.get("mushrooms", 28)))
        self.base_speed = max(2.0, float(self.config.get("speed", 8)))

        self.lives = self.max_lives
        self.wave = 1
        self.score = 0
        self._start_wave()

    def _start_wave(self) -> None:
        self.mushrooms = [[0] * COLS for _ in range(ROWS)]
        for _ in range(self.mushroom_count):
            x = self.random.randrange(COLS)
            # Leave the player's band clear enough to move in.
            y = self.random.randrange(1, ROWS - PLAYER_ROWS)
            self.mushrooms[y][x] = MUSHROOM_HITS
        self._spawn_centipede()
        self._place_player()

    def _spawn_centipede(self) -> None:
        length = min(COLS - 2, self.length + self.wave // 2)
        # One chain. The head decides where to go and the body follows it, so
        # it stays a centipede rather than becoming a swarm of independent
        # bugs that happen to have started together.
        self.chains = [[Segment(x=-index, y=0, direction=1, head=index == 0) for index in range(length)]]
        self.move_timer = 0.0

    @property
    def segments(self) -> list[Segment]:
        """Every segment on the board, whichever chain it belongs to."""
        return [segment for chain in self.chains for segment in chain]

    def _place_player(self) -> None:
        self.player_x = COLS // 2
        self.player_y = ROWS - 1
        self.shot: tuple[int, int] | None = None
        self.shot_timer = 0.0
        self.dying_for = 0.0

    # --- geometry --------------------------------------------------------

    def speed(self) -> float:
        return min(24.0, self.base_speed + (self.wave - 1) * 1.5)

    def _blocked(self, x: int, y: int) -> bool:
        return not (0 <= x < COLS) or (0 <= y < ROWS and self.mushrooms[y][x] > 0)

    # --- input -----------------------------------------------------------

    def handle(self, action: str) -> None:
        if self.finished() or self.dying_for > 0:
            return
        if action == "left":
            self.player_x = max(0, self.player_x - 1)
        elif action == "right":
            self.player_x = min(COLS - 1, self.player_x + 1)
        elif action == "up":
            self.player_y = max(ROWS - PLAYER_ROWS, self.player_y - 1)
        elif action == "down":
            self.player_y = min(ROWS - 1, self.player_y + 1)
        elif action == "fire" and self.shot is None:
            self.shot = (self.player_x, self.player_y - 1)
            self.audio.play("shoot")

    # --- stepping --------------------------------------------------------

    def advance(self, elapsed: float) -> None:
        if self.finished():
            return
        if self.dying_for > 0:
            self.dying_for = max(0.0, self.dying_for - elapsed)
            if self.dying_for == 0:
                self._after_death()
            return

        self._advance_shot(elapsed)
        self._advance_centipede(elapsed)
        self._check_reached_player()

    def _advance_shot(self, elapsed: float) -> None:
        if self.shot is None:
            return
        self.shot_timer += elapsed
        step = 1.0 / 40.0
        while self.shot is not None and self.shot_timer >= step:
            self.shot_timer -= step
            x, y = self.shot
            y -= 1
            if y < 0:
                self.shot = None
                return
            if self._hit_segment(x, y):
                return
            if self.mushrooms[y][x] > 0:
                self.mushrooms[y][x] -= 1
                self.shot = None
                self.score += 1
                self.audio.play("mushroom", 0.6)
                return
            self.shot = (x, y)

    def _hit_segment(self, x: int, y: int) -> bool:
        for chain_index, chain in enumerate(self.chains):
            for index, segment in enumerate(chain):
                if segment.x != x or segment.y != y:
                    continue
                self.shot = None
                # A shot segment becomes a mushroom, so clearing the
                # centipede is also what makes the field harder to shoot
                # through next time.
                if 0 <= y < ROWS:
                    self.mushrooms[y][x] = MUSHROOM_HITS
                self.score += 100 if segment.head else 10
                self.audio.play("hit")
                self._split(chain_index, index)
                if not self.segments:
                    self._clear_wave()
                return True
        return False

    def _split(self, chain_index: int, index: int) -> None:
        """Losing a segment breaks its chain in two, each with its own head."""
        chain = self.chains[chain_index]
        front, tail = chain[:index], chain[index + 1 :]
        replacements = []
        for part in (front, tail):
            if not part:
                continue
            part[0].head = True
            # The tail was following; now it leads, and it turns down like a
            # head that has just been blocked rather than carrying straight on.
            replacements.append(part)
        self.chains[chain_index : chain_index + 1] = replacements

    def _advance_centipede(self, elapsed: float) -> None:
        self.move_timer += elapsed
        interval = 1.0 / self.speed()
        while self.move_timer >= interval and self.segments and not self.finished():
            self.move_timer -= interval
            self._step_centipede()

    def _step_centipede(self) -> None:
        for chain in self.chains:
            if not chain:
                continue
            head = chain[0]
            was = (head.x, head.y, head.direction)
            self._step_head(head)
            # Each segment takes the place of the one ahead of it, which is
            # what makes the body trace the head's path down the field.
            previous = was
            for segment in chain[1:]:
                current = (segment.x, segment.y, segment.direction)
                segment.x, segment.y, segment.direction = previous
                previous = current

    def _step_head(self, head: Segment) -> None:
        if head.descending > 0:
            head.descending -= 1
            head.y += 1
            if head.y >= ROWS:
                # Off the bottom: it comes back around at the top.
                head.y = 0
            return
        if head.x < 0:
            # Still entering from off-screen.
            head.x += 1
            return

        ahead = head.x + head.direction
        if self._blocked(ahead, head.y):
            head.direction *= -1
            head.descending = 1
        else:
            head.x = ahead

    def _check_reached_player(self) -> None:
        for segment in self.segments:
            if segment.x == self.player_x and segment.y == self.player_y:
                self._die()
                return

    def _die(self) -> None:
        self.lives -= 1
        self.dying_for = 1.0
        self.audio.play("player_hit")

    def _after_death(self) -> None:
        if self.lives <= 0:
            self.game_over = True
            self.audio.play("game_over")
            return
        self._spawn_centipede()
        self._place_player()

    def _clear_wave(self) -> None:
        self.wave += 1
        self.score += 200
        self.audio.play("wave")
        if self.wave > 8:
            self.won = True
            self.audio.play("win")
            return
        self._spawn_centipede()
        self._place_player()

    # --- reporting -------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Best": max(self.store.best, self.score),
            "Lives": max(0, self.lives),
            "Wave": self.wave,
            "Left": len(self.segments),
        }

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame(BACKGROUND)
        origin_x, origin_y = ORIGIN

        draw_pixel_text(draw, 1, 1, f"{self.score:05d}", TEXT, 1)
        draw_pixel_text(draw, 34, 1, f"L{max(0, self.lives)}", DIM, 1)
        draw_pixel_text(draw, PANEL - 20, 1, f"W{self.wave}", DIM, 1)

        def cell(x: int, y: int) -> tuple[int, int]:
            return origin_x + x * CELL, origin_y + y * CELL

        for y in range(ROWS):
            for x in range(COLS):
                hits = self.mushrooms[y][x]
                if not hits:
                    continue
                left, top = cell(x, y)
                # A chewed mushroom shades towards red, so the field reads.
                draw.rectangle(
                    (left, top, left + CELL - 2, top + CELL - 2),
                    fill=MUSHROOM[MUSHROOM_HITS - hits],
                )

        for segment in self.segments:
            if segment.x < 0:
                continue
            left, top = cell(segment.x, segment.y)
            draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), fill=HEAD if segment.head else BODY)

        if self.shot is not None:
            left, top = cell(*self.shot)
            draw.rectangle((left, top + 1, left + CELL - 2, top + CELL - 1), fill=SHOT)

        if self.dying_for == 0 or int(self.dying_for * 8) % 2:
            left, top = cell(self.player_x, self.player_y)
            draw.rectangle((left, top + 1, left + CELL - 1, top + CELL - 1), fill=PLAYER)
            draw.point((left + 1, top), fill=PLAYER)

        if self.won:
            draw_banner(draw, ("CLEARED",), TEXT)
        elif self.game_over:
            draw_banner(draw, ("GAME", "OVER"), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        return fit_panel(image, size)


def demo_snapshot() -> CentipedeGame:
    game = CentipedeGame(seed=6)
    for _ in range(90):
        game.advance(0.05)
    game.score = 1840
    return game
