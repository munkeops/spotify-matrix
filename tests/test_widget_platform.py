from __future__ import annotations

import importlib
import json
import sys
import tarfile
from pathlib import Path


SERVICE_MODULES = [
    "src.domain.services.config_service",
    "src.domain.services.runtime_service",
    "src.domain.services.widget_registry_service",
    "src.domain.services.display_policy_service",
    "src.domain.services.display_policy_runner_service",
    "src.domain.services.widget_store_service",
]


def reload_services(monkeypatch, data_dir: Path, store_index: Path | None = None):
    monkeypatch.setenv("SPOTIFY_MATRIX_DATA_DIR", str(data_dir))
    if store_index is None:
        monkeypatch.delenv("ASSISTANT_MATRIX_WIDGET_STORE_INDEX", raising=False)
    else:
        monkeypatch.setenv("ASSISTANT_MATRIX_WIDGET_STORE_INDEX", str(store_index))

    for name in SERVICE_MODULES:
        sys.modules.pop(name, None)

    config_module = importlib.import_module("src.domain.services.config_service")
    registry_module = importlib.import_module("src.domain.services.widget_registry_service")
    store_module = importlib.import_module("src.domain.services.widget_store_service")
    policy_module = importlib.import_module("src.domain.services.display_policy_service")
    runner_module = importlib.import_module("src.domain.services.display_policy_runner_service")
    return config_module, registry_module, store_module, policy_module, runner_module


def create_widget_archive(tmp_path: Path, widget_id: str = "example.local", version: str = "0.1.0") -> Path:
    package_dir = tmp_path / "package"
    renderer_dir = package_dir / "renderer"
    renderer_dir.mkdir(parents=True)
    (renderer_dir / "__init__.py").write_text("", encoding="utf-8")
    (renderer_dir / "widget.py").write_text(
        """from assistant_matrix_sdk import MatrixCanvas, Widget, WidgetContext

class LocalWidget(Widget):
    def render(self, canvas: MatrixCanvas, context: WidgetContext) -> None:
        canvas.background("#000000")
        canvas.text(2, 2, context.config.get("message", "HI"), "#ffffff")
""",
        encoding="utf-8",
    )
    (package_dir / "widget.toml").write_text(
        f"""[widget]
id = "{widget_id}"
name = "Local Widget"
version = "{version}"
summary = "Runnable local widget."
author = "Assistant Matrix"
category = "custom"
runtime = "python"
entrypoint = "renderer.widget:LocalWidget"
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

    archive_path = tmp_path / f"{widget_id}-{version}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in package_dir.rglob("*"):
            archive.add(path, arcname=path.relative_to(package_dir))
    return archive_path


def write_store_index(path: Path, archive_path: Path, widget_id: str = "example.local") -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "widgets": [
                    {
                        "id": widget_id,
                        "name": "Local Widget",
                        "version": "0.1.0",
                        "summary": "Runnable local widget.",
                        "category": "custom",
                        "author": "Assistant Matrix",
                        "archiveUrl": str(archive_path),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def write_store_index_payload(path: Path, widgets: list[dict]) -> None:
    path.write_text(json.dumps({"schemaVersion": 1, "widgets": widgets}), encoding="utf-8")


def test_store_index_can_come_from_saved_config(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    index_path = tmp_path / "store-index.json"
    index_path.write_text(
        json.dumps({"schemaVersion": 1, "widgets": [{"id": "example.remote", "name": "Remote", "version": "0.1.0", "summary": "Remote", "category": "custom"}]}),
        encoding="utf-8",
    )

    config_module, _, store_module, _, _ = reload_services(monkeypatch, data_dir)
    config = config_module.config_service.get_config()
    config.store.indexUrl = str(index_path)
    config_module.config_service.save_config(config)

    widgets = store_module.widget_store_service.list_widgets().widgets

    assert [widget.id for widget in widgets] == ["example.remote"]


def test_install_configure_apply_and_uninstall_widget(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = create_widget_archive(tmp_path)
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path)
    config_module, registry_module, store_module, policy_module, _ = reload_services(monkeypatch, data_dir, index_path)

    registry_module.runtime_service.apply = lambda: {"stub": True}

    store_module.widget_store_service.install_widget("example.local")
    widget = registry_module.widget_registry_service.get_local_widget("example.local")
    assert widget is not None
    assert widget.configurable is True
    assert (data_dir / "widgets" / "packages" / "example.local" / "widget.toml").exists()

    assert registry_module.widget_registry_service.get_widget_config("example.local")["message"] == "HI"
    registry_module.widget_registry_service.update_widget_config("example.local", {"message": "OK"})
    assert registry_module.widget_registry_service.get_widget_config("example.local")["message"] == "OK"

    _, runtime = registry_module.widget_registry_service.apply_widget("example.local")
    assert runtime == {"stub": True}
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "widget"
    assert saved.display.widgetId == "example.local"

    from src.domain.models.widget_schemas import DisplayPolicy, DisplayRotationItem, DisplayTriggerRule

    policy_module.display_policy_service.save_policy(
        DisplayPolicy(
            activeWidgetId="example.local",
            rotation=[DisplayRotationItem(widgetId="example.local", enabled=True)],
            triggers=[DisplayTriggerRule(event="test.event", widgetId="example.local", enabled=True)],
        )
    )

    store_module.widget_store_service.uninstall_widget("example.local")

    assert registry_module.widget_registry_service.get_local_widget("example.local") is None
    assert not (data_dir / "widgets" / "packages" / "example.local").exists()
    assert not (data_dir / "widgets" / "config" / "example.local.json").exists()
    saved = config_module.config_service.get_config()
    assert saved.display.mode == "spotify"
    assert saved.display.widgetId == ""
    policy = policy_module.display_policy_service.get_policy()
    assert policy.activeWidgetId == "core.spotify"
    assert policy.rotation == []
    assert policy.triggers == []


def test_install_rejects_store_widget_without_archive(tmp_path, monkeypatch):
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
        store_module.widget_store_service.install_widget("example.missing")
    except ValueError as exc:
        assert "archiveUrl" in str(exc)
    else:
        raise AssertionError("Expected missing archiveUrl to fail install.")

    assert registry_module.widget_registry_service.get_local_widget("example.missing") is None
    assert store_module.widget_store_service.read_installed_widgets() == []


def test_install_rejects_archive_with_mismatched_manifest_id(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = create_widget_archive(tmp_path, widget_id="example.actual")
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path, widget_id="example.expected")
    _, registry_module, store_module, _, _ = reload_services(monkeypatch, data_dir, index_path)

    try:
        store_module.widget_store_service.install_widget("example.expected")
    except ValueError as exc:
        assert "does not match store id" in str(exc)
    else:
        raise AssertionError("Expected mismatched manifest id to fail install.")

    assert registry_module.widget_registry_service.get_local_widget("example.expected") is None
    assert not (data_dir / "widgets" / "packages" / "example.expected").exists()
    assert store_module.widget_store_service.read_installed_widgets() == []


def test_install_rejects_unsafe_archive_links(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("widget.toml")
        content = b"""[widget]
id = "example.unsafe"
name = "Unsafe"
version = "0.1.0"
summary = "Unsafe archive."
runtime = "python"
entrypoint = "renderer.widget:LocalWidget"
"""
        info.size = len(content)
        import io

        archive.addfile(info, io.BytesIO(content))
        link = tarfile.TarInfo("renderer/link.py")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside.py"
        archive.addfile(link)
    index_path = tmp_path / "store-index.json"
    write_store_index(index_path, archive_path, widget_id="example.unsafe")
    _, _, store_module, _, _ = reload_services(monkeypatch, data_dir, index_path)

    try:
        store_module.widget_store_service.install_widget("example.unsafe")
    except ValueError as exc:
        assert "Unsafe archive link" in str(exc)
    else:
        raise AssertionError("Expected unsafe archive link to fail install.")

    assert not (data_dir / "widgets" / "packages" / "example.unsafe").exists()
    assert store_module.widget_store_service.read_installed_widgets() == []


def test_display_event_uses_highest_priority_trigger(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    _, registry_module, _, policy_module, runner_module = reload_services(monkeypatch, data_dir)

    calls: list[str] = []

    def fake_apply(widget_id, values=None):
        calls.append(widget_id)
        return registry_module.widget_registry_service.get_local_widget(widget_id), {"widget": widget_id}

    registry_module.widget_registry_service.apply_widget = fake_apply

    from src.domain.models.widget_schemas import DisplayPolicy, DisplayTriggerRule

    policy_module.display_policy_service.save_policy(
        DisplayPolicy(
            mode="single",
            activeWidgetId="core.clock",
            triggers=[
                DisplayTriggerRule(event="spotify.playback_started", widgetId="core.agent", enabled=True, priority=10, minDurationSeconds=0),
                DisplayTriggerRule(event="spotify.playback_started", widgetId="core.spotify", enabled=True, priority=50, minDurationSeconds=0),
            ],
        )
    )

    state, runtime, widget_id = runner_module.display_policy_runner_service.trigger_event("spotify.playback_started")
    unmatched_state, unmatched_runtime, unmatched_widget_id = runner_module.display_policy_runner_service.trigger_event("missing.event")

    assert widget_id == "core.spotify"
    assert runtime == {"widget": "core.spotify"}
    assert state.activeWidgetId == "core.spotify"
    assert state.activeEvent == "spotify.playback_started"
    assert calls == ["core.spotify"]
    assert unmatched_widget_id is None
    assert unmatched_runtime is None
    assert unmatched_state.lastError is None
