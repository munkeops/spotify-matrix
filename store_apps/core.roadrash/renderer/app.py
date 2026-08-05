"""A Road Rash style bike racer for the 64x64 matrix.

The road is drawn in pseudo-3D: horizontal bands from the horizon down, each
wider and shifted by the curve ahead, which is what sells the speed at this
size. Rivals are sprites scaled by distance. Ride alongside one and swing at
them; land it and they go down.

Single player against the pack, over a fixed distance.
"""

from __future__ import annotations

import math
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_centered_text, draw_pixel_text, fit_panel, new_frame

HORIZON = 22
ROAD_BOTTOM = PANEL - 1
PLAYER_Y = PANEL - 10

#: Half-width of the road at the very bottom of the screen, in pixels.
ROAD_HALF_WIDTH = 23
#: How far ahead a rival can be and still be drawn, in metres.
DRAW_DISTANCE = 90.0

SKY = (12, 14, 34)
GROUND = (26, 44, 30)
ROAD = (52, 54, 62)
ROAD_ALT = (58, 60, 70)
EDGE = (226, 226, 236)
EDGE_ALT = (206, 72, 72)
PLAYER_COLOR = (110, 220, 255)
RIVAL_COLOR = (250, 200, 70)
DOWNED_COLOR = (120, 110, 110)
TEXT = (214, 222, 240)
DIM = (126, 136, 162)


class Rival:
    def __init__(self, distance: float, offset: float, speed: float) -> None:
        self.distance = distance      # metres ahead of the player
        self.offset = offset          # -1 left verge, +1 right verge
        self.speed = speed
        self.down_for = 0.0

    @property
    def down(self) -> bool:
        return self.down_for > 0


class RoadRashGame(GameApp):
    game_id = "roadrash"
    id = "core.roadrash"
    name = "Road Rash"
    summary = "Race the pack, and throw an elbow when you draw level."
    layout = "horizontal"
    actions = ("left", "right", "up", "down", "fire")
    config_fields = [
        ConfigField.number("distance", label="Race length", default=1500, minimum=400, maximum=5000, step=100, help_text="Metres to the finish."),
        ConfigField.number("rivals", label="Rivals", default=5, minimum=1, maximum=9, step=1),
        ConfigField.number("topSpeed", label="Top speed", default=60, minimum=30, maximum=110, step=5),
        ConfigField.boolean("combat", label="Allow attacks", default=True, help_text="Draw level with a rival and hit fire."),
    ]

    def reset(self) -> None:
        self.race_length = max(200.0, float(self.config.get("distance", 1500)))
        self.top_speed = max(20.0, float(self.config.get("topSpeed", 60)))
        self.combat = bool(self.config.get("combat", True))
        rivals = max(1, int(self.config.get("rivals", 5)))

        self.position = 0.0          # metres travelled
        self.speed_now = 0.0
        self.offset = 0.0            # -1..1 across the road
        self.curve = 0.0             # current bend
        self.next_curve_at = 120.0
        self.target_curve = 0.0
        self.score = 0
        self.crashes = 0
        self.knockdowns = 0
        self.crash_for = 0.0
        self.swing_for = 0.0
        self.finished_at = 0.0

        self.rivals = [
            Rival(
                distance=30.0 + index * 26.0,
                offset=self.random.uniform(-0.6, 0.6),
                speed=self.top_speed * self.random.uniform(0.62, 0.84),
            )
            for index in range(rivals)
        ]

    # --- shape of the road -------------------------------------------------

    def road_centre(self, distance: float) -> float:
        """How far the road's centre has slid sideways at this distance."""
        return self.curve * (distance * distance) * 0.0016

    def _perspective(self, distance: float) -> tuple[int, float]:
        """Screen row and scale for something ``distance`` metres ahead."""
        depth = max(0.0001, distance / DRAW_DISTANCE)
        row = int(HORIZON + (ROAD_BOTTOM - HORIZON) * (1.0 - depth))
        scale = 1.0 - depth
        return row, max(0.02, scale)

    def road_half_width(self, row: int) -> float:
        if row <= HORIZON:
            return 1.0
        blend = (row - HORIZON) / max(1, ROAD_BOTTOM - HORIZON)
        return 2.0 + (ROAD_HALF_WIDTH - 2.0) * blend

    def _centre_at_row(self, row: int) -> float:
        blend = (row - HORIZON) / max(1, ROAD_BOTTOM - HORIZON)
        # Straight ahead at the horizon, fully bent by the bottom.
        return PANEL / 2 - self.curve * 13.0 * (1.0 - blend) ** 2

    # --- input and stepping ------------------------------------------------

    def handle(self, action: str) -> None:
        if self.crash_for > 0:
            return
        if action == "left":
            self.offset = max(-1.4, self.offset - 0.16)
        elif action == "right":
            self.offset = min(1.4, self.offset + 0.16)
        elif action == "up":
            self.speed_now = min(self.top_speed, self.speed_now + self.top_speed * 0.18)
        elif action == "down":
            self.speed_now = max(0.0, self.speed_now - self.top_speed * 0.22)
        elif action == "fire" and self.combat:
            self._swing()

    def _swing(self) -> None:
        self.swing_for = 0.22
        self.audio.play("swing")
        for rival in self.rivals:
            # Level with you, and close enough across the road to reach.
            if rival.down or abs(rival.distance) > 6.0:
                continue
            if abs(rival.offset - self.offset) <= 0.42:
                rival.down_for = 2.5
                rival.speed *= 0.45
                self.knockdowns += 1
                self.score += 250
                self.audio.play("knockdown")
                return

    def advance(self, elapsed: float) -> None:
        if self.finished_at > 0:
            return

        self.swing_for = max(0.0, self.swing_for - elapsed)
        if self.crash_for > 0:
            self.crash_for = max(0.0, self.crash_for - elapsed)
            self.speed_now *= 0.9
        else:
            # Coasting bleeds speed, so you have to keep on the throttle.
            self.speed_now = max(0.0, self.speed_now - self.top_speed * 0.08 * elapsed)

        self._advance_curve(elapsed)
        self.position += self.speed_now * elapsed
        # A bend pushes you towards the outside of the corner.
        self.offset += self.curve * elapsed * (self.speed_now / max(1.0, self.top_speed)) * 1.6

        self._advance_rivals(elapsed)
        self._check_verge(elapsed)
        self._check_contact()

        self.score = int(self.position) + self.knockdowns * 250 - self.crashes * 100
        if self.position >= self.race_length:
            self._finish()

    def _advance_curve(self, elapsed: float) -> None:
        self.next_curve_at -= self.speed_now * elapsed
        if self.next_curve_at <= 0:
            self.target_curve = self.random.choice((-1.0, -0.5, 0.0, 0.5, 1.0))
            self.next_curve_at = self.random.uniform(80.0, 200.0)
        # Ease towards the new bend so corners arrive rather than snap.
        self.curve += (self.target_curve - self.curve) * min(1.0, elapsed * 0.9)

    def _advance_rivals(self, elapsed: float) -> None:
        for rival in self.rivals:
            if rival.down:
                rival.down_for = max(0.0, rival.down_for - elapsed)
                if not rival.down:
                    rival.speed = self.top_speed * self.random.uniform(0.6, 0.8)
            # Distance closes at the difference in speed.
            rival.distance += (rival.speed - self.speed_now) * elapsed
            rival.offset += math.sin((self.position + rival.distance) * 0.02) * elapsed * 0.25
            rival.offset = max(-0.9, min(0.9, rival.offset))
            if rival.distance < -40.0:
                # Dropped well behind: bring them back up the road.
                rival.distance = self.random.uniform(60.0, 100.0)

    def _check_verge(self, elapsed: float) -> None:
        if abs(self.offset) <= 1.0 or self.crash_for > 0:
            return
        # Off the tarmac: scrub speed hard.
        self.speed_now *= max(0.0, 1.0 - 2.2 * elapsed)
        if abs(self.offset) > 1.3:
            self._crash()

    def _check_contact(self) -> None:
        if self.crash_for > 0:
            return
        for rival in self.rivals:
            if rival.down or abs(rival.distance) > 3.0:
                continue
            if abs(rival.offset - self.offset) < 0.24:
                self._crash()
                return

    def _crash(self) -> None:
        self.crash_for = 1.1
        self.crashes += 1
        self.speed_now *= 0.25
        self.offset = max(-1.0, min(1.0, self.offset))
        self.audio.play("crash")

    def _finish(self) -> None:
        self.finished_at = self.position
        ahead = sum(1 for rival in self.rivals if rival.distance > 0)
        self.place = ahead + 1
        self.won = self.place == 1
        self.game_over = not self.won
        self.audio.play("win" if self.won else "game_over")

    # --- reporting ---------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        return {
            "Score": max(0, self.score),
            "Best": max(self.store.best, max(0, self.score)),
            "Speed": f"{int(self.speed_now)}",
            "To go": f"{max(0, int(self.race_length - self.position))}m",
            "Downed": self.knockdowns,
        }

    # --- drawing -----------------------------------------------------------

    def _draw_road(self, draw) -> None:
        draw.rectangle((0, 0, PANEL - 1, HORIZON - 1), fill=SKY)
        draw.rectangle((0, HORIZON, PANEL - 1, ROAD_BOTTOM), fill=GROUND)

        for row in range(HORIZON, ROAD_BOTTOM + 1):
            half = self.road_half_width(row)
            centre = self._centre_at_row(row)
            left = int(round(centre - half))
            right = int(round(centre + half))
            # Alternating bands scroll towards you, which is the speed cue.
            depth = (row - HORIZON) / max(1, ROAD_BOTTOM - HORIZON)
            phase = (self.position * 0.35 + (1.0 - depth) * 26.0)
            band = int(phase) % 2
            draw.line((left, row, right, row), fill=ROAD_ALT if band else ROAD)
            edge = EDGE_ALT if band else EDGE
            draw.point((left, row), fill=edge)
            draw.point((right, row), fill=edge)

    def _draw_rival(self, draw, rival: Rival) -> None:
        if rival.distance < -2.0 or rival.distance > DRAW_DISTANCE:
            return
        row, scale = self._perspective(max(0.5, rival.distance))
        if row < HORIZON or row > ROAD_BOTTOM:
            return
        half = self.road_half_width(row)
        centre = self._centre_at_row(row) + rival.offset * half
        width = max(1, int(6 * scale))
        height = max(1, int(7 * scale))
        left = int(centre - width / 2)
        top = row - height
        colour = DOWNED_COLOR if rival.down else RIVAL_COLOR
        if rival.down:
            # Sliding down the road, so draw them flat.
            draw.rectangle((left - 1, row - 2, left + width, row), fill=colour)
            return
        draw.rectangle((left, top, left + width - 1, row), fill=colour)
        if height > 3:
            draw.rectangle((left, top, left + width - 1, top + 1), fill=(20, 20, 28))

    def _draw_player(self, draw) -> None:
        half = self.road_half_width(PLAYER_Y + 6)
        centre = PANEL / 2 + self.offset * half * 0.82
        x = int(centre)
        shake = 1 if self.crash_for > 0 and int(self.crash_for * 20) % 2 else 0
        colour = DOWNED_COLOR if self.crash_for > 0 else PLAYER_COLOR

        draw.rectangle((x - 3 + shake, PLAYER_Y, x + 3 + shake, PLAYER_Y + 7), fill=colour)
        draw.rectangle((x - 4 + shake, PLAYER_Y + 5, x + 4 + shake, PLAYER_Y + 6), fill=(20, 20, 28))
        draw.rectangle((x - 2 + shake, PLAYER_Y - 2, x + 2 + shake, PLAYER_Y), fill=(30, 34, 48))
        if self.swing_for > 0:
            # An arm out to whichever side is nearer the middle of the road.
            reach = 6 if self.offset <= 0 else -6
            draw.line((x, PLAYER_Y + 2, x + reach, PLAYER_Y + 1), fill=(250, 240, 200))

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        self._draw_road(draw)

        for rival in sorted(self.rivals, key=lambda item: -item.distance):
            self._draw_rival(draw, rival)
        self._draw_player(draw)

        draw_pixel_text(draw, 1, 1, f"{int(self.speed_now):3d}", TEXT, 1)
        remaining = max(0, int(self.race_length - self.position))
        label = f"{remaining}M"
        draw_pixel_text(draw, PANEL - 4 * len(label) - 1, 1, label, DIM, 1)
        if self.knockdowns:
            draw_pixel_text(draw, 1, 8, f"X{self.knockdowns}", RIVAL_COLOR, 1)

        if self.won:
            draw_banner(draw, ("FIRST", "PLACE"), TEXT)
        elif self.game_over:
            draw_banner(draw, ("FINISHED", f"P{getattr(self, 'place', 0)}"), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        elif self.crash_for > 0:
            draw_centered_text(draw, PANEL // 2, "CRASH", TEXT, 1)
        return fit_panel(image, size)


def demo_snapshot() -> RoadRashGame:
    game = RoadRashGame(seed=9)
    game.speed_now = 48.0
    game.position = 240.0
    game.curve = 0.6
    game.offset = -0.25
    game.knockdowns = 2
    for index, rival in enumerate(game.rivals):
        rival.distance = 8.0 + index * 15.0
        rival.offset = (-0.5, 0.4, -0.2, 0.6, 0.0)[index % 5]
    game.rivals[0].down_for = 1.0
    return game
