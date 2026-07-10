from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

import pytest

try:
    import PIL  # noqa: F401
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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

    if HAS_PIL:
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


def test_validate_rejects_bad_manifest_metadata(tmp_path):
    manifest_path = tmp_path / "widget.toml"
    cli.write_manifest(
        manifest_path,
        {
            "widget": {
                "id": "bad widget",
                "name": "Bad",
                "version": "first",
                "summary": "Invalid widget.",
                "runtime": "python",
                "entrypoint": "renderer.widget:WidgetRenderer",
                "category": "unknown",
                "matrix_size": "big",
            },
            "config": [
                {
                    "key": "mode",
                    "label": "Mode",
                    "type": "select",
                    "options": ["one", "two"],
                }
            ],
            "permissions": [{"name": "network"}],
            "triggers": [{"priority": 1}],
        },
    )

    errors = cli.validate_manifest_data(cli.read_manifest(manifest_path))

    assert any("widget.id" in error for error in errors)
    assert any("widget.version" in error for error in errors)
    assert any("widget.category" in error for error in errors)
    assert any("widget.matrix_size" in error for error in errors)
    assert any("options[0]" in error for error in errors)
    assert any("missing reason" in error for error in errors)
    assert any("missing event" in error for error in errors)


def test_package_requires_declared_entrypoint_and_previews(tmp_path):
    widget_dir = tmp_path / "user.missing"
    cli.command_init(
        argparse.Namespace(
            widget_id="user.missing",
            directory=str(widget_dir),
            name="Missing Preview",
            summary="Missing preview test widget.",
            author="Tester",
            category="custom",
            version="0.1.0",
            license="MIT",
            force=False,
        )
    )

    errors = cli.validate_widget_package_files(cli.read_manifest(widget_dir / "widget.toml"), widget_dir)

    assert "Missing preview.matrix_png file previews/matrix-64.png." in errors
    assert cli.command_package(argparse.Namespace(widget_dir=str(widget_dir), output_dir=str(tmp_path / "dist"))) == 1


def test_publish_allows_missing_optional_card_gif(tmp_path):
    widget_dir = tmp_path / "user.static"
    cli.command_init(
        argparse.Namespace(
            widget_id="user.static",
            directory=str(widget_dir),
            name="Static Preview",
            summary="Static preview test widget.",
            author="Tester",
            category="custom",
            version="0.1.0",
            license="MIT",
            force=False,
        )
    )
    (widget_dir / "previews" / "matrix-64.png").write_bytes(b"png")

    store_dir = tmp_path / "store-dist"
    assert cli.command_publish(
        argparse.Namespace(
            widget_dir=str(widget_dir),
            store_dir=str(store_dir),
            base_url="https://store.example.com",
            index="store-index.json",
        )
    ) == 0

    index = json.loads((store_dir / "store-index.json").read_text(encoding="utf-8"))
    entry = index["widgets"][0]
    assert entry["previewGifUrl"] == ""
    assert entry["matrixPreviewUrl"] == "https://store.example.com/widgets/user.static/0.1.0/previews/matrix-64.png"


def test_validate_store_accepts_published_index(tmp_path):
    widget_dir = tmp_path / "user.storecheck"
    cli.command_init(
        argparse.Namespace(
            widget_id="user.storecheck",
            directory=str(widget_dir),
            name="Store Check",
            summary="Store validation test widget.",
            author="Tester",
            category="custom",
            version="0.1.0",
            license="MIT",
            force=False,
        )
    )
    (widget_dir / "previews" / "matrix-64.png").write_bytes(b"png")
    store_dir = tmp_path / "store-dist"
    cli.command_publish(
        argparse.Namespace(
            widget_dir=str(widget_dir),
            store_dir=str(store_dir),
            base_url="https://store.example.com",
            index="store-index.json",
        )
    )

    index_path = store_dir / "store-index.json"

    assert cli.command_validate_store(argparse.Namespace(index=str(index_path))) == 0


def test_validate_store_rejects_bad_index(tmp_path):
    index_path = tmp_path / "store-index.json"
    index_path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "widgets": [
                    {
                        "id": "bad widget",
                        "name": "Bad",
                        "version": "first",
                        "summary": "Bad widget.",
                        "category": "unknown",
                        "sha256": "nope",
                    },
                    {
                        "id": "bad widget",
                        "name": "Duplicate",
                        "version": "0.1.0",
                        "summary": "Duplicate widget.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = cli.validate_store_index_data(cli.read_store_index(index_path))

    assert "schemaVersion must be 1." in errors
    assert any(".id may only contain" in error for error in errors)
    assert any(".id duplicates bad widget" in error for error in errors)
    assert any(".version should use semantic version" in error for error in errors)
    assert any(".category must be one of" in error for error in errors)
    assert any(".sha256 must be empty or a 64-character hex digest" in error for error in errors)
    assert cli.command_validate_store(argparse.Namespace(index=str(index_path))) == 1
