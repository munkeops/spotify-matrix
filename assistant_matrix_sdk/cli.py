"""Command line tools for Assistant Matrix widget authors."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import sys
import tarfile
import tomllib
from pathlib import Path
from typing import Any

from assistant_matrix_sdk.context import WidgetContext
from assistant_matrix_sdk.widget import Widget

ALLOWED_CATEGORIES = {"media", "time", "assistant", "information", "diagnostics", "custom"}
ALLOWED_FIELD_TYPES = {"string", "number", "boolean", "select", "secret", "location", "color"}
ALLOWED_RUNTIMES = {"python", "builtin"}
WIDGET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SEMVERISH_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?$")
MATRIX_SIZE_PATTERN = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")


def class_name_from_widget_id(widget_id: str) -> str:
    parts = [part for part in widget_id.replace("-", ".").replace("_", ".").split(".") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) + "Widget"


def display_name_from_widget_id(widget_id: str) -> str:
    tail = widget_id.split(".")[-1]
    return tail.replace("-", " ").replace("_", " ").title() or widget_id


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

    widget_id = str(widget.get("id", ""))
    version = str(widget.get("version", ""))
    category = str(widget.get("category", "custom"))
    matrix_size = str(widget.get("matrix_size", widget.get("matrixSize", "64x64")))

    if widget_id and not WIDGET_ID_PATTERN.match(widget_id):
        errors.append("widget.id may only contain letters, numbers, dots, underscores, and hyphens, and must start with a letter or number.")
    if version and not SEMVERISH_PATTERN.match(version):
        errors.append("widget.version should use semantic version format, for example 0.1.0.")
    if widget.get("runtime") not in ALLOWED_RUNTIMES:
        errors.append("widget.runtime must be python or builtin.")
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"widget.category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}.")
    if matrix_size and not MATRIX_SIZE_PATTERN.match(matrix_size):
        errors.append("widget.matrix_size must look like 64x64.")

    preview = data.get("preview")
    if preview is not None and not isinstance(preview, dict):
        errors.append("[preview] must be a table.")
    if data.get("config") is not None and not isinstance(data["config"], list):
        errors.append("[[config]] entries must be a list.")
    if data.get("permissions") is not None and not isinstance(data["permissions"], list):
        errors.append("[[permissions]] entries must be a list.")
    if data.get("triggers") is not None and not isinstance(data["triggers"], list):
        errors.append("[[triggers]] entries must be a list.")

    for index, field in enumerate(data.get("config") or []):
        if not isinstance(field, dict):
            errors.append(f"config[{index}] must be a table.")
            continue
        for key in ("key", "label", "type"):
            if not str(field.get(key, "")).strip():
                errors.append(f"config[{index}] missing {key}.")
        field_type = field.get("type")
        if field_type and field_type not in ALLOWED_FIELD_TYPES:
            errors.append(f"config[{index}].type must be one of: {', '.join(sorted(ALLOWED_FIELD_TYPES))}.")
        options = field.get("options", [])
        if field_type == "select" and not options:
            errors.append(f"config[{index}] select fields need options.")
        if options and not isinstance(options, list):
            errors.append(f"config[{index}].options must be a list.")
        for option_index, option in enumerate(options if isinstance(options, list) else []):
            if not isinstance(option, dict) or "label" not in option or "value" not in option:
                errors.append(f"config[{index}].options[{option_index}] must be an inline table with label and value.")

    for index, permission in enumerate(data.get("permissions") or []):
        if not isinstance(permission, dict):
            errors.append(f"permissions[{index}] must be a table.")
            continue
        if not str(permission.get("name", "")).strip():
            errors.append(f"permissions[{index}] missing name.")
        if not str(permission.get("reason", "")).strip():
            errors.append(f"permissions[{index}] missing reason.")

    for index, trigger in enumerate(data.get("triggers") or []):
        if not isinstance(trigger, dict):
            errors.append(f"triggers[{index}] must be a table.")
            continue
        if not str(trigger.get("event", "")).strip():
            errors.append(f"triggers[{index}] missing event.")
    return errors


def validate_widget_package_files(manifest: dict[str, Any], widget_dir: Path) -> list[str]:
    errors: list[str] = []
    widget = manifest.get("widget", {})
    if not isinstance(widget, dict):
        return errors
    if widget.get("runtime") == "python":
        entrypoint = str(widget.get("entrypoint", ""))
        module_name = entrypoint.split(":", 1)[0]
        if not module_name:
            return errors
        module_path = widget_dir / Path(*module_name.split(".")).with_suffix(".py")
        if not module_path.exists():
            errors.append(f"Missing Python entrypoint file {module_path.relative_to(widget_dir)}.")

    preview = manifest.get("preview", {})
    if not isinstance(preview, dict):
        return errors
    for key in ("matrix_png",):
        relative = str(preview.get(key, "")).strip()
        if not relative:
            continue
        preview_path = widget_dir / relative
        try:
            preview_path.resolve().relative_to(widget_dir.resolve())
        except ValueError:
            errors.append(f"preview.{key} must stay inside the widget package.")
            continue
        if not preview_path.exists():
            errors.append(f"Missing preview.{key} file {relative}.")
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


def command_init(args: argparse.Namespace) -> int:
    widget_id = args.widget_id
    target_dir = Path(args.directory or widget_id).resolve()
    if target_dir.exists() and any(target_dir.iterdir()) and not args.force:
        raise FileExistsError(f"{target_dir} is not empty. Use --force to write into it.")

    name = args.name or display_name_from_widget_id(widget_id)
    class_name = class_name_from_widget_id(widget_id)
    summary = args.summary or f"{name} widget for Assistant Matrix."
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "renderer").mkdir(parents=True, exist_ok=True)
    (target_dir / "previews").mkdir(parents=True, exist_ok=True)
    (target_dir / "assets").mkdir(parents=True, exist_ok=True)

    manifest = {
        "widget": {
            "id": widget_id,
            "name": name,
            "version": args.version,
            "summary": summary,
            "author": args.author,
            "category": args.category,
            "runtime": "python",
            "entrypoint": "renderer.widget:WidgetRenderer",
            "matrix_size": "64x64",
            "license": args.license,
        },
        "preview": {
            "card_gif": "previews/card.gif",
            "matrix_png": "previews/matrix-64.png",
            "description": f"{name} matrix preview.",
        },
        "permissions": [],
        "config": [
            {
                "key": "message",
                "label": "Message",
                "type": "string",
                "default": "HI",
                "placeholder": "HI",
            }
        ],
        "triggers": [
            {
                "event": "schedule.rotation",
                "default_enabled": True,
                "priority": 10,
            }
        ],
    }
    write_manifest(target_dir / "widget.toml", manifest)

    renderer = f'''"""Starter Assistant Matrix widget."""

from __future__ import annotations

from assistant_matrix_sdk import MatrixCanvas, Widget, WidgetContext


class {class_name}(Widget):
    def render(self, canvas: MatrixCanvas, context: WidgetContext) -> None:
        message = str(context.config.get("message", "HI"))[:8].upper()
        canvas.background("#050607")
        canvas.rect(0, 0, 64, 16, "#203a5f")
        canvas.text(4, 4, "{name[:8].upper()}", "#ffffff")
        canvas.text(8, 28, message, "#9bd0d9")


WidgetRenderer = {class_name}
'''
    (target_dir / "renderer" / "widget.py").write_text(renderer, encoding="utf-8")
    (target_dir / "renderer" / "__init__.py").write_text("", encoding="utf-8")

    readme = f"""# {name}

{summary}

## Develop

```bash
assistant-matrix-widget validate widget.toml
assistant-matrix-widget preview renderer.widget:{class_name} --output previews/matrix-64.png --config '{{"message":"HI"}}'
assistant-matrix-widget package . --output-dir dist
assistant-matrix-widget publish . --store-dir store-dist --base-url https://store.example.com
```
"""
    (target_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Created widget scaffold at {target_dir}")
    print(f"Entrypoint renderer.widget:{class_name}")
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


def widget_store_entry(manifest: dict[str, Any], *, base_url: str, archive_path: Path, widget_dir: Path | None = None) -> dict[str, Any]:
    widget = manifest["widget"]
    preview = manifest.get("preview", {})
    widget_id = widget["id"]
    version = widget["version"]
    base = base_url.rstrip("/")
    widget_base = f"{base}/widgets/{widget_id}/{version}"
    card_gif = preview.get("card_gif", "previews/card.gif")
    matrix_png = preview.get("matrix_png", "previews/matrix-64.png")
    entry = {
        "id": widget_id,
        "name": widget["name"],
        "version": version,
        "summary": widget["summary"],
        "category": widget.get("category", "custom"),
        "author": widget.get("author", "Assistant Matrix"),
        "manifestUrl": f"{widget_base}/widget.toml",
        "archiveUrl": f"{widget_base}/{archive_path.name}",
        "previewGifUrl": "",
        "matrixPreviewUrl": f"{widget_base}/{matrix_png}",
        "sha256": sha256_file(archive_path),
    }
    if card_gif and (widget_dir is None or (widget_dir / card_gif).exists()):
        entry["previewGifUrl"] = f"{widget_base}/{card_gif}"
    return entry


def command_package(args: argparse.Namespace) -> int:
    widget_dir = Path(args.widget_dir).resolve()
    manifest_path = widget_dir / "widget.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected {manifest_path}")
    manifest = read_manifest(manifest_path)
    errors = validate_manifest_data(manifest)
    errors.extend(validate_widget_package_files(manifest, widget_dir))
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
    errors.extend(validate_widget_package_files(manifest, widget_dir))
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
    errors.extend(validate_widget_package_files(manifest, widget_dir))
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
    entry = widget_store_entry(manifest, base_url=args.base_url, archive_path=archive_path, widget_dir=widget_dir)
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

    init = subparsers.add_parser("init", help="Create a starter widget package.")
    init.add_argument("widget_id", help="Stable widget id, for example user.weather-badge.")
    init.add_argument("--directory", default="", help="Target directory. Defaults to the widget id.")
    init.add_argument("--name", default="", help="Display name. Defaults from widget id.")
    init.add_argument("--summary", default="", help="Short store summary.")
    init.add_argument("--author", default="Assistant Matrix")
    init.add_argument("--category", default="custom", choices=("media", "time", "assistant", "information", "diagnostics", "custom"))
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--license", default="MIT")
    init.add_argument("--force", action="store_true", help="Allow writing into a non-empty directory.")
    init.set_defaults(func=command_init)

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
