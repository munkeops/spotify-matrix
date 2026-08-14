# Game Apps

Games are not built into Assistant Matrix. Each one is a app package that the
host discovers on disk, so adding a game is dropping in a folder — no change to
the app, no restart.

## Where games live

| Directory | Contents |
|---|---|
| `store_apps/` | The games that ship with Assistant Matrix |
| `<data>/apps/packages/` | Anything installed from the Store |

Both roots are scanned. An installed package **shadows** a bundled one with the
same id, so you can replace a shipped game with your own build of it.

Manifests are read without importing anything, so listing the arcade never runs
app code. A package's entrypoint is imported only when its game is created,
and a package that fails to parse is skipped rather than taking the app down.

## Anatomy of a game package

```text
core.snake/
  app.toml          # the contract
  README.md
  renderer/
    __init__.py
    app.py          # a GameApp subclass
  previews/
    matrix-64.png      # tile shown in the app
```

`app.toml` is an ordinary app manifest with three extra keys:

```toml
[app]
id = "core.snake"
name = "Snake"
version = "1.0.0"
summary = "Eat, grow, and do not bite yourself."
category = "games"
runtime = "python"
entrypoint = "renderer.app:SnakeGame"
kind = "game"                                   # drives the controller path
layout = "dpad"                                 # which pad to render
actions = ["up", "down", "left", "right", "pause", "resume", "togglePause", "restart"]
```

`layout` is one of `dpad`, `horizontal`, `vertical`, `tap` or `tetris`. The app
and the joystick both read it to decide what controls to offer, and a game only
ever receives actions it declared.

## Writing one

Subclass `GameApp` and implement four methods. The host owns timing and IO,
so a game is pure enough to unit test on its own:

```python
from typing import Any

from PIL import Image

from assistant_matrix_sdk.config import ConfigField
from assistant_matrix_sdk.game import GameApp
from assistant_matrix_sdk.pixels import PANEL, draw_banner, fit_panel, new_frame


class DodgeGame(GameApp):
    game_id = "dodge"
    id = "core.dodge"
    name = "Dodge"
    summary = "Slide out of the way of falling blocks."
    layout = "horizontal"
    actions = ("left", "right")
    config_fields = [
        ConfigField.number("fallSpeed", label="Fall speed", default=26, minimum=10, maximum=60, step=2),
    ]

    def reset(self) -> None:
        """Start a new game. Called on construction and on restart."""
        self.player_x = 30
        self.score = 0

    def handle(self, action: str) -> None:
        """One controller action. Never called while paused or finished."""
        self.player_x += 3 if action == "right" else -3

    def advance(self, elapsed: float) -> None:
        """Move the game on by `elapsed` seconds. Never called while paused."""

    def hud(self) -> dict[str, Any]:
        """Label/value pairs shown beside the board in the app."""
        return {"Dodged": self.score}

    def render(self, size: int = PANEL) -> Image.Image:
        image, draw = new_frame()
        draw.rectangle((self.player_x, 54, self.player_x + 4, 57), fill=(96, 220, 255))
        if self.game_over:
            draw_banner(draw, ("GAME", "OVER"), (226, 234, 248))
        return fit_panel(image, size)
```

### Remembering things between sessions

The runtime restarts whenever the panel switches apps, so anything a game
wants to keep has to go to disk. Every game gets `self.store` for that:

```python
def reset(self) -> None:
    self.best = self.store.best          # highest score ever recorded
    self.level = self.store.get("level", 1)

def _on_level_up(self) -> None:
    self.store.set("level", self.level)  # saved immediately
```

**High scores need no code at all.** When a game finishes, the base class files
whatever `final_score()` returns — which defaults to a `score` attribute — so a
game with `self.score` gets a persisted best, a top ten and a play count for
free. Override `final_score()` to return something else, or `None` for a game
that has no meaningful score; it will still count plays.

| | |
|---|---|
| `store.best` | Highest score recorded |
| `store.plays` | Rounds finished |
| `store.top(n)` | Recent high scores, newest first on a tie |
| `store.get(key, default)` / `store.set(key, value)` | Anything else |
| `store.record_score(value)` | File a score yourself; True if it is a new best |

Scores live in `<data>/apps/scores/<game-id>.json` and are readable over the
API:

```bash
curl http://<pi-host>:3000/api/games/flappy/scores
curl -X DELETE http://<pi-host>:3000/api/games/flappy/scores   # reset
```

Constructing a game without a store gives an in-memory one, which is what tests
and preview tiles use, so nothing writes to disk by accident.

What the base class handles for you:

- `pause`, `resume`, `togglePause` and `restart`, so you never implement them.
- Setting `self.game_over = True` or `self.won = True` ends the round; a fire or
  drop button then starts a new one, but only after a short grace period so the
  final score stays readable.
- `self.random` is a seeded `random.Random`, which is what makes a game
  reproducible in tests.
- `self.config` holds the saved settings for your `config_fields`.

Optional: a module-level `demo_snapshot()` returning a posed game gives the app
a good-looking preview tile instead of an empty board.

The drawing helpers in `assistant_matrix_sdk.pixels` are the same ones the
shipped games use — `new_frame`, `fit_panel`, `draw_pixel_text`,
`draw_centered_text`, `draw_banner`, `shade` and `parse_color`.

## Building and installing

Generate the manifest from the class so the two can never drift:

```python
from renderer.app import DodgeGame

manifest = DodgeGame.manifest(entrypoint="renderer.app:DodgeGame")
```

Then package and publish it with the app CLI:

```bash
poetry run assistant-matrix-app validate app.toml
poetry run assistant-matrix-app package . --output-dir dist
poetry run assistant-matrix-app publish . --store-dir store-dist --base-url https://store.example.com
```

Install it from the Store, or drop the folder straight into
`<data>/apps/packages/`. Either way it appears in **Play** with the right
pad, gets a config drawer from its `config_fields`, and is drivable from the
mini-joystick — all from the manifest.

## How the host runs a game

1. Applying a game sets `display.mode = "app"` and `display.appId` to the
   package id, exactly like any other app.
2. The runtime sees `kind = "game"` in the manifest and drives the game loop
   instead of asking for a single frame.
3. Controller input arrives through a sequenced queue at
   `<data>/apps/state/<game-id>-input.json`, so presses are never dropped or
   replayed twice.
4. Each frame is published to `<game-id>-state.json` as a colour palette plus
   one row string per line, which is what the app mirrors on its canvas.

None of that is game-specific, which is why a new package needs no host changes.
