"""Local app registry for built-in Assistant Matrix apps."""

from __future__ import annotations

import json
import os
import tomllib
from typing import Any

# "always" keeps built-ins available (classic behavior); "store" makes the app a
# pure app host that starts empty and shows built-ins only once installed.
BUILTIN_MODE = os.environ.get("ASSISTANT_MATRIX_BUILTIN_MODE", "always").lower()

from pydantic import BaseModel

from matrix_games import GAMES, discover
from src.domain.models.api_schemas import AgentConfig, ClockConfig, DrawConfig, ImageConfig, SlideshowConfig, SpotifyConfig, TextConfig, WeatherConfig
from src.domain.models.app_schemas import LocalApp, StoreApp, AppConfigField, AppConfigOption, AppManifest, AppPermission, AppPreview, AppTrigger
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service


def _option(label: str, value: str | int | float | bool) -> AppConfigOption:
    return AppConfigOption(label=label, value=value)


APP_MODE_MAP = {
    "core.spotify": "spotify",
    "core.clock": "clock",
    "core.agent": "agent",
    "core.weather": "weather",
    "core.text": "text",
    "core.image": "image",
    "core.draw": "draw",
    "core.slideshow": "slideshow",
    "core.testPattern": "testPattern",
}



def _safe_app_id(app_id: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not app_id or any(character not in allowed for character in app_id):
        raise ValueError(f"Invalid app id {app_id}.")
    return app_id


def _manifest_from_toml(payload: dict[str, Any]) -> AppManifest:
    app = payload.get("app", {})
    preview = payload.get("preview", {})
    config_fields = []
    for field in payload.get("config", []):
        config_fields.append(
            {
                **field,
                "helpText": field.get("helpText", field.get("help_text", "")),
            }
        )
    triggers = []
    for trigger in payload.get("triggers", []):
        triggers.append(
            {
                "event": trigger.get("event", ""),
                "defaultEnabled": trigger.get("defaultEnabled", trigger.get("default_enabled", False)),
                "priority": trigger.get("priority", 0),
                "minDurationSeconds": trigger.get("minDurationSeconds", trigger.get("min_duration_seconds", 0)),
            }
        )
    return AppManifest.model_validate(
        {
            "id": app.get("id", ""),
            "name": app.get("name", ""),
            "version": app.get("version", ""),
            "summary": app.get("summary", ""),
            "author": app.get("author", "Assistant Matrix"),
            "category": app.get("category", "custom"),
            "runtime": app.get("runtime", "python"),
            "entrypoint": app.get("entrypoint", ""),
            "matrixSize": app.get("matrixSize", app.get("matrix_size", "64x64")),
            "license": app.get("license", "MIT"),
            "preview": {
                "cardGif": preview.get("cardGif", preview.get("card_gif", "")),
                "matrixPreview": preview.get("matrixPreview", preview.get("matrix_png", "")),
                "description": preview.get("description", ""),
            },
            "kind": app.get("kind", "app"),
            "layout": app.get("layout", ""),
            "actions": app.get("actions", []),
            "permissions": payload.get("permissions", []),
            "config": config_fields,
            "triggers": triggers,
        }
    )


class AppRegistryService:
    def list_local_apps(self) -> list[LocalApp]:
        config = config_service.get_config()
        active_mode = "testPattern" if config.runtime.testPattern else config.display.mode
        installed_ids = self._installed_ids()
        builtin_ids = {manifest.id for manifest in self._built_in_manifests()}
        apps = [
            self._local_app(manifest, active_mode)
            for manifest in self._built_in_manifests()
            if BUILTIN_MODE != "store" or manifest.id in installed_ids
        ]
        apps.extend(app for app in self._installed_store_apps() if app.manifest.id not in builtin_ids)
        seen = {app.manifest.id for app in apps}
        apps.extend(
            app
            for app in self._game_package_apps()
            if app.manifest.id not in seen
            # A game shipped in the image is available, not installed. The
            # files being present is what makes installing one instant and
            # possible offline; it is not consent to have fifteen games on
            # a unit somebody just unboxed, and it left the store with
            # nothing to offer.
            and (BUILTIN_MODE != "store" or app.manifest.id in installed_ids)
        )
        return apps

    def bundled_manifests(self) -> list[AppManifest]:
        """Manifests for the app packages shipped inside the image.

        These are what the store can offer on a unit with no network: the
        files are already on disk, so installing one is a bookkeeping entry
        rather than a download.
        """
        manifests: list[AppManifest] = []
        for spec in discover(config_service.data_dir / "apps" / "packages").values():
            manifest_path = spec.package_dir / "app.toml"
            if not manifest_path.exists():
                continue
            manifests.append(_manifest_from_toml(tomllib.loads(manifest_path.read_text(encoding="utf-8"))))
        return manifests

    def _game_package_apps(self) -> list[LocalApp]:
        """Game apps found on disk, bundled with the app or installed."""
        config = config_service.get_config()
        active_app_id = config.display.appId if config.display.mode == "app" else ""
        apps: list[LocalApp] = []
        for spec in discover(config_service.data_dir / "apps" / "packages").values():
            manifest = self._read_installed_manifest(spec.app_id)
            if manifest is None:
                continue
            apps.append(
                LocalApp(
                    manifest=manifest,
                    installed=True,
                    builtIn=spec.bundled,
                    enabled=True,
                    configurable=bool(manifest.config),
                    active=spec.app_id == active_app_id and not config.runtime.testPattern,
                )
            )
        return apps

    def _installed_ids(self) -> set[str]:
        path = config_service.data_dir / "apps" / "installed.json"
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return set()
        raw = payload.get("apps", payload if isinstance(payload, list) else [])
        return {item.get("id") for item in raw if isinstance(item, dict) and item.get("id")}

    def get_local_app(self, app_id: str) -> LocalApp | None:
        for app in self.list_local_apps():
            if app.manifest.id == app_id:
                return app
        return None

    def get_app_config(self, app_id: str) -> dict[str, Any]:
        self._require_app(app_id)
        config = config_service.get_public_config()
        if app_id == "core.spotify":
            return config.spotify.model_dump()
        if app_id == "core.clock":
            return config.clock.model_dump()
        if app_id == "core.agent":
            return config.agent.model_dump()
        if app_id == "core.weather":
            return config.weather.model_dump()
        if app_id == "core.text":
            return config.text.model_dump()
        if app_id == "core.image":
            return config.image.model_dump()
        if app_id == "core.draw":
            return config.draw.model_dump()
        if app_id == "core.slideshow":
            return config.slideshow.model_dump()
        if app_id == "core.testPattern":
            return {"testPattern": config.runtime.testPattern}
        return self._read_installed_app_config(app_id)

    def update_app_config(self, app_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._require_app(app_id)
        config = config_service.get_config()
        if app_id == "core.spotify":
            if values.get("clientSecret") == "********":
                values = {key: value for key, value in values.items() if key != "clientSecret"}
            config.spotify = self._merge_model(config.spotify, values, SpotifyConfig)
        elif app_id == "core.clock":
            config.clock = self._merge_model(config.clock, values, ClockConfig)
        elif app_id == "core.agent":
            config.agent = self._merge_model(config.agent, values, AgentConfig)
        elif app_id == "core.weather":
            config.weather = self._merge_model(config.weather, values, WeatherConfig)
        elif app_id == "core.text":
            config.text = self._merge_model(config.text, values, TextConfig)
        elif app_id == "core.image":
            config.image = self._merge_model(config.image, values, ImageConfig)
        elif app_id == "core.draw":
            config.draw = self._merge_model(config.draw, values, DrawConfig)
        elif app_id == "core.slideshow":
            config.slideshow = self._merge_model(config.slideshow, values, SlideshowConfig)
        elif app_id == "core.testPattern":
            config.runtime.testPattern = bool(values.get("testPattern", config.runtime.testPattern))
        else:
            self._write_installed_app_config(app_id, values)
            return self.get_app_config(app_id)
        config_service.save_config(config)
        return self.get_app_config(app_id)

    def apply_app(self, app_id: str, values: dict[str, Any] | None = None):
        app = self._require_app(app_id)
        if values:
            self.update_app_config(app_id, values)
        config = config_service.get_config()
        if app_id in APP_MODE_MAP:
            mode = APP_MODE_MAP[app_id]
            config.display.mode = mode
            config.display.appId = ""
            config.runtime.testPattern = mode == "testPattern"
        else:
            self._require_installed_package(app_id)
            config.display.mode = "app"
            config.display.appId = app_id
            config.runtime.testPattern = False
        config_service.save_config(config)
        runtime = runtime_service.apply()
        return self.get_local_app(app.manifest.id), runtime

    def _require_app(self, app_id: str) -> LocalApp:
        app = self.get_local_app(app_id)
        if app is None:
            raise ValueError(f"Unknown app {app_id}.")
        return app

    def _merge_model(self, current: BaseModel, values: dict[str, Any], model_type: type[BaseModel]) -> Any:
        payload = current.model_dump()
        payload.update(values)
        return model_type.model_validate(payload)

    def _local_app(self, manifest: AppManifest, active_mode: str) -> LocalApp:
        return LocalApp(
            manifest=manifest,
            installed=True,
            builtIn=True,
            enabled=True,
            configurable=bool(manifest.config),
            active=manifest.id == f"core.{active_mode}",
        )

    def _built_in_manifests(self) -> list[AppManifest]:
        return [
            AppManifest(
                id="core.spotify",
                name="Spotify",
                version="1.0.0",
                summary="Shows the current Spotify album art as a spinning record.",
                category="media",
                runtime="builtin",
                entrypoint="spotify_matrix:run_spotify",
                preview=AppPreview(description="Album-art record with playback-aware rotation."),
                permissions=[AppPermission(name="network", reason="Reads Spotify playback state and downloads album art.")],
                config=[
                    AppConfigField(key="clientId", label="Client ID", type="string", required=True),
                    AppConfigField(key="clientSecret", label="Client Secret", type="secret", required=True),
                    AppConfigField(key="redirectUri", label="Redirect URI", type="string", required=True),
                ],
                triggers=[AppTrigger(event="spotify.playback_started", defaultEnabled=True, priority=50, minDurationSeconds=15)],
            ),
            AppManifest(
                id="core.clock",
                name="Clock",
                version="1.0.0",
                summary="Displays analog, digital, or minimal clock faces.",
                category="time",
                runtime="builtin",
                entrypoint="spotify_matrix:run_clock",
                preview=AppPreview(description="Live 64x64 clock face preview."),
                config=[
                    AppConfigField(
                        key="face",
                        label="Clock face",
                        type="select",
                        default="analog",
                        options=[_option("Analog", "analog"), _option("Digital", "digital"), _option("Minimal", "minimal")],
                    ),
                    AppConfigField(key="use24Hour", label="24-hour time", type="boolean", default=False),
                    AppConfigField(key="showSeconds", label="Show seconds", type="boolean", default=False),
                    AppConfigField(key="timezone", label="Timezone", type="select", default="America/Chicago"),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=10)],
            ),
            AppManifest(
                id="core.agent",
                name="Agent Face",
                version="1.0.0",
                summary="Animated assistant face with blinking and idle motion.",
                category="assistant",
                runtime="builtin",
                entrypoint="spotify_matrix:run_agent",
                preview=AppPreview(description="Animated assistant expression for idle and future voice modes."),
                config=[
                    AppConfigField(
                        key="faceStyle",
                        label="Face style",
                        type="select",
                        default="classic",
                        options=[_option("Classic", "classic"), _option("Wide", "wide"), _option("Sleepy", "sleepy"), _option("Happy", "happy"), _option("Cool", "cool")],
                    ),
                    AppConfigField(
                        key="animationSpeed",
                        label="Animation speed",
                        type="select",
                        default="normal",
                        options=[_option("Slow", "slow"), _option("Normal", "normal"), _option("Fast", "fast")],
                    ),
                ],
                triggers=[AppTrigger(event="agent.listening", defaultEnabled=False, priority=80)],
            ),
            AppManifest(
                id="core.weather",
                name="Weather",
                version="1.0.0",
                summary="Shows weather metrics, AQI, UV, wind, and animated assistant weather scenes.",
                category="information",
                runtime="builtin",
                entrypoint="spotify_matrix:run_weather",
                preview=AppPreview(description="Alternates weather metric tiles with a playful assistant weather scene."),
                permissions=[
                    AppPermission(name="network", reason="Fetches weather, geocoding, UV, and air quality data."),
                    AppPermission(name="location", reason="Uses ZIP/postal code or coordinates to request local weather."),
                ],
                config=[
                    AppConfigField(key="label", label="Location label", type="string", default="Local weather"),
                    AppConfigField(key="postalCode", label="ZIP / PIN / postal code", type="string", placeholder="60601 or 560001"),
                    AppConfigField(
                        key="countryCode",
                        label="Country",
                        type="select",
                        default="US",
                        options=[_option("United States", "US"), _option("Canada", "CA"), _option("United Kingdom", "GB"), _option("India", "IN")],
                    ),
                    AppConfigField(
                        key="temperatureUnit",
                        label="Temperature unit",
                        type="select",
                        default="fahrenheit",
                        options=[_option("Fahrenheit", "fahrenheit"), _option("Celsius", "celsius")],
                    ),
                    AppConfigField(
                        key="faceAccessory",
                        label="Face accessory",
                        type="select",
                        default="auto",
                        options=[_option("Auto", "auto"), _option("None", "none"), _option("Sunglasses", "sunglasses"), _option("Umbrella", "umbrella")],
                    ),
                    AppConfigField(key="refreshMinutes", label="Refresh minutes", type="number", default=15, min=5, max=120, step=1),
                    AppConfigField(key="metricsSeconds", label="Dashboard seconds", type="number", default=45, min=30, max=120, step=1),
                    AppConfigField(key="sceneSeconds", label="Scene seconds", type="number", default=20, min=15, max=60, step=1),
                    AppConfigField(key="latitude", label="Latitude override", type="number", required=False),
                    AppConfigField(key="longitude", label="Longitude override", type="number", required=False),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=20)],
            ),
            AppManifest(
                id="core.text",
                name="Custom Message",
                version="1.0.0",
                summary="Show your own static or scrolling text message.",
                category="custom",
                runtime="builtin",
                entrypoint="spotify_matrix:run_text",
                preview=AppPreview(description="Custom message on the 64x64 matrix with color and scroll options."),
                config=[
                    AppConfigField(key="text", label="Message", type="string", default="HELLO", required=True),
                    AppConfigField(key="color", label="Text color", type="string", default="#ffffff", placeholder="#ffffff"),
                    AppConfigField(key="background", label="Background color", type="string", default="#000000", placeholder="#000000"),
                    AppConfigField(
                        key="fontFamily",
                        label="Font",
                        type="select",
                        default="pixel",
                        options=[_option("Pixel", "pixel"), _option("Sans", "sans"), _option("Mono", "mono"), _option("Devanagari", "devanagari")],
                    ),
                    AppConfigField(
                        key="fontSize",
                        label="Font size",
                        type="select",
                        default="medium",
                        options=[_option("Small", "small"), _option("Medium", "medium"), _option("Large", "large")],
                    ),
                    AppConfigField(key="bold", label="Bold", type="boolean", default=False),
                    AppConfigField(key="italic", label="Italic", type="boolean", default=False),
                    AppConfigField(key="wrap", label="Wrap text", type="boolean", default=False),
                    AppConfigField(key="fit", label="Fit to screen", type="boolean", default=False),
                    AppConfigField(
                        key="align",
                        label="Alignment",
                        type="select",
                        default="center",
                        options=[_option("Left", "left"), _option("Center", "center"), _option("Right", "right")],
                    ),
                    AppConfigField(key="scroll", label="Scroll long text", type="boolean", default=False),
                    AppConfigField(
                        key="scrollSpeed",
                        label="Scroll speed",
                        type="select",
                        default="normal",
                        options=[_option("Slow", "slow"), _option("Normal", "normal"), _option("Fast", "fast")],
                    ),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=15)],
            ),
            AppManifest(
                id="core.image",
                name="Image",
                version="1.0.0",
                summary="Upload an image and display it on the matrix.",
                category="custom",
                runtime="builtin",
                entrypoint="spotify_matrix:run_image",
                preview=AppPreview(description="Shows an uploaded image scaled to the 64x64 panel."),
                config=[
                    AppConfigField(key="assetPath", label="Image", type="string"),
                    AppConfigField(
                        key="fit",
                        label="Fit",
                        type="select",
                        default="contain",
                        options=[_option("Contain", "contain"), _option("Cover", "cover"), _option("Stretch", "stretch")],
                    ),
                    AppConfigField(key="background", label="Background color", type="string", default="#000000"),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=15)],
            ),
            AppManifest(
                id="core.draw",
                name="Draw",
                version="1.0.0",
                summary="Compose shapes and text into a custom matrix drawing.",
                category="custom",
                runtime="builtin",
                entrypoint="spotify_matrix:run_draw",
                preview=AppPreview(description="Custom drawing built from rectangles, circles, lines, and text."),
                config=[
                    AppConfigField(key="background", label="Background color", type="string", default="#000000"),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=15)],
            ),
            AppManifest(
                id="core.slideshow",
                name="Slideshow",
                version="1.0.0",
                summary="Cycle through a gallery of images and memes.",
                category="media",
                runtime="builtin",
                entrypoint="spotify_matrix:run_slideshow",
                preview=AppPreview(description="Rotating photo and meme slideshow from your gallery."),
                config=[
                    AppConfigField(key="intervalSeconds", label="Seconds per image", type="number", default=8, min=1, max=120, step=1),
                    AppConfigField(
                        key="fit",
                        label="Fit",
                        type="select",
                        default="cover",
                        options=[_option("Contain", "contain"), _option("Cover", "cover"), _option("Stretch", "stretch")],
                    ),
                    AppConfigField(key="background", label="Background color", type="string", default="#000000"),
                ],
                triggers=[AppTrigger(event="schedule.rotation", defaultEnabled=True, priority=15)],
            ),
            AppManifest(
                id="core.testPattern",
                name="Test Pattern",
                version="1.0.0",
                summary="Displays a diagnostic matrix test pattern.",
                category="diagnostics",
                runtime="builtin",
                entrypoint="spotify_matrix:run_test_pattern",
                preview=AppPreview(description="RGB matrix diagnostics pattern."),
                config=[],
            ),
        ]

    def _app_package_dir(self, app_id: str):
        """Installed packages win, so a Store build can replace a shipped game."""
        from src.domain.services.game_service import game_service

        return game_service.app_package_dir(_safe_app_id(app_id))

    def _app_config_path(self, app_id: str):
        return config_service.data_dir / "apps" / "config" / f"{_safe_app_id(app_id)}.json"

    def _read_installed_manifest(self, app_id: str) -> AppManifest | None:
        manifest_path = self._app_package_dir(app_id) / "app.toml"
        if not manifest_path.exists():
            return None
        return _manifest_from_toml(tomllib.loads(manifest_path.read_text(encoding="utf-8")))

    def _require_installed_package(self, app_id: str) -> None:
        manifest = self._read_installed_manifest(app_id)  # bundled or installed
        if manifest is None:
            raise ValueError(f"App {app_id} is installed as catalog metadata but no runnable package is present.")
        if manifest.runtime != "python" or not manifest.entrypoint:
            raise ValueError(f"App {app_id} does not declare a runnable Python entrypoint.")

    def _read_installed_app_config(self, app_id: str) -> dict[str, Any]:
        self._require_installed_package(app_id)
        path = self._app_config_path(app_id)
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            return payload if isinstance(payload, dict) else {}
        manifest = self._read_installed_manifest(app_id)
        defaults: dict[str, Any] = {}
        if manifest:
            for field in manifest.config:
                if field.default is not None:
                    defaults[field.key] = field.default
        return defaults

    def _write_installed_app_config(self, app_id: str, values: dict[str, Any]) -> None:
        self._require_installed_package(app_id)
        current = self._read_installed_app_config(app_id)
        current.update(values)
        path = self._app_config_path(app_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(current, file, indent=2)
            file.write("\n")

    def _installed_store_apps(self) -> list[LocalApp]:
        installed_path = config_service.data_dir / "apps" / "installed.json"
        try:
            with installed_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError:
            return []
        raw_apps = payload.get("apps", payload if isinstance(payload, list) else [])
        apps: list[LocalApp] = []
        for raw_app in raw_apps:
            store_app = StoreApp.model_validate(raw_app)
            package_manifest = self._read_installed_manifest(store_app.id)
            manifest = package_manifest or AppManifest(
                id=store_app.id,
                name=store_app.name,
                version=store_app.version,
                summary=store_app.summary,
                author=store_app.author,
                category=store_app.category,
                runtime="python",
                matrixSize="64x64",
                preview=AppPreview(cardGif=store_app.previewGifUrl, matrixPreview=store_app.matrixPreviewUrl),
            )
            config = config_service.get_config()
            apps.append(
                LocalApp(
                    manifest=manifest,
                    installed=True,
                    builtIn=False,
                    enabled=True,
                    configurable=bool(manifest.config),
                    active=config.display.mode == "app" and config.display.appId == store_app.id,
                )
            )
        return apps


app_registry_service = AppRegistryService()
