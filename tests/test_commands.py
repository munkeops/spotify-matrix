from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

from src.domain.models.api_schemas import CommandRequest, RuntimeState
from src.domain.models.app_schemas import DisplayPolicy, DisplayTriggerRule


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.runtime_service",
    "src.domain.services.app_registry_service",
    "src.domain.services.display_policy_service",
    "src.domain.services.display_policy_runner_service",
    "src.api.http.rest.commands",
]


def reload_command_stack(monkeypatch, data_dir: Path):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)
    config_module = importlib.import_module("src.domain.services.config_service")
    registry_module = importlib.import_module("src.domain.services.app_registry_service")
    policy_module = importlib.import_module("src.domain.services.display_policy_service")
    commands_module = importlib.import_module("src.api.http.rest.commands")
    return config_module, registry_module, policy_module, commands_module


def test_set_app_command_applies_local_app(tmp_path, monkeypatch):
    config_module, registry_module, _, commands_module = reload_command_stack(monkeypatch, tmp_path / "data")
    registry_module.runtime_service.apply = lambda: RuntimeState(running=True, pid=123)

    response = asyncio.run(commands_module.run_command(CommandRequest(command="set_app", value="core.clock")))

    saved = config_module.config_service.get_config()
    assert response.ok is True
    assert response.matched is True
    assert response.appId == "core.clock"
    assert saved.display.mode == "clock"
    assert saved.display.appId == ""


def test_trigger_event_command_uses_display_policy(tmp_path, monkeypatch):
    config_module, registry_module, policy_module, commands_module = reload_command_stack(monkeypatch, tmp_path / "data")
    registry_module.runtime_service.apply = lambda: RuntimeState(running=True, pid=321)
    policy_module.display_policy_service.save_policy(
        DisplayPolicy(
            mode="single",
            activeAppId="core.weather",
            triggers=[
                DisplayTriggerRule(
                    event="spotify.playback_started",
                    appId="core.spotify",
                    enabled=True,
                    priority=50,
                    minDurationSeconds=0,
                )
            ],
        )
    )

    response = asyncio.run(commands_module.run_command(CommandRequest(command="trigger_event", value="spotify.playback_started")))

    saved = config_module.config_service.get_config()
    assert response.ok is True
    assert response.matched is True
    assert response.appId == "core.spotify"
    assert saved.display.mode == "spotify"


def test_trigger_event_command_reports_unmatched_event(tmp_path, monkeypatch):
    _, _, policy_module, commands_module = reload_command_stack(monkeypatch, tmp_path / "data")
    policy_module.display_policy_service.save_policy(DisplayPolicy(mode="single", activeAppId="core.clock", triggers=[]))

    response = asyncio.run(commands_module.run_command(CommandRequest(command="trigger_event", value="missing.event")))

    assert response.ok is True
    assert response.matched is False
    assert response.appId is None
    assert response.runtime is None
