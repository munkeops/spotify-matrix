"""App runtime context values."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Asset:
    path: Path
    kind: str = "file"


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppContext:
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    assets_dir: Path | None = None
    frame_index: int = 0
    event: Event | None = None

    def asset(self, relative_path: str) -> Asset:
        if self.assets_dir is None:
            raise RuntimeError("AppContext.assets_dir is not set.")
        return Asset(path=self.assets_dir / relative_path)


# The names these had before apps were called apps.
#
# Kept on the module as well as the package, because importing
# straight from the module is just as common as importing from the
# package, and both used to work.
WidgetContext = AppContext
