"""Battleship for the 64x64 matrix.

Two 10x10 grids stacked: your shots on the enemy fleet up top, the enemy's
shots on yours below. Move the crosshair with the stick and fire; the computer
answers by hunting around its own hits the way a person would.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

GRID = 10
CELL = 3
ENEMY_ORIGIN = (2, 8)
PLAYER_ORIGIN = (32, 8)

FLEET = ((5, "CAR"), (4, "BAT"), (3, "CRU"), (3, "SUB"), (2, "DES"))

WATER = (14, 24, 52)
GRID_LINE = (26, 40, 78)
SHIP = (120, 132, 156)
HIT = (240, 92, 78)
SUNK = (150, 40, 40)
MISS = (70, 90, 130)
CURSOR = (250, 220, 60)
TEXT = (206, 216, 236)
LABEL = (120, 134, 162)

EMPTY, MISSED, STRUCK = 0, 1, 2


class Ship:
    def __init__(self, size: int, label: str) -> None:
        self.size = size
        self.label = label
        self.cells: list[tuple[int, int]] = []
        self.hits: set[tuple[int, int]] = set()

    @property
    def sunk(self) -> bool:
        return len(self.hits) >= self.size


class Fleet:
    """One player's board: where the ships are and what has been fired at it."""

    def __init__(self, random) -> None:
        self.ships = [Ship(size, label) for size, label in FLEET]
        self.shots: dict[tuple[int, int], int] = {}
        self._place(random)

    def _place(self, random) -> None:
        taken: set[tuple[int, int]] = set()
        for ship in self.ships:
            for _ in range(400):
                horizontal = random.random() < 0.5
                span_x = ship.size if horizontal else 1
                span_y = 1 if horizontal else ship.size
                x = random.randint(0, GRID - span_x)
                y = random.randint(0, GRID - span_y)
                cells = [(x + (i if horizontal else 0), y + (0 if horizontal else i)) for i in range(ship.size)]
                # Keep a one cell gap so ships never touch, which makes hunting fair.
                halo = {
                    (cx + dx, cy + dy)
                    for cx, cy in cells
                    for dx in (-1, 0, 1)
                    for dy in (-1, 0, 1)
                }
                if halo & taken:
                    continue
                ship.cells = cells
                taken.update(cells)
                break

    def ship_at(self, cell: tuple[int, int]) -> Ship | None:
        for ship in self.ships:
            if cell in ship.cells:
                return ship
        return None

    def fire(self, cell: tuple[int, int]) -> str:
        """Returns "repeat", "miss", "hit" or "sunk"."""
        if cell in self.shots:
            return "repeat"
        ship = self.ship_at(cell)
        if ship is None:
            self.shots[cell] = MISSED
            return "miss"
        self.shots[cell] = STRUCK
        ship.hits.add(cell)
        return "sunk" if ship.sunk else "hit"

    @property
    def defeated(self) -> bool:
        return all(ship.sunk for ship in self.ships)

    def remaining(self) -> int:
        return sum(1 for ship in self.ships if not ship.sunk)


class BattleshipGame(GameApp):
    game_id = "battleship"
    id = "core.battleship"
    name = "Battleship"
    summary = "Hunt the hidden fleet before the computer sinks yours."
    layout = "dpad"
    actions = ("up", "down", "left", "right", "fire")
    config_fields = [
        ConfigField.select(
            "difficulty",
            [("Random shots", "easy"), ("Hunts your ships", "hunt")],
            label="Computer",
            default="hunt",
            help_text="Hunting narrows in after a hit, the way a person plays.",
        ),
        ConfigField.boolean("revealEnemy", label="Show enemy ships", default=False, help_text="Practice mode."),
    ]

    def reset(self) -> None:
        self.difficulty = str(self.config.get("difficulty", "hunt"))
        self.reveal = bool(self.config.get("revealEnemy", False))
        self.enemy = Fleet(self.random)
        self.player = Fleet(self.random)
        self.cursor = [GRID // 2, GRID // 2]
        self.message = "FIRE"
        self.turn = "player"
        self.enemy_timer = 0.0
        # Cells the computer wants to try next, seeded by its own hits.
        self.hunt: list[tuple[int, int]] = []
        self.player_shots = 0
        self.hits = 0

    # --- player -----------------------------------------------------------

    def handle(self, action: str) -> None:
        if self.turn != "player":
            return
        if action == "left":
            self.audio.play("move", 0.5)
            self.cursor[0] = (self.cursor[0] - 1) % GRID
        elif action == "right":
            self.cursor[0] = (self.cursor[0] + 1) % GRID
        elif action == "up":
            self.cursor[1] = (self.cursor[1] - 1) % GRID
        elif action == "down":
            self.cursor[1] = (self.cursor[1] + 1) % GRID
        elif action == "fire":
            self._fire()

    def _fire(self) -> None:
        cell = (self.cursor[0], self.cursor[1])
        result = self.enemy.fire(cell)
        if result == "repeat":
            self.message = "AGAIN"
            return
        self.player_shots += 1
        if result == "miss":
            self.message = "MISS"
            self.audio.play("miss")
        else:
            self.audio.play("sunk" if result == "sunk" else "hit")
            self.hits += 1
            ship = self.enemy.ship_at(cell)
            self.message = f"SUNK {ship.label}" if result == "sunk" and ship else "HIT"
        if self.enemy.defeated:
            self.won = True
            self.audio.play("win")
            self.message = "YOU WIN"
            return
        self.turn = "enemy"
        self.enemy_timer = 0.0

    # --- computer ---------------------------------------------------------

    def advance(self, elapsed: float) -> None:
        if self.turn != "enemy":
            return
        self.enemy_timer += elapsed
        if self.enemy_timer < 0.8:
            return
        self.enemy_timer = 0.0
        self._enemy_fire()

    def _enemy_target(self) -> tuple[int, int] | None:
        while self.hunt:
            cell = self.hunt.pop(0)
            if cell not in self.player.shots:
                return cell
        untried = [(x, y) for x in range(GRID) for y in range(GRID) if (x, y) not in self.player.shots]
        if not untried:
            return None
        # Ships are at least two long, so a checkerboard finds them in half the shots.
        parity = [cell for cell in untried if sum(cell) % 2 == 0]
        if self.difficulty != "easy" and parity:
            untried = parity
        return self.random.choice(untried)

    def _enemy_fire(self) -> None:
        cell = self._enemy_target()
        if cell is None:
            # Nothing left to shoot at, which can only happen once the board is
            # exhausted. Hand the turn back rather than raising.
            self.turn = "player"
            return
        result = self.player.fire(cell)
        if result in ("hit", "sunk") and self.difficulty != "easy":
            if result == "hit":
                x, y = cell
                for step_x, step_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    neighbour = (x + step_x, y + step_y)
                    if 0 <= neighbour[0] < GRID and 0 <= neighbour[1] < GRID and neighbour not in self.player.shots:
                        self.hunt.append(neighbour)
            else:
                # The ship is down, so stop chasing its neighbours.
                ship = self.player.ship_at(cell)
                if ship is not None:
                    self.hunt = [pending for pending in self.hunt if pending not in ship.cells]
        if self.player.defeated:
            self.game_over = True
            self.audio.play("game_over")
            self.message = "FLEET LOST"
            return
        self.turn = "player"

    # --- reporting --------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        accuracy = f"{round(100 * self.hits / self.player_shots)}%" if self.player_shots else "-"
        return {
            "Status": self.message,
            "Enemy left": self.enemy.remaining(),
            "Yours left": self.player.remaining(),
            "Accuracy": accuracy,
        }

    def extra(self) -> dict[str, Any]:
        return {"turn": self.turn, "message": self.message}

    # --- drawing ----------------------------------------------------------

    def _draw_grid(self, draw, origin: tuple[int, int], fleet: Fleet, *, show_ships: bool) -> None:
        origin_x, origin_y = origin
        size = GRID * CELL
        draw.rectangle((origin_x - 1, origin_y - 1, origin_x + size, origin_y + size), outline=GRID_LINE)
        for y in range(GRID):
            for x in range(GRID):
                left = origin_x + x * CELL
                top = origin_y + y * CELL
                shot = fleet.shots.get((x, y), EMPTY)
                ship = fleet.ship_at((x, y))
                color = WATER
                if shot == STRUCK:
                    color = SUNK if ship is not None and ship.sunk else HIT
                elif shot == MISSED:
                    color = MISS
                elif show_ships and ship is not None:
                    color = SHIP
                draw.rectangle((left, top, left + CELL - 2, top + CELL - 2), fill=color)

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame((6, 10, 22))

        draw_pixel_text(draw, 2, 1, "ENEMY", LABEL, 1)
        draw_pixel_text(draw, 32, 1, "YOURS", LABEL, 1)
        self._draw_grid(draw, ENEMY_ORIGIN, self.enemy, show_ships=self.reveal)
        self._draw_grid(draw, PLAYER_ORIGIN, self.player, show_ships=True)

        if not self.finished() and self.turn == "player":
            left = ENEMY_ORIGIN[0] + self.cursor[0] * CELL
            top = ENEMY_ORIGIN[1] + self.cursor[1] * CELL
            draw.rectangle((left - 1, top - 1, left + CELL - 1, top + CELL - 1), outline=CURSOR)

        draw_pixel_text(draw, 2, 42, self.message[:14], TEXT, 1)
        draw_pixel_text(draw, 2, 50, f"SHIPS {self.enemy.remaining()}V{self.player.remaining()}", LABEL, 1)
        if self.turn == "enemy" and not self.finished():
            draw_pixel_text(draw, 2, 58, "ENEMY FIRES", LABEL, 1)

        if self.won:
            draw_banner(draw, ("YOU", "WIN"), TEXT)
        elif self.game_over:
            draw_banner(draw, ("FLEET", "LOST"), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        return fit_panel(image, size)


def demo_snapshot() -> BattleshipGame:
    game = BattleshipGame(seed=12)
    for cell in list(game.enemy.ships[0].cells)[:3]:
        game.enemy.fire(cell)
    game.enemy.fire((9, 9))
    game.enemy.fire((0, 4))
    for cell in game.player.ships[4].cells:
        game.player.fire(cell)
    game.player.fire((2, 7))
    game.cursor = [4, 5]
    game.message = "HIT"
    game.player_shots, game.hits = 5, 3
    return game
