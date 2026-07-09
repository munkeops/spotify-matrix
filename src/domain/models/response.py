"""Shared API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    data: Any = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    message: str
    detail: str | None = None
