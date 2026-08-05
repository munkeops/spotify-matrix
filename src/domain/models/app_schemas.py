"""App registry schemas for Assistant Matrix."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ConfigFieldType = Literal["string", "number", "boolean", "select", "secret", "location", "color"]
AppCategory = Literal["media", "time", "assistant", "information", "diagnostics", "games", "custom"]
AppKind = Literal["app", "game"]
AppRuntime = Literal["builtin", "python"]


class AppPreview(BaseModel):
    cardGif: str = ""
    matrixPreview: str = ""
    description: str = ""


class AppPermission(BaseModel):
    name: str
    reason: str


class AppConfigOption(BaseModel):
    label: str
    value: str | int | float | bool


class AppConfigField(BaseModel):
    key: str
    label: str
    type: ConfigFieldType
    required: bool = False
    default: Any = None
    placeholder: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[AppConfigOption] = Field(default_factory=list)
    helpText: str = ""


class AppTrigger(BaseModel):
    event: str
    defaultEnabled: bool = False
    priority: int = 0
    minDurationSeconds: int = 0


class AppManifest(BaseModel):
    id: str
    name: str
    version: str
    summary: str
    author: str = "Assistant Matrix"
    category: AppCategory = "custom"
    runtime: AppRuntime = "builtin"
    entrypoint: str = ""
    matrixSize: str = "64x64"
    license: str = "MIT"
    preview: AppPreview = Field(default_factory=AppPreview)
    permissions: list[AppPermission] = Field(default_factory=list)
    config: list[AppConfigField] = Field(default_factory=list)
    triggers: list[AppTrigger] = Field(default_factory=list)
    kind: AppKind = "app"
    layout: str = ""
    actions: list[str] = Field(default_factory=list)


class LocalApp(BaseModel):
    manifest: AppManifest
    installed: bool = True
    builtIn: bool = False
    enabled: bool = True
    configurable: bool = True
    active: bool = False


class LocalAppListResponse(BaseModel):
    apps: list[LocalApp]


class AppConfigResponse(BaseModel):
    appId: str
    config: dict[str, Any] = Field(default_factory=dict)


class AppConfigUpdateRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class AppPreviewRequest(BaseModel):
    appId: str
    config: dict[str, Any] = Field(default_factory=dict)


class AppPreviewResponse(BaseModel):
    ok: bool
    appId: str
    dataUrl: str


class AppApplyRequest(BaseModel):
    config: dict[str, Any] | None = None


class AppApplyResponse(BaseModel):
    ok: bool
    app: LocalApp
    runtime: Any


class StoreApp(BaseModel):
    id: str
    name: str
    version: str
    summary: str
    category: AppCategory = "custom"
    author: str = "Assistant Matrix"
    runtime: str = "python"
    manifestUrl: str = ""
    archiveUrl: str = ""
    previewGifUrl: str = ""
    matrixPreviewUrl: str = ""
    sha256: str = ""
    installed: bool = False


class AppStoreIndex(BaseModel):
    schemaVersion: int = 1
    apps: list[StoreApp] = Field(default_factory=list)


class AppStoreListResponse(BaseModel):
    schemaVersion: int = 1
    apps: list[StoreApp] = Field(default_factory=list)


class AppInstallRequest(BaseModel):
    appId: str


class AppInstallResponse(BaseModel):
    ok: bool
    app: LocalApp


class AppUninstallResponse(BaseModel):
    ok: bool
    appId: str


DisplayPolicyMode = Literal["single", "rotation"]


class DisplayRotationItem(BaseModel):
    appId: str
    durationSeconds: int = Field(default=60, ge=5, le=86400)
    enabled: bool = True


class DisplayTriggerRule(BaseModel):
    event: str
    appId: str
    enabled: bool = True
    priority: int = 0
    minDurationSeconds: int = Field(default=15, ge=0, le=86400)


class DisplayPolicy(BaseModel):
    mode: DisplayPolicyMode = "single"
    activeAppId: str = "core.spotify"
    rotation: list[DisplayRotationItem] = Field(default_factory=list)
    triggers: list[DisplayTriggerRule] = Field(default_factory=list)


class DisplayPolicyResponse(BaseModel):
    policy: DisplayPolicy


class DisplayPolicyUpdateRequest(BaseModel):
    policy: DisplayPolicy


class DisplayPolicyRuntimeState(BaseModel):
    schedulerRunning: bool = False
    activeAppId: str | None = None
    mode: DisplayPolicyMode = "single"
    activeEvent: str | None = None
    lastError: str | None = None


class DisplayPolicyApplyResponse(BaseModel):
    ok: bool
    policy: DisplayPolicy
    state: DisplayPolicyRuntimeState
    runtime: Any = None


class DisplayEventRequest(BaseModel):
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DisplayEventResponse(BaseModel):
    ok: bool
    matched: bool
    event: str
    appId: str | None = None
    state: DisplayPolicyRuntimeState
    runtime: Any = None
