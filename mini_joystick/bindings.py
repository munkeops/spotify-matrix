"""Map joystick events onto Assistant Matrix actions.

Two modes, chosen by what is on the panel:

* **Game** — a game is running, so the stick and buttons drive it. Each game
  declares its own action list, so the binding picks the closest fit rather
  than assuming a d-pad.
* **Shell** — anything else is on the panel, so the stick shuffles through
  plugins and OK applies the highlighted one.
"""

from __future__ import annotations

from dataclasses import dataclass

from mini_joystick.events import JoystickEvent
from mini_joystick.protocol import Button, ButtonEvent, Direction

# Games that take a d-pad get the stick verbatim. Everything else needs the
# vertical or horizontal axis folded onto whatever the game does accept.
DIRECTION_ACTIONS = {
    Direction.UP: "up",
    Direction.DOWN: "down",
    Direction.LEFT: "left",
    Direction.RIGHT: "right",
}

# Preference order when a game has no direct action for a stick push.
DIRECTION_FALLBACKS: dict[Direction, tuple[str, ...]] = {
    Direction.UP: ("rotateCw", "flap", "fire"),
    Direction.DOWN: ("softDrop", "drop"),
    Direction.LEFT: ("left",),
    Direction.RIGHT: ("right",),
}

# Face buttons, in the order the module labels them.
BUTTON_FALLBACKS: dict[Button, tuple[str, ...]] = {
    Button.A: ("hardDrop", "fire", "flap", "drop", "rotateCw"),
    Button.B: ("rotateCcw", "hold", "fire", "flap", "drop"),
    Button.C: ("hold", "rotateCcw", "fire"),
    Button.D: ("restart",),
    Button.OK: ("togglePause",),
}

#: Stick pushes that should auto-repeat while held, per game action.
REPEATABLE = frozenset({"left", "right", "up", "down", "softDrop", "p2Up", "p2Down"})


@dataclass(frozen=True)
class ShellAction:
    """A joystick action while no game is on the panel."""

    kind: str  # "next", "previous", "apply", "power", "open"
    value: str = ""


def game_action(event: JoystickEvent, actions: set[str]) -> str:
    """The action ``event`` should send to a game accepting ``actions``.

    Returns an empty string when the game has nothing sensible bound.
    """
    if event.kind == "direction":
        direct = DIRECTION_ACTIONS.get(event.direction, "")
        candidates = ([direct] if direct else []) + list(DIRECTION_FALLBACKS.get(event.direction, ()))
        for candidate in candidates:
            if candidate not in actions:
                continue
            # Only true movement auto-repeats; never spin a piece or spam a drop.
            if event.repeat and candidate not in REPEATABLE:
                return ""
            return candidate
        return ""

    if event.kind != "button" or event.button is None:
        return ""

    # Long-press on D restarts; a plain click is handled below.
    if event.event not in (ButtonEvent.PRESS_DOWN, ButtonEvent.SINGLE_CLICK, ButtonEvent.LONG_PRESS_START):
        return ""
    if event.button == Button.D and event.event != ButtonEvent.LONG_PRESS_START:
        return ""
    if event.button == Button.OK and event.event == ButtonEvent.LONG_PRESS_START:
        return "restart" if "restart" in actions else ""

    for candidate in BUTTON_FALLBACKS.get(event.button, ()):
        if candidate in actions:
            return candidate
    return ""


def shell_action(event: JoystickEvent) -> ShellAction | None:
    """The action ``event`` should take when no game is running."""
    if event.kind == "direction":
        if event.direction in (Direction.RIGHT, Direction.DOWN):
            return ShellAction(kind="next")
        if event.direction in (Direction.LEFT, Direction.UP):
            return ShellAction(kind="previous")
        return None

    if event.kind != "button" or event.button is None:
        return None
    if event.event not in (ButtonEvent.SINGLE_CLICK, ButtonEvent.LONG_PRESS_START):
        return None

    if event.button == Button.OK:
        return ShellAction(kind="apply")
    if event.button == Button.A:
        return ShellAction(kind="apply")
    if event.button == Button.D and event.event == ButtonEvent.LONG_PRESS_START:
        return ShellAction(kind="power")
    if event.button == Button.B:
        # Jump straight to the arcade so games are always two presses away.
        return ShellAction(kind="open", value="core.pacman")
    return None


__all__ = [
    "game_action",
    "shell_action",
    "ShellAction",
    "DIRECTION_ACTIONS",
    "DIRECTION_FALLBACKS",
    "BUTTON_FALLBACKS",
    "REPEATABLE",
]
