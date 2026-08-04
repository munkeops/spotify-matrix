"""Per-game persistent storage.

Games run in a process that restarts whenever the panel switches plugins, so
anything a game wants to remember between sessions — a high score, how many
times it has been played, which level you reached — has to live on disk.

A game gets one of these as ``self.store``. Writes are saved immediately and
atomically, because the runtime can be killed at any moment.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

#: How many past scores to keep. Enough for a leaderboard, small enough that
#: the file stays a single cheap write.
SCORE_HISTORY = 10


class GameStore:
    """A small key/value store plus a high score table, saved as JSON.

    Constructing one without a path gives an in-memory store, which is what
    tests and previews use.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._values: dict[str, Any] = {}
        self._scores: list[dict[str, Any]] = []
        self._plays = 0
        self._load()

    # --- values -----------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value
        self._save()

    def update(self, **values: Any) -> None:
        self._values.update(values)
        self._save()

    def clear(self) -> None:
        self._values = {}
        self._scores = []
        self._plays = 0
        self._save()

    # --- scores -----------------------------------------------------------

    @property
    def best(self) -> int:
        return int(self._scores[0]["score"]) if self._scores else 0

    @property
    def plays(self) -> int:
        return self._plays

    def top(self, limit: int = SCORE_HISTORY) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._scores[:limit]]

    def record_play(self) -> None:
        """Count a finished game that has no score, so plays still add up."""
        self._plays += 1
        self._save()

    def record_score(self, score: int, *, at: float | None = None) -> bool:
        """File a finished game. Returns True when it beat the previous best."""
        score = int(score)
        beaten = score > self.best
        self._plays += 1
        self._scores.append({"score": score, "at": at if at is not None else time.time()})
        self._scores.sort(key=lambda entry: (-int(entry["score"]), entry["at"]))
        del self._scores[SCORE_HISTORY:]
        self._save()
        return beaten

    # --- persistence ------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {"values": dict(self._values), "scores": self.top(), "plays": self._plays, "best": self.best}

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            # A corrupt file should cost you your scores, not the game.
            return
        if not isinstance(payload, dict):
            return
        values = payload.get("values")
        self._values = dict(values) if isinstance(values, dict) else {}
        scores = payload.get("scores")
        self._scores = [
            {"score": int(entry.get("score", 0)), "at": float(entry.get("at", 0.0))}
            for entry in (scores if isinstance(scores, list) else [])
            if isinstance(entry, dict)
        ]
        self._scores.sort(key=lambda entry: (-entry["score"], entry["at"]))
        del self._scores[SCORE_HISTORY:]
        try:
            self._plays = max(0, int(payload.get("plays", 0)))
        except (TypeError, ValueError):
            self._plays = 0

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {"values": self._values, "scores": self._scores, "plays": self._plays}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_name(self.path.name + ".tmp")
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
            for _ in range(3):
                try:
                    os.replace(temp_path, self.path)
                    return
                except PermissionError:
                    # Windows refuses the swap while a reader has the file open.
                    time.sleep(0.01)
            with self.path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
            temp_path.unlink(missing_ok=True)
        except OSError:
            # Losing a score is not worth crashing a game over.
            pass


__all__ = ["GameStore", "SCORE_HISTORY"]
