#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import datetime
from io import BytesIO
import json
import math
import os
import random
import secrets
import sys
import threading
import time
import tomllib
import urllib.parse
import urllib.request
from email.message import Message
from urllib.error import HTTPError
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps, ImageSequence

from assistant_matrix_sdk import MatrixCanvas, Widget, WidgetContext

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYER_STATE_URL = "https://api.spotify.com/v1/me/player"
SCOPE = "user-read-playback-state user-read-currently-playing"
DEFAULT_CONFIG_PATH = Path(os.environ.get("SPOTIFY_MATRIX_CONFIG", "data/config.json"))
DEFAULT_TOKEN_CACHE = Path(os.environ.get("SPOTIFY_TOKEN_CACHE", "data/spotify_token.json"))
WEATHER_METRICS_SECONDS = 45
WEATHER_SCENE_SECONDS = 20


@dataclass
class PlaybackArt:
    key: str
    image_url: str
    is_playing: bool


@dataclass
class SharedPlaybackState:
    art_key: str | None = None
    image_url: str | None = None
    image: Image.Image | None = None
    is_playing: bool = False


@dataclass
class WeatherState:
    temperature: float | None = None
    apparent_temperature: float | None = None
    uv_index: float | None = None
    aqi: float | None = None
    weather_code: int | None = None
    is_day: bool = True
    precipitation: float = 0.0
    rain: float = 0.0
    snowfall: float = 0.0
    cloud_cover: float = 0.0
    wind_speed: float = 0.0
    label: str = "Local weather"
    summary: str = "Loading"


@dataclass
class HttpResponse:
    status: int
    headers: Message
    body: bytes

    def json(self) -> dict[str, Any]:
        return json.loads(self.body.decode("utf-8"))


def http_request(
    method: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10,
) -> HttpResponse:
    if params:
        separator = "&" if urllib.parse.urlparse(url).query else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"

    encoded_data = urllib.parse.urlencode(data).encode("utf-8") if data else None
    request = urllib.request.Request(
        url,
        data=encoded_data,
        headers=headers or {},
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.headers, response.read())
    except HTTPError as exc:
        return HttpResponse(exc.code, exc.headers, exc.read())


def raise_http_error(response: HttpResponse, context: str) -> None:
    body = response.body.decode("utf-8", errors="replace")
    raise RuntimeError(f"{context} failed with HTTP {response.status}: {body}")


def post_json(url: str, payload: dict[str, Any], *, timeout: float = 2.0) -> HttpResponse:
    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.headers, response.read())
    except HTTPError as exc:
        return HttpResponse(exc.code, exc.headers, exc.read())


def load_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    if not isinstance(config, dict):
        raise RuntimeError(f"Config file {path} must contain a JSON object.")
    return config


def get_nested(config: dict[str, Any], section: str, name: str) -> Any:
    value = config.get(section, {})
    if isinstance(value, dict):
        return value.get(name)
    return None


def apply_config_defaults(args: argparse.Namespace, config: dict[str, Any]) -> None:
    matrix_fields = {
        "rows": int,
        "cols": int,
        "chainLength": int,
        "parallel": int,
        "brightness": int,
        "gpioSlowdown": int,
        "hardwareMapping": str,
        "pwmBits": int,
        "limitRefreshRateHz": int,
        "pollSeconds": float,
        "fps": float,
        "rpm": float,
        "noHardwarePulse": bool,
        "rotation": int,
    }
    attr_names = {
        "chainLength": "chain_length",
        "gpioSlowdown": "gpio_slowdown",
        "hardwareMapping": "hardware_mapping",
        "pwmBits": "pwm_bits",
        "limitRefreshRateHz": "limit_refresh_rate_hz",
        "pollSeconds": "poll_seconds",
        "noHardwarePulse": "no_hardware_pulse",
    }
    cli_flags = {
        "rows": ("--rows",),
        "cols": ("--cols",),
        "chainLength": ("--chain-length",),
        "parallel": ("--parallel",),
        "brightness": ("--brightness",),
        "gpioSlowdown": ("--gpio-slowdown",),
        "hardwareMapping": ("--hardware-mapping",),
        "pwmBits": ("--pwm-bits",),
        "limitRefreshRateHz": ("--limit-refresh-rate-hz",),
        "pollSeconds": ("--poll-seconds",),
        "fps": ("--fps",),
        "rpm": ("--rpm",),
        "noHardwarePulse": ("--no-hardware-pulse",),
        "rotation": ("--rotation",),
    }

    for config_name, caster in matrix_fields.items():
        if any(flag in sys.argv[1:] for flag in cli_flags[config_name]):
            continue
        value = get_nested(config, "matrix", config_name)
        if value is None:
            continue
        attr_name = attr_names.get(config_name, config_name)
        setattr(args, attr_name, caster(value))

    display_mode = get_nested(config, "display", "mode")
    if display_mode and "--display-mode" not in sys.argv[1:]:
        args.display_mode = str(display_mode)

    clock_fields = {
        "face": ("clock_face", str),
        "use24Hour": ("clock_24_hour", bool),
        "showSeconds": ("clock_show_seconds", bool),
        "timezone": ("clock_timezone", str),
    }
    clock_flags = {
        "face": ("--clock-face",),
        "use24Hour": ("--clock-24-hour",),
        "showSeconds": ("--clock-show-seconds",),
        "timezone": ("--clock-timezone",),
    }
    for config_name, (attr_name, caster) in clock_fields.items():
        if any(flag in sys.argv[1:] for flag in clock_flags[config_name]):
            continue
        value = get_nested(config, "clock", config_name)
        if value is not None:
            setattr(args, attr_name, caster(value))

    agent_fields = {
        "faceStyle": ("agent_face_style", str),
        "animationSpeed": ("agent_animation_speed", str),
    }
    agent_flags = {
        "faceStyle": ("--agent-face-style",),
        "animationSpeed": ("--agent-animation-speed",),
    }
    for config_name, (attr_name, caster) in agent_fields.items():
        if any(flag in sys.argv[1:] for flag in agent_flags[config_name]):
            continue
        value = get_nested(config, "agent", config_name)
        if value is not None:
            setattr(args, attr_name, caster(value))

    weather_fields = {
        "label": ("weather_label", str),
        "postalCode": ("weather_postal_code", str),
        "countryCode": ("weather_country_code", str),
        "latitude": ("weather_latitude", float),
        "longitude": ("weather_longitude", float),
        "temperatureUnit": ("weather_temperature_unit", str),
        "faceAccessory": ("weather_face_accessory", str),
        "refreshMinutes": ("weather_refresh_minutes", int),
        "metricsSeconds": ("weather_metrics_seconds", int),
        "sceneSeconds": ("weather_scene_seconds", int),
    }
    weather_flags = {
        "label": ("--weather-label",),
        "postalCode": ("--weather-postal-code",),
        "countryCode": ("--weather-country-code",),
        "latitude": ("--weather-latitude",),
        "longitude": ("--weather-longitude",),
        "temperatureUnit": ("--weather-temperature-unit",),
        "faceAccessory": ("--weather-face-accessory",),
        "refreshMinutes": ("--weather-refresh-minutes",),
        "metricsSeconds": ("--weather-metrics-seconds",),
        "sceneSeconds": ("--weather-scene-seconds",),
    }
    for config_name, (attr_name, caster) in weather_fields.items():
        if any(flag in sys.argv[1:] for flag in weather_flags[config_name]):
            continue
        value = get_nested(config, "weather", config_name)
        if value is not None:
            setattr(args, attr_name, caster(value))

    tetris_fields = {
        "startLevel": ("tetris_start_level", int, "--tetris-start-level"),
        "autoRestartSeconds": ("tetris_auto_restart_seconds", int, "--tetris-auto-restart-seconds"),
    }
    for config_name, (attr_name, caster, flag) in tetris_fields.items():
        if flag in sys.argv[1:]:
            continue
        value = get_nested(config, "tetris", config_name)
        if value is not None:
            setattr(args, attr_name, caster(value))

    ghost = get_nested(config, "tetris", "ghost")
    if ghost is not None and "--tetris-no-ghost" not in sys.argv[1:]:
        args.tetris_no_ghost = not bool(ghost)


def spotify_credentials(config: dict[str, Any]) -> tuple[str | None, str | None, str]:
    client_id = (
        get_nested(config, "spotify", "clientId")
        or get_nested(config, "spotify", "client_id")
        or os.environ.get("SPOTIFY_CLIENT_ID")
    )
    client_secret = (
        get_nested(config, "spotify", "clientSecret")
        or get_nested(config, "spotify", "client_secret")
        or os.environ.get("SPOTIFY_CLIENT_SECRET")
    )
    redirect_uri = (
        get_nested(config, "spotify", "redirectUri")
        or get_nested(config, "spotify", "redirect_uri")
        or os.environ.get("SPOTIFY_REDIRECT_URI")
        or "http://127.0.0.1:8888/callback"
    )
    return client_id, client_secret, str(redirect_uri)


class SpotifyClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_cache: Path,
        open_browser: bool,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_cache = token_cache
        self.open_browser = open_browser
        self.token = self._load_token()

    def get_currently_playing(self) -> dict[str, Any] | None:
        token = self._valid_access_token()
        response = http_request(
            "GET",
            PLAYER_STATE_URL,
            params={"additional_types": "track,episode"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

        if response.status == 204:
            return None
        if response.status == 401:
            self._refresh_access_token()
            return self.get_currently_playing()
        if response.status == 403:
            print("Spotify playback state returned 403 - re-authorize Spotify to grant the playback-state scope.", flush=True)
            return None
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            time.sleep(max(retry_after, 1))
            return None
        if response.status != 200:
            raise_http_error(response, "Spotify player-state request")

        return response.json()

    def authorize(self) -> None:
        self._valid_access_token()

    def _valid_access_token(self) -> str:
        if not self.token:
            self.token = self._authorize()

        if time.time() >= float(self.token.get("expires_at", 0)):
            self._refresh_access_token()

        return str(self.token["access_token"])

    def _load_token(self) -> dict[str, Any] | None:
        if not self.token_cache.exists():
            return None

        with self.token_cache.open("r", encoding="utf-8") as token_file:
            return json.load(token_file)

    def _save_token(self, token: dict[str, Any]) -> None:
        self.token_cache.parent.mkdir(parents=True, exist_ok=True)
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 60

        previous_refresh_token = self.token.get("refresh_token") if self.token else None
        if previous_refresh_token and "refresh_token" not in token:
            token["refresh_token"] = previous_refresh_token

        with self.token_cache.open("w", encoding="utf-8") as token_file:
            json.dump(token, token_file, indent=2)

        self.token = token

    def _authorize(self) -> dict[str, Any]:
        state = secrets.token_urlsafe(18)
        parsed_redirect = urllib.parse.urlparse(self.redirect_uri)
        if parsed_redirect.hostname not in {"127.0.0.1", "localhost"}:
            raise RuntimeError("This script expects a localhost Spotify redirect URI.")

        callback = LocalCallbackServer(
            host=parsed_redirect.hostname or "127.0.0.1",
            port=parsed_redirect.port or 80,
            path=parsed_redirect.path or "/callback",
            expected_state=state,
        )

        query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": SCOPE,
                "state": state,
            }
        )
        auth_url = f"{AUTH_URL}?{query}"

        print("Authorize Spotify in your browser:")
        print(auth_url)
        if self.open_browser:
            webbrowser.open(auth_url)

        code = callback.wait_for_code()
        token = self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            }
        )
        self._save_token(token)
        return token

    def _refresh_access_token(self) -> None:
        refresh_token = self.token.get("refresh_token") if self.token else None
        if not refresh_token:
            self.token = self._authorize()
            return

        token = self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        self._save_token(token)

    def _post_token(self, data: dict[str, str]) -> dict[str, Any]:
        credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        basic_auth = base64.b64encode(credentials).decode("ascii")
        response = http_request(
            "POST",
            TOKEN_URL,
            data=data,
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10,
        )
        if response.status != 200:
            raise_http_error(response, "Spotify token request")
        return response.json()


class LocalCallbackServer:
    def __init__(self, host: str, port: int, path: str, expected_state: str) -> None:
        self.code: str | None = None
        self.error: str | None = None
        self.state_error: str | None = None
        self.path = path
        self.expected_state = expected_state

        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if parsed.path != parent.path:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Wrong callback path.")
                    return

                returned_state = params.get("state", [""])[0]
                if returned_state != parent.expected_state:
                    parent.state_error = "Spotify callback state did not match."
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"State mismatch.")
                    return

                if "error" in params:
                    parent.error = params["error"][0]
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Spotify authorization failed.")
                    return

                parent.code = params.get("code", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Spotify authorization complete. You can close this tab.")

            def log_message(self, format: str, *args: Any) -> None:
                return

        self.server = HTTPServer((host, port), Handler)

    def wait_for_code(self) -> str:
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        try:
            while not self.code and not self.error and not self.state_error:
                time.sleep(0.1)
        finally:
            self.server.shutdown()
            self.server.server_close()

        if self.state_error:
            raise RuntimeError(self.state_error)
        if self.error:
            raise RuntimeError(f"Spotify authorization failed: {self.error}")
        if not self.code:
            raise RuntimeError("Spotify authorization did not return a code.")
        return self.code


class MatrixDisplay:
    def __init__(self, args: argparse.Namespace) -> None:
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions
        except ImportError as exc:
            raise RuntimeError(
                "The rgbmatrix Python bindings are not installed. "
                "Install hzeller/rpi-rgb-led-matrix on the Pi, or run with --mock-output."
            ) from exc

        options = RGBMatrixOptions()
        options.rows = args.rows
        options.cols = args.cols
        options.chain_length = args.chain_length
        options.parallel = args.parallel
        options.brightness = args.brightness
        options.gpio_slowdown = args.gpio_slowdown
        options.hardware_mapping = args.hardware_mapping
        options.pwm_bits = args.pwm_bits
        options.limit_refresh_rate_hz = args.limit_refresh_rate_hz
        options.disable_hardware_pulsing = args.no_hardware_pulse

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.rotation = args.rotation

    def show(self, image: Image.Image) -> None:
        if self.rotation:
            image = image.rotate(-self.rotation, expand=False)
        self.canvas.SetImage(image.convert("RGB"))
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def clear(self) -> None:
        self.matrix.Clear()


class MockDisplay:
    def __init__(self, output: Path, rotation: int = 0) -> None:
        self.output = output
        self.rotation = rotation
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def show(self, image: Image.Image) -> None:
        if self.rotation:
            image = image.rotate(-self.rotation, expand=False)
        image.save(self.output)

    def clear(self) -> None:
        return


def demo_album_art(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), (18, 18, 18))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size // 2, size // 2), fill=(238, 70, 60))
    draw.rectangle((size // 2, 0, size, size // 2), fill=(245, 180, 40))
    draw.rectangle((0, size // 2, size // 2, size), fill=(35, 150, 235))
    draw.rectangle((size // 2, size // 2, size, size), fill=(65, 185, 95))
    draw.line((0, 0, size, size), fill=(255, 255, 255), width=max(2, size // 18))
    draw.line((size, 0, 0, size), fill=(0, 0, 0), width=max(2, size // 22))
    return image


def playback_art_from_response(playback: dict[str, Any] | None) -> PlaybackArt | None:
    if not playback:
        return None

    item = playback.get("item")
    if not item:
        return None

    item_type = item.get("type")
    if item_type == "track":
        images = item.get("album", {}).get("images", [])
    else:
        images = item.get("images", [])

    if not images:
        return None

    image = max(images, key=lambda candidate: candidate.get("width") or 0)
    item_id = item.get("id") or item.get("uri") or image["url"]
    return PlaybackArt(
        key=str(item_id),
        image_url=image["url"],
        is_playing=bool(playback.get("is_playing")),
    )


def download_image(url: str) -> Image.Image:
    import requests

    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return Image.open(BytesIO(response.content)).convert("RGB")


def render_record(art: Image.Image | None, angle: float, size: int) -> Image.Image:
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    if art is None:
        return frame.convert("RGB")

    margin = max(2, size // 32)
    disc_size = size - margin * 2
    # The album art is the record surface: rotate it first, then cut it into a circular disk.
    art_square = ImageOps.fit(art, (disc_size, disc_size), method=Image.Resampling.LANCZOS)
    rotated = art_square.rotate(angle, resample=Image.Resampling.BICUBIC)

    disc_mask = Image.new("L", (disc_size, disc_size), 0)
    mask_draw = ImageDraw.Draw(disc_mask)
    mask_draw.ellipse((0, 0, disc_size - 1, disc_size - 1), fill=255)
    frame.paste(rotated.convert("RGBA"), (margin, margin), disc_mask)

    draw = ImageDraw.Draw(frame, "RGBA")
    outer = (margin, margin, size - margin - 1, size - margin - 1)
    draw.ellipse(outer, outline=(6, 6, 6, 255), width=max(1, size // 32))

    center = size // 2
    label_radius = max(5, size // 11)
    hole_radius = max(2, size // 25)
    draw.ellipse(
        (
            center - label_radius,
            center - label_radius,
            center + label_radius,
            center + label_radius,
        ),
        fill=(16, 16, 16, 210),
        outline=(220, 220, 220, 90),
    )
    draw.ellipse(
        (
            center - hole_radius,
            center - hole_radius,
            center + hole_radius,
            center + hole_radius,
        ),
        fill=(0, 0, 0, 255),
    )
    return frame.convert("RGB")


def render_idle(size: int) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    margin = max(2, size // 32)
    draw.ellipse((margin, margin, size - margin - 1, size - margin - 1), outline=(55, 55, 55), width=2)
    center = size // 2
    radius = max(3, size // 18)
    draw.ellipse((center - radius, center - radius, center + radius, center + radius), fill=(18, 18, 18))
    return frame


def render_test_pattern(size: int, offset: int) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    colors = (
        (255, 0, 0),
        (255, 160, 0),
        (255, 255, 0),
        (0, 255, 0),
        (0, 120, 255),
        (80, 0, 255),
        (255, 255, 255),
        (0, 0, 0),
    )
    stripe_width = max(1, size // len(colors))
    for index, color in enumerate(colors):
        x0 = (index * stripe_width + offset) % size
        draw.rectangle((x0, 0, min(size - 1, x0 + stripe_width - 1), size - 1), fill=color)
        if x0 + stripe_width > size:
            draw.rectangle((0, 0, (x0 + stripe_width) % size, size - 1), fill=color)
    draw.rectangle((0, 0, size - 1, size - 1), outline=(255, 255, 255))
    return frame


DIGIT_SEGMENTS = {
    "0": ("a", "b", "c", "d", "e", "f"),
    "1": ("b", "c"),
    "2": ("a", "b", "g", "e", "d"),
    "3": ("a", "b", "c", "d", "g"),
    "4": ("f", "g", "b", "c"),
    "5": ("a", "f", "g", "c", "d"),
    "6": ("a", "f", "e", "d", "c", "g"),
    "7": ("a", "b", "c"),
    "8": ("a", "b", "c", "d", "e", "f", "g"),
    "9": ("a", "b", "c", "d", "f", "g"),
}


def now_for_clock(timezone_name: str) -> datetime:
    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            print(f"Clock timezone not found: {timezone_name}; using system timezone.", flush=True)
    return datetime.now().astimezone()


def draw_segment_digit(draw: ImageDraw.ImageDraw, origin: tuple[int, int], digit: str, scale: int, color: tuple[int, int, int]) -> None:
    x, y = origin
    thickness = max(1, scale)
    width = scale * 4
    height = scale * 7
    segments = DIGIT_SEGMENTS.get(digit, ())
    boxes = {
        "a": (x + thickness, y, x + width - thickness, y + thickness),
        "b": (x + width - thickness, y + thickness, x + width, y + height // 2 - thickness // 2),
        "c": (x + width - thickness, y + height // 2 + thickness // 2, x + width, y + height - thickness),
        "d": (x + thickness, y + height - thickness, x + width - thickness, y + height),
        "e": (x, y + height // 2 + thickness // 2, x + thickness, y + height - thickness),
        "f": (x, y + thickness, x + thickness, y + height // 2 - thickness // 2),
        "g": (x + thickness, y + height // 2 - thickness // 2, x + width - thickness, y + height // 2 + thickness // 2),
    }
    for segment in segments:
        draw.rounded_rectangle(boxes[segment], radius=max(1, thickness // 2), fill=color)


def render_digital_clock(size: int, now: datetime, use_24_hour: bool, show_seconds: bool) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    hour = now.hour if use_24_hour else ((now.hour - 1) % 12) + 1
    text = f"{hour:02d}{now.minute:02d}"
    scale = max(1, size // 26)
    digit_width = scale * 4
    gap = max(1, scale)
    colon_width = scale
    total_width = digit_width * 4 + gap * 4 + colon_width
    start_x = max(0, (size - total_width) // 2)
    start_y = max(2, (size - scale * 7) // 2 - (scale if show_seconds else 0))
    color = (245, 245, 245)
    x = start_x
    for index, digit in enumerate(text):
        if index == 2:
            cx = x + gap
            cy = start_y + scale * 2
            dot = max(1, scale)
            draw.rectangle((cx, cy, cx + dot, cy + dot), fill=(150, 255, 190))
            draw.rectangle((cx, cy + scale * 3, cx + dot, cy + scale * 3 + dot), fill=(150, 255, 190))
            x += colon_width + gap * 2
        draw_segment_digit(draw, (x, start_y), digit, scale, color)
        x += digit_width + gap
    if show_seconds:
        seconds_width = max(1, size // 2)
        filled = int(seconds_width * (now.second / 59))
        x0 = (size - seconds_width) // 2
        y0 = min(size - 5, start_y + scale * 8 + 3)
        draw.rectangle((x0, y0, x0 + seconds_width, y0 + 1), fill=(32, 32, 32))
        draw.rectangle((x0, y0, x0 + filled, y0 + 1), fill=(150, 255, 190))
    return frame


def render_analog_clock(size: int, now: datetime) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    center = size // 2
    radius = max(8, size // 2 - 4)
    draw.ellipse((center - radius, center - radius, center + radius, center + radius), outline=(240, 240, 240), width=max(1, size // 32))
    for tick in range(12):
        angle = (tick / 12.0) * math.tau - math.pi / 2
        inner = radius - (5 if tick % 3 == 0 else 3)
        x1 = center + int(math.cos(angle) * inner)
        y1 = center + int(math.sin(angle) * inner)
        x2 = center + int(math.cos(angle) * radius)
        y2 = center + int(math.sin(angle) * radius)
        draw.line((x1, y1, x2, y2), fill=(140, 255, 185) if tick % 3 == 0 else (95, 95, 95), width=1)

    minute_angle = ((now.minute + now.second / 60.0) / 60.0) * math.tau - math.pi / 2
    hour_angle = (((now.hour % 12) + now.minute / 60.0) / 12.0) * math.tau - math.pi / 2
    hour_len = radius * 0.46
    minute_len = radius * 0.72
    draw.line((center, center, center + int(math.cos(hour_angle) * hour_len), center + int(math.sin(hour_angle) * hour_len)), fill=(255, 255, 255), width=max(2, size // 22))
    draw.line((center, center, center + int(math.cos(minute_angle) * minute_len), center + int(math.sin(minute_angle) * minute_len)), fill=(130, 255, 180), width=max(1, size // 32))
    draw.ellipse((center - 2, center - 2, center + 2, center + 2), fill=(255, 255, 255))
    return frame


def render_minimal_clock(size: int, now: datetime, use_24_hour: bool) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    center = size // 2
    radius = max(8, size // 2 - 5)
    progress = (now.minute * 60 + now.second) / 3600.0
    steps = max(12, size * 2)
    previous: tuple[int, int] | None = None
    for step in range(int(steps * progress) + 1):
        angle = (step / steps) * math.tau - math.pi / 2
        point = (center + int(math.cos(angle) * radius), center + int(math.sin(angle) * radius))
        if previous:
            draw.line((previous[0], previous[1], point[0], point[1]), fill=(140, 255, 190), width=2)
        previous = point
    draw.ellipse((center - radius, center - radius, center + radius, center + radius), outline=(38, 38, 38), width=1)
    hour = now.hour if use_24_hour else ((now.hour - 1) % 12) + 1
    label = f"{hour:02d}:{now.minute:02d}"
    bbox = draw.textbbox((0, 0), label)
    draw.text(((size - (bbox[2] - bbox[0])) // 2, center - 4), label, fill=(245, 245, 245))
    return frame


def render_clock(size: int, now: datetime, face: str, use_24_hour: bool, show_seconds: bool) -> Image.Image:
    if face == "digital":
        return render_digital_clock(size, now, use_24_hour, show_seconds)
    if face == "minimal":
        return render_minimal_clock(size, now, use_24_hour)
    return render_analog_clock(size, now)


def render_agent_face(size: int, frame_index: int, style: str, speed: str) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    speed_factor = {"slow": 0.65, "normal": 1.0, "fast": 1.45}.get(speed, 1.0)
    phase = frame_index * speed_factor
    blink = int(phase) % 72 in {0, 1, 2}
    glance = int(phase // 36) % 3 - 1
    eye_size = max(5, size // (7 if style == "wide" else 8))
    eye_y = size // 3
    eye_gap = size // (4 if style == "wide" else 5)
    eye_offset = int(glance * max(1, size // 18))
    eye_color = (245, 245, 245)
    smile_color = (245, 245, 245)

    for eye_center_x in (size // 2 - eye_gap, size // 2 + eye_gap):
        x = eye_center_x - eye_size // 2 + eye_offset
        y = eye_y - eye_size // 2
        if style == "cool":
            draw.rectangle((x - 1, eye_y - eye_size // 3, x + eye_size + 2, eye_y + eye_size // 2), fill=(245, 245, 245))
            draw.rectangle((x + 1, eye_y - eye_size // 4, x + eye_size, eye_y + eye_size // 3), fill=(0, 0, 0))
        elif blink or style == "sleepy" and int(phase) % 48 < 10:
            draw.rectangle((x, eye_y, x + eye_size, eye_y + max(1, eye_size // 4)), fill=eye_color)
        else:
            draw.rectangle((x, y, x + eye_size, y + eye_size), fill=eye_color)

    smile_y = size // 2 + size // 7
    smile_w = size // (2 if style == "happy" else 3)
    smile_h = size // (5 if style == "happy" else 7)
    mouth_shift = int(math.sin(phase / 12.0) * max(1, size // 40))
    for step in range(smile_w):
        progress = step / max(1, smile_w - 1)
        x = size // 2 - smile_w // 2 + step
        y = smile_y + int(math.sin(progress * math.pi) * smile_h) + mouth_shift
        draw.rectangle((x, y, x + 1, y + 1), fill=smile_color)

    return frame


def weather_summary(code: int | None, precipitation: float, snowfall: float) -> str:
    if snowfall > 0:
        return "snow"
    if precipitation > 0:
        return "rain"
    if code is None:
        return "weather"
    if code in {0, 1}:
        return "sunny"
    if code in {2, 3, 45, 48}:
        return "cloudy"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    return "weather"


def resolve_weather_location(args: argparse.Namespace) -> tuple[float, float, str]:
    if args.weather_latitude is not None and args.weather_longitude is not None:
        return args.weather_latitude, args.weather_longitude, args.weather_label
    if not args.weather_postal_code:
        raise RuntimeError("Weather mode needs a ZIP/postal code or latitude and longitude.")

    country_code = (args.weather_country_code or "US").strip().lower()
    postal_code = urllib.parse.quote(str(args.weather_postal_code).strip())
    response = http_request(
        "GET",
        f"https://api.zippopotam.us/{country_code}/{postal_code}",
        timeout=10,
    )
    if response.status != 200:
        raise_http_error(response, "Postal code lookup")
    payload = response.json()
    places = payload.get("places") or []
    if not places:
        raise RuntimeError(f"No location found for postal code {args.weather_postal_code}.")
    place = places[0]
    latitude = float(place["latitude"])
    longitude = float(place["longitude"])
    label = args.weather_label
    if label == "Local weather":
        city = place.get("place name")
        region = place.get("state abbreviation") or place.get("state")
        label = ", ".join(part for part in (city, region) if part) or label
    return latitude, longitude, label


def fetch_weather(args: argparse.Namespace) -> WeatherState:
    latitude, longitude, label = resolve_weather_location(args)

    response = http_request(
        "GET",
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": str(latitude),
            "longitude": str(longitude),
            "current": "temperature_2m,apparent_temperature,is_day,precipitation,rain,snowfall,weather_code,cloud_cover,wind_speed_10m",
            "daily": "uv_index_max",
            "temperature_unit": args.weather_temperature_unit,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": "1",
        },
        timeout=15,
    )
    if response.status != 200:
        raise_http_error(response, "Open-Meteo weather request")
    payload = response.json()
    current = payload.get("current") or {}
    daily = payload.get("daily") or {}
    uv_values = daily.get("uv_index_max") or []
    state = WeatherState(
        temperature=current.get("temperature_2m"),
        apparent_temperature=current.get("apparent_temperature"),
        uv_index=uv_values[0] if uv_values else None,
        weather_code=current.get("weather_code"),
        is_day=bool(current.get("is_day", 1)),
        precipitation=float(current.get("precipitation") or 0),
        rain=float(current.get("rain") or 0),
        snowfall=float(current.get("snowfall") or 0),
        cloud_cover=float(current.get("cloud_cover") or 0),
        wind_speed=float(current.get("wind_speed_10m") or 0),
        label=label,
    )
    state.summary = weather_summary(state.weather_code, state.precipitation + state.rain, state.snowfall)
    try:
        air_response = http_request(
            "GET",
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": str(latitude),
                "longitude": str(longitude),
                "current": "uv_index,us_aqi",
                "timezone": "auto",
                "forecast_days": "1",
            },
            timeout=10,
        )
        if air_response.status == 200:
            air_current = (air_response.json().get("current") or {})
            state.uv_index = air_current.get("uv_index", state.uv_index)
            state.aqi = air_current.get("us_aqi")
    except Exception:
        pass
    return state


def short_weather_value(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "--"
    rounded = round(value)
    if abs(value) < 1 and value > 0:
        return f"{value:.1f}{suffix}"
    return f"{rounded:.0f}{suffix}"


def draw_sun_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, phase: float = 0.0) -> None:
    for ray in range(8):
        angle = ray * math.tau / 8 + phase
        draw.line(
            (
                cx + int(math.cos(angle) * radius * 1.35),
                cy + int(math.sin(angle) * radius * 1.35),
                cx + int(math.cos(angle) * radius * 2.0),
                cy + int(math.sin(angle) * radius * 2.0),
            ),
            fill=(255, 205, 45),
        )
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 210, 45), outline=(255, 245, 140))


def draw_rain_icon(draw: ImageDraw.ImageDraw, x: int, y: int, frame_index: int = 0) -> None:
    draw.ellipse((x, y, x + 20, y + 9), fill=(120, 150, 170))
    draw.ellipse((x + 8, y - 4, x + 25, y + 10), fill=(165, 180, 190))
    draw.rectangle((x + 2, y + 5, x + 25, y + 11), fill=(145, 165, 180))
    for drop in range(4):
        dx = x + 3 + drop * 6
        dy = y + 15 + ((frame_index + drop * 2) % 4)
        draw.line((dx, dy, dx - 2, dy + 6), fill=(70, 190, 255))


def draw_moon_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int) -> None:
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(230, 235, 190))
    draw.ellipse((cx - radius // 3, cy - radius, cx + radius + 2, cy + radius), fill=(24, 30, 48))
    draw.point((cx - 13, cy - 7), fill=(255, 255, 210))
    draw.point((cx + 10, cy - 10), fill=(255, 255, 210))
    draw.point((cx + 13, cy + 7), fill=(255, 255, 210))


def draw_uv_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    draw.arc((cx - 12, cy - 11, cx + 12, cy + 13), 205, 335, fill=(190, 110, 255), width=2)
    draw.rectangle((cx - 10, cy + 8, cx + 10, cy + 10), fill=(190, 110, 255))
    draw.text((cx - 7, cy - 2), "UV", fill=(245, 235, 255))


def draw_wind_icon(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.arc((x, y, x + 14, y + 8), 180, 20, fill=(170, 225, 255), width=1)
    draw.line((x + 2, y + 8, x + 22, y + 8), fill=(170, 225, 255))
    draw.arc((x + 6, y + 9, x + 24, y + 18), 190, 20, fill=(170, 225, 255), width=1)


def draw_aqi_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    colors = [(90, 210, 110), (230, 210, 70), (235, 125, 55), (190, 75, 160)]
    for index, color in enumerate(colors):
        draw.rectangle((cx - 10 + index * 5, cy + 6 - index * 3, cx - 7 + index * 5, cy + 9), fill=color)


DIGIT_FONT_3X5 = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "-": ("000", "000", "111", "000", "000"),
    ".": ("000", "000", "000", "000", "010"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "110", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    ":": ("000", "010", "000", "010", "000"),
    "!": ("010", "010", "010", "000", "010"),
    "?": ("111", "001", "010", "000", "010"),
    ",": ("000", "000", "000", "010", "100"),
    "'": ("010", "010", "000", "000", "000"),
    "/": ("001", "001", "010", "100", "100"),
    "+": ("000", "010", "111", "010", "000"),
    "(": ("001", "010", "010", "010", "001"),
    ")": ("100", "010", "010", "010", "100"),
    "&": ("010", "101", "010", "101", "011"),
    "#": ("101", "111", "101", "111", "101"),
    "%": ("101", "001", "010", "100", "101"),
    "*": ("000", "101", "010", "101", "000"),
}


def compact_weather_value(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "--"
    rounded = round(value)
    if abs(value) < 1 and value > 0:
        text = f"{value:.1f}"
    else:
        text = f"{rounded:.0f}"
    return f"{text}{suffix}"


def draw_pixel_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 2) -> None:
    cursor = x
    for char in text:
        glyph = DIGIT_FONT_3X5.get(char.upper())
        if char == " ":
            cursor += 2 * scale
            continue
        if not glyph:
            draw.text((cursor, y), char, fill=color)
            cursor += 6
            continue
        for row, pattern in enumerate(glyph):
            for col, pixel in enumerate(pattern):
                if pixel == "1":
                    draw.rectangle(
                        (
                            cursor + col * scale,
                            y + row * scale,
                            cursor + (col + 1) * scale - 1,
                            y + (row + 1) * scale - 1,
                        ),
                        fill=color,
                    )
        cursor += 4 * scale


def pixel_text_width(text: str, scale: int = 2) -> int:
    width = 0
    for char in text:
        if char == " ":
            width += 2 * scale
        elif char.upper() in DIGIT_FONT_3X5:
            width += 4 * scale
        else:
            width += 6
    return max(0, width - scale)


TEXT_FONT_SCALES = {"small": 1, "medium": 2, "large": 3}


def parse_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not value:
        return fallback
    try:
        color = ImageColor.getrgb(value)
    except ValueError:
        return fallback
    return color[:3]


TTF_FONT_SIZES = {"small": 12, "medium": 18, "large": 28}

FONT_SEARCH_DIRS = [
    Path(__file__).resolve().parent / "fonts",
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts"),
    Path("C:/Windows/Fonts"),
]

FONT_CANDIDATES = {
    ("sans", False, False): ["NotoSans-Regular.ttf", "DejaVuSans.ttf", "arial.ttf"],
    ("sans", True, False): ["NotoSans-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
    ("sans", False, True): ["NotoSans-Italic.ttf", "DejaVuSans-Oblique.ttf", "ariali.ttf"],
    ("sans", True, True): ["NotoSans-BoldItalic.ttf", "DejaVuSans-BoldOblique.ttf", "arialbi.ttf"],
    ("devanagari", False, False): ["NotoSansDevanagari-Regular.ttf", "Nirmala.ttf", "Nirmala.ttc", "mangal.ttf"],
    ("devanagari", True, False): ["NotoSansDevanagari-Bold.ttf", "NirmalaB.ttf", "Nirmala.ttc", "mangalb.ttf"],
    ("mono", False, False): ["DejaVuSansMono.ttf", "NotoSansMono-Regular.ttf", "cour.ttf", "consola.ttf"],
    ("mono", True, False): ["DejaVuSansMono-Bold.ttf", "NotoSansMono-Bold.ttf", "courbd.ttf", "consolab.ttf"],
    ("mono", False, True): ["DejaVuSansMono-Oblique.ttf", "cour.ttf", "consolai.ttf"],
    ("mono", True, True): ["DejaVuSansMono-BoldOblique.ttf", "courbd.ttf", "consolaz.ttf"],
}

EMOJI_FONT_CANDIDATES = ["NotoColorEmoji.ttf", "seguiemj.ttf", "AppleColorEmoji.ttc", "TwitterColorEmoji-SVGinOT.ttf", "EmojiOneColor.otf"]
EMOJI_STRIKE_SIZES = [109, 128, 136, 96, 64, 48, 32]

_emoji_font_cache: dict[int, tuple[Any, int] | None] = {}
_emoji_glyph_cache: dict[tuple[str, int], Any] = {}

_font_file_cache: dict[tuple[str, ...], Path | None] = {}
_font_cache: dict[tuple[str, bool, bool, int], Any] = {}


def _find_font_file(candidates: list[str]) -> Path | None:
    key = tuple(candidates)
    if key in _font_file_cache:
        return _font_file_cache[key]
    found: Path | None = None
    for name in candidates:
        for directory in FONT_SEARCH_DIRS:
            candidate = directory / name
            if candidate.exists():
                found = candidate
                break
        if found:
            break
    if found is None:
        for directory in FONT_SEARCH_DIRS:
            if not directory.exists():
                continue
            for name in candidates:
                hits = list(directory.rglob(name))
                if hits:
                    found = hits[0]
                    break
            if found:
                break
    _font_file_cache[key] = found
    return found


def load_font(family: str, bold: bool, italic: bool, size: int) -> Any:
    if family == "devanagari":
        italic = False
    key = (family, bold, italic, size)
    if key in _font_cache:
        return _font_cache[key]
    candidates = (
        FONT_CANDIDATES.get((family, bold, italic))
        or FONT_CANDIDATES.get((family, bold, False))
        or FONT_CANDIDATES.get((family, False, False))
    )
    font = None
    if candidates:
        path = _find_font_file(candidates)
        if path is not None:
            try:
                if path.suffix.lower() == ".ttc":
                    font = ImageFont.truetype(str(path), size, index=0)
                else:
                    font = ImageFont.truetype(str(path), size)
            except OSError:
                font = None
    _font_cache[key] = font
    return font


def _is_emoji_char(char: str) -> bool:
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0x2B00 <= code <= 0x2BFF
        or 0x2300 <= code <= 0x23FF
        or 0x1F1E6 <= code <= 0x1F1FF
        or code in (0x2049, 0x203C, 0x2122, 0x2139)
    )


def _is_emoji_joiner(char: str) -> bool:
    code = ord(char)
    return code in (0x200D, 0xFE0F, 0xFE0E) or 0x1F3FB <= code <= 0x1F3FF


def _tokenize_text(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    buffer = ""
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if _is_emoji_char(char):
            if buffer:
                tokens.append(("text", buffer))
                buffer = ""
            cluster = char
            index += 1
            while index < length and (_is_emoji_char(text[index]) or _is_emoji_joiner(text[index])):
                cluster += text[index]
                index += 1
            tokens.append(("emoji", cluster))
        else:
            buffer += char
            index += 1
    if buffer:
        tokens.append(("text", buffer))
    return tokens


def _load_emoji_font(target_px: int) -> tuple[Any, int] | None:
    if target_px in _emoji_font_cache:
        return _emoji_font_cache[target_px]
    path = _find_font_file(EMOJI_FONT_CANDIDATES)
    result: tuple[Any, int] | None = None
    if path is not None:
        for size in (target_px, *EMOJI_STRIKE_SIZES):
            try:
                font = ImageFont.truetype(str(path), size)
                result = (font, size)
                break
            except OSError:
                continue
    _emoji_font_cache[target_px] = result
    return result


def render_emoji_image(cluster: str, target_px: int) -> Any:
    key = (cluster, target_px)
    if key in _emoji_glyph_cache:
        return _emoji_glyph_cache[key]
    loaded = _load_emoji_font(target_px)
    glyph = None
    if loaded is not None:
        font, base = loaded
        canvas = Image.new("RGBA", (base * len(cluster) + base, base * 2), (0, 0, 0, 0))
        drawer = ImageDraw.Draw(canvas)
        try:
            drawer.text((base // 4, base // 4), cluster, font=font, embedded_color=True)
            bbox = canvas.getbbox()
            if bbox:
                cropped = canvas.crop(bbox)
                scale = target_px / cropped.height
                width = max(1, round(cropped.width * scale))
                glyph = cropped.resize((width, target_px), Image.LANCZOS)
        except Exception:
            glyph = None
    _emoji_glyph_cache[key] = glyph
    return glyph


def _text_backend(image: Image.Image, draw: ImageDraw.ImageDraw, family: str, bold: bool, italic: bool, size_key: str):
    """Return (measure, line_height, render_line); handles inline emoji for any family."""
    font = None
    if family != "pixel":
        font = load_font(family, bold, italic, TTF_FONT_SIZES.get(size_key, 18))
    if font is not None:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + 2
        emoji_px = max(6, int((ascent + descent) * 0.85))

        def text_measure(value: str) -> int:
            return int(draw.textlength(value, font=font))

        def text_render(x: int, y: int, value: str, color: tuple[int, int, int]) -> None:
            draw.text((x, y), value, fill=color, font=font)
    else:
        scale = TEXT_FONT_SCALES.get(size_key, 2)
        line_height = 5 * scale + scale
        emoji_px = 6 * scale

        def text_measure(value: str) -> int:
            return pixel_text_width(value, scale)

        def text_render(x: int, y: int, value: str, color: tuple[int, int, int]) -> None:
            draw_pixel_text(draw, x, y, value, color, scale)

    def measure(value: str) -> int:
        width = 0
        for kind, chunk in _tokenize_text(value):
            if kind == "text":
                width += text_measure(chunk)
            else:
                glyph = render_emoji_image(chunk, emoji_px)
                width += (glyph.width + 1) if glyph is not None else text_measure(chunk)
        return width

    def render_line(x: int, y: int, value: str, color: tuple[int, int, int]) -> None:
        cursor = x
        for kind, chunk in _tokenize_text(value):
            if kind == "text":
                text_render(cursor, y, chunk, color)
                cursor += text_measure(chunk)
            else:
                glyph = render_emoji_image(chunk, emoji_px)
                if glyph is not None:
                    offset_y = y + max(0, (line_height - glyph.height) // 2)
                    image.paste(glyph, (int(cursor), int(offset_y)), glyph)
                    cursor += glyph.width + 1
                else:
                    text_render(cursor, y, chunk, color)
                    cursor += text_measure(chunk)

    return measure, line_height, render_line


def _wrap_text(text: str, measure, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            if measure(trial) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    wrapped: list[str] = []
    for line in lines:
        if measure(line) <= max_width or not line:
            wrapped.append(line)
            continue
        piece = ""
        for char in line:
            if measure(piece + char) <= max_width or not piece:
                piece += char
            else:
                wrapped.append(piece)
                piece = char
        wrapped.append(piece)
    return wrapped or [""]


def _draw_text_block(
    canvas_width: int,
    canvas_height: int,
    text: str,
    color: tuple[int, int, int],
    background: tuple[int, int, int],
    family: str,
    bold: bool,
    italic: bool,
    size_key: str,
    align: str,
    lines: list[str],
) -> Image.Image:
    image = Image.new("RGB", (canvas_width, canvas_height), background)
    draw = ImageDraw.Draw(image)
    measure, line_height, render_line = _text_backend(image, draw, family, bold, italic, size_key)
    total_height = line_height * len(lines)
    y = max(0, (canvas_height - total_height) // 2)
    for line in lines:
        width = measure(line)
        if align == "left":
            x = 1
        elif align == "right":
            x = canvas_width - width - 1
        else:
            x = (canvas_width - width) // 2
        render_line(x, y, line, color)
        y += line_height
    return image


def render_text(
    size: int,
    text: str,
    color: tuple[int, int, int],
    background: tuple[int, int, int],
    *,
    family: str = "pixel",
    bold: bool = False,
    italic: bool = False,
    size_key: str = "medium",
    align: str = "center",
    wrap: bool = False,
    fit: bool = False,
    scroll_offset: int | None = None,
) -> Image.Image:
    text = text or ""

    if scroll_offset is not None and not wrap and not fit:
        image = Image.new("RGB", (size, size), background)
        draw = ImageDraw.Draw(image)
        measure, line_height, render_line = _text_backend(image, draw, family, bold, italic, size_key)
        render_line(size - scroll_offset, (size - line_height) // 2, text, color)
        return image

    probe = Image.new("RGB", (1, 1))
    measure, line_height, _ = _text_backend(probe, ImageDraw.Draw(probe), family, bold, italic, size_key)
    lines = _wrap_text(text, measure, size - 2) if wrap else text.split("\n")

    if fit:
        content_width = max((measure(line) for line in lines), default=1) + 2
        content_height = line_height * len(lines) + 2
        block = _draw_text_block(max(content_width, 1), max(content_height, 1), text, color, background, family, bold, italic, size_key, align, lines)
        if block.width <= size and block.height <= size:
            canvas = Image.new("RGB", (size, size), background)
            canvas.paste(block, ((size - block.width) // 2, (size - block.height) // 2))
            return canvas
        scale = min(size / block.width, size / block.height)
        scaled = block.resize((max(1, round(block.width * scale)), max(1, round(block.height * scale))), Image.LANCZOS)
        canvas = Image.new("RGB", (size, size), background)
        canvas.paste(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
        return canvas

    return _draw_text_block(size, size, text, color, background, family, bold, italic, size_key, align, lines)


def text_line_width(text: str, family: str, bold: bool, italic: bool, size_key: str) -> int:
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    measure, _, _ = _text_backend(probe, draw, family, bold, italic, size_key)
    return max((measure(line) for line in (text or "").split("\n")), default=0)


def draw_rich_text(image: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, value: str, color: tuple[int, int, int], family: str, bold: bool, italic: bool, size_key: str) -> None:
    _, _, render_line = _text_backend(image, draw, family, bold, italic, size_key)
    render_line(x, y, value, color)


def draw_weather_metric(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, value: str, color: tuple[int, int, int]) -> None:
    tile_size = 32
    title_bbox = draw.textbbox((0, 0), title)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text((x + max(1, (tile_size - title_width) // 2), y + 3), title, fill=(245, 248, 255))

    scale = 2 if len(value) <= 4 else 1
    value_width = pixel_text_width(value, scale)
    value_x = x + max(1, (tile_size - value_width) // 2)
    value_y = y + 17 if scale == 2 else y + 19
    draw_pixel_text(draw, value_x, value_y, value, color, scale=scale)


def render_weather_quad(state: WeatherState, frame_index: int, size: int, temperature_unit: str) -> Image.Image:
    image = Image.new("RGB", (size, size), (8, 12, 20))
    draw = ImageDraw.Draw(image)
    mid = size // 2
    panels = [
        ((0, 0, mid, mid), (18, 48, 86)),
        ((mid, 0, size, mid), (48, 30, 76)),
        ((0, mid, mid, size), (40, 50, 30)),
        ((mid, mid, size, size), (12, 42, 62)),
    ]
    for box, fill in panels:
        draw.rectangle(box, fill=fill)
    draw.line((mid, 0, mid, size), fill=(8, 12, 20))
    draw.line((0, mid, size, mid), fill=(8, 12, 20))

    temp_unit = "F" if temperature_unit == "fahrenheit" else "C"
    wind_unit = ""
    wind_speed = state.wind_speed if temperature_unit == "fahrenheit" else state.wind_speed * 1.609344
    draw_weather_metric(draw, 0, 0, "TEMP", compact_weather_value(state.temperature, temp_unit), (255, 235, 130))
    draw_weather_metric(draw, mid, 0, "UV", compact_weather_value(state.uv_index), (235, 205, 255))
    draw_weather_metric(draw, 0, mid, "AQI", compact_weather_value(state.aqi), (175, 235, 125))
    draw_weather_metric(draw, mid, mid, "WIND", compact_weather_value(wind_speed, wind_unit), (145, 225, 255))
    return image


def render_weather_face(draw: ImageDraw.ImageDraw, size: int, accessory: str, summary: str) -> None:
    eye_y = int(size * 0.52)
    left_x = int(size * 0.34)
    right_x = int(size * 0.60)
    eye = max(3, size // 11)
    face_color = (245, 248, 255)
    if accessory == "auto":
        accessory = "umbrella" if summary in {"rain", "snow"} else "sunglasses" if summary == "sunny" else "none"

    if accessory == "sunglasses":
        lens_h = max(5, size // 9)
        draw.rectangle((left_x - 1, eye_y - 2, left_x + eye + 3, eye_y + lens_h), fill=(10, 10, 10), outline=face_color)
        draw.rectangle((right_x - 1, eye_y - 2, right_x + eye + 3, eye_y + lens_h), fill=(10, 10, 10), outline=face_color)
        draw.line((left_x + eye + 3, eye_y + 2, right_x - 1, eye_y + 2), fill=face_color)
    else:
        draw.rectangle((left_x, eye_y, left_x + eye, eye_y + eye), fill=face_color)
        draw.rectangle((right_x, eye_y, right_x + eye, eye_y + eye), fill=face_color)

    draw.arc((int(size * 0.37), int(size * 0.62), int(size * 0.65), int(size * 0.82)), start=20, end=160, fill=face_color, width=max(1, size // 28))

    if accessory == "umbrella":
        canopy_y = int(size * 0.18)
        draw.pieslice((int(size * 0.18), canopy_y, int(size * 0.82), int(size * 0.62)), 180, 360, fill=(120, 200, 245), outline=face_color)
        draw.line((size // 2, int(size * 0.4), size // 2, int(size * 0.68)), fill=face_color, width=max(1, size // 24))
        draw.arc((size // 2, int(size * 0.62), int(size * 0.62), int(size * 0.76)), start=0, end=180, fill=face_color, width=max(1, size // 24))


def render_weather_scene(state: WeatherState, frame_index: int, size: int, accessory: str, temperature_unit: str) -> Image.Image:
    summary = state.summary
    if summary == "sunny":
        bg_top, bg_bottom = (20, 55, 115), (240, 135, 35)
    elif summary == "rain":
        bg_top, bg_bottom = (5, 20, 42), (20, 70, 120)
    elif summary == "snow":
        bg_top, bg_bottom = (18, 35, 70), (115, 165, 210)
    elif summary == "cloudy":
        bg_top, bg_bottom = (25, 35, 55), (85, 100, 115)
    else:
        bg_top, bg_bottom = (16, 20, 30), (42, 50, 64)

    image = Image.new("RGB", (size, size), bg_top)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / max(1, size - 1)
        color = tuple(int(bg_top[index] * (1 - ratio) + bg_bottom[index] * ratio) for index in range(3))
        draw.line((0, y, size, y), fill=color)

    if summary == "sunny":
        cx, cy, radius = int(size * 0.72), int(size * 0.20), max(10, size // 6)
        draw_sun_icon(draw, cx, cy, radius, frame_index * 0.035)
    elif summary == "cloudy":
        draw.ellipse((int(size * 0.12), int(size * 0.12), int(size * 0.48), int(size * 0.34)), fill=(190, 200, 205))
        draw.ellipse((int(size * 0.32), int(size * 0.08), int(size * 0.75), int(size * 0.35)), fill=(215, 220, 222))
        draw.rectangle((int(size * 0.16), int(size * 0.23), int(size * 0.78), int(size * 0.37)), fill=(205, 212, 216))
    elif summary in {"rain", "snow"}:
        for drop in range(16):
            x = (drop * 9 + frame_index * 2) % size
            y = (drop * 13 + frame_index * 5) % size
            if summary == "snow":
                draw.rectangle((x, y, x + 2, y + 2), fill=(245, 250, 255))
            else:
                draw.line((x, y, x - 3, y + 7), fill=(70, 190, 255), width=max(1, size // 32))

    if summary == "weather":
        draw.rectangle((8, int(size * 0.20), size - 8, int(size * 0.36)), fill=(210, 180, 70))
        draw.text((11, int(size * 0.22)), "SET", fill=(10, 10, 10))
        draw.text((30, int(size * 0.22)), "LOC", fill=(10, 10, 10))

    render_weather_face(draw, size, accessory, summary)

    if state.temperature is not None:
        temp = f"{round(state.temperature):.0f}"
        suffix = "F" if temperature_unit == "fahrenheit" else "C"
        label = f"{temp}{suffix}"
        bbox = draw.textbbox((0, 0), label)
        draw.rectangle((2, 2, 4 + bbox[2] - bbox[0], 13), fill=(0, 0, 0))
        draw.text((3, 3), label, fill=(255, 255, 255))
    return image


def render_weather(
    state: WeatherState,
    frame_index: int,
    size: int,
    accessory: str,
    temperature_unit: str,
    fps: float,
    metrics_seconds: int,
    scene_seconds: int,
) -> Image.Image:
    metrics_frames = max(1, int(round(fps * max(30, metrics_seconds))))
    scene_frames = max(1, int(round(fps * max(15, scene_seconds))))
    cycle_frame = frame_index % (metrics_frames + scene_frames)
    if cycle_frame < metrics_frames:
        return render_weather_quad(state, frame_index, size, temperature_unit)
    return render_weather_scene(state, frame_index, size, accessory, temperature_unit)


def emit_display_event(event_api_url: str, event: str, payload: dict[str, Any]) -> None:
    if not event_api_url:
        return
    try:
        response = post_json(event_api_url, {"event": event, "payload": payload}, timeout=2)
        if response.status >= 400:
            print(f"Display event {event} failed with HTTP {response.status}", flush=True)
    except Exception as exc:
        print(f"Display event {event} failed: {exc}", flush=True)


def poll_spotify(
    spotify: SpotifyClient,
    state: SharedPlaybackState,
    state_lock: threading.Lock,
    stop_event: threading.Event,
    poll_seconds: float,
    event_api_url: str = "",
) -> None:
    last_status: str | None = None
    last_is_playing: bool | None = None
    last_art_key: str | None = None
    last_progress: int | None = None

    while not stop_event.is_set():
        try:
            playback = spotify.get_currently_playing()
            art = playback_art_from_response(playback)

            if art:
                # Some devices/accounts report is_playing=false while music is
                # actually playing. Treat the track as playing if its position
                # advanced since the last poll (a reliable "it's moving" signal).
                progress = playback.get("progress_ms") if isinstance(playback, dict) else None
                playing = art.is_playing
                if not playing and progress is not None and last_progress is not None and progress - last_progress > 200:
                    playing = True
                last_progress = progress

                with state_lock:
                    needs_download = art.key != state.art_key or art.image_url != state.image_url

                image = download_image(art.image_url) if needs_download else None

                with state_lock:
                    state.art_key = art.key
                    state.image_url = art.image_url
                    state.is_playing = playing
                    if image is not None:
                        state.image = image

                device = playback.get("device", {}).get("name") if isinstance(playback, dict) else None
                status = f"art found, is_playing={art.is_playing}, playing={playing}, progress={progress}, device={device}"
                if playing and (last_is_playing is not True or art.key != last_art_key):
                    emit_display_event(
                        event_api_url,
                        "spotify.playback_started",
                        {"source": "spotify", "artKey": art.key, "imageUrl": art.image_url, "isPlaying": True},
                    )
                elif not playing and last_is_playing is True:
                    emit_display_event(
                        event_api_url,
                        "spotify.playback_paused",
                        {"source": "spotify", "artKey": art.key, "imageUrl": art.image_url, "isPlaying": False},
                    )
                last_is_playing = playing
                last_art_key = art.key
            else:
                last_progress = None
                with state_lock:
                    state.art_key = None
                    state.image_url = None
                    state.image = None
                    state.is_playing = False
                status = "no currently playing item"
                if last_art_key is not None:
                    emit_display_event(
                        event_api_url,
                        "spotify.playback_stopped",
                        {"source": "spotify", "artKey": last_art_key, "isPlaying": False},
                    )
                last_is_playing = False
                last_art_key = None

            if status != last_status:
                print(f"Spotify: {status}", flush=True)
                last_status = status
        except Exception as exc:
            print(f"Spotify poll failed: {exc}", flush=True)

        stop_event.wait(poll_seconds)


def create_display(args: argparse.Namespace) -> MatrixDisplay | MockDisplay:
    display: MatrixDisplay | MockDisplay
    if args.mock_output:
        display = MockDisplay(args.mock_output, args.rotation)
    else:
        display = MatrixDisplay(args)
    return display


def run_test_pattern(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    try:
        offset = 0
        while True:
            display.show(render_test_pattern(size, offset))
            offset = (offset + 1) % size
            if args.once:
                break
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_clock(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    try:
        while True:
            now = now_for_clock(args.clock_timezone)
            display.show(render_clock(size, now, args.clock_face, args.clock_24_hour, args.clock_show_seconds))
            if args.once:
                break
            time.sleep(1.0 if not args.clock_show_seconds else min(1.0, 1.0 / args.fps))
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_agent(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    try:
        frame_index = 0
        while True:
            display.show(render_agent_face(size, frame_index, args.agent_face_style, args.agent_animation_speed))
            frame_index += 1
            if args.once:
                break
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_weather(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    state = WeatherState(label=args.weather_label)
    next_fetch = 0.0
    frame_index = 0
    try:
        while True:
            now = time.monotonic()
            if now >= next_fetch:
                try:
                    state = fetch_weather(args)
                    print(f"Weather: {state.label} {state.temperature} {state.summary}", flush=True)
                except Exception as exc:
                    print(f"Weather fetch failed: {exc}", flush=True)
                next_fetch = now + max(60, args.weather_refresh_minutes * 60)

            display.show(
                render_weather(
                    state,
                    frame_index,
                    size,
                    args.weather_face_accessory,
                    args.weather_temperature_unit,
                    args.fps,
                    args.weather_metrics_seconds,
                    args.weather_scene_seconds,
                )
            )
            frame_index += 1
            if args.once:
                break
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_text(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    text = args.text_value or ""
    color = parse_color(args.text_color, (255, 255, 255))
    background = parse_color(args.text_background, (0, 0, 0))
    family = args.text_font_family or "pixel"
    bold = bool(args.text_bold)
    italic = bool(args.text_italic)
    size_key = args.text_font_size
    wrap = bool(args.text_wrap)
    fit = bool(args.text_fit)
    width = text_line_width(text.strip(), family, bold, italic, size_key)
    scroll = bool(args.text_scroll) and not wrap and not fit and width > size
    speeds = {"slow": 1.0, "normal": 2.0, "fast": 4.0}
    pixels_per_frame = max(1, round(speeds.get(args.text_scroll_speed, 2.0)))
    travel = width + size
    offset = 0
    common = dict(family=family, bold=bold, italic=italic, size_key=size_key, align=args.text_align, wrap=wrap, fit=fit)
    try:
        while True:
            if scroll:
                display.show(render_text(size, text.strip(), color, background, scroll_offset=offset, **common))
                offset = (offset + pixels_per_frame) % travel
            else:
                display.show(render_text(size, text, color, background, **common))
            if args.once:
                break
            time.sleep(1.0 / args.fps if scroll else 0.5)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def _fit_image(source: Image.Image, size: int, mode: str, background: tuple[int, int, int]) -> Image.Image:
    image = source.convert("RGB")
    if mode == "stretch":
        return image.resize((size, size))
    if mode == "cover":
        return ImageOps.fit(image, (size, size), method=Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), background)
    scaled = image.copy()
    scaled.thumbnail((size, size), Image.LANCZOS)
    canvas.paste(scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2))
    return canvas


def render_image_frame(size: int, asset_path: str, fit: str, background: tuple[int, int, int], rotate: int = 0) -> Image.Image:
    if not asset_path or not Path(asset_path).exists():
        placeholder = Image.new("RGB", (size, size), background)
        draw = ImageDraw.Draw(placeholder)
        message = "NO IMG"
        draw_pixel_text(draw, max(1, (size - pixel_text_width(message, 1)) // 2), size // 2 - 3, message, (200, 200, 200), 1)
        return placeholder
    source = Image.open(asset_path)
    if rotate:
        source = source.rotate(-int(rotate), expand=True)
    return _fit_image(source, size, fit, background)


def _resolve_image_settings(args: argparse.Namespace) -> tuple[str, str, tuple[int, int, int], int]:
    config = load_json_config(args.config_path)
    image_cfg = config.get("image", {}) if isinstance(config.get("image"), dict) else {}
    fit = args.image_fit or image_cfg.get("fit", "contain")
    background = parse_color(args.image_background or image_cfg.get("background", "#000000"), (0, 0, 0))
    rotate = args.image_rotate if args.image_rotate is not None else int(image_cfg.get("rotate", 0) or 0)
    asset = args.image_asset
    if not asset:
        asset_name = image_cfg.get("assetPath", "")
        if asset_name:
            asset = str(args.config_path.parent / "widgets" / "assets" / asset_name)
    return asset or "", fit, background, rotate


def render_image(args: argparse.Namespace, size: int) -> Image.Image:
    asset, fit, background, rotate = _resolve_image_settings(args)
    return render_image_frame(size, asset, fit, background, rotate)


def is_animated_gif(path: str) -> bool:
    try:
        with Image.open(path) as image:
            return getattr(image, "is_animated", False)
    except (OSError, ValueError):
        return False


def load_gif_frames(path: str, size: int, fit: str, background: tuple[int, int, int], rotate: int) -> list[tuple[Image.Image, float]]:
    frames: list[tuple[Image.Image, float]] = []
    with Image.open(path) as source:
        for frame in ImageSequence.Iterator(source):
            rendered = frame.convert("RGB")
            if rotate:
                rendered = rendered.rotate(-int(rotate), expand=True)
            fitted = _fit_image(rendered, size, fit, background)
            duration_ms = frame.info.get("duration", 100) or 100
            frames.append((fitted, max(0.02, duration_ms / 1000.0)))
    return frames


def run_image(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    asset, fit, background, rotate = _resolve_image_settings(args)
    if asset and Path(asset).exists() and is_animated_gif(asset):
        frames = load_gif_frames(asset, size, fit, background, rotate)
        try:
            index = 0
            while frames:
                frame, delay = frames[index % len(frames)]
                display.show(frame)
                if args.once:
                    break
                time.sleep(delay)
                index += 1
        except KeyboardInterrupt:
            pass
        finally:
            display.clear()
        return
    frame = render_image_frame(size, asset, fit, background, rotate)
    try:
        while True:
            display.show(frame)
            if args.once:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def run_slideshow(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    config = load_json_config(args.config_path)
    cfg = config.get("slideshow", {}) if isinstance(config.get("slideshow"), dict) else {}
    fit = cfg.get("fit", "cover")
    background = parse_color(cfg.get("background", "#000000"), (0, 0, 0))
    rotate = int(cfg.get("rotate", 0) or 0)
    interval = max(1, int(cfg.get("intervalSeconds", 8) or 8))
    assets_dir = args.config_path.parent / "widgets" / "assets"
    paths = [str(assets_dir / name) for name in cfg.get("items", []) if name and (assets_dir / name).exists()]
    try:
        if not paths:
            display.show(render_image_frame(size, "", fit, background, rotate))
            while not args.once:
                time.sleep(1.0)
            return
        index = 0
        while True:
            display.show(render_image_frame(size, paths[index % len(paths)], fit, background, rotate))
            if args.once:
                break
            waited = 0.0
            while waited < interval:
                time.sleep(min(0.5, interval - waited))
                waited += 0.5
            index += 1
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


DRAW_FONT_SCALES = {"small": 1, "medium": 2, "large": 3}


def render_draw_frame(size: int, draw_cfg: dict[str, Any]) -> Image.Image:
    background = parse_color(draw_cfg.get("background", "#000000"), (0, 0, 0))
    image = Image.new("RGB", (size, size), background)
    draw = ImageDraw.Draw(image)
    for shape in draw_cfg.get("shapes", []):
        if not isinstance(shape, dict):
            continue
        kind = shape.get("type", "rect")
        color = parse_color(shape.get("color", "#ffffff"), (255, 255, 255))
        x = int(shape.get("x", 0))
        y = int(shape.get("y", 0))
        filled = bool(shape.get("fill", True))
        if kind == "rect":
            w = int(shape.get("w", 8))
            h = int(shape.get("h", 8))
            draw.rectangle((x, y, x + w - 1, y + h - 1), fill=color if filled else None, outline=None if filled else color)
        elif kind == "circle":
            r = int(shape.get("radius", 4))
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color if filled else None, outline=None if filled else color)
        elif kind == "line":
            draw.line((x, y, int(shape.get("x2", x)), int(shape.get("y2", y))), fill=color, width=1)
        elif kind == "pixel":
            draw.point((x, y), fill=color)
        elif kind == "text":
            draw_rich_text(
                image,
                draw,
                x,
                y,
                str(shape.get("text", "")),
                color,
                shape.get("fontFamily", "pixel"),
                bool(shape.get("bold", False)),
                bool(shape.get("italic", False)),
                shape.get("size", "small"),
            )
    return image


def render_draw(args: argparse.Namespace, size: int) -> Image.Image:
    config = load_json_config(args.config_path)
    draw_cfg = config.get("draw", {}) if isinstance(config.get("draw"), dict) else {}
    return render_draw_frame(size, draw_cfg)


def run_draw(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    frame = render_draw(args, size)
    try:
        while True:
            display.show(frame)
            if args.once:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


TETRIS_COLS = 10
TETRIS_ROWS = 20
TETRIS_CELL = 3
TETRIS_ORIGIN = (1, 2)
TETRIS_PANEL_X = 34

# Each piece is a rotation box size plus the filled cells inside that box.
TETRIS_SHAPES: dict[str, tuple[int, tuple[tuple[int, int], ...]]] = {
    "I": (4, ((0, 1), (1, 1), (2, 1), (3, 1))),
    "O": (2, ((0, 0), (1, 0), (0, 1), (1, 1))),
    "T": (3, ((1, 0), (0, 1), (1, 1), (2, 1))),
    "S": (3, ((1, 0), (2, 0), (0, 1), (1, 1))),
    "Z": (3, ((0, 0), (1, 0), (1, 1), (2, 1))),
    "J": (3, ((0, 0), (0, 1), (1, 1), (2, 1))),
    "L": (3, ((2, 0), (0, 1), (1, 1), (2, 1))),
}

TETRIS_COLORS = {
    "I": (0, 214, 228),
    "O": (240, 206, 46),
    "T": (176, 84, 232),
    "S": (72, 214, 96),
    "Z": (238, 74, 84),
    "J": (74, 118, 240),
    "L": (244, 148, 44),
}

TETRIS_KICKS = ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1))
TETRIS_LINE_SCORES = (0, 100, 300, 500, 800)
TETRIS_LOCK_DELAY = 0.45
TETRIS_LOCK_RESET_LIMIT = 12
TETRIS_FRAME_COLOR = (36, 40, 58)
TETRIS_LABEL_COLOR = (120, 132, 156)
TETRIS_VALUE_COLOR = (226, 234, 248)
TETRIS_ACTIONS = ("left", "right", "softDrop", "hardDrop", "rotateCw", "rotateCcw", "hold", "pause", "resume", "togglePause", "restart")


def tetris_cells(piece_type: str, rotation: int) -> tuple[tuple[int, int], ...]:
    box, cells = TETRIS_SHAPES[piece_type]
    result = cells
    for _ in range(rotation % 4):
        result = tuple((box - 1 - y, x) for x, y in result)
    return result


class TetrisGame:
    """Headless Tetris driven by queued commands from the Assistant Matrix API."""

    def __init__(self, start_level: int = 1, ghost: bool = True, seed: int | None = None) -> None:
        self.start_level = max(1, min(15, int(start_level or 1)))
        self.ghost = bool(ghost)
        self.random = random.Random(seed)
        self.reset()

    def reset(self) -> None:
        self.board: list[list[str]] = [[""] * TETRIS_COLS for _ in range(TETRIS_ROWS)]
        self.bag: list[str] = []
        self.score = 0
        self.lines = 0
        self.level = self.start_level
        self.game_over = False
        self.game_over_elapsed = 0.0
        self.paused = False
        self.hold = ""
        self.hold_locked = False
        self.drop_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.piece_type = ""
        self.rotation = 0
        self.piece_x = 0
        self.piece_y = 0
        self.next_type = self._take()
        self._spawn()

    def _take(self) -> str:
        if not self.bag:
            self.bag = list(TETRIS_SHAPES)
            self.random.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self, piece_type: str = "") -> None:
        self.piece_type = piece_type or self.next_type
        if not piece_type:
            self.next_type = self._take()
        self.rotation = 0
        self.piece_x = (TETRIS_COLS - TETRIS_SHAPES[self.piece_type][0]) // 2
        self.piece_y = 0
        self.drop_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        if self._collides(self.piece_x, self.piece_y, self.rotation):
            self.game_over = True

    def _cells(self, x: int, y: int, rotation: int) -> list[tuple[int, int]]:
        return [(x + cell_x, y + cell_y) for cell_x, cell_y in tetris_cells(self.piece_type, rotation)]

    def _collides(self, x: int, y: int, rotation: int) -> bool:
        for cell_x, cell_y in self._cells(x, y, rotation):
            if cell_x < 0 or cell_x >= TETRIS_COLS or cell_y >= TETRIS_ROWS:
                return True
            if cell_y >= 0 and self.board[cell_y][cell_x]:
                return True
        return False

    def _reset_lock_delay(self) -> None:
        if self.lock_timer > 0 and self.lock_resets < TETRIS_LOCK_RESET_LIMIT:
            self.lock_timer = 0.0
            self.lock_resets += 1

    def move(self, dx: int, dy: int) -> bool:
        if self.game_over or self.paused:
            return False
        if self._collides(self.piece_x + dx, self.piece_y + dy, self.rotation):
            return False
        self.piece_x += dx
        self.piece_y += dy
        self._reset_lock_delay()
        return True

    def rotate(self, direction: int) -> bool:
        if self.game_over or self.paused:
            return False
        rotation = (self.rotation + direction) % 4
        for dx, dy in TETRIS_KICKS:
            if not self._collides(self.piece_x + dx, self.piece_y + dy, rotation):
                self.piece_x += dx
                self.piece_y += dy
                self.rotation = rotation
                self._reset_lock_delay()
                return True
        return False

    def soft_drop(self) -> None:
        if self.move(0, 1):
            self.score += 1
            self.drop_timer = 0.0

    def hard_drop(self) -> None:
        if self.game_over or self.paused:
            return
        distance = 0
        while not self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.piece_y += 1
            distance += 1
        self.score += distance * 2
        self._lock()

    def hold_piece(self) -> None:
        if self.game_over or self.paused or self.hold_locked:
            return
        held = self.hold
        self.hold = self.piece_type
        if held:
            self._spawn(held)
        else:
            self._spawn()
        self.hold_locked = True

    def landing_y(self) -> int:
        y = self.piece_y
        while not self._collides(self.piece_x, y + 1, self.rotation):
            y += 1
        return y

    def _lock(self) -> None:
        for cell_x, cell_y in self._cells(self.piece_x, self.piece_y, self.rotation):
            if 0 <= cell_y < TETRIS_ROWS and 0 <= cell_x < TETRIS_COLS:
                self.board[cell_y][cell_x] = self.piece_type
        cleared = self._clear_lines()
        if cleared:
            self.lines += cleared
            self.score += TETRIS_LINE_SCORES[cleared] * self.level
            self.level = self.start_level + self.lines // 10
        self.hold_locked = False
        self._spawn()

    def _clear_lines(self) -> int:
        kept = [row for row in self.board if not all(row)]
        cleared = TETRIS_ROWS - len(kept)
        if cleared:
            self.board = [[""] * TETRIS_COLS for _ in range(cleared)] + kept
        return cleared

    def drop_interval(self) -> float:
        return max(0.06, 0.80 - (self.level - 1) * 0.06)

    def step(self, elapsed: float) -> None:
        elapsed = max(0.0, elapsed)
        if self.game_over:
            self.game_over_elapsed += elapsed
            return
        if self.paused:
            return
        if self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.lock_timer += elapsed
            if self.lock_timer >= TETRIS_LOCK_DELAY:
                self._lock()
            return
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.drop_timer += elapsed
        interval = self.drop_interval()
        while self.drop_timer >= interval and not self._collides(self.piece_x, self.piece_y + 1, self.rotation):
            self.piece_y += 1
            self.drop_timer -= interval

    def command(self, action: str) -> None:
        if action == "restart":
            self.reset()
            return
        if action in ("pause", "resume", "togglePause"):
            self.paused = action == "pause" or (action == "togglePause" and not self.paused)
            return
        if self.game_over:
            # Any drop button starts a fresh game once the board has topped out.
            if action in ("hardDrop", "softDrop"):
                self.reset()
            return
        if action == "left":
            self.move(-1, 0)
        elif action == "right":
            self.move(1, 0)
        elif action == "softDrop":
            self.soft_drop()
        elif action == "hardDrop":
            self.hard_drop()
        elif action == "rotateCw":
            self.rotate(1)
        elif action == "rotateCcw":
            self.rotate(-1)
        elif action == "hold":
            self.hold_piece()

    def snapshot(self) -> dict[str, Any]:
        active = [] if self.game_over else [[x, y] for x, y in self._cells(self.piece_x, self.piece_y, self.rotation)]
        ghost: list[list[int]] = []
        if self.ghost and not self.game_over and not self.paused:
            landing = self.landing_y()
            if landing != self.piece_y:
                ghost = [[x, y] for x, y in self._cells(self.piece_x, landing, self.rotation)]
        return {
            "board": ["".join(cell or "." for cell in row) for row in self.board],
            "active": active,
            "activeType": "" if self.game_over else self.piece_type,
            "ghost": ghost,
            "next": self.next_type,
            "hold": self.hold,
            "holdLocked": self.hold_locked,
            "score": self.score,
            "lines": self.lines,
            "level": self.level,
            "gameOver": self.game_over,
            "paused": self.paused,
        }


def tetris_demo_snapshot() -> dict[str, Any]:
    """Static board used for the widget preview tile."""
    game = TetrisGame(seed=7)
    game.board[19] = ["J", "J", "L", "L", "O", "O", "S", "S", "Z", ""]
    game.board[18] = ["J", "", "", "L", "O", "O", "", "S", "Z", ""]
    game.board[17] = ["", "", "", "L", "", "", "", "", "Z", ""]
    game.piece_type = "T"
    game.next_type = "I"
    game.hold = "L"
    game.piece_x = 3
    game.piece_y = 6
    game.score = 2400
    game.lines = 12
    game.level = 2
    return game.snapshot()


def _tetris_block(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int]) -> None:
    draw.rectangle((x, y, x + TETRIS_CELL - 1, y + TETRIS_CELL - 1), fill=color)
    draw.point((x, y), fill=tuple(min(255, channel + 60) for channel in color))


def _tetris_mini_piece(draw: ImageDraw.ImageDraw, x: int, y: int, piece_type: str, cell: int = 2, area: int = 8) -> None:
    if piece_type not in TETRIS_SHAPES:
        return
    cells = TETRIS_SHAPES[piece_type][1]
    min_x = min(cell_x for cell_x, _ in cells)
    min_y = min(cell_y for _, cell_y in cells)
    span_x = max(cell_x for cell_x, _ in cells) - min_x + 1
    span_y = max(cell_y for _, cell_y in cells) - min_y + 1
    start_x = x + (area - span_x * cell) // 2
    start_y = y + (area - span_y * cell) // 2
    color = TETRIS_COLORS[piece_type]
    for cell_x, cell_y in cells:
        left = start_x + (cell_x - min_x) * cell
        top = start_y + (cell_y - min_y) * cell
        draw.rectangle((left, top, left + cell - 1, top + cell - 1), fill=color)


def tetris_score_text(value: int) -> str:
    value = max(0, int(value))
    return str(value) if value < 100000 else f"{value // 1000}K"


def _render_tetris_panel(draw: ImageDraw.ImageDraw, snapshot: dict[str, Any]) -> None:
    x = TETRIS_PANEL_X
    draw_pixel_text(draw, x, 1, "NEXT", TETRIS_LABEL_COLOR, 1)
    _tetris_mini_piece(draw, x + 2, 8, str(snapshot.get("next", "")))
    draw_pixel_text(draw, x, 18, "HOLD", TETRIS_LABEL_COLOR, 1)
    _tetris_mini_piece(draw, x + 2, 25, str(snapshot.get("hold", "")))
    draw_pixel_text(draw, x, 35, "SCORE", TETRIS_LABEL_COLOR, 1)
    draw_pixel_text(draw, x, 41, tetris_score_text(snapshot.get("score", 0)), TETRIS_VALUE_COLOR, 1)
    draw_pixel_text(draw, x, 49, "LINES", TETRIS_LABEL_COLOR, 1)
    draw_pixel_text(draw, x, 55, str(max(0, int(snapshot.get("lines", 0)))), TETRIS_VALUE_COLOR, 1)
    level = min(99, max(1, int(snapshot.get("level", 1))))
    draw_pixel_text(draw, x + 16, 55, f"L{level}", TETRIS_LABEL_COLOR, 1)


def _tetris_overlay(draw: ImageDraw.ImageDraw, lines: tuple[str, ...], width: int, height: int) -> None:
    origin_x, origin_y = TETRIS_ORIGIN
    top = origin_y + height // 2 - (len(lines) * 7) // 2
    draw.rectangle((origin_x, top - 3, origin_x + width - 1, top + len(lines) * 7 + 1), fill=(0, 0, 0), outline=TETRIS_FRAME_COLOR)
    for index, line in enumerate(lines):
        draw_pixel_text(draw, origin_x + (width - pixel_text_width(line, 1)) // 2, top + index * 7, line, TETRIS_VALUE_COLOR, 1)


def render_tetris_frame(size: int, snapshot: dict[str, Any]) -> Image.Image:
    image = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    origin_x, origin_y = TETRIS_ORIGIN
    width = TETRIS_COLS * TETRIS_CELL
    height = TETRIS_ROWS * TETRIS_CELL
    draw.rectangle((origin_x - 1, origin_y - 1, origin_x + width, origin_y + height), outline=TETRIS_FRAME_COLOR)

    for row_index, row in enumerate(snapshot.get("board", [])):
        for col_index, cell in enumerate(row):
            if cell != ".":
                _tetris_block(draw, origin_x + col_index * TETRIS_CELL, origin_y + row_index * TETRIS_CELL, TETRIS_COLORS.get(cell, TETRIS_VALUE_COLOR))

    active_color = TETRIS_COLORS.get(str(snapshot.get("activeType", "")), TETRIS_VALUE_COLOR)
    ghost_color = tuple(channel // 4 for channel in active_color)
    for cell_x, cell_y in snapshot.get("ghost", []):
        if cell_y >= 0:
            left = origin_x + cell_x * TETRIS_CELL
            top = origin_y + cell_y * TETRIS_CELL
            draw.rectangle((left, top, left + TETRIS_CELL - 1, top + TETRIS_CELL - 1), fill=ghost_color)
    for cell_x, cell_y in snapshot.get("active", []):
        if cell_y >= 0:
            _tetris_block(draw, origin_x + cell_x * TETRIS_CELL, origin_y + cell_y * TETRIS_CELL, active_color)

    _render_tetris_panel(draw, snapshot)

    if snapshot.get("gameOver"):
        _tetris_overlay(draw, ("GAME", "OVER"), width, height)
    elif snapshot.get("paused"):
        _tetris_overlay(draw, ("PAUSED",), width, height)

    return image if size == 64 else image.resize((size, size), Image.NEAREST)


def read_tetris_commands(path: Path | None, last_seq: int) -> tuple[list[str], int]:
    """Drain queued controller commands written by the API, newest sequence wins."""
    if path is None or not path.exists():
        return [], last_seq
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return [], last_seq
    entries = payload.get("commands", []) if isinstance(payload, dict) else []
    pairs = [
        (int(entry.get("seq", 0) or 0), str(entry.get("action", "")))
        for entry in entries
        if isinstance(entry, dict) and entry.get("action")
    ]
    if not pairs:
        return [], last_seq
    highest = max(seq for seq, _ in pairs)
    if highest < last_seq:
        # The API restarted and rewound its counter, so replay from the start.
        last_seq = 0
    fresh = sorted((pair for pair in pairs if pair[0] > last_seq), key=lambda pair: pair[0])
    return [action for _, action in fresh], max(last_seq, highest)


def write_tetris_state(path: Path | None, snapshot: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(path.name + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump({**snapshot, "updatedAt": time.time()}, file)
        for _ in range(3):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                # Windows refuses the swap while the API has the file open.
                time.sleep(0.01)
        with path.open("w", encoding="utf-8") as file:
            json.dump({**snapshot, "updatedAt": time.time()}, file)
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass


def run_tetris(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    game = TetrisGame(start_level=args.tetris_start_level, ghost=not args.tetris_no_ghost)
    input_path = args.tetris_input
    state_path = args.tetris_state
    auto_restart = max(0, int(args.tetris_auto_restart_seconds or 0))
    frame_time = 1.0 / max(1.0, float(args.fps))
    # Ignore anything queued before this game started.
    _, last_seq = read_tetris_commands(input_path, 0)
    previous = time.monotonic()
    next_state_write = 0.0
    last_written = ""
    try:
        while True:
            started = time.monotonic()
            elapsed = started - previous
            previous = started

            actions, last_seq = read_tetris_commands(input_path, last_seq)
            for action in actions:
                game.command(action)
            game.step(elapsed)
            if auto_restart and game.game_over and game.game_over_elapsed >= auto_restart:
                game.reset()

            snapshot = game.snapshot()
            display.show(render_tetris_frame(size, snapshot))

            if state_path is not None and started >= next_state_write:
                serialized = json.dumps(snapshot, sort_keys=True)
                if serialized != last_written:
                    write_tetris_state(state_path, snapshot)
                    last_written = serialized
                next_state_write = started + 0.2

            if args.once:
                break
            time.sleep(max(0.0, frame_time - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        display.clear()


def load_external_widget(widget_dir: Path, entrypoint: str) -> Any:
    if str(widget_dir) not in sys.path:
        sys.path.insert(0, str(widget_dir))
    if ":" not in entrypoint:
        raise RuntimeError("Widget entrypoint must use module.path:object.")
    module_name, object_name = entrypoint.split(":", 1)
    module = __import__(module_name, fromlist=[object_name])
    target = getattr(module, object_name)
    if isinstance(target, type) and issubclass(target, Widget):
        return target()
    return target


def read_external_widget_manifest(widget_dir: Path) -> dict[str, Any]:
    manifest_path = widget_dir / "widget.toml"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing widget manifest at {manifest_path}.")
    return tomllib.loads(manifest_path.read_text(encoding="utf-8"))


def read_external_widget_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}


def run_external_widget(args: argparse.Namespace, display: MatrixDisplay | MockDisplay, size: int) -> None:
    if not args.widget_dir:
        raise RuntimeError("Widget mode requires --widget-dir.")

    widget_dir = args.widget_dir.resolve()
    manifest = read_external_widget_manifest(widget_dir)
    widget_info = manifest.get("widget", {})
    entrypoint = str(widget_info.get("entrypoint", ""))
    if not entrypoint:
        raise RuntimeError("Widget manifest is missing widget.entrypoint.")

    renderer = load_external_widget(widget_dir, entrypoint)
    state: dict[str, Any] = {}
    context = WidgetContext(config=read_external_widget_config(args.widget_config), state=state, assets_dir=widget_dir / "assets")

    if isinstance(renderer, Widget):
        renderer.setup(context)
    elif hasattr(renderer, "setup"):
        renderer.setup(context)

    frame_index = 0
    try:
        while True:
            context.frame_index = frame_index
            canvas = MatrixCanvas(size, size)
            if isinstance(renderer, Widget):
                renderer.render(canvas, context)
            else:
                renderer(canvas, context)
            display.show(canvas.frame())
            frame_index += 1
            if args.once:
                break
            time.sleep(1.0 / args.fps)
    except KeyboardInterrupt:
        pass
    finally:
        if isinstance(renderer, Widget):
            renderer.teardown(context)
        elif hasattr(renderer, "teardown"):
            renderer.teardown(context)
        display.clear()


def run_spotify(
    args: argparse.Namespace,
    config: dict[str, Any],
    display: MatrixDisplay | MockDisplay | None = None,
    size: int | None = None,
) -> None:
    client_id, client_secret, redirect_uri = spotify_credentials(config)

    missing = [
        name
        for name, value in (
            ("Spotify Client ID", client_id),
            ("Spotify Client Secret", client_secret),
            ("Spotify Redirect URI", redirect_uri),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Missing required Spotify configuration values: "
            f"{', '.join(missing)}. Add them through the setup UI or environment."
        )

    spotify = SpotifyClient(
        client_id=client_id or "",
        client_secret=client_secret or "",
        redirect_uri=redirect_uri,
        token_cache=args.token_cache,
        open_browser=not args.no_browser,
    )

    if args.auth_only:
        spotify.authorize()
        print(f"Spotify token cached at {args.token_cache}")
        return

    if display is None:
        display = create_display(args)
    if size is None:
        size = min(args.rows, args.cols)
    idle = render_idle(size)
    spin_mode = str(get_nested(config, "spotify", "spin") or "auto")
    playback_state = SharedPlaybackState()
    playback_lock = threading.Lock()
    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=poll_spotify,
        args=(spotify, playback_state, playback_lock, stop_event, args.poll_seconds, args.event_api_url),
        daemon=True,
    )
    poll_thread.start()

    angle = 0.0
    last_frame = time.monotonic()

    try:
        while True:
            frame_start = time.monotonic()
            with playback_lock:
                current_art_image = playback_state.image
                is_playing = playback_state.is_playing

            now = time.monotonic()
            delta = now - last_frame
            last_frame = now

            should_spin = spin_mode == "always" or (spin_mode != "off" and is_playing)
            if should_spin and current_art_image is not None:
                angle = (angle - 360.0 * (args.rpm / 60.0) * delta) % 360.0

            image = render_record(current_art_image, angle, size) if current_art_image else idle
            display.show(image)

            if args.once:
                break

            sleep_for = max(0.0, (1.0 / args.fps) - (time.monotonic() - frame_start))
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        poll_thread.join(timeout=1)
        display.clear()


def run(args: argparse.Namespace) -> None:
    if args.preview_frames:
        render_preview_frames(args.preview_frames)
        return

    load_dotenv()
    config = load_json_config(args.config_path)
    apply_config_defaults(args, config)

    mode = "testPattern" if args.test_pattern else args.display_mode

    if mode == "spotify":
        run_spotify(args, config)
        return

    display = create_display(args)
    size = min(args.rows, args.cols)

    if mode == "testPattern":
        run_test_pattern(args, display, size)
    elif mode == "clock":
        run_clock(args, display, size)
    elif mode == "agent":
        run_agent(args, display, size)
    elif mode == "weather":
        run_weather(args, display, size)
    elif mode == "text":
        run_text(args, display, size)
    elif mode == "image":
        run_image(args, display, size)
    elif mode == "draw":
        run_draw(args, display, size)
    elif mode == "slideshow":
        run_slideshow(args, display, size)
    elif mode == "tetris":
        run_tetris(args, display, size)
    elif mode == "widget":
        run_external_widget(args, display, size)
    else:
        run_spotify(args, config, display, size)


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def render_preview_frames(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    art = demo_album_art(96)
    for index, angle in enumerate((0, 45, 90, 135)):
        render_record(art, angle, 64).save(directory / f"album-disk-{index:02d}.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Assistant Matrix display modes on a 64x64 RGB matrix.")
    parser.add_argument("--display-mode", choices=("spotify", "clock", "agent", "weather", "text", "image", "draw", "slideshow", "tetris", "testPattern", "widget"), default="spotify")
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--cols", type=int, default=64)
    parser.add_argument("--chain-length", type=int, default=1)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--brightness", type=int, default=65)
    parser.add_argument("--gpio-slowdown", type=int, default=2)
    parser.add_argument("--hardware-mapping", default="regular")
    parser.add_argument("--pwm-bits", type=int, default=11)
    parser.add_argument("--limit-refresh-rate-hz", type=int, default=120)
    parser.add_argument(
        "--no-hardware-pulse",
        action="store_true",
        help="Avoid Pi onboard sound conflict at the cost of more possible flicker.",
    )
    parser.add_argument("--poll-seconds", type=positive_float, default=2.0)
    parser.add_argument("--fps", type=positive_float, default=20.0)
    parser.add_argument("--rpm", type=positive_float, default=20.0)
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0, help="Rotate rendered frames before display.")
    parser.add_argument("--config-path", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--token-cache", type=Path, default=DEFAULT_TOKEN_CACHE)
    parser.add_argument("--mock-output", type=Path, help="Write the current frame PNG instead of using RGB matrix hardware.")
    parser.add_argument("--preview-frames", type=Path, help="Render sample spinning-album-art disk frames and exit.")
    parser.add_argument("--auth-only", action="store_true", help="Authorize Spotify, cache the token, and exit without using the matrix.")
    parser.add_argument("--test-pattern", action="store_true", help="Show a bright moving color test pattern without using Spotify.")
    parser.add_argument("--clock-face", choices=("analog", "digital", "minimal"), default="analog")
    parser.add_argument("--clock-24-hour", action="store_true", help="Use 24-hour time in clock mode.")
    parser.add_argument("--clock-show-seconds", action="store_true", help="Show second progress in clock mode.")
    parser.add_argument("--clock-timezone", default="", help="IANA timezone name for clock mode, such as America/Chicago.")
    parser.add_argument("--agent-face-style", choices=("classic", "wide", "sleepy", "happy", "cool"), default="classic")
    parser.add_argument("--agent-animation-speed", choices=("slow", "normal", "fast"), default="normal")
    parser.add_argument("--weather-label", default="Local weather")
    parser.add_argument("--weather-postal-code", default="")
    parser.add_argument("--weather-country-code", default="US")
    parser.add_argument("--weather-latitude", type=float)
    parser.add_argument("--weather-longitude", type=float)
    parser.add_argument("--weather-temperature-unit", choices=("fahrenheit", "celsius"), default="fahrenheit")
    parser.add_argument("--weather-face-accessory", choices=("auto", "none", "sunglasses", "umbrella"), default="auto")
    parser.add_argument("--weather-refresh-minutes", type=int, default=15)
    parser.add_argument("--weather-metrics-seconds", type=int, default=WEATHER_METRICS_SECONDS)
    parser.add_argument("--weather-scene-seconds", type=int, default=WEATHER_SCENE_SECONDS)
    parser.add_argument("--text-value", default="", help="Message to display in text mode.")
    parser.add_argument("--text-color", default="#ffffff", help="Text color in text mode.")
    parser.add_argument("--text-background", default="#000000", help="Background color in text mode.")
    parser.add_argument("--text-scroll", action="store_true", help="Scroll long messages horizontally in text mode.")
    parser.add_argument("--text-scroll-speed", choices=("slow", "normal", "fast"), default="normal")
    parser.add_argument("--text-font-size", choices=("small", "medium", "large"), default="medium")
    parser.add_argument("--text-align", choices=("left", "center", "right"), default="center")
    parser.add_argument("--text-font-family", choices=("pixel", "sans", "mono", "devanagari"), default="pixel")
    parser.add_argument("--text-bold", action="store_true", help="Render text with a bold font weight.")
    parser.add_argument("--text-italic", action="store_true", help="Render text with an italic font style.")
    parser.add_argument("--text-wrap", action="store_true", help="Wrap long text onto multiple lines.")
    parser.add_argument("--text-fit", action="store_true", help="Scale the whole text block to fit the panel (good for ASCII art).")
    parser.add_argument("--image-asset", default="", help="Absolute path to the image file for image mode.")
    parser.add_argument("--image-fit", choices=("contain", "cover", "stretch"), default="", help="How the image is scaled to the panel.")
    parser.add_argument("--image-background", default="", help="Background color behind a contained image.")
    parser.add_argument("--image-rotate", type=int, choices=(0, 90, 180, 270), default=None, help="Rotate the image before fitting.")
    parser.add_argument("--tetris-start-level", type=int, default=1, help="Starting gravity level for tetris mode.")
    parser.add_argument("--tetris-no-ghost", action="store_true", help="Hide the landing preview in tetris mode.")
    parser.add_argument("--tetris-auto-restart-seconds", type=int, default=0, help="Seconds to wait after game over before starting a new tetris game (0 waits for a button).")
    parser.add_argument("--tetris-input", type=Path, help="JSON command queue the Assistant Matrix API writes for tetris mode.")
    parser.add_argument("--tetris-state", type=Path, help="JSON file where tetris mode publishes live game state.")
    parser.add_argument("--widget-id", default="", help="Installed widget id for external widget mode.")
    parser.add_argument("--widget-dir", type=Path, help="Installed widget package directory for external widget mode.")
    parser.add_argument("--widget-config", type=Path, help="Saved widget config JSON for external widget mode.")
    parser.add_argument("--event-api-url", default="", help="Optional Assistant Matrix display event endpoint URL.")
    parser.add_argument("--once", action="store_true", help="Render one frame and exit.")
    parser.add_argument("--no-browser", action="store_true", help="Print the Spotify auth URL without trying to open a browser.")
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
