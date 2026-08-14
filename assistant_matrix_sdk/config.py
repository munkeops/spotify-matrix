"""App configuration field helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ConfigFieldType = Literal["string", "number", "boolean", "select", "secret", "location", "color"]


@dataclass(frozen=True)
class ConfigField:
    key: str
    label: str
    type: ConfigFieldType
    required: bool = False
    default: Any = None
    placeholder: str = ""
    #: Either plain values, or (label, value) pairs when they should differ.
    options: list[Any] = field(default_factory=list)
    help_text: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None

    @classmethod
    def string(cls, key: str, *, label: str, required: bool = False, default: str = "", placeholder: str = "", help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="string", required=required, default=default, placeholder=placeholder, help_text=help_text)

    @classmethod
    def number(
        cls,
        key: str,
        *,
        label: str,
        required: bool = False,
        default: int | float = 0,
        help_text: str = "",
        minimum: float | None = None,
        maximum: float | None = None,
        step: float | None = None,
    ) -> "ConfigField":
        return cls(
            key=key, label=label, type="number", required=required, default=default,
            help_text=help_text, minimum=minimum, maximum=maximum, step=step,
        )

    @classmethod
    def boolean(cls, key: str, *, label: str, default: bool = False, help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="boolean", default=default, help_text=help_text)

    @classmethod
    def select(cls, key: str, options: list[Any], *, label: str, required: bool = False, default: Any = None, help_text: str = "") -> "ConfigField":
        first = options[0] if options else ""
        fallback = first[1] if isinstance(first, (tuple, list)) else first
        return cls(
            key=key, label=label, type="select", required=required,
            default=fallback if default is None else default, options=options, help_text=help_text,
        )

    @classmethod
    def secret(cls, key: str, *, label: str, required: bool = False, placeholder: str = "", help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="secret", required=required, placeholder=placeholder, help_text=help_text)

    def to_manifest(self) -> dict[str, Any]:
        options = []
        for option in self.options:
            if isinstance(option, (tuple, list)) and len(option) == 2:
                options.append({"label": option[0], "value": option[1]})
            else:
                options.append({"label": str(option), "value": option})
        manifest: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "placeholder": self.placeholder,
            "options": options,
            "helpText": self.help_text,
        }
        for name, value in (("min", self.minimum), ("max", self.maximum), ("step", self.step)):
            if value is not None:
                manifest[name] = value
        return manifest
