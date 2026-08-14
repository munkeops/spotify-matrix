"""Map joystick events onto Assistant Matrix actions.

Two modes, chosen by what is on the panel:

* **Game** — a game is running, so the stick and buttons drive it. Each game
  declares its own action list, so the binding picks the closest fit rather
  than assuming a d-pad.
* **Shell** — anything else is on the panel, so the stick shuffles through
  apps and OK applies the highlighted one.
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


#: What a control can be set to do while the module is on system duty.
#:
#: Which physical button is which is the owner's business - the silkscreen
#: order has nothing to do with where the buttons sit under a thumb, so
#: brightness up and down landed on buttons that are not a pair.
SYSTEM_ACTIONS: tuple[tuple[str, str], ...] = (
    ("brightnessUp", "Brighter"),
    ("brightnessDown", "Dimmer"),
    ("volumeUp", "Louder"),
    ("volumeDown", "Quieter"),
    ("openMenu", "App menu"),
    ("nextApp", "Next app"),
    ("previousApp", "Previous app"),
    ("exitApp", "Exit app"),
    ("power", "Power"),
    ("none", "Nothing"),
)

#: Controls a person can put a system action on.
SYSTEM_CONTROLS = ("a", "b", "c", "d", "ok")

#: Where they sit before anyone changes them.
DEFAULT_SYSTEM_BINDINGS: dict[str, str] = {
    "a": "brightnessUp",
    "b": "brightnessDown",
    "c": "volumeUp",
    "d": "volumeDown",
    "ok": "openMenu",
}


@dataclass(frozen=True)
class ShellAction:
    """A joystick action while no game is on the panel."""

    kind: str  # "next", "previous", "apply", "power", "open"
    value: str = ""


#: The controls a player can rebind, in the order a settings screen shows them.
CONTROLS = ("up", "down", "left", "right", "a", "b", "c", "d", "ok")

#: Everything a gamepad can offer, on top of what the module has.
PAD_CONTROLS = CONTROLS + ("lb", "rb", "lt", "rt", "start", "select", "l3", "r3", "home")

MODULE, GAMEPAD = "module", "gamepad"


@dataclass(frozen=True)
class Profile:
    """One kind of input device, and what its controls are called.

    A control id like "c" is the same idea on both devices, but it is
    silkscreened C on the module and printed X on an Xbox pad. Sharing the id
    keeps one binding vocabulary; the labels stop the settings screen lying
    about which button you are about to press.
    """

    id: str
    name: str
    controls: tuple[str, ...]
    labels: dict[str, str]

    def label(self, control: str) -> str:
        return self.labels.get(control, control.upper())


ARROWS = {"up": "Up", "down": "Down", "left": "Left", "right": "Right"}

PROFILES: dict[str, Profile] = {
    MODULE: Profile(
        id=MODULE,
        name="Mini-joystick module",
        controls=CONTROLS,
        labels={
            **ARROWS,
            "a": "A",
            "b": "B",
            "c": "C",
            "d": "D",
            "ok": "Stick press",
        },
    ),
    GAMEPAD: Profile(
        id=GAMEPAD,
        name="Gamepad",
        controls=PAD_CONTROLS,
        labels={
            **ARROWS,
            "a": "A",
            "b": "B",
            "c": "X",
            "d": "Y",
            "ok": "Stick click",
            "lb": "LB",
            "rb": "RB",
            "lt": "LT",
            "rt": "RT",
            "start": "Start",
            "select": "Select",
            "l3": "L3",
            "r3": "R3",
            "home": "Home",
        },
    ),
}

DEFAULT_PROFILE = MODULE


def profile(name: str) -> Profile:
    return PROFILES.get(name, PROFILES[DEFAULT_PROFILE])


# What the extra gamepad controls reach for, tried in order. The shoulders get
# the secondary actions that would otherwise need a spare face button, and
# Start pauses because that is what Start has always done.
PAD_FALLBACKS: dict[Button, tuple[str, ...]] = {
    Button.LB: ("rotateCcw", "hold", "left"),
    Button.RB: ("rotateCw", "hold", "right"),
    Button.LT: ("softDrop", "down"),
    Button.RT: ("fire", "flap", "hardDrop", "drop"),
    Button.START: ("togglePause",),
    Button.SELECT: ("restart",),
    Button.L3: ("togglePause",),
    Button.R3: ("fire", "flap"),
    # Home is the way out, never a game action.
    Button.HOME: (),
}


def control_name(event: JoystickEvent) -> str:
    """Which rebindable control an event came from, if any."""
    if event.kind == "direction":
        return event.direction.value if event.direction != Direction.NEUTRAL else ""
    if event.kind == "button" and event.button is not None:
        return event.button.value
    return ""


def default_bindings(actions: set[str], device: str = DEFAULT_PROFILE) -> dict[str, str]:
    """What each control does on ``device`` before anything is rebound."""
    chosen = profile(device)
    resolved: dict[str, str] = {}
    for direction in (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT):
        direct = DIRECTION_ACTIONS.get(direction, "")
        for candidate in ([direct] if direct else []) + list(DIRECTION_FALLBACKS.get(direction, ())):
            if candidate in actions:
                resolved[direction.value] = candidate
                break

    fallbacks = dict(BUTTON_FALLBACKS)
    if chosen.id == GAMEPAD:
        fallbacks.update(PAD_FALLBACKS)
    for button, candidates in fallbacks.items():
        if button.value not in chosen.controls:
            continue
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

    # A shoulder or Start can only have come from a pad, so both tables apply.
    for candidate in BUTTON_FALLBACKS.get(event.button, ()) or PAD_FALLBACKS.get(event.button, ()):
        if candidate in actions:
            return candidate
    return ""


#: Button presses count on the way down or as a click, so both the I2C
#: module (which reports clicks) and a gamepad (which reports presses) work.
PRESS_EVENTS = (ButtonEvent.PRESS_DOWN, ButtonEvent.SINGLE_CLICK)


def shell_action(
    event: JoystickEvent,
    menu_open: bool = False,
    bindings: dict[str, str] | None = None,
) -> ShellAction | None:
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
        # Closed, the stick still flicks through apps directly.
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

    # A control the owner has bound wins over anything below, except while the
    # menu is open, where the buttons have to mean pick and cancel.
    if not menu_open and bindings:
        chosen = bindings.get(control_name(event), "")
        if chosen == "none":
            return None
        if chosen:
            return ShellAction(kind=chosen)

    if menu_open:
        if event.button in (Button.OK, Button.A, Button.START):
            return ShellAction(kind="select")
        if event.button == Button.HOME:
            return ShellAction(kind="closeMenu")
        if event.button in (Button.B, Button.D, Button.SELECT):
            return ShellAction(kind="closeMenu")
        return None

    # Start now has its own control rather than collapsing onto the stick
    # press, so the way into the menu has to name both.
    if event.button in (Button.OK, Button.START, Button.HOME):
        return ShellAction(kind="openMenu")
    if event.button == Button.A:
        return ShellAction(kind="brightnessUp")
    if event.button == Button.B:
        return ShellAction(kind="brightnessDown")
    if event.button == Button.C:
        return ShellAction(kind="openMenu")
    return None


__all__ = [
    "PROFILES",
    "PAD_CONTROLS",
    "Profile",
    "profile",
    "MODULE",
    "GAMEPAD",
    "DEFAULT_PROFILE",
    "SYSTEM_ACTIONS",
    "SYSTEM_CONTROLS",
    "DEFAULT_SYSTEM_BINDINGS",
    "game_action",
    "shell_action",
    "ShellAction",
    "DIRECTION_ACTIONS",
    "DIRECTION_FALLBACKS",
    "BUTTON_FALLBACKS",
    "REPEATABLE",
]
