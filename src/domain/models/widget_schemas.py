"""Widget registry schemas for Assistant Matrix."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ConfigFieldType = Literal["string", "number", "boolean", "select", "secret", "location", "color"]
WidgetCategory = Literal["media", "time", "assistant", "information", "diagnostics", "custom"]
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
