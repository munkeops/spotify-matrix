"""Discovery of installable game plugins.

A game is a widget package: a directory with a ``widget.toml`` whose
``[widget] kind`` is ``"game"``, plus a Python entrypoint exposing a
:class:`assistant_matrix_sdk.game.GameWidget` subclass.

Two roots are searched:

* ``store_widgets/`` beside the app, which is where the games that ship with
  Assistant Matrix live.
* ``<data>/widgets/packages/``, where the Store installs anything you add.

Manifests are read without importing anything, so listing the arcade never
executes plugin code. The entrypoint is imported only when a game is created.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from assistant_matrix_sdk.game import GameWidget

#: Games that ship with the app.
BUNDLED_DIR = Path(os.environ.get("ASSISTANT_MATRIX_BUNDLED_WIDGETS", Path(__file__).resolve().parent.parent / "store_widgets"))

GAME_KIND = "game"
DEFAULT_LAYOUT = "dpad"


@dataclass(frozen=True)
class GameSpec:
    """Everything the host needs about a game without importing it."""

    game_id: str
    widget_id: str
    name: str
    summary: str
    layout: str
    actions: tuple[str, ...]
    package_dir: Path
    entrypoint: str
    version: str = "1.0.0"
    author: str = "Assistant Matrix"
    config: list[dict[str, Any]] = field(default_factory=list)
    bundled: bool = True

    @property
    def mode(self) -> str:
        return self.game_id

    @property
    def preview_path(self) -> Path:
        return self.package_dir / "previews" / "matrix-64.png"

    def load(self) -> type[GameWidget]:
        return load_game_class(self)

    def create(
        self,
        config: dict[str, Any] | None = None,
        seed: int | None = None,
        store: Any = None,
        audio: Any = None,
    ) -> GameWidget:
        return self.load()(config or {}, seed, store, audio)

    @property
    def sounds_dir(self) -> Path:
        return self.package_dir / "sounds"


def _spec_from_manifest(package_dir: Path, *, bundled: bool) -> GameSpec | None:
    manifest_path = package_dir / "widget.toml"
    if not manifest_path.exists():
        return None
    try:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    widget = payload.get("widget", {})
    if widget.get("kind") != GAME_KIND:
        return None
    widget_id = str(widget.get("id", "") or "")
    entrypoint = str(widget.get("entrypoint", "") or "")
    if not widget_id or ":" not in entrypoint:
        return None
    return GameSpec(
        game_id=widget_id.split(".", 1)[-1],
        widget_id=widget_id,
        name=str(widget.get("name", widget_id)),
        summary=str(widget.get("summary", "")),
        layout=str(widget.get("layout", DEFAULT_LAYOUT) or DEFAULT_LAYOUT),
        actions=tuple(widget.get("actions", []) or ()),
        package_dir=package_dir,
        entrypoint=entrypoint,
        version=str(widget.get("version", "1.0.0")),
        author=str(widget.get("author", "Assistant Matrix")),
        config=list(payload.get("config", []) or []),
        bundled=bundled,
    )


def discover(installed_dir: Path | None = None) -> dict[str, GameSpec]:
    """Every game plugin available, keyed by game id.

    An installed package shadows a bundled one with the same id, so a user can
    upgrade a shipped game by installing a newer build of it.
    """
    specs: dict[str, GameSpec] = {}
    roots: list[tuple[Path, bool]] = [(BUNDLED_DIR, True)]
    if installed_dir is not None:
        roots.append((installed_dir, False))
    for root, bundled in roots:
        if not root.is_dir():
            continue
        for package_dir in sorted(root.iterdir()):
            if not package_dir.is_dir():
                continue
            spec = _spec_from_manifest(package_dir, bundled=bundled)
            if spec is not None:
                specs[spec.game_id] = spec
    return specs


def load_game_class(spec: GameSpec) -> type[GameWidget]:
    """Import a package's entrypoint under a name unique to that package.

    Every package uses the same ``renderer.widget`` path, so importing them
    normally would make the second one collide with the first.
    """
    module_name, _, object_name = spec.entrypoint.partition(":")
    unique = f"matrix_games._plugins.{spec.widget_id.replace('.', '_')}.{module_name.replace('.', '_')}"
    cached = sys.modules.get(unique)
    if cached is not None:
        return getattr(cached, object_name)

    module_path = spec.package_dir.joinpath(*module_name.split(".")).with_suffix(".py")
    if not module_path.exists():
        raise ValueError(f"Game {spec.widget_id} entrypoint {spec.entrypoint} is missing at {module_path}.")

    loader_spec = importlib.util.spec_from_file_location(unique, module_path)
    if loader_spec is None or loader_spec.loader is None:
        raise ValueError(f"Could not load game {spec.widget_id} from {module_path}.")
    module = importlib.util.module_from_spec(loader_spec)
    sys.modules[unique] = module
    # On the path so a package can split itself across several modules.
    package_root = str(spec.package_dir)
    added = package_root not in sys.path
    if added:
        sys.path.insert(0, package_root)
    try:
        loader_spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(unique, None)
        raise
    finally:
        if added and package_root in sys.path:
            sys.path.remove(package_root)

    game_class = getattr(module, object_name, None)
    if game_class is None or not (isinstance(game_class, type) and issubclass(game_class, GameWidget)):
        raise ValueError(f"Game {spec.widget_id} entrypoint {spec.entrypoint} is not a GameWidget subclass.")
    return game_class


def _module_name(spec: GameSpec) -> str:
    module_path = spec.entrypoint.partition(":")[0]
    return f"matrix_games._plugins.{spec.widget_id.replace('.', '_')}.{module_path.replace('.', '_')}"


def load_module(spec: GameSpec):
    """The imported plugin module, for its constants and helpers."""
    load_game_class(spec)
    return sys.modules[_module_name(spec)]


def demo_instance(spec: GameSpec) -> GameWidget:
    """A game posed mid-play for preview tiles, if the package provides one."""
    game_class = load_game_class(spec)
    demo = getattr(load_module(spec), "demo_snapshot", None)
    if demo is not None:
        posed = demo()
        if isinstance(posed, GameWidget):
            return posed
    return game_class({}, 1)


__all__ = ["GameSpec", "BUNDLED_DIR", "discover", "load_game_class", "load_module", "demo_instance", "GAME_KIND"]
