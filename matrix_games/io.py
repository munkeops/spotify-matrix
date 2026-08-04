"""File based bridge between the API process and the matrix runtime.

The runtime renders in its own process, so controller input arrives as a small
sequenced JSON queue and the runtime publishes state back the same way. The
sequence numbers mean a command is never dropped or applied twice.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def read_commands(path: Path | None, last_seq: int) -> tuple[list[str], int]:
    """Drain queued controller commands, returning everything newer than ``last_seq``."""
    if path is None or not path.exists():
        return [], last_seq
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return [], last_seq
    entries = payload.get("commands", []) if isinstance(payload, dict) else []
    pairs = [
        (int(entry.get("seq", 0) or 0), str(entry.get("action", "")))
        for entry in entries
        if isinstance(entry, dict) and entry.get("action")
    ]
    if not pairs:
        return [], last_seq
    highest = max(seq for seq, _ in pairs)
    if highest < last_seq:
        # The API restarted and rewound its counter, so replay from the start.
        last_seq = 0
    fresh = sorted((pair for pair in pairs if pair[0] > last_seq), key=lambda pair: pair[0])
    return [action for _, action in fresh], max(last_seq, highest)


def write_state(path: Path | None, snapshot: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        payload = {**snapshot, "updatedAt": time.time()}
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file)
        for _ in range(3):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                # Windows refuses the swap while the API has the file open.
                time.sleep(0.01)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file)
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass


__all__ = ["read_commands", "write_state"]
