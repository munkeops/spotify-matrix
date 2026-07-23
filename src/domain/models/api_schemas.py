"""API request and response schemas for Spotify Matrix."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SpotifyConfig(BaseModel):
    clientId: str = ""
    clientSecret: str = ""
    redirectUri: str = "http://127.0.0.1:8888/callback"


class MatrixConfig(BaseModel):
    rows: int = 64
    cols: int = 64
    chainLength: int = 1
    parallel: int = 1
    brightness: int = 65
    gpioSlowdown: int = 4
    hardwareMapping: str = "adafruit-hat"
    pwmBits: int = 11
    limitRefreshRateHz: int = 120
    noHardwarePulse: bool = True
    pollSeconds: float = 2
    fps: float = 20
    rpm: float = 20
    rotation: Literal[0, 90, 180, 270] = 0


class RuntimeConfig(BaseModel):
    mockOutput: str = ""
    testPattern: bool = False


class DisplayConfig(BaseModel):
    mode: Literal["spotify", "clock", "agent", "weather", "text", "image", "draw", "slideshow", "testPattern", "widget"] = "spotify"
    widgetId: str = ""


class ClockConfig(BaseModel):
    face: Literal["analog", "digital", "minimal"] = "analog"
    use24Hour: bool = False
    showSeconds: bool = False
    timezone: str = ""


class AgentConfig(BaseModel):
    faceStyle: Literal["classic", "wide", "sleepy", "happy", "cool"] = "classic"
    animationSpeed: Literal["slow", "normal", "fast"] = "normal"


class WeatherConfig(BaseModel):
    label: str = "Local weather"
    postalCode: str = ""
    countryCode: str = "US"
    latitude: float | None = None
    longitude: float | None = None
    temperatureUnit: Literal["fahrenheit", "celsius"] = "fahrenheit"
    faceAccessory: Literal["auto", "none", "sunglasses", "umbrella"] = "auto"
    refreshMinutes: int = 15
    metricsSeconds: int = 45
    sceneSeconds: int = 20


class TextConfig(BaseModel):
    text: str = "HELLO"
    color: str = "#ffffff"
    background: str = "#000000"
    scroll: bool = False
    scrollSpeed: Literal["slow", "normal", "fast"] = "normal"
    fontSize: Literal["small", "medium", "large"] = "medium"
    align: Literal["left", "center", "right"] = "center"
    fontFamily: Literal["pixel", "sans", "mono", "devanagari"] = "pixel"
    bold: bool = False
    italic: bool = False
    wrap: bool = False
    fit: bool = False


class ImageConfig(BaseModel):
    assetPath: str = ""
    fit: Literal["contain", "cover", "stretch"] = "contain"
    background: str = "#000000"
    rotate: Literal[0, 90, 180, 270] = 0


class DrawShape(BaseModel):
    type: Literal["rect", "circle", "line", "text", "pixel"] = "rect"
    color: str = "#ffffff"
    x: int = 0
    y: int = 0
    w: int = 8
    h: int = 8
    radius: int = 4
    x2: int = 16
    y2: int = 16
    text: str = ""
    size: Literal["small", "medium", "large"] = "small"
    fill: bool = True
    fontFamily: Literal["pixel", "sans", "mono", "devanagari"] = "pixel"
    bold: bool = False
    italic: bool = False


class DrawConfig(BaseModel):
    background: str = "#000000"
    shapes: list[DrawShape] = Field(default_factory=list)


class SlideshowConfig(BaseModel):
    items: list[str] = Field(default_factory=list)
    intervalSeconds: int = 8
    fit: Literal["contain", "cover", "stretch"] = "cover"
    background: str = "#000000"
    rotate: Literal[0, 90, 180, 270] = 0
    shuffle: bool = False


class StoreConfig(BaseModel):
    indexUrl: str = "configs/widget_store_index.json"


class AssetUploadRequest(BaseModel):
    name: str = ""
    data: str


class AssetUploadResponse(BaseModel):
    ok: bool
    assetPath: str
    url: str


class AssetItem(BaseModel):
    name: str
    url: str
    animated: bool = False


class AssetListResponse(BaseModel):
    assets: list[AssetItem] = Field(default_factory=list)


class AppConfig(BaseModel):
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    clock: ClockConfig = Field(default_factory=ClockConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    text: TextConfig = Field(default_factory=TextConfig)
    image: ImageConfig = Field(default_factory=ImageConfig)
    draw: DrawConfig = Field(default_factory=DrawConfig)
    slideshow: SlideshowConfig = Field(default_factory=SlideshowConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)


class TokenStatus(BaseModel):
    present: bool
    hasRefreshToken: bool = False
    expiresAt: float | None = None


class RuntimeExit(BaseModel):
    code: int | None = None
    signal: str | None = None
    at: str | None = None


class RuntimeState(BaseModel):
    running: bool
    pid: int | None = None
    startedAt: str | None = None
    lastExit: RuntimeExit | None = None


class StatusResponse(BaseModel):
    configured: bool
    missing: list[str]
    token: TokenStatus
    runtime: RuntimeState
    dataDir: str


class AuthSessionResponse(BaseModel):
    pairingToken: str
    expiresInSeconds: int
    command: str


class AuthSessionSecrets(BaseModel):
    clientId: str
    clientSecret: str
    scope: str


class SpotifyToken(BaseModel):
    access_token: str | None = None
    token_type: str | None = None
    scope: str | None = None
    expires_in: int = 3600
    refresh_token: str

    class Config:
        extra = "allow"


class TokenRequest(BaseModel):
    pairingToken: str
    token: SpotifyToken


class TokenSaveResponse(BaseModel):
    ok: bool
    token: TokenStatus


class RuntimeActionResponse(BaseModel):
    runtime: RuntimeState


class CommandRequest(BaseModel):
    command: Literal["set_mode", "set_widget", "set_clock_face", "set_brightness", "trigger_event", "start_runtime", "stop_runtime"]
    value: str | int | None = None


class CommandResponse(BaseModel):
    ok: bool
    config: AppConfig
    runtime: Any = None
    matched: bool | None = None
    widgetId: str | None = None
