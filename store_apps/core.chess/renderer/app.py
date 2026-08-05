"""Chess for the 64x64 matrix.

A full ruleset — castling, en passant, promotion, stalemate and the fifty
move rule — against an alpha-beta search. Pieces are 6x6 sprites, which is
about the smallest a bishop and a pawn can be told apart at.

The search runs on the tick *after* the computer's turn begins so that the
"thinking" frame is on screen before the panel stops updating, and it is
capped by a node budget rather than by depth alone, so a Pi never stalls.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, draw_pixel_text, fit_panel, new_frame

CELL = 6
ORIGIN = (8, 12)
BOARD = 8 * CELL

WHITE, BLACK = "w", "b"

LIGHT_SQUARE = (196, 182, 152)
DARK_SQUARE = (108, 88, 68)
WHITE_PIECE = (250, 250, 245)
BLACK_PIECE = (24, 22, 30)
CURSOR = (110, 230, 255)
PICKED = (120, 240, 150)
TARGET = (250, 220, 90)
CHECK = (230, 80, 80)
TEXT = (206, 216, 236)
DIM = (122, 132, 158)

# 6x6 silhouettes. Small, but the crown, the cross and the castellation are
# what make queen, king and rook readable at this size.
SPRITES = {
    "p": ("......", "..##..", ".####.", "..##..", ".####.", "......"),
    "r": ("......", "#.##.#", "######", ".####.", "######", "......"),
    "n": ("......", ".####.", "##.##.", "..###.", ".####.", "......"),
    "b": ("..##..", ".####.", "..##..", ".####.", ".####.", "......"),
    "q": ("#.##.#", "######", ".####.", "..##..", "######", "......"),
    "k": ("..##..", "######", "..##..", ".####.", "######", "......"),
}

VALUES = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 20000}

# One shared table: the middle of the board is worth more than the rim. Real
# engines use a table per piece; at this depth the difference does not show.
CENTRE = (
    (0, 1, 2, 3, 3, 2, 1, 0),
    (1, 3, 4, 5, 5, 4, 3, 1),
    (2, 4, 6, 7, 7, 6, 4, 2),
    (3, 5, 7, 9, 9, 7, 5, 3),
    (3, 5, 7, 9, 9, 7, 5, 3),
    (2, 4, 6, 7, 7, 6, 4, 2),
    (1, 3, 4, 5, 5, 4, 3, 1),
    (0, 1, 2, 3, 3, 2, 1, 0),
)

STEPS = {
    "n": ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)),
    "b": ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    "r": ((-1, 0), (1, 0), (0, -1), (0, 1)),
    "q": ((-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)),
    "k": ((-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)),
}
SLIDERS = ("b", "r", "q")

START = (
    "rnbqkbnr",
    "pppppppp",
    "........",
    "........",
    "........",
    "........",
    "PPPPPPPP",
    "RNBQKBNR",
)

PROMOTIONS = ("q", "r", "b", "n")


class TimeUp(Exception):
    """Raised to unwind a search that has run out of its allotted time."""

class Move:
    __slots__ = ("origin", "target", "promotion", "castle", "en_passant")

    def __init__(self, origin, target, promotion="", castle="", en_passant=False):
        self.origin = origin
        self.target = target
        self.promotion = promotion
        self.castle = castle
        self.en_passant = en_passant

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Move)
            and (self.origin, self.target, self.promotion)
            == (other.origin, other.target, other.promotion)
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return f"Move({self.origin}->{self.target}{self.promotion})"


class Board:
    """Just enough chess to be correct, and small enough to search."""

    def __init__(self) -> None:
        self.squares = [list(row) for row in START]
        self.to_move = WHITE
        # Which castles are still legally available.
        self.rights = {"K": True, "Q": True, "k": True, "q": True}
        self.en_passant: tuple[int, int] | None = None
        self.halfmoves = 0
        self.fullmoves = 1
        self.kings = {WHITE: (7, 4), BLACK: (0, 4)}

    def copy(self) -> "Board":
        clone = Board.__new__(Board)
        clone.squares = [row[:] for row in self.squares]
        clone.to_move = self.to_move
        clone.rights = dict(self.rights)
        clone.en_passant = self.en_passant
        clone.halfmoves = self.halfmoves
        clone.fullmoves = self.fullmoves
        clone.kings = dict(self.kings)
        return clone

    # --- squares ---------------------------------------------------------

    def at(self, square: tuple[int, int]) -> str:
        return self.squares[square[0]][square[1]]

    @staticmethod
    def colour_of(piece: str) -> str:
        if piece == ".":
            return ""
        return WHITE if piece.isupper() else BLACK

    @staticmethod
    def inside(row: int, column: int) -> bool:
        return 0 <= row < 8 and 0 <= column < 8

    def king_square(self, colour: str) -> tuple[int, int] | None:
        return self.kings.get(colour)

    # --- attacks ---------------------------------------------------------

    def attacked(self, square: tuple[int, int], by: str) -> bool:
        """Is ``square`` attacked by ``by``? Used for check and castling."""
        row, column = square
        pawn_row = row + (1 if by == WHITE else -1)
        pawn = "P" if by == WHITE else "p"
        for delta in (-1, 1):
            if self.inside(pawn_row, column + delta) and self.squares[pawn_row][column + delta] == pawn:
                return True

        for name in ("n", "k"):
            wanted = name.upper() if by == WHITE else name
            for step_row, step_column in STEPS[name]:
                near_row, near_column = row + step_row, column + step_column
                if self.inside(near_row, near_column) and self.squares[near_row][near_column] == wanted:
                    return True

        for name in ("b", "r"):
            wanted = {name, "q"}
            if by == WHITE:
                wanted = {piece.upper() for piece in wanted}
            for step_row, step_column in STEPS[name]:
                near_row, near_column = row + step_row, column + step_column
                while self.inside(near_row, near_column):
                    piece = self.squares[near_row][near_column]
                    if piece != ".":
                        if piece in wanted:
                            return True
                        break
                    near_row += step_row
                    near_column += step_column
        return False

    def in_check(self, colour: str) -> bool:
        king = self.king_square(colour)
        if king is None:
            return False
        return self.attacked(king, BLACK if colour == WHITE else WHITE)

    # --- move generation -------------------------------------------------

    def pseudo_moves(self, colour: str) -> Iterator[Move]:
        for row in range(8):
            for column in range(8):
                piece = self.squares[row][column]
                if piece == "." or self.colour_of(piece) != colour:
                    continue
                name = piece.lower()
                if name == "p":
                    yield from self._pawn_moves(row, column, colour)
                elif name in SLIDERS:
                    yield from self._ray_moves(row, column, colour, STEPS[name])
                else:
                    yield from self._step_moves(row, column, colour, STEPS[name])
        yield from self._castles(colour)

    def _pawn_moves(self, row: int, column: int, colour: str) -> Iterator[Move]:
        forward = -1 if colour == WHITE else 1
        start_row = 6 if colour == WHITE else 1
        last_row = 0 if colour == WHITE else 7

        ahead = row + forward
        if self.inside(ahead, column) and self.squares[ahead][column] == ".":
            yield from self._pawn_move(row, column, ahead, column, last_row)
            two = row + forward * 2
            if row == start_row and self.squares[two][column] == ".":
                yield Move((row, column), (two, column))

        for delta in (-1, 1):
            side = column + delta
            if not self.inside(ahead, side):
                continue
            target = self.squares[ahead][side]
            if target != "." and self.colour_of(target) != colour:
                yield from self._pawn_move(row, column, ahead, side, last_row)
            elif self.en_passant == (ahead, side):
                yield Move((row, column), (ahead, side), en_passant=True)

    def _pawn_move(self, row, column, ahead, side, last_row) -> Iterator[Move]:
        if ahead == last_row:
            for promotion in PROMOTIONS:
                yield Move((row, column), (ahead, side), promotion=promotion)
        else:
            yield Move((row, column), (ahead, side))

    def _step_moves(self, row, column, colour, steps) -> Iterator[Move]:
        for step_row, step_column in steps:
            near_row, near_column = row + step_row, column + step_column
            if not self.inside(near_row, near_column):
                continue
            target = self.squares[near_row][near_column]
            if target == "." or self.colour_of(target) != colour:
                yield Move((row, column), (near_row, near_column))

    def _ray_moves(self, row, column, colour, steps) -> Iterator[Move]:
        for step_row, step_column in steps:
            near_row, near_column = row + step_row, column + step_column
            while self.inside(near_row, near_column):
                target = self.squares[near_row][near_column]
                if target == ".":
                    yield Move((row, column), (near_row, near_column))
                else:
                    if self.colour_of(target) != colour:
                        yield Move((row, column), (near_row, near_column))
                    break
                near_row += step_row
                near_column += step_column

    def _castles(self, colour: str) -> Iterator[Move]:
        row = 7 if colour == WHITE else 0
        king = "K" if colour == WHITE else "k"
        if self.squares[row][4] != king:
            return
        enemy = BLACK if colour == WHITE else WHITE
        if self.attacked((row, 4), enemy):
            return

        short, long = ("K", "Q") if colour == WHITE else ("k", "q")
        rook = "R" if colour == WHITE else "r"
        if self.rights[short] and self.squares[row][7] == rook:
            if all(self.squares[row][column] == "." for column in (5, 6)):
                # The king may not pass through an attacked square.
                if not any(self.attacked((row, column), enemy) for column in (5, 6)):
                    yield Move((row, 4), (row, 6), castle=short)
        if self.rights[long] and self.squares[row][0] == rook:
            if all(self.squares[row][column] == "." for column in (1, 2, 3)):
                if not any(self.attacked((row, column), enemy) for column in (2, 3)):
                    yield Move((row, 4), (row, 2), castle=long)

    def children(self, colour: str | None = None) -> Iterator[tuple[Move, "Board"]]:
        """Legal moves paired with the position they lead to.

        Testing legality already costs a copy and a check test, so the search
        keeps that position rather than building it a second time.
        """
        colour = colour or self.to_move
        for move in self.pseudo_moves(colour):
            trial = self.copy()
            trial.apply(move)
            if not trial.in_check(colour):
                yield move, trial

    def legal_moves(self, colour: str | None = None) -> list[Move]:
        return [move for move, _ in self.children(colour)]

    # --- making moves ----------------------------------------------------

    def apply(self, move: Move) -> None:
        row, column = move.origin
        target_row, target_column = move.target
        piece = self.squares[row][column]
        captured = self.squares[target_row][target_column]
        colour = self.colour_of(piece)

        self.squares[row][column] = "."
        self.squares[target_row][target_column] = (
            (move.promotion.upper() if colour == WHITE else move.promotion)
            if move.promotion
            else piece
        )

        if move.en_passant:
            # The pawn taken sits beside the target, not on it.
            self.squares[row][target_column] = "."
            captured = "p"

        if move.castle:
            rook_from, rook_to = (7, 5) if move.castle.lower() == "k" else (0, 3)
            self.squares[target_row][rook_to] = self.squares[target_row][rook_from]
            self.squares[target_row][rook_from] = "."

        if piece.lower() == "k":
            self.kings[colour] = move.target
        self._update_rights(move, piece)

        self.en_passant = None
        if piece.lower() == "p" and abs(target_row - row) == 2:
            self.en_passant = ((row + target_row) // 2, column)

        # Anything but a pawn move or a capture ticks towards the draw.
        self.halfmoves = 0 if piece.lower() == "p" or captured != "." else self.halfmoves + 1
        if colour == BLACK:
            self.fullmoves += 1
        self.to_move = BLACK if colour == WHITE else WHITE

    def _update_rights(self, move: Move, piece: str) -> None:
        if piece == "K":
            self.rights["K"] = self.rights["Q"] = False
        elif piece == "k":
            self.rights["k"] = self.rights["q"] = False
        for square, right in (((7, 7), "K"), ((7, 0), "Q"), ((0, 7), "k"), ((0, 0), "q")):
            # A rook that moves or is taken ends that castle either way.
            if move.origin == square or move.target == square:
                self.rights[right] = False

    # --- scoring ---------------------------------------------------------

    def evaluate(self) -> int:
        """Positive favours white. Material first, position as a tiebreak."""
        score = 0
        for row in range(8):
            for column in range(8):
                piece = self.squares[row][column]
                if piece == ".":
                    continue
                value = VALUES[piece.lower()] + CENTRE[row][column]
                score += value if piece.isupper() else -value
        return score


class ChessGame(GameApp):
    game_id = "chess"
    id = "core.chess"
    name = "Chess"
    summary = "Full chess against a searching engine, on 64 by 64 pixels."
    layout = "dpad"
    actions = ("up", "down", "left", "right", "fire")
    config_fields = [
        ConfigField.select(
            "level",
            [("Gives pieces away", "easy"), ("Plays a decent game", "normal"), ("Takes its time", "hard")],
            label="Engine",
            default="normal",
        ),
        ConfigField.select("side", [("White", "w"), ("Black", "b")], label="You play", default="w"),
        ConfigField.boolean("hints", label="Show legal moves", default=True, help_text="Mark where a picked-up piece can go."),
    ]

    #: Level to (search depth ceiling, seconds it may think for).
    #:
    #: The clock is what actually bounds it. A node budget would mean one
    #: number for a laptop and another for a Pi; a deadline is the same
    #: promise on both, and iterative deepening keeps a usable move in hand
    #: whenever it runs out.
    LEVELS = {"easy": (1, 0.15), "normal": (3, 0.5), "hard": (4, 1.5)}

    #: Plies of captures to play out past the depth limit.
    QUIET_PLIES = 6

    def reset(self) -> None:
        level = str(self.config.get("level", "normal"))
        self.depth, self.think_seconds = self.LEVELS.get(level, self.LEVELS["normal"])
        self.side = WHITE if str(self.config.get("side", "w")) == "w" else BLACK
        self.hints = bool(self.config.get("hints", True))

        self.board = Board()
        self.cursor = [6, 4] if self.side == WHITE else [1, 4]
        self.picked: tuple[int, int] | None = None
        self.picked_moves: list[Move] = []
        self.promoting: Move | None = None
        self.promotion_choice = 0
        self.last_move: Move | None = None
        self.message = ""
        self.result = ""
        self.score = 0
        self.thinking = False
        self._think_delay = 0.0
        self._nodes = 0
        self._deadline = 0.0
        self.reached_depth = 0

        if self.board.to_move != self.side:
            self._begin_thinking()

    # --- input -----------------------------------------------------------

    def handle(self, action: str) -> None:
        if self.finished() or self.thinking or self.board.to_move != self.side:
            return
        if self.promoting is not None:
            self._handle_promotion(action)
            return

        if action in ("up", "down", "left", "right"):
            self._move_cursor(action)
        elif action == "fire":
            self._select()

    def _move_cursor(self, action: str) -> None:
        # Black plays from the far side, so the pad matches what you see.
        flip = -1 if self.side == BLACK else 1
        row, column = self.cursor
        if action == "up":
            row -= flip
        elif action == "down":
            row += flip
        elif action == "left":
            column -= flip
        else:
            column += flip
        self.cursor = [max(0, min(7, row)), max(0, min(7, column))]
        self.audio.play("move", 0.35)

    def _select(self) -> None:
        square = (self.cursor[0], self.cursor[1])
        if self.picked is not None:
            chosen = [move for move in self.picked_moves if move.target == square]
            if chosen:
                if len(chosen) > 1 and chosen[0].promotion:
                    # A pawn reaching the last rank: pick what it becomes.
                    self.promoting = chosen[0]
                    self.promotion_choice = 0
                    return
                self._play(chosen[0])
                return
            if square == self.picked:
                self.picked, self.picked_moves = None, []
                self.audio.play("move", 0.3)
                return

        piece = self.board.at(square)
        if piece != "." and Board.colour_of(piece) == self.side:
            self.picked = square
            self.picked_moves = [move for move in self.board.legal_moves(self.side) if move.origin == square]
            self.audio.play("pick")
        else:
            self.audio.play("deny", 0.5)

    def _handle_promotion(self, action: str) -> None:
        if action in ("left", "up"):
            self.promotion_choice = (self.promotion_choice - 1) % len(PROMOTIONS)
            self.audio.play("move", 0.35)
        elif action in ("right", "down"):
            self.promotion_choice = (self.promotion_choice + 1) % len(PROMOTIONS)
            self.audio.play("move", 0.35)
        elif action == "fire":
            move = self.promoting
            self.promoting = None
            move.promotion = PROMOTIONS[self.promotion_choice]
            self._play(move)

    # --- play ------------------------------------------------------------

    def _play(self, move: Move) -> None:
        captured = self.board.at(move.target) != "." or move.en_passant
        self.board.apply(move)
        self.last_move = move
        self.picked, self.picked_moves = None, []
        self.audio.play("capture" if captured else "place")
        self.score = max(0, self.board.evaluate() if self.side == WHITE else -self.board.evaluate())

        if self._settle():
            return
        if self.board.to_move != self.side:
            self._begin_thinking()

    def _settle(self) -> bool:
        """End the game if the side to move has no way to continue."""
        moving = self.board.to_move
        if self.board.legal_moves(moving):
            if self.board.halfmoves >= 100:
                self._end("DRAW", "FIFTY MOVE")
                return True
            self.message = "CHECK" if self.board.in_check(moving) else ""
            return False

        if self.board.in_check(moving):
            self._end("YOU WIN" if moving != self.side else "CHECKMATE", "MATE")
        else:
            self._end("DRAW", "STALEMATE")
        return True

    def _end(self, headline: str, detail: str) -> None:
        self.result = detail
        self.message = detail
        if headline == "YOU WIN":
            self.won = True
            self.score += 1000
            self.audio.play("win")
        elif headline == "DRAW":
            self.game_over = True
            self.audio.play("game_over")
        else:
            self.game_over = True
            self.audio.play("game_over")

    def _begin_thinking(self) -> None:
        self.thinking = True
        # One tick of grace so the "thinking" frame reaches the panel before
        # the search takes over the loop.
        self._think_delay = 0.12

    def advance(self, elapsed: float) -> None:
        if not self.thinking or self.finished():
            return
        self._think_delay -= elapsed
        if self._think_delay > 0:
            return
        self.thinking = False
        move = self.best_move()
        if move is None:
            self._settle()
            return
        captured = self.board.at(move.target) != "." or move.en_passant
        self.board.apply(move)
        self.last_move = move
        self.audio.play("capture" if captured else "place")
        self._settle()

    # --- the engine ------------------------------------------------------

    def best_move(self) -> Move | None:
        moves = self.board.legal_moves()
        if not moves:
            return None
        self._nodes = 0
        self._deadline = time.monotonic() + self.think_seconds
        maximising = self.board.to_move == WHITE

        ordered = self._ordered(self.board, moves)
        best = ordered[0]
        self.reached_depth = 0
        for depth in range(1, self.depth + 1):
            try:
                found = self._root(ordered, depth, maximising)
            except TimeUp:
                # Keep the move from the last depth that finished.
                break
            best = found
            self.reached_depth = depth
            # Search the best move first next time round; it cuts the most.
            ordered.remove(best)
            ordered.insert(0, best)
        return best

    def _root(self, moves: list[Move], depth: int, maximising: bool) -> Move:
        best, best_score = moves[0], None
        for move in moves:
            trial = self.board.copy()
            trial.apply(move)
            score = self._search(trial, depth - 1, -10**9, 10**9)
            if best_score is None or (score > best_score if maximising else score < best_score):
                best, best_score = move, score
        return best

    def _search(self, board: Board, depth: int, alpha: int, beta: int) -> int:
        self._nodes += 1
        # Checking the clock every node costs more than it saves.
        if self._nodes % 256 == 0 and time.monotonic() > self._deadline:
            raise TimeUp
        if depth <= 0:
            return self._quiet(board, alpha, beta, self.QUIET_PLIES)

        children = self._ranked(board, board.children())
        if not children:
            if board.in_check(board.to_move):
                # Prefer the mate that arrives sooner.
                return -10**6 - depth if board.to_move == WHITE else 10**6 + depth
            return 0

        maximising = board.to_move == WHITE
        best = -10**9 if maximising else 10**9
        for _, trial in children:
            score = self._search(trial, depth - 1, alpha, beta)
            if maximising:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if beta <= alpha:
                break
        return best

    def _quiet(self, board: Board, alpha: int, beta: int, plies: int) -> int:
        """Keep looking while pieces are still being taken.

        Stopping the search mid-exchange is what makes a shallow engine give
        material away: it sees its own capture and not the recapture. Playing
        the captures out first costs little and removes most of that.
        """
        self._nodes += 1
        standing = board.evaluate()
        maximising = board.to_move == WHITE
        if plies <= 0:
            return standing
        if self._nodes % 256 == 0 and time.monotonic() > self._deadline:
            raise TimeUp

        if maximising:
            if standing >= beta:
                return standing
            alpha = max(alpha, standing)
        else:
            if standing <= alpha:
                return standing
            beta = min(beta, standing)

        captures = self._ranked(
            board,
            ((move, trial) for move, trial in board.children() if board.at(move.target) != "." or move.promotion),
        )
        if not captures:
            return standing

        best = standing
        for _, trial in captures:
            score = self._quiet(trial, alpha, beta, plies - 1)
            if maximising:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if beta <= alpha:
                break
        return best

    @staticmethod
    def _rank(board: Board, move: Move) -> int:
        victim = board.at(move.target)
        gain = VALUES[victim.lower()] if victim != "." else 0
        return gain + (800 if move.promotion else 0)

    def _ranked(self, board: Board, children) -> list[tuple[Move, Board]]:
        """Captures first, so alpha-beta has something to cut against."""
        return sorted(children, key=lambda pair: self._rank(board, pair[0]), reverse=True)

    def _ordered(self, board: Board, moves: list[Move]) -> list[Move]:
        """The same ordering, for the root and for the move hints."""
        def rank(move: Move) -> int:
            return self._rank(board, move)

        ordered = sorted(moves, key=rank, reverse=True)
        if self.depth <= 1:
            # The easy engine is deliberately careless about quiet moves.
            self.random.shuffle(ordered)
            ordered.sort(key=lambda move: rank(move) > 0, reverse=True)
        return ordered

    # --- reporting -------------------------------------------------------

    def hud(self) -> dict[str, Any]:
        material = self.board.evaluate() // 100
        edge = material if self.side == WHITE else -material
        return {
            "Move": self.board.fullmoves,
            "Turn": "You" if self.board.to_move == self.side else "Engine",
            "Material": f"{edge:+d}",
            "State": self.result or self.message or "Playing",
        }

    def extra(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking,
            "picked": list(self.picked) if self.picked else None,
            "depth": self.reached_depth,
        }

    def _screen_square(self, row: int, column: int) -> tuple[int, int]:
        if self.side == BLACK:
            row, column = 7 - row, 7 - column
        return ORIGIN[0] + column * CELL, ORIGIN[1] + row * CELL

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()

        turn = "YOUR MOVE" if self.board.to_move == self.side else "THINKING"
        draw_pixel_text(draw, 1, 1, self.result or (self.message or turn), TEXT, 1)
        draw_pixel_text(draw, PANEL - 19, 1, f"M{self.board.fullmoves}", DIM, 1)

        check_square = None
        if self.board.in_check(self.board.to_move):
            check_square = self.board.king_square(self.board.to_move)

        for row in range(8):
            for column in range(8):
                left, top = self._screen_square(row, column)
                square = LIGHT_SQUARE if (row + column) % 2 == 0 else DARK_SQUARE
                if check_square == (row, column):
                    square = CHECK
                draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), fill=square)

                piece = self.board.squares[row][column]
                if piece != ".":
                    self._draw_piece(draw, left, top, piece)

        if self.last_move is not None:
            for square in (self.last_move.origin, self.last_move.target):
                left, top = self._screen_square(*square)
                draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), outline=(150, 150, 110))

        if self.hints:
            for move in self.picked_moves:
                left, top = self._screen_square(*move.target)
                draw.rectangle((left + 2, top + 2, left + 3, top + 3), fill=TARGET)

        if self.picked is not None:
            left, top = self._screen_square(*self.picked)
            draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), outline=PICKED)

        left, top = self._screen_square(self.cursor[0], self.cursor[1])
        draw.rectangle((left, top, left + CELL - 1, top + CELL - 1), outline=CURSOR)

        if self.promoting is not None:
            self._draw_promotion(draw)
        elif self.won:
            draw_banner(draw, ("YOU WIN",), TEXT)
        elif self.game_over:
            draw_banner(draw, (self.result or "GAME OVER",), TEXT)
        elif self.paused:
            draw_banner(draw, ("PAUSED",), TEXT)
        return fit_panel(image, size)

    def _draw_piece(self, draw, left: int, top: int, piece: str) -> None:
        colour = WHITE_PIECE if piece.isupper() else BLACK_PIECE
        for offset_y, row in enumerate(SPRITES[piece.lower()]):
            for offset_x, cell in enumerate(row):
                if cell == "#":
                    draw.point((left + offset_x, top + offset_y), fill=colour)

    def _draw_promotion(self, draw) -> None:
        top = ORIGIN[1] + BOARD // 2 - 6
        draw.rectangle((6, top, PANEL - 7, top + 13), fill=(16, 18, 28), outline=(80, 88, 116))
        draw_pixel_text(draw, 9, top + 2, "PROMOTE", TEXT, 1)
        for index, name in enumerate(PROMOTIONS):
            left = 10 + index * 11
            piece = name.upper() if self.side == WHITE else name
            self._draw_piece(draw, left, top + 7, piece)
            if index == self.promotion_choice:
                draw.rectangle((left - 1, top + 6, left + CELL, top + 6 + CELL), outline=CURSOR)


def demo_snapshot() -> ChessGame:
    game = ChessGame(seed=7)
    # A few book moves, so the tile shows a game rather than the start.
    for origin, target in (((6, 4), (4, 4)), ((1, 4), (3, 4)), ((7, 6), (5, 5)), ((0, 1), (2, 2))):
        game.board.apply(Move(origin, target))
    game.last_move = Move((0, 1), (2, 2))
    game.cursor = [5, 5]
    game.thinking = False
    game.score = 120
    return game
