"""Tron light cycles for the 64x64 matrix.

Two cycles leave solid trails and turn at right angles. Touch anything and you
derezz. The computer looks one step ahead and prefers open space, which is
enough to make it close you down rather than politely crash.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

CELL = 2
COLS = 32
ROWS = 28
ORIGIN = (0, 8)

EMPTY, PLAYER, RIVAL = 0, 1, 2

PLAYER_TRAIL = (96, 210, 255)
PLAYER_HEAD = (200, 245, 255)
RIVAL_TRAIL = (255, 140, 60)
RIVAL_HEAD = (255, 210, 150)
WALL = (40, 48, 72)
TEXT = (200, 212, 232)

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
TURNS = ((0, -1), (1, 0), (0, 1), (-1, 0))


class TronGame(GameApp):
    game_id = "tron"
    id = "core.tron"
    name = "Tron"
    summary = "Light cycles. Cut them off before they cut you off."
    layout = "dpad"
    actions = ("up", "down", "left", "right")
    #: Two cycles, so the second one can be a person instead of the machine.
    players = (1, 2)
    config_fields = [
        ConfigField.number("speed", label="Speed", default=12, minimum=5, maximum=25, step=1, help_text="Cells per second. Rises each round."),
        ConfigField.select(
            "difficulty",
            [("Careless", "easy"), ("Looks ahead", "normal"), ("Hunts you", "hard")],
            label="Rival",
            default="normal",
        ),
        ConfigField.number("rounds", label="Rounds to win", default=3, minimum=1, maximum=9, step=1),
    ]

    def reset(self) -> None:
        self.base_speed = max(4.0, float(self.config.get("speed", 12)))
        self.difficulty = str(self.config.get("difficulty", "normal"))
        self.target = max(1, int(self.config.get("rounds", 3)))
        self.player_wins = getattr(self, "player_wins", 0)
        self.rival_wins = getattr(self, "rival_wins", 0)
        self.round_number = getattr(self, "round_number", 1)
        # Set the moment a second player steers, and kept between rounds so
        # the machine does not take the wheel back mid-match.
        self.rival_human = getattr(self, "rival_human", False)
        self.score = getattr(self, "score", 0)
        self._start_round()

    def _start_round(self) -> None:
        self.grid = [[EMPTY] * COLS for _ in range(ROWS)]
        # Diagonally opposite and running perpendicular: facing each other on
        # one row makes every round a head-on before either has turned.
        self.player = (COLS // 4, ROWS // 4)
        self.rival = (COLS - COLS // 4, ROWS - ROWS // 4)
        self.player_dir = (0, 1)
        self.rival_dir = (0, -1)
        self.pending: tuple[int, int] | None = None
        self.rival_pending: tuple[int, int] | None = None
        self.grid[self.player[1]][self.player[0]] = PLAYER
        self.grid[self.rival[1]][self.rival[0]] = RIVAL
        self.move_timer = 0.0
        self.message = ""
        self.round_over = False

    # --- rules -----------------------------------------------------------

    def speed(self) -> float:
        return min(30.0, self.base_speed + (self.round_number - 1) * 1.5)

    def _free(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < COLS and 0 <= y < ROWS and self.grid[y][x] == EMPTY

    def _open_space(self, cell: tuple[int, int], depth: int = 12) -> int:
        """Roughly how much room a cell leads to, used to avoid dead ends."""
        seen = {cell}
        frontier = [cell]
        while frontier and len(seen) < depth:
            x, y = frontier.pop()
            for step_x, step_y in TURNS:
                nxt = (x + step_x, y + step_y)
                if nxt not in seen and self._free(nxt):
                    seen.add(nxt)
                    frontier.append(nxt)
        return len(seen)

    def _rival_direction(self) -> tuple[int, int]:
        if self.rival_human:
            # A person is driving; the computer keeps its hands off.
            step, self.rival_pending = self.rival_pending, None
            return step or self.rival_dir
        x, y = self.rival
        options = [step for step in TURNS if self._free((x + step[0], y + step[1]))]
        if not options:
            return self.rival_dir
        if self.difficulty == "easy":
            # Carry on when it can, turn at random when it cannot.
            return self.rival_dir if self.rival_dir in options else self.random.choice(options)

        def score(step: tuple[int, int]) -> float:
            target = (x + step[0], y + step[1])
            room = self._open_space(target)
            if self.difficulty == "hard":
                # Prefer room, then closing the gap on the player.
                distance = abs(target[0] - self.player[0]) + abs(target[1] - self.player[1])
                return room * 2 - distance
            return float(room)

        best = max(options, key=score)
        # A little inertia looks less twitchy than turning every step.
        if self.rival_dir in options and score(self.rival_dir) >= score(best) - 1:
            return self.rival_dir
        return best

    def handle(self, action: str, player: int = 0) -> None:
        step = DIRECTIONS.get(action)
        if step is None:
            return
        if player == 1:
            self.rival_human = True
            # No reversing into your own trail, for either of them.
            if (step[0], step[1]) == (-self.rival_dir[0], -self.rival_dir[1]):
                return
            self.rival_pending = step
        else:
            if (step[0], step[1]) == (-self.player_dir[0], -self.player_dir[1]):
                return
            self.pending = step
        self.audio.play("turn", 0.4)

    def advance(self, elapsed: float) -> None:
        if self.round_over:
            self.move_timer += elapsed
            if self.move_timer > 1.4:
                self._next_round()
            return

        self.move_timer += elapsed
        interval = 1.0 / self.speed()
        while self.move_timer >= interval and not self.round_over:
            self.move_timer -= interval
            self._step()

    def _step(self) -> None:
        if self.pending is not None:
            self.player_dir = self.pending
            self.pending = None
        self.rival_dir = self._rival_direction()

        player_next = (self.player[0] + self.player_dir[0], self.player[1] + self.player_dir[1])
        rival_next = (self.rival[0] + self.rival_dir[0], self.rival[1] + self.rival_dir[1])

        player_dead = not self._free(player_next)
        rival_dead = not self._free(rival_next)
        # Both reaching the same cell is a head-on, and kills both.
        if player_next == rival_next:
            player_dead = rival_dead = True

        if player_dead or rival_dead:
            self._end_round(player_dead, rival_dead)
            return

        self.player = player_next
        self.rival = rival_next
        self.grid[player_next[1]][player_next[0]] = PLAYER
        self.grid[rival_next[1]][rival_next[0]] = RIVAL
        self.score += 1

    def _end_round(self, player_dead: bool, rival_dead: bool) -> None:
        self.round_over = True
        self.move_timer = 0.0
        if player_dead and rival_dead:
            self.message = "DRAW"
            self.audio.play("crash")
        elif player_dead:
            self.rival_wins += 1
            self.message = "DEREZZED"
            self.audio.play("crash")
        else:
            self.player_wins += 1
            self.score += 100
            self.message = "ROUND WON"
            self.audio.play("win")

    def _next_round(self) -> None:
        if self.player_wins >= self.target:
            self.won = True
            self.message = "YOU WIN"
            return
        if self.rival_wins >= self.target:
            self.game_over = True
            self.message = "DEFEAT"
            return
        self.round_number += 1
        self._start_round()

    # --- reporting -------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        return {
            "Score": self.score,
            "Best": max(self.store.best, self.score),
            "Rounds": f"{self.player_wins}-{self.rival_wins}",
            "To win": self.target,
        }

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        origin_x, origin_y = ORIGIN

        draw_pixel_text(draw, 1, 1, f"{self.player_wins}-{self.rival_wins}", TEXT, 1)
        draw_pixel_text(draw, PANEL - 20, 1, f"R{self.round_number}", TEXT, 1)
        draw.rectangle(
            (origin_x, origin_y - 1, origin_x + COLS * CELL - 1, origin_y + ROWS * CELL),
            outline=WALL,
        )

        for y in range(ROWS):
            row = self.grid[y]
            for x in range(COLS):
                if not row[x]:
                    continue
                left = origin_x + x * CELL
                top = origin_y + y * CELL
                color = PLAYER_TRAIL if row[x] == PLAYER else RIVAL_TRAIL
                draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), fill=color)

        for cell, color in ((self.player, PLAYER_HEAD), (self.rival, RIVAL_HEAD)):
            left = origin_x + cell[0] * CELL
            top = origin_y + cell[1] * CELL
            draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), fill=color)

        if self.won:
            draw_banner(draw, ("YOU", "WIN"), TEXT)
        elif self.game_over:
            draw_banner(draw, ("DEFEAT",), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        elif self.round_over and self.message:
            draw_banner(draw, (self.message,), TEXT)
        return fit_panel(image, size)


def demo_snapshot() -> TronGame:
    game = TronGame(seed=5)
    for _ in range(60):
        game.advance(0.2)
        if game.round_over:
            break
    game.score = 420
    return game
