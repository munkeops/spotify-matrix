"""Guards that the container ships everything the app imports.

A missing ``COPY`` only shows up when the image runs, which is a slow and
confusing way to find out. These tests compare the Dockerfile against the
repository instead.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories that exist purely for development and never need to ship.
NON_RUNTIME = {"tests", "docs", "web", "logs", "data", "configs", "public", "scripts", "store_server"}


def local_packages() -> set[str]:
    """Top-level Python packages in the repo."""
    return {
        path.name
        for path in ROOT.iterdir()
        if path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith(".")
    }


def imported_top_level(paths: list[Path]) -> set[str]:
    """Top-level modules imported anywhere under ``paths``."""
    names: set[str] = set()
    for path in paths:
        files = [path] if path.is_file() else sorted(path.rglob("*.py"))
        for file in files:
            try:
                tree = ast.parse(file.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):  # pragma: no cover - nothing to check
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names.add(node.module.split(".")[0])
    return names


def dockerfile_copies() -> set[str]:
    """Paths the Dockerfile copies into the image."""
    copied: set[str] = set()
    for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^COPY\s+(?!--from)(.+)$", line.strip())
        if not match:
            continue
        parts = match.group(1).split()
        # Everything but the trailing destination.
        for part in parts[:-1]:
            copied.add(part.strip("./"))
    return copied


def test_dockerfile_ships_every_package_the_app_imports():
    app_sources = [ROOT / "src", ROOT / "spotify_matrix.py"]
    needed = imported_top_level(app_sources) & local_packages()
    # Anything those packages pull in transitively must ship too.
    for _ in range(3):
        extra = imported_top_level([ROOT / name for name in needed]) & local_packages()
        needed |= extra

    missing = sorted(needed - dockerfile_copies() - NON_RUNTIME)
    assert not missing, f"Dockerfile does not COPY these imported packages: {missing}"


def test_runtime_entrypoints_are_copied():
    copied = dockerfile_copies()
    for required in ("src", "spotify_matrix.py", "assistant_matrix_sdk", "configs"):
        assert required in copied, f"Dockerfile must COPY {required}"


def test_pyproject_lists_every_shipped_package():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for package in ("src", "assistant_matrix_sdk", "matrix_games", "mini_joystick"):
        assert f'include = "{package}"' in pyproject, f"pyproject packages must list {package}"
