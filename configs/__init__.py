"""Load TOML from `spotify-matrix/configs`."""

from __future__ import annotations

from pathlib import Path

import toml

_CONFIG_DIR = Path(__file__).resolve().parent


def load_config(name: str) -> dict:
    path = _CONFIG_DIR / f"{name}.toml"
    with open(path, "r", encoding="utf-8") as f:
        return toml.load(f)


base_config = load_config("base_config")

__all__ = ["base_config", "load_config"]
