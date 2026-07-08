"""API request and response schemas for Spotify Matrix."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SpotifyConfig(BaseModel):
    clientId: str = ""
    clientSecret: str = ""
    redirectUri: str = "http://127.0.0.1/callback"


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


class RuntimeConfig(BaseModel):
    mockOutput: str = ""
    testPattern: bool = False


class AppConfig(BaseModel):
    spotify: SpotifyConfig = Field(default_factory=SpotifyConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


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
