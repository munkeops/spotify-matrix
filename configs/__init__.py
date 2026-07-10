"""Load TOML from `spotify-matrix/configs`."""

from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

try:
    import toml
except ModuleNotFoundError:
    toml = None

_CONFIG_DIR = Path(__file__).resolve().parent


def load_config(name: str) -> dict:
    path = _CONFIG_DIR / f"{name}.toml"
    if tomllib is not None:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    if toml is not None:
        with open(path, "r", encoding="utf-8") as f:
            return toml.load(f)
    raise RuntimeError("TOML support requires Python 3.11+ or the toml package.")


base_config = load_config("base_config")

__all__ = ["base_config", "load_config"]
