"""Local widget registry for built-in Assistant Matrix widgets."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.domain.models.api_schemas import AgentConfig, ClockConfig, SpotifyConfig, WeatherConfig
from src.domain.models.widget_schemas import LocalWidget, WidgetConfigField, WidgetConfigOption, WidgetManifest, WidgetPermission, WidgetPreview, WidgetTrigger
from src.domain.services.config_service import config_service
from src.domain.services.runtime_service import runtime_service


def _option(label: str, value: str | int | float | bool) -> WidgetConfigOption:
    return WidgetConfigOption(label=label, value=value)


WIDGET_MODE_MAP = {
    "core.spotify": "spotify",
    "core.clock": "clock",
    "core.agent": "agent",
    "core.weather": "weather",
    "core.testPattern": "testPattern",
}


class WidgetRegistryService:
    def list_local_widgets(self) -> list[LocalWidget]:
        config = config_service.get_config()
        active_mode = "testPattern" if config.runtime.testPattern else config.display.mode
        return [self._local_widget(manifest, active_mode) for manifest in self._built_in_manifests()]

    def get_local_widget(self, widget_id: str) -> LocalWidget | None:
        for widget in self.list_local_widgets():
            if widget.manifest.id == widget_id:
                return widget
        return None

    def get_widget_config(self, widget_id: str) -> dict[str, Any]:
        self._require_widget(widget_id)
        config = config_service.get_public_config()
        if widget_id == "core.spotify":
            return config.spotify.model_dump()
        if widget_id == "core.clock":
            return config.clock.model_dump()
        if widget_id == "core.agent":
            return config.agent.model_dump()
        if widget_id == "core.weather":
            return config.weather.model_dump()
        if widget_id == "core.testPattern":
            return {"testPattern": config.runtime.testPattern}
        raise ValueError(f"Widget {widget_id} is not configurable.")

    def update_widget_config(self, widget_id: str, values: dict[str, Any]) -> dict[str, Any]:
        self._require_widget(widget_id)
        config = config_service.get_config()
        if widget_id == "core.spotify":
            if values.get("clientSecret") == "********":
                values = {key: value for key, value in values.items() if key != "clientSecret"}
            config.spotify = self._merge_model(config.spotify, values, SpotifyConfig)
        elif widget_id == "core.clock":
            config.clock = self._merge_model(config.clock, values, ClockConfig)
        elif widget_id == "core.agent":
            config.agent = self._merge_model(config.agent, values, AgentConfig)
        elif widget_id == "core.weather":
            config.weather = self._merge_model(config.weather, values, WeatherConfig)
        elif widget_id == "core.testPattern":
            config.runtime.testPattern = bool(values.get("testPattern", config.runtime.testPattern))
        else:
            raise ValueError(f"Widget {widget_id} is not configurable.")
        config_service.save_config(config)
        return self.get_widget_config(widget_id)

    def apply_widget(self, widget_id: str, values: dict[str, Any] | None = None):
        widget = self._require_widget(widget_id)
        if values:
            self.update_widget_config(widget_id, values)
        config = config_service.get_config()
        mode = WIDGET_MODE_MAP[widget_id]
        config.display.mode = mode
        config.runtime.testPattern = mode == "testPattern"
        config_service.save_config(config)
        runtime = runtime_service.apply()
        return self.get_local_widget(widget.manifest.id), runtime

    def _require_widget(self, widget_id: str) -> LocalWidget:
        widget = self.get_local_widget(widget_id)
        if widget is None:
            raise ValueError(f"Unknown widget {widget_id}.")
        return widget

    def _merge_model(self, current: BaseModel, values: dict[str, Any], model_type: type[BaseModel]) -> Any:
        payload = current.model_dump()
        payload.update(values)
        return model_type.model_validate(payload)

    def _local_widget(self, manifest: WidgetManifest, active_mode: str) -> LocalWidget:
        return LocalWidget(
            manifest=manifest,
            installed=True,
            builtIn=True,
            enabled=True,
            configurable=bool(manifest.config),
            active=manifest.id == f"core.{active_mode}",
        )

    def _built_in_manifests(self) -> list[WidgetManifest]:
        return [
            WidgetManifest(
                id="core.spotify",
                name="Spotify",
                version="1.0.0",
                summary="Shows the current Spotify album art as a spinning record.",
                category="media",
                runtime="builtin",
                entrypoint="spotify_matrix:run_spotify",
                preview=WidgetPreview(description="Album-art record with playback-aware rotation."),
                permissions=[WidgetPermission(name="network", reason="Reads Spotify playback state and downloads album art.")],
                config=[
                    WidgetConfigField(key="clientId", label="Client ID", type="string", required=True),
                    WidgetConfigField(key="clientSecret", label="Client Secret", type="secret", required=True),
                    WidgetConfigField(key="redirectUri", label="Redirect URI", type="string", required=True),
                ],
                triggers=[WidgetTrigger(event="spotify.playback_started", defaultEnabled=True, priority=50, minDurationSeconds=15)],
            ),
            WidgetManifest(
                id="core.clock",
                name="Clock",
                version="1.0.0",
                summary="Displays analog, digital, or minimal clock faces.",
                category="time",
                runtime="builtin",
                entrypoint="spotify_matrix:run_clock",
                preview=WidgetPreview(description="Live 64x64 clock face preview."),
                config=[
                    WidgetConfigField(
                        key="face",
                        label="Clock face",
                        type="select",
                        default="analog",
                        options=[_option("Analog", "analog"), _option("Digital", "digital"), _option("Minimal", "minimal")],
                    ),
                    WidgetConfigField(key="use24Hour", label="24-hour time", type="boolean", default=False),
                    WidgetConfigField(key="showSeconds", label="Show seconds", type="boolean", default=False),
                    WidgetConfigField(key="timezone", label="Timezone", type="select", default="America/Chicago"),
                ],
                triggers=[WidgetTrigger(event="schedule.rotation", defaultEnabled=True, priority=10)],
            ),
            WidgetManifest(
                id="core.agent",
                name="Agent Face",
                version="1.0.0",
                summary="Animated assistant face with blinking and idle motion.",
                category="assistant",
                runtime="builtin",
                entrypoint="spotify_matrix:run_agent",
                preview=WidgetPreview(description="Animated assistant expression for idle and future voice modes."),
                config=[
                    WidgetConfigField(
                        key="faceStyle",
                        label="Face style",
                        type="select",
                        default="classic",
                        options=[_option("Classic", "classic"), _option("Wide", "wide"), _option("Sleepy", "sleepy"), _option("Happy", "happy"), _option("Cool", "cool")],
                    ),
                    WidgetConfigField(
                        key="animationSpeed",
                        label="Animation speed",
                        type="select",
                        default="normal",
                        options=[_option("Slow", "slow"), _option("Normal", "normal"), _option("Fast", "fast")],
                    ),
                ],
                triggers=[WidgetTrigger(event="agent.listening", defaultEnabled=False, priority=80)],
            ),
            WidgetManifest(
                id="core.weather",
                name="Weather",
                version="1.0.0",
                summary="Shows weather metrics, AQI, UV, wind, and animated assistant weather scenes.",
                category="information",
                runtime="builtin",
                entrypoint="spotify_matrix:run_weather",
                preview=WidgetPreview(description="Alternates weather metric tiles with a playful assistant weather scene."),
                permissions=[
                    WidgetPermission(name="network", reason="Fetches weather, geocoding, UV, and air quality data."),
                    WidgetPermission(name="location", reason="Uses ZIP/postal code or coordinates to request local weather."),
                ],
                config=[
                    WidgetConfigField(key="label", label="Location label", type="string", default="Local weather"),
                    WidgetConfigField(key="postalCode", label="ZIP / postal code", type="string", placeholder="60601"),
                    WidgetConfigField(
                        key="countryCode",
                        label="Country",
                        type="select",
                        default="US",
                        options=[_option("United States", "US"), _option("Canada", "CA"), _option("United Kingdom", "GB"), _option("India", "IN")],
                    ),
                    WidgetConfigField(
                        key="temperatureUnit",
                        label="Temperature unit",
                        type="select",
                        default="fahrenheit",
                        options=[_option("Fahrenheit", "fahrenheit"), _option("Celsius", "celsius")],
                    ),
                    WidgetConfigField(
                        key="faceAccessory",
                        label="Face accessory",
                        type="select",
                        default="auto",
                        options=[_option("Auto", "auto"), _option("None", "none"), _option("Sunglasses", "sunglasses"), _option("Umbrella", "umbrella")],
                    ),
                    WidgetConfigField(key="refreshMinutes", label="Refresh minutes", type="number", default=15, min=5, max=120, step=1),
                    WidgetConfigField(key="latitude", label="Latitude override", type="number", required=False),
                    WidgetConfigField(key="longitude", label="Longitude override", type="number", required=False),
                ],
                triggers=[WidgetTrigger(event="schedule.rotation", defaultEnabled=True, priority=20)],
            ),
            WidgetManifest(
                id="core.testPattern",
                name="Test Pattern",
                version="1.0.0",
                summary="Displays a diagnostic matrix test pattern.",
                category="diagnostics",
                runtime="builtin",
                entrypoint="spotify_matrix:run_test_pattern",
                preview=WidgetPreview(description="RGB matrix diagnostics pattern."),
                config=[],
            ),
        ]


widget_registry_service = WidgetRegistryService()
