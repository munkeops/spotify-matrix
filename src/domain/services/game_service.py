"""Command queue and live frame bridge for the matrix games.

The matrix runtime is a separate process, so the API hands it controller input
through a small append-only JSON queue per game and reads back the frame the
runtime publishes. Both files live under the data directory.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from matrix_games import GameSpec, discover
from src.domain.models.api_schemas import GameFrame
from src.domain.services.config_service import config_service

# Commands older than this are dropped from the queue file; the runtime only
# needs the tail because it tracks the highest sequence it has already applied.
QUEUE_LIMIT = 64

# The runtime republishes a frame a few times a second while it is drawing, so
# anything older than this means nothing is playing right now.
STALE_SECONDS = 4.0


def _safe_game_id(game_id: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not game_id or any(character not in allowed for character in game_id):
        raise ValueError(f"Invalid game id {game_id}.")
    return game_id


class GameService:
    @property
    def state_dir(self) -> Path:
        return config_service.data_dir / "apps" / "state"

    def input_path(self, game_id: str) -> Path:
        return self.state_dir / f"{_safe_game_id(game_id)}-input.json"

    def state_path(self, game_id: str) -> Path:
        return self.state_dir / f"{_safe_game_id(game_id)}-state.json"

    @property
    def scores_dir(self) -> Path:
        return config_service.data_dir / "apps" / "scores"

    def scores_path(self, game_id: str) -> Path:
        return self.scores_dir / f"{_safe_game_id(game_id)}.json"

    def read_scores(self, game_id: str) -> dict[str, Any]:
        """High scores a game has saved, straight off disk."""
        from assistant_matrix_sdk.store import GameStore

        return GameStore(self.scores_path(_safe_game_id(game_id))).snapshot()

    def clear_scores(self, game_id: str) -> dict[str, Any]:
        from assistant_matrix_sdk.store import GameStore

        store = GameStore(self.scores_path(_safe_game_id(game_id)))
        store.clear()
        return store.snapshot()

    def packages_dir(self) -> Path:
        return config_service.data_dir / "apps" / "packages"

    def specs(self) -> dict[str, GameSpec]:
        """Every game app available right now, bundled or installed."""
        return discover(self.packages_dir())

    def spec(self, game_id: str) -> GameSpec | None:
        return self.specs().get(game_id)

    def require_spec(self, game_id: str) -> GameSpec:
        spec = self.spec(_safe_game_id(game_id))
        if spec is None:
            raise ValueError(f"Unknown game {game_id}.")
        return spec

    def app_package_dir(self, app_id: str) -> Path:
        """Where a app's package lives: installed if present, else bundled."""
        installed = self.packages_dir() / app_id
        if (installed / "app.toml").exists():
            return installed
        for spec in self.specs().values():
            if spec.app_id == app_id:
                return spec.package_dir
        return installed

    def active_game_id(self) -> str:
        config = config_service.get_config()
        if config.runtime.testPattern or config.display.mode != "app":
            return ""
        app_id = config.display.appId
        for game_id, spec in self.specs().items():
            if spec.app_id == app_id:
                return game_id
        return ""

    def queue_command(self, game_id: str, action: str, player: int = 0) -> int:
        # Reject unknown games here rather than leaving a queue file nothing reads.
        self.require_spec(game_id)
        path = self.input_path(game_id)
        payload = self._read_json(path)
        commands = payload.get("commands", []) if isinstance(payload, dict) else []
        commands = [command for command in commands if isinstance(command, dict) and command.get("action")]
        seq = max((int(command.get("seq", 0) or 0) for command in commands), default=0) + 1
        commands.append({"seq": seq, "action": action, "player": int(player), "at": time.time()})
        self._write_json(path, {"seq": seq, "commands": commands[-QUEUE_LIMIT:]})
        return seq

    def read_state(self, game_id: str) -> GameFrame | None:
        payload = self._read_json(self.state_path(game_id))
        if not isinstance(payload, dict) or not payload:
            return None
        return GameFrame.model_validate(payload)

    def read_raw_state(self, game_id: str) -> dict[str, Any]:
        payload = self._read_json(self.state_path(game_id))
        return payload if isinstance(payload, dict) else {}

    def is_live(self, state: GameFrame | None) -> bool:
        if state is None or not state.updatedAt:
            return False
        return (time.time() - state.updatedAt) <= STALE_SECONDS

    def _read_json(self, path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(value, file)
        for _ in range(5):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                # Windows refuses the swap while the runtime has the file open.
                time.sleep(0.01)
        # Last resort: overwrite in place. The runtime tolerates a torn read and
        # picks the command up on its next frame because sequences are retained.
        with path.open("w", encoding="utf-8") as file:
            json.dump(value, file)
        temp_path.unlink(missing_ok=True)


game_service = GameService()
