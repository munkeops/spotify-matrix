"""Widget configuration field helpers."""

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
    options: list[str] = field(default_factory=list)
    help_text: str = ""

    @classmethod
    def string(cls, key: str, *, label: str, required: bool = False, default: str = "", placeholder: str = "", help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="string", required=required, default=default, placeholder=placeholder, help_text=help_text)

    @classmethod
    def number(cls, key: str, *, label: str, required: bool = False, default: int | float = 0, help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="number", required=required, default=default, help_text=help_text)

    @classmethod
    def boolean(cls, key: str, *, label: str, default: bool = False, help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="boolean", default=default, help_text=help_text)

    @classmethod
    def select(cls, key: str, options: list[str], *, label: str, required: bool = False, default: str = "", help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="select", required=required, default=default or (options[0] if options else ""), options=options, help_text=help_text)

    @classmethod
    def secret(cls, key: str, *, label: str, required: bool = False, placeholder: str = "", help_text: str = "") -> "ConfigField":
        return cls(key=key, label=label, type="secret", required=required, placeholder=placeholder, help_text=help_text)

    def to_manifest(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "placeholder": self.placeholder,
            "options": [{"label": option, "value": option} for option in self.options],
            "helpText": self.help_text,
        }
