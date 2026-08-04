"""Widget registry schemas for Assistant Matrix."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ConfigFieldType = Literal["string", "number", "boolean", "select", "secret", "location", "color"]
WidgetCategory = Literal["media", "time", "assistant", "information", "diagnostics", "games", "custom"]
WidgetRuntime = Literal["builtin", "python"]


class WidgetPreview(BaseModel):
    cardGif: str = ""
    matrixPreview: str = ""
    description: str = ""


class WidgetPermission(BaseModel):
    name: str
    reason: str


class WidgetConfigOption(BaseModel):
    label: str
    value: str | int | float | bool


class WidgetConfigField(BaseModel):
    key: str
    label: str
    type: ConfigFieldType
    required: bool = False
    default: Any = None
    placeholder: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[WidgetConfigOption] = Field(default_factory=list)
    helpText: str = ""


class WidgetTrigger(BaseModel):
    event: str
    defaultEnabled: bool = False
    priority: int = 0
    minDurationSeconds: int = 0


class WidgetManifest(BaseModel):
    id: str
    name: str
    version: str
    summary: str
    author: str = "Assistant Matrix"
    category: WidgetCategory = "custom"
    runtime: WidgetRuntime = "builtin"
    entrypoint: str = ""
    matrixSize: str = "64x64"
    license: str = "MIT"
    preview: WidgetPreview = Field(default_factory=WidgetPreview)
    permissions: list[WidgetPermission] = Field(default_factory=list)
    config: list[WidgetConfigField] = Field(default_factory=list)
    triggers: list[WidgetTrigger] = Field(default_factory=list)


class LocalWidget(BaseModel):
    manifest: WidgetManifest
    installed: bool = True
    builtIn: bool = False
    enabled: bool = True
    configurable: bool = True
    active: bool = False


class LocalWidgetListResponse(BaseModel):
    widgets: list[LocalWidget]


class WidgetConfigResponse(BaseModel):
    widgetId: str
    config: dict[str, Any] = Field(default_factory=dict)


class WidgetConfigUpdateRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class WidgetPreviewRequest(BaseModel):
    widgetId: str
    config: dict[str, Any] = Field(default_factory=dict)


class WidgetPreviewResponse(BaseModel):
    ok: bool
    widgetId: str
    dataUrl: str


class WidgetApplyRequest(BaseModel):
    config: dict[str, Any] | None = None


class WidgetApplyResponse(BaseModel):
    ok: bool
    widget: LocalWidget
    runtime: Any


class StoreWidget(BaseModel):
    id: str
    name: str
    version: str
    summary: str
    category: WidgetCategory = "custom"
    author: str = "Assistant Matrix"
    runtime: str = "python"
    manifestUrl: str = ""
    archiveUrl: str = ""
    previewGifUrl: str = ""
    matrixPreviewUrl: str = ""
    sha256: str = ""
    installed: bool = False


class WidgetStoreIndex(BaseModel):
    schemaVersion: int = 1
    widgets: list[StoreWidget] = Field(default_factory=list)


class WidgetStoreListResponse(BaseModel):
    schemaVersion: int = 1
    widgets: list[StoreWidget] = Field(default_factory=list)


class WidgetInstallRequest(BaseModel):
    widgetId: str


class WidgetInstallResponse(BaseModel):
    ok: bool
    widget: LocalWidget


class WidgetUninstallResponse(BaseModel):
    ok: bool
    widgetId: str


DisplayPolicyMode = Literal["single", "rotation"]


class DisplayRotationItem(BaseModel):
    widgetId: str
    durationSeconds: int = Field(default=60, ge=5, le=86400)
    enabled: bool = True


class DisplayTriggerRule(BaseModel):
    event: str
    widgetId: str
    enabled: bool = True
    priority: int = 0
    minDurationSeconds: int = Field(default=15, ge=0, le=86400)


class DisplayPolicy(BaseModel):
    mode: DisplayPolicyMode = "single"
    activeWidgetId: str = "core.spotify"
    rotation: list[DisplayRotationItem] = Field(default_factory=list)
    triggers: list[DisplayTriggerRule] = Field(default_factory=list)


class DisplayPolicyResponse(BaseModel):
    policy: DisplayPolicy


class DisplayPolicyUpdateRequest(BaseModel):
    policy: DisplayPolicy


class DisplayPolicyRuntimeState(BaseModel):
    schedulerRunning: bool = False
    activeWidgetId: str | None = None
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
    widgetId: str | None = None
    state: DisplayPolicyRuntimeState
    runtime: Any = None
