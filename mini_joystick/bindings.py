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


#: The controls a player can rebind, in the order a settings screen shows them.
CONTROLS = ("up", "down", "left", "right", "a", "b", "c", "d", "ok")


def control_name(event: JoystickEvent) -> str:
    """Which rebindable control an event came from, if any."""
    if event.kind == "direction":
        return event.direction.value if event.direction != Direction.NEUTRAL else ""
    if event.kind == "button" and event.button is not None:
        return event.button.value
    return ""


def default_bindings(actions: set[str]) -> dict[str, str]:
    """What each control does before anything is rebound."""
    resolved: dict[str, str] = {}
    for direction in (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT):
        direct = DIRECTION_ACTIONS.get(direction, "")
        for candidate in ([direct] if direct else []) + list(DIRECTION_FALLBACKS.get(direction, ())):
            if candidate in actions:
                resolved[direction.value] = candidate
                break
    for button, candidates in BUTTON_FALLBACKS.items():
        for candidate in candidates:
            if candidate in actions:
                resolved[button.value] = candidate
                break
    return resolved


def game_action(event: JoystickEvent, actions: set[str], overrides: dict[str, str] | None = None) -> str:
    """The action ``event`` should send to a game accepting ``actions``.

    ``overrides`` rebinds a control by name; anything the game does not declare
    is ignored, so a stale binding cannot send a game an action it cannot take.
    """
    if overrides:
        control = control_name(event)
        chosen = overrides.get(control, "")
        if chosen and chosen in actions:
            if event.repeat and chosen not in REPEATABLE:
                return ""
            if event.kind == "button" and event.event not in (
                ButtonEvent.PRESS_DOWN,
                ButtonEvent.SINGLE_CLICK,
                ButtonEvent.LONG_PRESS_START,
            ):
                return ""
            return chosen
        if chosen == "none":
            return ""
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


#: Button presses count on the way down or as a click, so both the I2C
#: module (which reports clicks) and a gamepad (which reports presses) work.
PRESS_EVENTS = (ButtonEvent.PRESS_DOWN, ButtonEvent.SINGLE_CLICK)


def shell_action(event: JoystickEvent, menu_open: bool = False) -> ShellAction | None:
    """The action ``event`` should take when no game is on the panel.

    With the menu closed the buttons are a brightness pair and a way in. With
    it open the stick moves a highlight and nothing is applied until you pick.
    """
    if event.kind == "direction":
        if menu_open:
            if event.direction in (Direction.DOWN, Direction.RIGHT):
                return ShellAction(kind="cursorNext")
            if event.direction in (Direction.UP, Direction.LEFT):
                return ShellAction(kind="cursorPrevious")
            return None
        # Closed, the stick still flicks through plugins directly.
        if event.direction in (Direction.RIGHT, Direction.DOWN):
            return ShellAction(kind="next")
        if event.direction in (Direction.LEFT, Direction.UP):
            return ShellAction(kind="previous")
        return None

    if event.kind != "button" or event.button is None:
        return None

    long_press = event.event == ButtonEvent.LONG_PRESS_START
    if event.event not in PRESS_EVENTS and not long_press:
        return None

    if event.button == Button.D and long_press:
        return ShellAction(kind="power")

    if menu_open:
        if event.button in (Button.OK, Button.A):
            return ShellAction(kind="select")
        if event.button in (Button.B, Button.D):
            return ShellAction(kind="closeMenu")
        return None

    if event.button == Button.OK:
        return ShellAction(kind="openMenu")
    if event.button == Button.A:
        return ShellAction(kind="brightnessUp")
    if event.button == Button.B:
        return ShellAction(kind="brightnessDown")
    if event.button == Button.C:
        return ShellAction(kind="openMenu")
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
