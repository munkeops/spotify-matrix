"""Command line tools for Assistant Matrix app authors."""

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
import urllib.parse
from pathlib import Path
from typing import Any

ALLOWED_CATEGORIES = {"media", "time", "assistant", "information", "diagnostics", "games", "custom"}
ALLOWED_FIELD_TYPES = {"string", "number", "boolean", "select", "secret", "location", "color"}
ALLOWED_RUNTIMES = {"python", "builtin"}
APP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SEMVERISH_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?$")
MATRIX_SIZE_PATTERN = re.compile(r"^[1-9][0-9]*x[1-9][0-9]*$")


def class_name_from_app_id(app_id: str) -> str:
    parts = [part for part in app_id.replace("-", ".").replace("_", ".").split(".") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) + "App"


def display_name_from_app_id(app_id: str) -> str:
    tail = app_id.split(".")[-1]
    return tail.replace("-", " ").replace("_", " ").title() or app_id


def load_app(target: str):
    from assistant_matrix_sdk.app import App

    if ":" not in target:
        raise ValueError("App target must use module.path:ClassName.")
    module_name, class_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    candidate = getattr(module, class_name)
    if not isinstance(candidate, type) or not issubclass(candidate, App):
        raise TypeError(f"{target} is not an assistant_matrix_sdk.App subclass.")
    return candidate


def validate_manifest_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    app = data.get("app")
    if not isinstance(app, dict):
        return ["Missing [app] section."]

    for key in ("id", "name", "version", "summary", "runtime", "entrypoint"):
        if not str(app.get(key, "")).strip():
            errors.append(f"Missing app.{key}.")

    app_id = str(app.get("id", ""))
    version = str(app.get("version", ""))
    category = str(app.get("category", "custom"))
    matrix_size = str(app.get("matrix_size", app.get("matrixSize", "64x64")))

    if app_id and not APP_ID_PATTERN.match(app_id):
        errors.append("app.id may only contain letters, numbers, dots, underscores, and hyphens, and must start with a letter or number.")
    if version and not SEMVERISH_PATTERN.match(version):
        errors.append("app.version should use semantic version format, for example 0.1.0.")
    if app.get("runtime") not in ALLOWED_RUNTIMES:
        errors.append("app.runtime must be python or builtin.")
    if category not in ALLOWED_CATEGORIES:
        errors.append(f"app.category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}.")
    if matrix_size and not MATRIX_SIZE_PATTERN.match(matrix_size):
        errors.append("app.matrix_size must look like 64x64.")

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


def validate_app_package_files(manifest: dict[str, Any], app_dir: Path) -> list[str]:
    errors: list[str] = []
    app = manifest.get("app", {})
    if not isinstance(app, dict):
        return errors
    if app.get("runtime") == "python":
        entrypoint = str(app.get("entrypoint", ""))
        module_name = entrypoint.split(":", 1)[0]
        if not module_name:
            return errors
        module_path = app_dir / Path(*module_name.split(".")).with_suffix(".py")
        if not module_path.exists():
            errors.append(f"Missing Python entrypoint file {module_path.relative_to(app_dir)}.")

    preview = manifest.get("preview", {})
    if not isinstance(preview, dict):
        return errors
    for key in ("matrix_png",):
        relative = str(preview.get(key, "")).strip()
        if not relative:
            continue
        preview_path = app_dir / relative
        try:
            preview_path.resolve().relative_to(app_dir.resolve())
        except ValueError:
            errors.append(f"preview.{key} must stay inside the app package.")
            continue
        if not preview_path.exists():
            errors.append(f"Missing preview.{key} file {relative}.")
    return errors


def validate_store_index_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1.")
    apps = data.get("apps")
    if not isinstance(apps, list):
        return errors + ["apps must be a list."]

    seen_ids: set[str] = set()
    for index, app in enumerate(apps):
        if not isinstance(app, dict):
            errors.append(f"apps[{index}] must be an object.")
            continue
        prefix = f"apps[{index}]"
        for key in ("id", "name", "version", "summary"):
            if not str(app.get(key, "")).strip():
                errors.append(f"{prefix} missing {key}.")
        app_id = str(app.get("id", ""))
        version = str(app.get("version", ""))
        category = str(app.get("category", "custom"))
        sha256 = str(app.get("sha256", ""))
        archive_url = str(app.get("archiveUrl", ""))
        matrix_preview_url = str(app.get("matrixPreviewUrl", ""))

        if app_id:
            if app_id in seen_ids:
                errors.append(f"{prefix}.id duplicates {app_id}.")
            seen_ids.add(app_id)
            if not APP_ID_PATTERN.match(app_id):
                errors.append(f"{prefix}.id may only contain letters, numbers, dots, underscores, and hyphens, and must start with a letter or number.")
        if version and not SEMVERISH_PATTERN.match(version):
            errors.append(f"{prefix}.version should use semantic version format, for example 0.1.0.")
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{prefix}.category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}.")
        if sha256 and not re.fullmatch(r"[A-Fa-f0-9]{64}", sha256):
            errors.append(f"{prefix}.sha256 must be empty or a 64-character hex digest.")
        if archive_url and not _valid_store_url(archive_url):
            errors.append(f"{prefix}.archiveUrl must be http(s), file, absolute, or relative path.")
        if matrix_preview_url and not _valid_store_url(matrix_preview_url):
            errors.append(f"{prefix}.matrixPreviewUrl must be http(s), file, absolute, or relative path.")
    return errors


def _valid_store_url(value: str) -> bool:
    if not value:
        return True
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"", "http", "https", "file"}


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
    for section_name in ("app", "preview"):
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
    app_class = load_app(args.app)
    manifest = app_class.manifest(entrypoint=args.entrypoint or args.app)
    write_manifest(Path(args.output), manifest)
    print(f"Wrote {args.output}")
    return 0


def command_init(args: argparse.Namespace) -> int:
    app_id = args.app_id
    target_dir = Path(args.directory or app_id).resolve()
    if target_dir.exists() and any(target_dir.iterdir()) and not args.force:
        raise FileExistsError(f"{target_dir} is not empty. Use --force to write into it.")

    name = args.name or display_name_from_app_id(app_id)
    class_name = class_name_from_app_id(app_id)
    summary = args.summary or f"{name} app for Assistant Matrix."
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "renderer").mkdir(parents=True, exist_ok=True)
    (target_dir / "previews").mkdir(parents=True, exist_ok=True)
    (target_dir / "assets").mkdir(parents=True, exist_ok=True)

    manifest = {
        "app": {
            "id": app_id,
            "name": name,
            "version": args.version,
            "summary": summary,
            "author": args.author,
            "category": args.category,
            "runtime": "python",
            "entrypoint": "renderer.app:AppRenderer",
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
    write_manifest(target_dir / "app.toml", manifest)

    renderer = f'''"""Starter Assistant Matrix app."""

from __future__ import annotations

from assistant_matrix_sdk import MatrixCanvas, App, AppContext


class {class_name}(App):
    def render(self, canvas: MatrixCanvas, context: AppContext) -> None:
        message = str(context.config.get("message", "HI"))[:8].upper()
        canvas.background("#050607")
        canvas.rect(0, 0, 64, 16, "#203a5f")
        canvas.text(4, 4, "{name[:8].upper()}", "#ffffff")
        canvas.text(8, 28, message, "#9bd0d9")


AppRenderer = {class_name}
'''
    (target_dir / "renderer" / "app.py").write_text(renderer, encoding="utf-8")
    (target_dir / "renderer" / "__init__.py").write_text("", encoding="utf-8")

    readme = f"""# {name}

{summary}

## Develop

```bash
assistant-matrix-app validate app.toml
assistant-matrix-app preview renderer.app:{class_name} --output previews/matrix-64.png --config '{{"message":"HI"}}'
assistant-matrix-app package . --output-dir dist
assistant-matrix-app publish . --store-dir store-dist --base-url https://store.example.com
```
"""
    (target_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"Created app scaffold at {target_dir}")
    print(f"Entrypoint renderer.app:{class_name}")
    return 0


def command_preview(args: argparse.Namespace) -> int:
    from assistant_matrix_sdk.context import AppContext

    app_class = load_app(args.app)
    if args.config.startswith("@"):
        config = json.loads(Path(args.config[1:]).read_text(encoding="utf-8"))
    else:
        config = json.loads(args.config) if args.config else {}
    app = app_class()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    app.preview(args.output, AppContext(config=config), size=args.size)
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


def command_validate_store(args: argparse.Namespace) -> int:
    index = read_store_index(Path(args.index))
    errors = validate_store_index_data(index)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Valid store index: {args.index}")
    return 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def app_store_entry(manifest: dict[str, Any], *, base_url: str, archive_path: Path, app_dir: Path | None = None) -> dict[str, Any]:
    app = manifest["app"]
    preview = manifest.get("preview", {})
    app_id = app["id"]
    version = app["version"]
    base = base_url.rstrip("/")
    app_base = f"{base}/apps/{app_id}/{version}"
    card_gif = preview.get("card_gif", "previews/card.gif")
    matrix_png = preview.get("matrix_png", "previews/matrix-64.png")
    entry = {
        "id": app_id,
        "name": app["name"],
        "version": version,
        "summary": app["summary"],
        "category": app.get("category", "custom"),
        "author": app.get("author", "Assistant Matrix"),
        "manifestUrl": f"{app_base}/app.toml",
        "archiveUrl": f"{app_base}/{archive_path.name}",
        "previewGifUrl": "",
        "matrixPreviewUrl": f"{app_base}/{matrix_png}",
        "sha256": sha256_file(archive_path),
    }
    if card_gif and (app_dir is None or (app_dir / card_gif).exists()):
        entry["previewGifUrl"] = f"{app_base}/{card_gif}"
    return entry


def command_package(args: argparse.Namespace) -> int:
    app_dir = Path(args.app_dir).resolve()
    manifest_path = app_dir / "app.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected {manifest_path}")
    manifest = read_manifest(manifest_path)
    errors = validate_manifest_data(manifest)
    errors.extend(validate_app_package_files(manifest, app_dir))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    app = manifest["app"]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{app['id']}-{app['version']}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(app_dir))

    digest = sha256_file(archive_path)
    print(f"Wrote {archive_path}")
    print(f"sha256 {digest}")
    return 0


def read_store_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "apps": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schemaVersion", 1)
    payload.setdefault("apps", [])
    return payload


def write_store_index(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def package_app(app_dir: Path, output_dir: Path) -> Path:
    manifest = read_manifest(app_dir / "app.toml")
    errors = validate_manifest_data(manifest)
    errors.extend(validate_app_package_files(manifest, app_dir))
    if errors:
        raise ValueError("; ".join(errors))
    app = manifest["app"]
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{app['id']}-{app['version']}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=path.relative_to(app_dir))
    return archive_path


def command_publish(args: argparse.Namespace) -> int:
    app_dir = Path(args.app_dir).resolve()
    manifest_path = app_dir / "app.toml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected {manifest_path}")
    manifest = read_manifest(manifest_path)
    errors = validate_manifest_data(manifest)
    errors.extend(validate_app_package_files(manifest, app_dir))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    app = manifest["app"]
    publish_root = Path(args.store_dir)
    publish_dir = publish_root / "apps" / app["id"] / app["version"]
    publish_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(manifest_path, publish_dir / "app.toml")
    archive_path = package_app(app_dir, publish_dir)

    preview = manifest.get("preview", {})
    for preview_key in ("card_gif", "matrix_png"):
        relative = preview.get(preview_key)
        if not relative:
            continue
        source = app_dir / relative
        if source.exists():
            target = publish_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    index_path = Path(args.index)
    if not index_path.is_absolute():
        index_path = publish_root / index_path
    index = read_store_index(index_path)
    entry = app_store_entry(manifest, base_url=args.base_url, archive_path=archive_path, app_dir=app_dir)
    apps = [item for item in index.get("apps", []) if item.get("id") != entry["id"]]
    apps.append(entry)
    apps.sort(key=lambda item: item.get("name", item.get("id", "")))
    index["apps"] = apps
    errors = validate_store_index_data(index)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    write_store_index(index_path, index)

    print(f"Published {entry['id']} {entry['version']}")
    print(f"Archive {archive_path}")
    print(f"Index {index_path}")
    print(f"sha256 {entry['sha256']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assistant-matrix-app", description="Assistant Matrix app author tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a starter app package.")
    init.add_argument("app_id", help="Stable app id, for example user.weather-badge.")
    init.add_argument("--directory", default="", help="Target directory. Defaults to the app id.")
    init.add_argument("--name", default="", help="Display name. Defaults from app id.")
    init.add_argument("--summary", default="", help="Short store summary.")
    init.add_argument("--author", default="Assistant Matrix")
    init.add_argument("--category", default="custom", choices=("media", "time", "assistant", "information", "diagnostics", "games", "custom"))
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--license", default="MIT")
    init.add_argument("--force", action="store_true", help="Allow writing into a non-empty directory.")
    init.set_defaults(func=command_init)

    manifest = subparsers.add_parser("manifest", help="Generate app.toml from a App subclass.")
    manifest.add_argument("app", help="App class target, for example renderer.app:WeatherApp.")
    manifest.add_argument("--entrypoint", default="", help="Runtime entrypoint stored in app.toml. Defaults to the app target.")
    manifest.add_argument("--output", default="app.toml")
    manifest.set_defaults(func=command_manifest)

    preview = subparsers.add_parser("preview", help="Render a 64x64 preview image from a App subclass.")
    preview.add_argument("app", help="App class target, for example renderer.app:WeatherApp.")
    preview.add_argument("--output", default="previews/matrix-64.png")
    preview.add_argument("--config", default="", help="JSON config object passed to AppContext, or @path/to/config.json.")
    preview.add_argument("--size", type=int, default=64)
    preview.set_defaults(func=command_preview)

    validate = subparsers.add_parser("validate", help="Validate app.toml or app.json.")
    validate.add_argument("manifest")
    validate.set_defaults(func=command_validate)

    validate_store = subparsers.add_parser("validate-store", help="Validate a static app store index JSON.")
    validate_store.add_argument("index")
    validate_store.set_defaults(func=command_validate_store)

    package = subparsers.add_parser("package", help="Package a app folder into a store archive.")
    package.add_argument("app_dir")
    package.add_argument("--output-dir", default="dist")
    package.set_defaults(func=command_package)

    publish = subparsers.add_parser("publish", help="Publish a app folder into an object-store-style directory and update an index JSON.")
    publish.add_argument("app_dir")
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
