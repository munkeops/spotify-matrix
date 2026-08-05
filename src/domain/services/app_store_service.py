"""App store catalog service."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import hashlib
from pathlib import Path

from src.domain.models.app_schemas import StoreApp, AppStoreIndex
from matrix_games.registry import invalidate_cache
from src.domain.services.config_service import config_service
from src.domain.services.display_policy_service import display_policy_service
from src.domain.services.app_registry_service import app_registry_service


class AppStoreService:
    def __init__(self) -> None:
        self.installed_path = config_service.data_dir / "apps" / "installed.json"

    def list_apps(self) -> AppStoreIndex:
        index = self._read_index()
        installed_ids = {app.manifest.id for app in app_registry_service.list_local_apps()}
        for app in index.apps:
            app.installed = app.id in installed_ids
        return index

    def get_app(self, app_id: str) -> StoreApp | None:
        for app in self.list_apps().apps:
            if app.id == app_id:
                return app
        return None

    def install_app(self, app_id: str) -> StoreApp:
        app = self.get_app(app_id)
        invalidate_cache()
        if app is None:
            raise ValueError(f"Unknown store app {app_id}.")
        installed = self.read_installed_apps()
        by_id = {item.id: item for item in installed}
        by_id[app.id] = app
        if app.runtime != "builtin":
            self._install_archive_if_available(app)
        self._write_installed_apps(list(by_id.values()))
        app.installed = True
        return app

    def uninstall_app(self, app_id: str) -> None:
        installed = self.read_installed_apps()
        invalidate_cache()
        if app_id not in {app.id for app in installed}:
            raise ValueError(f"App {app_id} is not installed.")

        self._write_installed_apps([app for app in installed if app.id != app_id])
        self._remove_path(config_service.data_dir / "apps" / "packages" / app_id)
        self._remove_path(config_service.data_dir / "apps" / "config" / f"{app_id}.json")
        self._remove_path(config_service.data_dir / "apps" / "downloads" / f"{app_id}.tar.gz")
        display_policy_service.remove_app_references(app_id)

        config = config_service.get_config()
        if config.display.mode == "app" and config.display.appId == app_id:
            config.display.mode = "spotify"
            config.display.appId = ""
            config.runtime.testPattern = False
            config_service.save_config(config)

    def read_installed_apps(self) -> list[StoreApp]:
        try:
            with self.installed_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError:
            return []
        apps = payload.get("apps", payload if isinstance(payload, list) else [])
        return [StoreApp.model_validate(app) for app in apps]

    def _read_index(self) -> AppStoreIndex:
        source = self._index_source()
        try:
            if source.startswith(("http://", "https://")):
                with urllib.request.urlopen(source, timeout=10) as response:
                    return AppStoreIndex.model_validate(json.loads(response.read().decode("utf-8")))
            path = Path(source)
            if not path.is_absolute():
                path = Path.cwd() / path
            with path.open("r", encoding="utf-8") as file:
                return AppStoreIndex.model_validate(json.load(file))
        except (FileNotFoundError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return AppStoreIndex()

    def _index_source(self) -> str:
        env_source = os.environ.get("ASSISTANT_MATRIX_APP_STORE_INDEX")
        if env_source:
            return env_source
        return config_service.get_config().store.indexUrl or "configs/app_store_index.json"

    def _write_installed_apps(self, apps: list[StoreApp]) -> None:
        self.installed_path.parent.mkdir(parents=True, exist_ok=True)
        with self.installed_path.open("w", encoding="utf-8") as file:
            json.dump({"schemaVersion": 1, "apps": [app.model_dump() for app in apps]}, file, indent=2)
            file.write("\n")

    def _remove_path(self, path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    def _install_archive_if_available(self, app: StoreApp) -> None:
        if not app.archiveUrl:
            raise ValueError(f"Store app {app.id} does not provide an archiveUrl.")
        archive_path = self._resolve_archive(app.archiveUrl)
        if app.sha256:
            digest = self._sha256(archive_path)
            if digest.lower() != app.sha256.lower():
                raise ValueError(f"Archive checksum mismatch for {app.id}.")
        package_dir = config_service.data_dir / "apps" / "packages" / app.id
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_dir = Path(temp_dir) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            self._safe_extract(archive_path, extract_dir)
            self._validate_extracted_package(extract_dir, app)
            if package_dir.exists():
                shutil.rmtree(package_dir)
            package_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(extract_dir, package_dir)

    def _resolve_archive(self, archive_url: str) -> Path:
        parsed = urllib.parse.urlparse(archive_url)
        if parsed.scheme in {"http", "https"}:
            cache_dir = config_service.data_dir / "apps" / "downloads"
            cache_dir.mkdir(parents=True, exist_ok=True)
            target = cache_dir / Path(parsed.path).name
            urllib.request.urlretrieve(archive_url, target)
            return target
        if parsed.scheme == "file":
            return Path(urllib.request.url2pathname(parsed.path))
        path = Path(archive_url)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _safe_extract(self, archive_path: Path, target_dir: Path) -> None:
        target_root = target_dir.resolve()
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    raise ValueError(f"Unsafe archive link {member.name}.")
                destination = (target_dir / member.name).resolve()
                try:
                    destination.relative_to(target_root)
                except ValueError:
                    raise ValueError(f"Unsafe archive path {member.name}.")
            archive.extractall(target_dir)

    def _validate_extracted_package(self, package_dir: Path, app: StoreApp) -> None:
        manifest_path = package_dir / "app.toml"
        if not manifest_path.exists():
            raise ValueError(f"Archive for {app.id} is missing app.toml.")
        with manifest_path.open("rb") as file:
            manifest = tomllib.load(file)
        metadata = manifest.get("app", {})
        if metadata.get("id") != app.id:
            raise ValueError(f"Archive app id {metadata.get('id')} does not match store id {app.id}.")
        if str(metadata.get("version", "")) != app.version:
            raise ValueError(f"Archive app version {metadata.get('version')} does not match store version {app.version}.")
        if metadata.get("runtime") == "python":
            entrypoint = str(metadata.get("entrypoint", ""))
            module_name = entrypoint.split(":", 1)[0]
            if not module_name:
                raise ValueError(f"Archive for {app.id} is missing a Python entrypoint.")
            module_path = package_dir / Path(*module_name.split(".")).with_suffix(".py")
            if not module_path.exists():
                raise ValueError(f"Archive for {app.id} is missing entrypoint file {module_path.relative_to(package_dir)}.")


app_store_service = AppStoreService()
