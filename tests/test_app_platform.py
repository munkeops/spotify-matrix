from __future__ import annotations

import importlib
import json
import sys
import tarfile
from pathlib import Path
import pytest


SERVICE_MODULES = [
    "src.domain.services.config_service",
    # Reloaded with the rest so it does not keep a previous test's data dir.
    "src.domain.services.game_service",
    "src.domain.services.runtime_service",
    "src.domain.services.app_registry_service",
    "src.domain.services.display_policy_service",
    "src.domain.services.display_policy_runner_service",
    "src.domain.services.app_store_service",
]


def reload_services(monkeypatch, data_dir: Path, store_index: Path | None = None):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    if store_index is None:
        monkeypatch.delenv("ASSISTANT_MATRIX_APP_STORE_INDEX", raising=False)
    else:
        monkeypatch.setenv("ASSISTANT_MATRIX_APP_STORE_INDEX", str(store_index))

    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)

    config_module = importlib.import_module("src.domain.services.config_service")
    importlib.import_module("src.domain.services.game_service")
    registry_module = importlib.import_module("src.domain.services.app_registry_service")
    store_module = importlib.import_module("src.domain.services.app_store_service")
    policy_module = importlib.import_module("src.domain.services.display_policy_service")
    runner_module = importlib.import_module("src.domain.services.display_policy_runner_service")
    return config_module, registry_module, store_module, policy_module, runner_module


def create_app_archive(tmp_path: Path, app_id: str = "example.local", version: str = "0.1.0") -> Path:
    package_dir = tmp_path / "package"
    renderer_dir = package_dir / "renderer"
    renderer_dir.mkdir(parents=True)
    (renderer_dir / "__init__.py").write_text("", encoding="utf-8")
    (renderer_dir / "app.py").write_text(
        """from assistant_matrix_sdk import MatrixCanvas, App, AppContext

class LocalApp(App):
    def render(self, canvas: MatrixCanvas, context: AppContext) -> None:
        canvas.background("#000000")
        canvas.text(2, 2, context.config.get("message", "HI"), "#ffffff")
""",
        encoding="utf-8",
    )
    (package_dir / "app.toml").write_text(
        f"""[app]
id = "{app_id}"
name = "Local App"
version = "{version}"
summary = "Runnable local app."
author = "Assistant Matrix"
category = "custom"
runtime = "python"
entrypoint = "renderer.app:LocalApp"
matrix_size = "64x64"
license = "MIT"

[preview]
description = "Preview"

[[config]]
key = "message"
label = "Message"
type = "string"
default = "HI"
""",
        encoding="utf-8",
    )

    archive_path = tmp_path / f"{app_id}-{version}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in package_dir.rglob("*"):
            archive.add(path, arcname=path.relative_to(package_dir))
    return archive_path


def write_store_index(path: Path, archive_path: Path, app_id: str = "example.local") -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "apps": [
                    {
                        "id": app_id,
                        "name": "Local App",
                        "version": "0.1.0",
                        "summary": "Runnable local app.",
                        "category": "custom",
                        "author": "Assistant Matrix",
                        "archiveUrl": str(archive_path),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def write_store_index_payload(path: Path, apps: list[dict]) -> None:
    path.write_text(json.dumps({"schemaVersion": 1, "apps": apps}), encoding="utf-8")


def test_store_index_can_come_from_saved_config(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    index_path = tmp_path / "store-index.json"
    index_path.write_text(
        json.dumps({"schemaVersion": 1, "apps": [{"id": "example.remote", "name": "Remote", "version": "0.1.0", "summary": "Remote", "category": "custom"}]}),
        encoding="utf-8",
    )

    config_module, _, store_module, _, _ = reload_services(monkeypatch, data_dir)
    config = config_module.config_service.get_config()
    config.store.indexUrl = str(index_path)
    config_module.config_service.save_config(config)

    apps = store_module.app_store_service.list_apps().apps

    assert [app.id for app in apps] == ["example.remote"]


def test_install_configure_apply_and_uninstall_app(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = create_app_archive(tmp_path)
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path)
    config_module, registry_module, store_module, policy_module, _ = reload_services(monkeypatch, data_dir, index_path)

    registry_module.runtime_service.apply = lambda: {"stub": True}

    store_module.app_store_service.install_app("example.local")
    app = registry_module.app_registry_service.get_local_app("example.local")
    assert app is not None
    assert app.configurable is True
    assert (data_dir / "apps" / "packages" / "example.local" / "app.toml").exists()

    assert registry_module.app_registry_service.get_app_config("example.local")["message"] == "HI"
    registry_module.app_registry_service.update_app_config("example.local", {"message": "OK"})
    assert registry_module.app_registry_service.get_app_config("example.local")["message"] == "OK"

    _, runtime = registry_module.app_registry_service.apply_app("example.local")
    assert runtime == {"stub": True}
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "app"
    assert saved.display.appId == "example.local"

    from src.domain.models.app_schemas import DisplayPolicy, DisplayRotationItem, DisplayTriggerRule

    policy_module.display_policy_service.save_policy(
        DisplayPolicy(
            activeAppId="example.local",
            rotation=[DisplayRotationItem(appId="example.local", enabled=True)],
            triggers=[DisplayTriggerRule(event="test.event", appId="example.local", enabled=True)],
        )
    )

    store_module.app_store_service.uninstall_app("example.local")

    assert registry_module.app_registry_service.get_local_app("example.local") is None
    assert not (data_dir / "apps" / "packages" / "example.local").exists()
    assert not (data_dir / "apps" / "config" / "example.local.json").exists()
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "spotify"
    assert saved.display.appId == ""
    policy = policy_module.display_policy_service.get_policy()
    assert policy.activeAppId == "core.spotify"
    assert policy.rotation == []
    assert policy.triggers == []


def test_install_rejects_store_app_without_archive(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    index_path = tmp_path / "store-index.json"
    write_store_index_payload(
        index_path,
        [
            {
                "id": "example.missing",
                "name": "Missing",
                "version": "0.1.0",
                "summary": "No package.",
                "category": "custom",
            }
        ],
    )
    _, registry_module, store_module, _, _ = reload_services(monkeypatch, data_dir, index_path)

    try:
        store_module.app_store_service.install_app("example.missing")
    except ValueError as exc:
        assert "archiveUrl" in str(exc)
    else:
        raise AssertionError("Expected missing archiveUrl to fail install.")

    assert registry_module.app_registry_service.get_local_app("example.missing") is None
    assert store_module.app_store_service.read_installed_apps() == []


def test_install_rejects_archive_with_mismatched_manifest_id(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = create_app_archive(tmp_path, app_id="example.actual")
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path, app_id="example.expected")
    _, registry_module, store_module, _, _ = reload_services(monkeypatch, data_dir, index_path)

    try:
        store_module.app_store_service.install_app("example.expected")
    except ValueError as exc:
        assert "does not match store id" in str(exc)
    else:
        raise AssertionError("Expected mismatched manifest id to fail install.")

    assert registry_module.app_registry_service.get_local_app("example.expected") is None
    assert not (data_dir / "apps" / "packages" / "example.expected").exists()
    assert store_module.app_store_service.read_installed_apps() == []


def test_install_rejects_unsafe_archive_links(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("app.toml")
        content = b"""[app]
id = "example.unsafe"
name = "Unsafe"
version = "0.1.0"
summary = "Unsafe archive."
runtime = "python"
entrypoint = "renderer.app:LocalApp"
"""
        info.size = len(content)
        import io

        archive.addfile(info, io.BytesIO(content))
        link = tarfile.TarInfo("renderer/link.py")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside.py"
        archive.addfile(link)
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path, app_id="example.unsafe")
    _, _, store_module, _, _ = reload_services(monkeypatch, data_dir, index_path)

    try:
        store_module.app_store_service.install_app("example.unsafe")
    except ValueError as exc:
        assert "Unsafe archive link" in str(exc)
    else:
        raise AssertionError("Expected unsafe archive link to fail install.")

    assert not (data_dir / "apps" / "packages" / "example.unsafe").exists()
    assert store_module.app_store_service.read_installed_apps() == []


def test_display_event_uses_highest_priority_trigger(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    _, registry_module, _, policy_module, runner_module = reload_services(monkeypatch, data_dir)

    calls: list[str] = []

    def fake_apply(app_id, values=None):
        calls.append(app_id)
        return registry_module.app_registry_service.get_local_app(app_id), {"app": app_id}

    registry_module.app_registry_service.apply_app = fake_apply

    from src.domain.models.app_schemas import DisplayPolicy, DisplayTriggerRule

    policy_module.display_policy_service.save_policy(
        DisplayPolicy(
            mode="single",
            activeAppId="core.clock",
            triggers=[
                DisplayTriggerRule(event="spotify.playback_started", appId="core.agent", enabled=True, priority=10, minDurationSeconds=0),
                DisplayTriggerRule(event="spotify.playback_started", appId="core.spotify", enabled=True, priority=50, minDurationSeconds=0),
            ],
        )
    )

    state, runtime, app_id = runner_module.display_policy_runner_service.trigger_event("spotify.playback_started")
    unmatched_state, unmatched_runtime, unmatched_app_id = runner_module.display_policy_runner_service.trigger_event("missing.event")

    assert app_id == "core.spotify"
    assert runtime == {"app": "core.spotify"}
    assert state.activeAppId == "core.spotify"
    assert state.activeEvent == "spotify.playback_started"
    assert calls == ["core.spotify"]
    assert unmatched_app_id is None
    assert unmatched_runtime is None
    assert unmatched_state.lastError is None


# --- the widget-to-app rename --------------------------------------------


def test_an_app_installed_before_the_rename_still_loads(tmp_path):
    """Its manifest is called widget.toml and its table is [widget]."""
    from assistant_matrix_sdk.manifest import manifest_path, manifest_section

    package = tmp_path / "core.legacy"
    package.mkdir()
    (package / "widget.toml").write_text('[widget]\nid = "core.legacy"\n', encoding="utf-8")

    assert manifest_path(package).name == "widget.toml"
    assert manifest_section({"widget": {"id": "core.legacy"}}) == {"id": "core.legacy"}


def test_a_new_manifest_wins_when_both_are_present(tmp_path):
    from assistant_matrix_sdk.manifest import manifest_path

    package = tmp_path / "core.both"
    package.mkdir()
    (package / "widget.toml").write_text("[widget]\n", encoding="utf-8")
    (package / "app.toml").write_text("[app]\n", encoding="utf-8")

    assert manifest_path(package).name == "app.toml"


def test_a_legacy_game_package_is_still_discovered(tmp_path):
    """The rename must not make an installed game vanish from the arcade."""
    from matrix_games import registry

    package = tmp_path / "core.oldgame"
    (package / "renderer").mkdir(parents=True)
    (package / "renderer" / "__init__.py").write_text("", encoding="utf-8")
    (package / "renderer" / "widget.py").write_text(
        "from assistant_matrix_sdk import GameWidget\n\n\n"
        "class OldGame(GameWidget):\n"
        "    game_id = 'oldgame'\n"
        "    id = 'core.oldgame'\n"
        "    name = 'Old Game'\n"
        "    actions = ('fire',)\n",
        encoding="utf-8",
    )
    (package / "widget.toml").write_text(
        '[widget]\n'
        'id = "core.oldgame"\n'
        'name = "Old Game"\n'
        'kind = "game"\n'
        'entrypoint = "renderer/widget.py:OldGame"\n',
        encoding="utf-8",
    )

    registry.invalidate_cache()
    found = registry.discover(installed_dir=tmp_path)
    registry.invalidate_cache()

    assert "oldgame" in found, f"legacy package not discovered: {sorted(found)}"


def test_the_old_sdk_names_still_import():
    import assistant_matrix_sdk as sdk

    assert sdk.GameWidget is sdk.GameApp
    assert sdk.WidgetPreview is sdk.AppPreview
    assert sdk.Widget is sdk.App


def test_a_config_from_before_the_rename_is_migrated():
    from src.domain.services.config_service import migrate_config

    payload, changed = migrate_config(
        {
            "display": {"mode": "widget", "widgetId": "core.tetris"},
            "store": {"indexUrl": "configs/widget_store_index.json"},
        }
    )

    assert changed
    assert payload["display"]["mode"] == "app"
    assert payload["display"]["appId"] == "core.tetris"
    assert "widgetId" not in payload["display"]
    assert payload["store"]["indexUrl"] == "configs/app_store_index.json"


def test_the_old_api_routes_still_answer():
    """A cached bundle or a script holding /api/widgets should not 404."""
    from src.server import create_app

    paths = {getattr(route, "path", "") for route in create_app().routes}

    assert "/api/apps/local" in paths
    assert "/api/widgets/local" in paths, "the old prefix is still served"


def test_a_bundled_app_cannot_be_uninstalled(tmp_path, monkeypatch):
    """They live in the image, so removing one would either fail or break
    the install until the next rebuild."""
    import importlib
    import sys

    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(tmp_path / "data"))
    for name in ("src.domain.services.config_service", "src.domain.services.app_store_service"):
        sys.modules.pop(name, None)
    module = importlib.import_module("src.domain.services.app_store_service")

    with pytest.raises(ValueError, match="not installed"):
        module.app_store_service.uninstall_app("core.tetris")


def test_uninstalling_clears_the_panel_if_it_was_showing():
    """Otherwise the display points at an app whose files have gone."""
    import inspect

    from src.domain.services import app_store_service as module

    source = inspect.getsource(module.AppStoreService.uninstall_app)

    assert 'config.display.mode = "spotify"' in source
    assert "remove_app_references" in source, "and any rotation or trigger using it"
