"""A Donkey Kong style climb for the 64x64 matrix.

Five sloped girders, ladders between them, and barrels rolling down from the
ape at the top. Jump them for points, grab the hammer to smash them, and get
to the top before your three lives run out.

The girders slope, so a barrel's direction comes from the girder it is on
rather than from anything stored on the barrel. That is what makes the whole
board work off one `surface()` function.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameWidget
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

LEFT, RIGHT = 2, 60
#: Surface height of each girder at its high end, bottom girder first.
GIRDER_Y = (60, 49, 38, 27, 16)
TOP = len(GIRDER_Y) - 1
#: How far a girder drops across the screen. Enough to roll, not to trip on.
SLOPE = 4

#: (girder below, x) for each ladder. A ladder joins that girder to the next.
LADDERS = ((0, 14), (0, 45), (1, 23), (1, 52), (2, 11), (2, 41), (3, 20), (3, 50))

PLAYER_W, PLAYER_H = 4, 6
BARREL = 3
CLIMB_RANGE = 2

GIRDER_COLOR = (232, 96, 92)
GIRDER_DARK = (150, 52, 50)
LADDER_COLOR = (110, 190, 240)
BARREL_COLOR = (206, 150, 66)
BARREL_DARK = (128, 88, 34)
KONG_COLOR = (176, 104, 60)
KONG_DARK = (96, 56, 32)
PAULINE = (240, 120, 180)
SHIRT = (232, 64, 60)
OVERALLS = (80, 120, 230)
HAMMER = (250, 216, 90)
TEXT = (222, 228, 244)
DIM = (128, 138, 164)

PLAYER_SPRITE = (
    ".##.",
    "####",
    ".##.",
    "####",
    ".##.",
    "#..#",
)


def surface(index: int, x: float) -> int:
    """Height of girder ``index`` at ``x``. Everything stands on this."""
    base = GIRDER_Y[index]
    if index == TOP:
        return base
    across = min(1.0, max(0.0, (x - LEFT) / (RIGHT - LEFT)))
    # Odd girders fall to the left, even ones to the right, so the climb
    # zigzags the way the arcade one does.
    return base - SLOPE + int(SLOPE * (across if index % 2 == 0 else 1.0 - across))


def roll_direction(index: int) -> int:
    return 1 if index % 2 == 0 else -1


class Barrel:
    __slots__ = ("x", "y", "girder", "falling", "fall_to", "wobble")

    def __init__(self, x: float, girder: int) -> None:
        self.x = x
        self.girder = girder
        self.y = float(surface(girder, x) - BARREL)
        self.falling = False
        self.fall_to = girder
        self.wobble = 0.0


class KongGame(GameWidget):
    game_id = "kong"
    id = "core.kong"
    name = "Kong"
    summary = "Climb the girders, jump the barrels, reach the top."
    layout = "dpad"
    actions = ("left", "right", "up", "down", "fire")
    config_fields = [
        ConfigField.number("lives", label="Lives", default=3, minimum=1, maximum=5, step=1),
        ConfigField.number("barrelRate", label="Barrel rate", default=100, minimum=40, maximum=200, step=10, help_text="Percent of the normal throw rate."),
        ConfigField.boolean("hammer", label="Hammer", default=True, help_text="A hammer appears on each stage."),
    ]

    def reset(self) -> None:
        self.max_lives = max(1, int(self.config.get("lives", 3)))
        self.barrel_rate = max(0.4, float(self.config.get("barrelRate", 100)) / 100.0)
        self.hammer_enabled = bool(self.config.get("hammer", True))

        self.lives = self.max_lives
        self.stage = 1
        self.score = 0
        self._start_stage()

    def _start_stage(self) -> None:
        self.barrels: list[Barrel] = []
        self.throw_timer = 1.2
        self.bonus = 5000
        self.hammer_for = 0.0
        self.hammer_at: tuple[int, float] | None = (2, 30.0) if self.hammer_enabled else None
        self.dying_for = 0.0
        self.message = ""
        self._place_player()

    def _place_player(self) -> None:
        self.girder = 0
        self.x = 6.0
        self.y = float(surface(0, 6.0) - PLAYER_H)
        self.climbing: tuple[int, int] | None = None
        self.facing = 1
        self.vy = 0.0
        self.jumping = False
        self.jumped: set[int] = set()

    # --- geometry --------------------------------------------------------

    def _ladder_at(self, girder: int, x: float, going_up: bool):
        """The ladder you could take from here, if any."""
        for below, ladder_x in LADDERS:
            if abs(ladder_x - x) > CLIMB_RANGE:
                continue
            if going_up and below == girder and girder < TOP:
                return (below, ladder_x)
            if not going_up and below == girder - 1:
                return (below, ladder_x)
        return None

    def _feet(self) -> float:
        return self.y + PLAYER_H

    def _rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + PLAYER_W - 1, self.y + PLAYER_H - 1)

    # --- input -----------------------------------------------------------

    def handle(self, action: str) -> None:
        if self.finished() or self.dying_for > 0:
            return

        if self.climbing is not None:
            self._climb_input(action)
            return

        if action == "left":
            self._walk(-1)
        elif action == "right":
            self._walk(1)
        elif action in ("up", "down"):
            ladder = self._ladder_at(self.girder, self.x + PLAYER_W / 2, action == "up")
            if ladder is not None and not self.jumping:
                self.climbing = ladder
                self.x = ladder[1] - PLAYER_W / 2
                self.audio.play("climb", 0.5)
        elif action == "fire" and not self.jumping:
            self.jumping = True
            self.vy = -1.5
            self.jumped = set()
            self.audio.play("jump")

    def _walk(self, direction: int) -> None:
        self.facing = direction
        self.x = max(LEFT, min(RIGHT - PLAYER_W, self.x + direction * 2.0))
        if not self.jumping:
            self.y = float(surface(self.girder, self.x + PLAYER_W / 2) - PLAYER_H)

    def _climb_input(self, action: str) -> None:
        below, ladder_x = self.climbing
        top_y = surface(below + 1, ladder_x) - PLAYER_H
        bottom_y = surface(below, ladder_x) - PLAYER_H
        if action == "up":
            self.y -= 2.0
            self.audio.play("climb", 0.35)
        elif action == "down":
            self.y += 2.0
            self.audio.play("climb", 0.35)
        else:
            return

        if self.y <= top_y:
            self.y = float(top_y)
            self.girder = below + 1
            self.climbing = None
            self._reached_girder()
        elif self.y >= bottom_y:
            self.y = float(bottom_y)
            self.girder = below
            self.climbing = None

    def _reached_girder(self) -> None:
        self.score += 20
        if self.girder == TOP:
            self._win_stage()

    # --- stepping --------------------------------------------------------

    def advance(self, elapsed: float) -> None:
        if self.finished():
            return
        if self.dying_for > 0:
            self.dying_for = max(0.0, self.dying_for - elapsed)
            if self.dying_for == 0:
                self._after_death()
            return

        self.bonus = max(0, self.bonus - int(elapsed * 100))
        self.hammer_for = max(0.0, self.hammer_for - elapsed)
        self._advance_jump(elapsed)
        self._throw_barrels(elapsed)
        self._advance_barrels(elapsed)
        self._pick_up_hammer()
        self._check_hit()

        if self.girder == TOP and self.x + PLAYER_W >= 44:
            self._win_stage()

    def _advance_jump(self, elapsed: float) -> None:
        if not self.jumping:
            return
        self.vy += 9.0 * elapsed
        self.y += self.vy
        ground = float(surface(self.girder, self.x + PLAYER_W / 2) - PLAYER_H)
        if self.y >= ground:
            self.y = ground
            self.jumping = False
            self.vy = 0.0

    def _throw_barrels(self, elapsed: float) -> None:
        self.throw_timer -= elapsed * self.barrel_rate * (1.0 + (self.stage - 1) * 0.15)
        if self.throw_timer > 0:
            return
        self.throw_timer = self.random.uniform(1.6, 2.8)
        self.barrels.append(Barrel(float(LEFT + 8), TOP))
        self.audio.play("barrel", 0.6)

    def _advance_barrels(self, elapsed: float) -> None:
        speed = 22.0 + (self.stage - 1) * 3.0
        for barrel in list(self.barrels):
            barrel.wobble += elapsed * 8
            if barrel.falling:
                barrel.y += 40.0 * elapsed
                if barrel.y >= surface(barrel.fall_to, barrel.x) - BARREL:
                    barrel.girder = barrel.fall_to
                    barrel.y = float(surface(barrel.girder, barrel.x) - BARREL)
                    barrel.falling = False
                continue

            direction = roll_direction(barrel.girder)
            before = barrel.x
            barrel.x += direction * speed * elapsed
            barrel.y = float(surface(barrel.girder, barrel.x) - BARREL)

            if barrel.girder > 0 and self._crosses_ladder(before, barrel.x):
                # Most barrels carry on; the ones that drop are what make the
                # lower girders dangerous.
                if self.random.random() < 0.35:
                    barrel.falling = True
                    barrel.fall_to = barrel.girder - 1
                    continue

            if barrel.x < LEFT or barrel.x > RIGHT - BARREL:
                if barrel.girder == 0:
                    self.barrels.remove(barrel)
                else:
                    barrel.x = float(max(LEFT, min(RIGHT - BARREL, barrel.x)))
                    barrel.falling = True
                    barrel.fall_to = barrel.girder - 1

    def _crosses_ladder(self, before: float, after: float) -> bool:
        low, high = (before, after) if before <= after else (after, before)
        return any(low <= ladder_x <= high for below, ladder_x in LADDERS if below == self.girder or True)

    def _pick_up_hammer(self) -> None:
        if self.hammer_at is None:
            return
        girder, hammer_x = self.hammer_at
        if self.girder != girder or self.climbing is not None:
            return
        if abs(hammer_x - (self.x + PLAYER_W / 2)) <= 4:
            self.hammer_at = None
            self.hammer_for = 6.0
            self.score += 100
            self.audio.play("hammer")

    def _check_hit(self) -> None:
        left, top, right, bottom = self._rect()
        for barrel in list(self.barrels):
            b_left, b_top = barrel.x, barrel.y
            b_right, b_bottom = barrel.x + BARREL - 1, barrel.y + BARREL - 1
            overlap = left <= b_right and b_left <= right and top <= b_bottom and b_top <= bottom
            if overlap:
                if self.hammer_for > 0:
                    self.barrels.remove(barrel)
                    self.score += 300
                    self.audio.play("smash")
                    continue
                self._die()
                return
            # Cleared it in the air: score it once, as it passes underneath.
            if self.jumping and id(barrel) not in self.jumped:
                if left <= b_right and b_left <= right and bottom < b_top:
                    self.jumped.add(id(barrel))
                    self.score += 100
                    self.audio.play("point", 0.7)

    def _die(self) -> None:
        self.lives -= 1
        self.dying_for = 1.0
        self.message = "OUCH"
        self.audio.play("hit")

    def _after_death(self) -> None:
        self.message = ""
        if self.lives <= 0:
            self.game_over = True
            self.audio.play("game_over")
            return
        self.barrels = []
        self._place_player()

    def _win_stage(self) -> None:
        self.score += 500 + self.bonus // 10
        self.stage += 1
        self.audio.play("level")
        if self.stage > 4:
            self.won = True
            self.message = "RESCUED"
            self.audio.play("win")
            return
        self._start_stage()

    # --- reporting -------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Best": max(self.store.best, self.score),
            "Lives": max(0, self.lives),
            "Stage": self.stage,
            "Bonus": self.bonus,
        }

    def extra(self) -> dict[str, Any]:
        return {"hammer": round(self.hammer_for, 1), "barrels": len(self.barrels)}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()

        draw_pixel_text(draw, 1, 1, f"{self.score:05d}", TEXT, 1)
        draw_pixel_text(draw, 32, 1, f"L{self.lives}", HAMMER if self.hammer_for else DIM, 1)
        draw_pixel_text(draw, PANEL - 20, 1, f"S{self.stage}", DIM, 1)

        for index in range(len(GIRDER_Y)):
            for x in range(LEFT, RIGHT + 1):
                y = surface(index, x)
                draw.point((x, y), fill=GIRDER_COLOR)
                draw.point((x, y + 1), fill=GIRDER_DARK if x % 3 else GIRDER_COLOR)

        for below, ladder_x in LADDERS:
            top_y = surface(below + 1, ladder_x)
            bottom_y = surface(below, ladder_x)
            for side in (ladder_x - 1, ladder_x + 1):
                draw.line((side, top_y, side, bottom_y), fill=LADDER_COLOR)
            for rung in range(top_y + 2, bottom_y, 3):
                draw.point((ladder_x, rung), fill=LADDER_COLOR)

        self._draw_kong(draw)
        self._draw_pauline(draw)

        if self.hammer_at is not None:
            girder, hammer_x = self.hammer_at
            top_y = surface(girder, hammer_x) - 5
            draw.rectangle((int(hammer_x) - 1, top_y, int(hammer_x) + 1, top_y + 1), fill=HAMMER)
            draw.line((int(hammer_x), top_y + 2, int(hammer_x), top_y + 4), fill=(190, 140, 70))

        for barrel in self.barrels:
            left, top = int(barrel.x), int(barrel.y)
            draw.rectangle((left, top, left + BARREL - 1, top + BARREL - 1), fill=BARREL_COLOR)
            # The stripe turns as it rolls, which is the whole read at 3 pixels.
            stripe = int(barrel.wobble) % 2
            draw.point((left + 1, top + stripe), fill=BARREL_DARK)

        self._draw_player(draw)

        if self.won:
            draw_banner(draw, ("RESCUED",), TEXT)
        elif self.game_over:
            draw_banner(draw, ("GAME", "OVER"), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        elif self.message:
            draw_banner(draw, (self.message,), TEXT)
        return fit_panel(image, size)

    def _draw_player(self, draw) -> None:
        if self.dying_for > 0 and int(self.dying_for * 8) % 2:
            return
        left, top = int(self.x), int(self.y)
        for offset_y, row in enumerate(PLAYER_SPRITE):
            colour = SHIRT if offset_y < 3 else OVERALLS
            for offset_x, cell in enumerate(row):
                if cell == "#":
                    draw.point((left + offset_x, top + offset_y), fill=colour)
        if self.hammer_for > 0:
            # Held high or swung down, on a beat you can time a barrel to.
            swing = int(self.hammer_for * 6) % 2
            hammer_x = left + (PLAYER_W if self.facing > 0 else -2)
            hammer_y = top + (0 if swing else 3)
            draw.rectangle((hammer_x, hammer_y, hammer_x + 1, hammer_y + 1), fill=HAMMER)

    def _draw_kong(self, draw) -> None:
        top = GIRDER_Y[TOP] - 9
        draw.rectangle((LEFT + 4, top, LEFT + 12, top + 8), fill=KONG_COLOR)
        draw.rectangle((LEFT + 6, top + 2, LEFT + 10, top + 5), fill=KONG_DARK)
        for eye in (LEFT + 6, LEFT + 10):
            draw.point((eye, top + 1), fill=(20, 20, 24))

    def _draw_pauline(self, draw) -> None:
        top = GIRDER_Y[TOP] - 6
        draw.rectangle((48, top, 50, top + 5), fill=PAULINE)
        draw.point((49, top - 1), fill=(250, 220, 160))


def demo_snapshot() -> KongGame:
    game = KongGame(seed=4)
    game.score = 3400
    game.stage = 2
    game.girder = 2
    game.x = 26.0
    game.y = float(surface(2, 28.0) - PLAYER_H)
    game.jumping = True
    game.hammer_at = None
    game.hammer_for = 3.0
    game.barrels = [Barrel(34.0, 2), Barrel(18.0, 3), Barrel(50.0, 4), Barrel(9.0, 1)]
    return game
