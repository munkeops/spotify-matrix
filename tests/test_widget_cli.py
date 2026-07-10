from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from assistant_matrix_sdk import cli


def test_init_creates_runnable_widget_package(tmp_path, monkeypatch):
    widget_dir = tmp_path / "user.hello"
    result = cli.command_init(
        argparse.Namespace(
            widget_id="user.hello",
            directory=str(widget_dir),
            name="Hello Matrix",
            summary="Starter hello widget.",
            author="Tester",
            category="custom",
            version="0.1.0",
            license="MIT",
            force=False,
        )
    )

    assert result == 0
    assert (widget_dir / "widget.toml").exists()
    assert (widget_dir / "README.md").exists()
    assert (widget_dir / "renderer" / "widget.py").exists()
    assert (widget_dir / "renderer" / "__init__.py").exists()
    assert (widget_dir / "previews").is_dir()
    assert (widget_dir / "assets").is_dir()

    manifest = cli.read_manifest(widget_dir / "widget.toml")
    assert cli.validate_manifest_data(manifest) == []
    assert manifest["widget"]["id"] == "user.hello"
    assert manifest["widget"]["entrypoint"] == "renderer.widget:WidgetRenderer"

    monkeypatch.syspath_prepend(str(widget_dir))
    preview_path = widget_dir / "previews" / "matrix-64.png"
    cli.command_preview(
        argparse.Namespace(
            widget="renderer.widget:UserHelloWidget",
            output=str(preview_path),
            config='{"message":"OK"}',
            size=64,
        )
    )
    assert preview_path.exists()


def test_package_and_publish_create_store_index(tmp_path):
    widget_dir = tmp_path / "user.publish"
    cli.command_init(
        argparse.Namespace(
            widget_id="user.publish",
            directory=str(widget_dir),
            name="Publish Widget",
            summary="Publish test widget.",
            author="Tester",
            category="custom",
            version="0.1.0",
            license="MIT",
            force=False,
        )
    )
    (widget_dir / "previews" / "matrix-64.png").write_bytes(b"png")
    (widget_dir / "previews" / "card.gif").write_bytes(b"gif")

    dist_dir = tmp_path / "dist"
    assert cli.command_package(argparse.Namespace(widget_dir=str(widget_dir), output_dir=str(dist_dir))) == 0
    archive_path = dist_dir / "user.publish-0.1.0.tar.gz"
    assert archive_path.exists()
    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    assert "widget.toml" in names
    assert "renderer/widget.py" in names

    store_dir = tmp_path / "store-dist"
    result = cli.command_publish(
        argparse.Namespace(
            widget_dir=str(widget_dir),
            store_dir=str(store_dir),
            base_url="https://store.example.com",
            index="store-index.json",
        )
    )
    assert result == 0

    index = json.loads((store_dir / "store-index.json").read_text(encoding="utf-8"))
    assert index["schemaVersion"] == 1
    assert len(index["widgets"]) == 1
    entry = index["widgets"][0]
    assert entry["id"] == "user.publish"
    assert entry["archiveUrl"] == "https://store.example.com/widgets/user.publish/0.1.0/user.publish-0.1.0.tar.gz"
    assert entry["previewGifUrl"] == "https://store.example.com/widgets/user.publish/0.1.0/previews/card.gif"
    assert entry["matrixPreviewUrl"] == "https://store.example.com/widgets/user.publish/0.1.0/previews/matrix-64.png"
    assert len(entry["sha256"]) == 64
    assert (store_dir / "widgets" / "user.publish" / "0.1.0" / "widget.toml").exists()
    assert (store_dir / "widgets" / "user.publish" / "0.1.0" / "user.publish-0.1.0.tar.gz").exists()


def test_init_refuses_non_empty_directory_without_force(tmp_path):
    widget_dir = tmp_path / "existing"
    widget_dir.mkdir()
    (widget_dir / "file.txt").write_text("occupied", encoding="utf-8")

    args = argparse.Namespace(
        widget_id="user.existing",
        directory=str(widget_dir),
        name="",
        summary="",
        author="Tester",
        category="custom",
        version="0.1.0",
        license="MIT",
        force=False,
    )

    try:
        cli.command_init(args)
    except FileExistsError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("Expected FileExistsError")
