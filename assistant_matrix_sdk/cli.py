"""Command line tools for Assistant Matrix widget authors."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import sys
import tarfile
import tomllib
from pathlib import Path
from typing import Any

from assistant_matrix_sdk.context import WidgetContext
from assistant_matrix_sdk.widget import Widget


def load_widget(target: str) -> type[Widget]:
    if ":" not in target:
        raise ValueError("Widget target must use module.path:ClassName.")
    module_name, class_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    candidate = getattr(module, class_name)
    if not isinstance(candidate, type) or not issubclass(candidate, Widget):
        raise TypeError(f"{target} is not an assistant_matrix_sdk.Widget subclass.")
    return candidate


def validate_manifest_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    widget = data.get("widget")
    if not isinstance(widget, dict):
        return ["Missing [widget] section."]
    for key in ("id", "name", "version", "summary", "runtime", "entrypoint"):
        if not str(widget.get(key, "")).strip():
            errors.append(f"Missing widget.{key}.")
    if widget.get("runtime") not in {"python", "builtin"}:
        errors.append("widget.runtime must be python or builtin.")
    if data.get("config") is not None and not isinstance(data["config"], list):
        errors.append("[[config]] entries must be a list.")
    if data.get("permissions") is not None and not isinstance(data["permissions"], list):
        errors.append("[[permissions]] entries must be a list.")
    if data.get("triggers") is not None and not isinstance(data["triggers"], list):
        errors.append("[[triggers]] entries must be a list.")
    return errors


def read_manifest(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return tomllib.loads(path.read_text(encoding="utf-8"))


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return "[" + ", ".join(inline_table(item) for item in value) + "]"
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value))


def inline_table(data: dict[str, Any]) -> str:
    fields = ", ".join(f"{key} = {toml_value(value)}" for key, value in data.items() if value not in ("", None, []))
    return "{ " + fields + " }"


def write_toml_manifest(path: Path, data: dict[str, Any]) -> None:
    lines: list[str] = []
    for section_name in ("widget", "preview"):
        section = data.get(section_name, {})
        lines.append(f"[{section_name}]")
        for key, value in section.items():
            lines.append(f"{key} = {toml_value(value)}")
        lines.append("")

    for table_name in ("permissions", "config", "triggers"):
        for item in data.get(table_name, []):
            lines.append(f"[[{table_name}]]")
            for key, value in item.items():
                if value in ("", None, []):
                    continue
                lines.append(f"{key} = {toml_value(value)}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        write_toml_manifest(path, data)


def command_manifest(args: argparse.Namespace) -> int:
    widget_class = load_widget(args.widget)
    manifest = widget_class.manifest(entrypoint=args.entrypoint or args.widget)
    write_manifest(Path(args.output), manifest)
    print(f"Wrote {args.output}")
    return 0


def command_preview(args: argparse.Namespace) -> int:
    widget_class = load_widget(args.widget)
    if args.config.startswith("@"):
        config = json.loads(Path(args.config[1:]).read_text(encoding="utf-8"))
    else:
        config = json.loads(args.config) if args.config else {}
    widget = widget_class()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    widget.preview(args.output, WidgetContext(config=config), size=args.size)
    print(f"Wrote {args.output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    manifest = read_manifest(Path(args.manifest))
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Valid manifest: {args.manifest}")
    return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def widget_store_entry(manifest: dict[str, Any], *, base_url: str, archive_path: Path) -> dict[str, Any]:
    widget = manifest["widget"]
    preview = manifest.get("preview", {})
    widget_id = widget["id"]
    version = widget["version"]
    base = base_url.rstrip("/")
    widget_base = f"{base}/widgets/{widget_id}/{version}"
    return {
        "id": widget_id,
        "name": widget["name"],
        "version": version,
        "summary": widget["summary"],
        "category": widget.get("category", "custom"),
        "author": widget.get("author", "Assistant Matrix"),
        "manifestUrl": f"{widget_base}/widget.toml",
        "archiveUrl": f"{widget_base}/{archive_path.name}",
        "previewGifUrl": f"{widget_base}/{preview.get('card_gif', 'previews/card.gif')}",
        "matrixPreviewUrl": f"{widget_base}/{preview.get('matrix_png', 'previews/matrix-64.png')}",
        "sha256": sha256_file(archive_path),
    }


def command_package(args: argparse.Namespace) -> int:
    widget_dir = Path(args.widget_dir).resolve()
    manifest_path = widget_dir / "widget.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected {manifest_path}")
    manifest = read_manifest(manifest_path)
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    widget = manifest["widget"]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{widget['id']}-{widget['version']}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(widget_dir.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(widget_dir))

    digest = sha256_file(archive_path)
    print(f"Wrote {archive_path}")
    print(f"sha256 {digest}")
    return 0


def read_store_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "widgets": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schemaVersion", 1)
    payload.setdefault("widgets", [])
    return payload


def write_store_index(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def package_widget(widget_dir: Path, output_dir: Path) -> Path:
    manifest = read_manifest(widget_dir / "widget.toml")
    errors = validate_manifest_data(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    widget = manifest["widget"]
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{widget['id']}-{widget['version']}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(widget_dir.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(widget_dir))
    return archive_path


def command_publish(args: argparse.Namespace) -> int:
    widget_dir = Path(args.widget_dir).resolve()
    manifest_path = widget_dir / "widget.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected {manifest_path}")
    manifest = read_manifest(manifest_path)
    errors = validate_manifest_data(manifest)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    widget = manifest["widget"]
    publish_root = Path(args.store_dir)
    publish_dir = publish_root / "widgets" / widget["id"] / widget["version"]
    publish_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(manifest_path, publish_dir / "widget.toml")
    archive_path = package_widget(widget_dir, publish_dir)

    preview = manifest.get("preview", {})
    for preview_key in ("card_gif", "matrix_png"):
        relative = preview.get(preview_key)
        if not relative:
            continue
        source = widget_dir / relative
        if source.exists():
            target = publish_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    index_path = Path(args.index)
    if not index_path.is_absolute():
        index_path = publish_root / index_path
    index = read_store_index(index_path)
    entry = widget_store_entry(manifest, base_url=args.base_url, archive_path=archive_path)
    widgets = [item for item in index.get("widgets", []) if item.get("id") != entry["id"]]
    widgets.append(entry)
    widgets.sort(key=lambda item: item.get("name", item.get("id", "")))
    index["widgets"] = widgets
    write_store_index(index_path, index)

    print(f"Published {entry['id']} {entry['version']}")
    print(f"Archive {archive_path}")
    print(f"Index {index_path}")
    print(f"sha256 {entry['sha256']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assistant-matrix-widget", description="Assistant Matrix widget author tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest", help="Generate widget.toml from a Widget subclass.")
    manifest.add_argument("widget", help="Widget class target, for example renderer.widget:WeatherWidget.")
    manifest.add_argument("--entrypoint", default="", help="Runtime entrypoint stored in widget.toml. Defaults to the widget target.")
    manifest.add_argument("--output", default="widget.toml")
    manifest.set_defaults(func=command_manifest)

    preview = subparsers.add_parser("preview", help="Render a 64x64 preview image from a Widget subclass.")
    preview.add_argument("widget", help="Widget class target, for example renderer.widget:WeatherWidget.")
    preview.add_argument("--output", default="previews/matrix-64.png")
    preview.add_argument("--config", default="", help="JSON config object passed to WidgetContext, or @path/to/config.json.")
    preview.add_argument("--size", type=int, default=64)
    preview.set_defaults(func=command_preview)

    validate = subparsers.add_parser("validate", help="Validate widget.toml or widget.json.")
    validate.add_argument("manifest")
    validate.set_defaults(func=command_validate)

    package = subparsers.add_parser("package", help="Package a widget folder into a store archive.")
    package.add_argument("widget_dir")
    package.add_argument("--output-dir", default="dist")
    package.set_defaults(func=command_package)

    publish = subparsers.add_parser("publish", help="Publish a widget folder into an object-store-style directory and update an index JSON.")
    publish.add_argument("widget_dir")
    publish.add_argument("--store-dir", default="store-dist", help="Local directory that mirrors the object store root.")
    publish.add_argument("--base-url", required=True, help="Public base URL for the store root.")
    publish.add_argument("--index", default="store-index.json", help="Index path, relative to store-dir unless absolute.")
    publish.set_defaults(func=command_publish)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
