"""Pac-Man for the 64x64 matrix.

The maze is 28x29 tiles drawn at two pixels per tile, which leaves a six pixel
strip at the top for the score and remaining lives. Movement is tile based with
turn buffering, and the four ghosts use the classic targeting rules.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from matrix_games.base import Game
from matrix_games.render import PANEL, draw_banner, draw_centered_text, draw_pixel_text, fit_panel, new_frame

MAZE = (
    "############################",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o####.#####.##.#####.####o#",
    "#.####.#####.##.#####.####.#",
    "#..........................#",
    "#.####.##.########.##.####.#",
    "#.####.##.########.##.####.#",
    "#......##....##....##......#",
    "######.##### ## #####.######",
    "     #.##### ## #####.#     ",
    "     #.##          ##.#     ",
    "     #.## ###--### ##.#     ",
    "######.## #      # ##.######",
    "      .   #      #   .      ",
    "######.## #      # ##.######",
    "     #.## ######## ##.#     ",
    "     #.##          ##.#     ",
    "     #.## ######## ##.#     ",
    "######.## ######## ##.######",
    "#............##............#",
    "#.####.#####.##.#####.####.#",
    "#o..##................##..o#",
    "###.##.##.########.##.##.###",
    "#......##....##....##......#",
    "#.##########.##.##########.#",
    "#.##########.##.##########.#",
    "#..........................#",
    "############################",
)

COLS = 28
ROWS = 29
TILE = 2
ORIGIN_X = (PANEL - COLS * TILE) // 2
ORIGIN_Y = PANEL - ROWS * TILE

assert all(len(row) == COLS for row in MAZE), "Pac-Man maze rows must be 28 tiles wide."
assert len(MAZE) == ROWS, "Pac-Man maze must be 29 tiles tall."

WALL = "#"
DOOR = "-"
PELLET = "."
POWER = "o"

PAC_START = (13.0, 22.0)
HOUSE_DOOR = (13.5, 12.0)
HOUSE_CENTER = (13.5, 14.0)

WALL_COLOR = (40, 62, 190)
DOOR_COLOR = (200, 160, 200)
PELLET_COLOR = (232, 210, 170)
POWER_COLOR = (255, 236, 190)
PAC_COLOR = (250, 220, 60)
FRIGHT_COLOR = (48, 72, 235)
FRIGHT_FLASH = (235, 240, 255)
EYES_COLOR = (225, 235, 255)
TEXT_COLOR = (210, 220, 240)

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

SCATTER_CHASE = ((7.0, "scatter"), (20.0, "chase"), (7.0, "scatter"), (20.0, "chase"), (5.0, "scatter"))
GHOST_POINTS = (200, 400, 800, 1600)


class Ghost:
    def __init__(self, name: str, color: tuple[int, int, int], scatter: tuple[int, int], release: float) -> None:
        self.name = name
        self.color = color
        self.scatter = scatter
        self.release = release
        self.x = HOUSE_CENTER[0]
        self.y = HOUSE_CENTER[1]
        self.direction = (0, -1)
        self.state = "house"
        self.frightened = False
        self.eaten = False
        self.wait = release

    def tile(self) -> tuple[int, int]:
        return int(round(self.x)), int(round(self.y))


def tile_at(x: int, y: int) -> str:
    if not (0 <= y < ROWS):
        return WALL
    x %= COLS
    return MAZE[y][x]


def walkable(x: int, y: int, *, doors: bool = False) -> bool:
    tile = tile_at(x, y)
    if tile == WALL:
        return False
    if tile == DOOR:
        return doors
    return True


class PacmanGame(Game):
    game_id = "pacman"
    name = "Pac-Man"
    actions = ("up", "down", "left", "right")

    def reset(self) -> None:
        self.speed = max(2.0, float(self.config.get("speed", 5.5)))
        self.fright_seconds = max(2.0, float(self.config.get("frightSeconds", 7)))
        self.lives = max(1, int(self.config.get("lives", 3)))
        self.score = 0
        self.level = 1
        self.pellets = {
            (x, y)
            for y in range(ROWS)
            for x in range(COLS)
            if MAZE[y][x] in (PELLET, POWER)
        }
        self.eaten_pellets: set[tuple[int, int]] = set()
        self._reset_actors(ready=2.0)

    def _reset_actors(self, ready: float) -> None:
        self.pac_x, self.pac_y = PAC_START
        self.direction = (-1, 0)
        self.desired = (-1, 0)
        self.ready_timer = ready
        self.death_timer = 0.0
        self.mode_index = 0
        self.mode_timer = 0.0
        self.fright_timer = 0.0
        self.fright_chain = 0
        self.animation = 0.0
        self.ghosts = [
            Ghost("blinky", (255, 72, 60), (25, 0), 0.0),
            Ghost("pinky", (255, 168, 220), (2, 0), 2.0),
            Ghost("inky", (80, 226, 240), (27, 28), 5.0),
            Ghost("clyde", (255, 172, 70), (0, 28), 8.0),
        ]
        self.ghosts[0].x, self.ghosts[0].y = HOUSE_DOOR[0], 11.0
        self.ghosts[0].state = "maze"
        self.ghosts[0].direction = (-1, 0)

    # --- input -----------------------------------------------------------

    def handle(self, action: str) -> None:
        step = DIRECTIONS.get(action)
        if step is not None:
            self.desired = step

    # --- stepping --------------------------------------------------------

    def advance(self, elapsed: float) -> None:
        self.animation += elapsed
        if self.ready_timer > 0:
            self.ready_timer = max(0.0, self.ready_timer - elapsed)
            return
        if self.death_timer > 0:
            self.death_timer = max(0.0, self.death_timer - elapsed)
            if self.death_timer == 0:
                self._after_death()
            return

        self._advance_modes(elapsed)
        self._move_pac(elapsed)
        for ghost in self.ghosts:
            self._move_ghost(ghost, elapsed)
        self._check_collisions()

    def _advance_modes(self, elapsed: float) -> None:
        if self.fright_timer > 0:
            self.fright_timer = max(0.0, self.fright_timer - elapsed)
            if self.fright_timer == 0:
                for ghost in self.ghosts:
                    ghost.frightened = False
                self.fright_chain = 0
            return
        self.mode_timer += elapsed
        if self.mode_index < len(SCATTER_CHASE) and self.mode_timer >= SCATTER_CHASE[self.mode_index][0]:
            self.mode_timer = 0.0
            self.mode_index += 1
            for ghost in self.ghosts:
                if ghost.state == "maze" and not ghost.eaten:
                    # Mode flips reverse the ghosts, exactly like the arcade.
                    ghost.direction = (-ghost.direction[0], -ghost.direction[1])

    def mode(self) -> str:
        if self.mode_index >= len(SCATTER_CHASE):
            return "chase"
        return SCATTER_CHASE[self.mode_index][1]

    def _aligned(self, x: float, y: float) -> bool:
        return abs(x - round(x)) < 0.2 and abs(y - round(y)) < 0.2

    def _advance_axis(self, x: float, y: float, direction: tuple[int, int], distance: float, *, doors: bool) -> tuple[float, float]:
        step_x, step_y = direction
        tile_x, tile_y = int(round(x)), int(round(y))
        next_x, next_y = x + step_x * distance, y + step_y * distance
        if not walkable(tile_x + step_x, tile_y + step_y, doors=doors):
            # Stop dead on the tile centre rather than sliding into the wall.
            if step_x > 0:
                next_x = min(next_x, tile_x)
            elif step_x < 0:
                next_x = max(next_x, tile_x)
            if step_y > 0:
                next_y = min(next_y, tile_y)
            elif step_y < 0:
                next_y = max(next_y, tile_y)
        if next_x < -1:
            next_x += COLS
        elif next_x > COLS:
            next_x -= COLS
        return next_x, next_y

    def _move_pac(self, elapsed: float) -> None:
        if self.desired != self.direction and self._aligned(self.pac_x, self.pac_y):
            tile_x, tile_y = int(round(self.pac_x)), int(round(self.pac_y))
            if walkable(tile_x + self.desired[0], tile_y + self.desired[1]):
                self.pac_x, self.pac_y = float(tile_x), float(tile_y)
                self.direction = self.desired

        self.pac_x, self.pac_y = self._advance_axis(self.pac_x, self.pac_y, self.direction, self.speed * elapsed, doors=False)
        self._eat()

    def _eat(self) -> None:
        tile = (int(round(self.pac_x)) % COLS, int(round(self.pac_y)))
        if tile not in self.pellets or tile in self.eaten_pellets:
            return
        self.eaten_pellets.add(tile)
        if MAZE[tile[1]][tile[0]] == POWER:
            self.score += 50
            self.fright_timer = max(1.0, self.fright_seconds - (self.level - 1) * 0.5)
            self.fright_chain = 0
            for ghost in self.ghosts:
                if not ghost.eaten:
                    ghost.frightened = True
                    ghost.direction = (-ghost.direction[0], -ghost.direction[1])
        else:
            self.score += 10
        if len(self.eaten_pellets) >= len(self.pellets):
            self._next_level()

    def _next_level(self) -> None:
        self.level += 1
        self.speed = min(9.0, self.speed + 0.35)
        self.eaten_pellets = set()
        self._reset_actors(ready=2.0)

    def ghost_speed(self, ghost: Ghost) -> float:
        if ghost.eaten:
            return self.speed * 1.9
        if ghost.frightened:
            return self.speed * 0.55
        return self.speed * (0.82 + min(0.25, (self.level - 1) * 0.04))

    def _move_ghost(self, ghost: Ghost, elapsed: float) -> None:
        if ghost.state == "house":
            ghost.wait -= elapsed
            if ghost.wait <= 0:
                ghost.state = "leaving"
            return
        if ghost.state == "leaving":
            target_x, target_y = HOUSE_DOOR[0], 11.0
            ghost.x += max(-1.0, min(1.0, target_x - ghost.x)) * self.speed * elapsed
            ghost.y += max(-1.0, min(1.0, target_y - ghost.y)) * self.speed * elapsed
            if abs(ghost.x - target_x) < 0.15 and abs(ghost.y - target_y) < 0.15:
                ghost.x, ghost.y = target_x, target_y
                ghost.state = "maze"
                ghost.direction = (-1, 0)
            return

        if self._aligned(ghost.x, ghost.y):
            tile_x, tile_y = ghost.tile()
            ghost.x, ghost.y = float(tile_x), float(tile_y)
            ghost.direction = self._choose_direction(ghost, tile_x, tile_y)

        ghost.x, ghost.y = self._advance_axis(ghost.x, ghost.y, ghost.direction, self.ghost_speed(ghost) * elapsed, doors=True)

        if ghost.eaten and abs(ghost.x - HOUSE_CENTER[0]) < 0.6 and abs(ghost.y - HOUSE_CENTER[1]) < 0.6:
            ghost.eaten = False
            ghost.frightened = False
            ghost.state = "leaving"

    def _choose_direction(self, ghost: Ghost, tile_x: int, tile_y: int) -> tuple[int, int]:
        options = []
        for step in DIRECTIONS.values():
            if step == (-ghost.direction[0], -ghost.direction[1]):
                continue
            if walkable(tile_x + step[0], tile_y + step[1], doors=ghost.eaten):
                options.append(step)
        if not options:
            return (-ghost.direction[0], -ghost.direction[1])
        if ghost.frightened and not ghost.eaten:
            return self.random.choice(options)
        target = self._ghost_target(ghost)
        return min(options, key=lambda step: (tile_x + step[0] - target[0]) ** 2 + (tile_y + step[1] - target[1]) ** 2)

    def _ghost_target(self, ghost: Ghost) -> tuple[float, float]:
        if ghost.eaten:
            return HOUSE_CENTER
        if self.mode() == "scatter":
            return float(ghost.scatter[0]), float(ghost.scatter[1])
        pac_tile = (round(self.pac_x), round(self.pac_y))
        if ghost.name == "blinky":
            return float(pac_tile[0]), float(pac_tile[1])
        if ghost.name == "pinky":
            return pac_tile[0] + self.direction[0] * 4.0, pac_tile[1] + self.direction[1] * 4.0
        if ghost.name == "inky":
            pivot_x = pac_tile[0] + self.direction[0] * 2.0
            pivot_y = pac_tile[1] + self.direction[1] * 2.0
            blinky = self.ghosts[0]
            return pivot_x * 2 - blinky.x, pivot_y * 2 - blinky.y
        distance = (ghost.x - pac_tile[0]) ** 2 + (ghost.y - pac_tile[1]) ** 2
        if distance > 64:
            return float(pac_tile[0]), float(pac_tile[1])
        return float(ghost.scatter[0]), float(ghost.scatter[1])

    def _check_collisions(self) -> None:
        for ghost in self.ghosts:
            if ghost.state != "maze" or ghost.eaten:
                continue
            if abs(ghost.x - self.pac_x) < 0.8 and abs(ghost.y - self.pac_y) < 0.8:
                if ghost.frightened:
                    ghost.eaten = True
                    ghost.frightened = False
                    self.score += GHOST_POINTS[min(self.fright_chain, len(GHOST_POINTS) - 1)]
                    self.fright_chain += 1
                else:
                    self.lives -= 1
                    self.death_timer = 1.6
                    return

    def _after_death(self) -> None:
        if self.lives <= 0:
            self.game_over = True
            return
        self._reset_actors(ready=1.5)

    def hud(self) -> dict[str, Any]:
        return {"Score": self.score, "Lives": max(0, self.lives), "Level": self.level}

    def extra(self) -> dict[str, Any]:
        return {"pellets": len(self.pellets) - len(self.eaten_pellets)}

    # --- drawing ---------------------------------------------------------

    def _pixel(self, tile_x: float, tile_y: float) -> tuple[int, int]:
        return ORIGIN_X + int(round(tile_x * TILE)), ORIGIN_Y + int(round(tile_y * TILE))

    def _sprite(self, draw, tile_x: float, tile_y: float, color: tuple[int, int, int]) -> None:
        x, y = self._pixel(tile_x, tile_y)
        draw.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=color)

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()

        draw_pixel_text(draw, 1, 0, str(self.score), TEXT_COLOR, 1)
        for life in range(max(0, min(4, self.lives - 1))):
            draw.rectangle((PANEL - 3 - life * 4, 1, PANEL - 2 - life * 4, 2), fill=PAC_COLOR)

        for tile_y in range(ROWS):
            for tile_x in range(COLS):
                tile = MAZE[tile_y][tile_x]
                x, y = self._pixel(tile_x, tile_y)
                if tile == WALL:
                    draw.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=WALL_COLOR)
                elif tile == DOOR:
                    draw.line((x, y, x + TILE - 1, y), fill=DOOR_COLOR)
                elif tile in (PELLET, POWER) and (tile_x, tile_y) not in self.eaten_pellets:
                    if tile == POWER:
                        if int(self.animation * 5) % 2 == 0:
                            draw.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=POWER_COLOR)
                    else:
                        draw.point((x, y), fill=PELLET_COLOR)

        for ghost in self.ghosts:
            if ghost.eaten:
                color = EYES_COLOR
            elif ghost.frightened:
                flashing = self.fright_timer < 2.0 and int(self.fright_timer * 6) % 2 == 0
                color = FRIGHT_FLASH if flashing else FRIGHT_COLOR
            else:
                color = ghost.color
            self._sprite(draw, ghost.x, ghost.y, color)

        if self.death_timer > 0:
            if int(self.death_timer * 6) % 2 == 0:
                self._sprite(draw, self.pac_x, self.pac_y, PAC_COLOR)
        else:
            x, y = self._pixel(self.pac_x, self.pac_y)
            draw.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=PAC_COLOR)
            # Chomp by blanking the leading pixel every other beat.
            if int(self.animation * 8) % 2 == 0:
                mouth_x = x + (1 if self.direction[0] >= 0 else 0)
                mouth_y = y + (1 if self.direction[1] > 0 else 0)
                draw.point((mouth_x, mouth_y), fill=(0, 0, 0))

        if self.game_over:
            draw_banner(draw, ("GAME", "OVER", f"{self.score}"), TEXT_COLOR)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT_COLOR)
        elif self.ready_timer > 0:
            draw_centered_text(draw, ORIGIN_Y + 17 * TILE, "READY", PAC_COLOR, 1)
        return fit_panel(image, size)


def demo_snapshot() -> PacmanGame:
    game = PacmanGame(seed=13)
    game.ready_timer = 0.0
    game.score = 1240
    game.pac_x, game.pac_y = 13.0, 20.0
    game.direction = (1, 0)
    for tile in list(game.pellets)[:120]:
        game.eaten_pellets.add(tile)
    game.ghosts[0].x, game.ghosts[0].y = 13.0, 17.0
    game.ghosts[0].state = "maze"
    game.ghosts[1].x, game.ghosts[1].y = 9.0, 20.0
    game.ghosts[1].state = "maze"
    game.ghosts[2].x, game.ghosts[2].y = 18.0, 14.0
    game.ghosts[2].state = "maze"
    game.ghosts[3].x, game.ghosts[3].y = 21.0, 24.0
    game.ghosts[3].state = "maze"
    return game


__all__ = ["PacmanGame", "demo_snapshot", "MAZE", "COLS", "ROWS"]
