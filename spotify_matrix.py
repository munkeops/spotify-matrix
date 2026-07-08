#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from io import BytesIO
import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
from email.message import Message
from urllib.error import HTTPError
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SCOPE = "user-read-currently-playing"
DEFAULT_CONFIG_PATH = Path(os.environ.get("SPOTIFY_MATRIX_CONFIG", "data/config.json"))
DEFAULT_TOKEN_CACHE = Path(os.environ.get("SPOTIFY_TOKEN_CACHE", "data/spotify_token.json"))


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
    }

    for config_name, caster in matrix_fields.items():
        if any(flag in sys.argv[1:] for flag in cli_flags[config_name]):
            continue
        value = get_nested(config, "matrix", config_name)
        if value is None:
            continue
        attr_name = attr_names.get(config_name, config_name)
        setattr(args, attr_name, caster(value))

    runtime = config.get("runtime", {})
    if isinstance(runtime, dict):
        if "--display-mode" not in sys.argv[1:] and runtime.get("displayMode"):
            args.display_mode = str(runtime["displayMode"])
        if "--image-path" not in sys.argv[1:] and runtime.get("imagePath"):
            args.image_path = str(runtime["imagePath"])
        if runtime.get("testPattern"):
            args.display_mode = "test_pattern"

    weather = config.get("weather", {})
    if isinstance(weather, dict):
        if "--weather-location" not in sys.argv[1:]:
            args.weather_location = str(weather.get("location") or args.weather_location)
        if "--weather-temperature" not in sys.argv[1:]:
            args.weather_temperature = str(weather.get("temperature") or args.weather_temperature)
        if "--weather-condition" not in sys.argv[1:]:
            args.weather_condition = str(weather.get("condition") or args.weather_condition)

    calendar = config.get("calendar", {})
    if isinstance(calendar, dict) and "--calendar-title" not in sys.argv[1:]:
        args.calendar_title = str(calendar.get("title") or args.calendar_title)


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
            CURRENTLY_PLAYING_URL,
            params={"additional_types": "track,episode"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

        if response.status == 204:
            return None
        if response.status == 401:
            self._refresh_access_token()
            return self.get_currently_playing()
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            time.sleep(max(retry_after, 1))
            return None
        if response.status != 200:
            raise_http_error(response, "Spotify currently-playing request")

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

    def show(self, image: Image.Image) -> None:
        self.canvas.SetImage(image.convert("RGB"))
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def clear(self) -> None:
        self.matrix.Clear()


class MockDisplay:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def show(self, image: Image.Image) -> None:
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


def render_centered_lines(size: int, lines: list[str], accent: tuple[int, int, int]) -> Image.Image:
    frame = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(frame)
    font = ImageDraw.load_default()
    clean_lines = [line for line in lines if line]
    if not clean_lines:
        clean_lines = ["--"]

    line_height = 10
    total_height = len(clean_lines) * line_height
    y = max(1, (size - total_height) // 2)
    for index, line in enumerate(clean_lines):
        text = line[:12]
        bbox = draw.textbbox((0, 0), text, font=font)
        x = max(0, (size - (bbox[2] - bbox[0])) // 2)
        color = accent if index == 0 else (230, 230, 220)
        draw.text((x, y), text, fill=color, font=font)
        y += line_height
    return frame


def render_calendar(size: int, title: str = "") -> Image.Image:
    now = time.localtime()
    return render_centered_lines(
        size,
        [
            title or time.strftime("%a", now),
            time.strftime("%b %d", now),
            time.strftime("%I:%M", now).lstrip("0"),
        ],
        (110, 231, 168),
    )


def render_weather(size: int, location: str, temperature: str, condition: str) -> Image.Image:
    return render_centered_lines(
        size,
        [
            location or "Weather",
            temperature or "--",
            condition or "Set in UI",
        ],
        (96, 165, 250),
    )


def render_uploaded_image(path: str, size: int) -> Image.Image:
    if not path:
        return render_centered_lines(size, ["No image", "uploaded"], (248, 113, 113))
    try:
        with Image.open(path) as image:
            return ImageOps.fit(image.convert("RGB"), (size, size), method=Image.Resampling.LANCZOS)
    except Exception:
        return render_centered_lines(size, ["Image", "failed"], (248, 113, 113))


def poll_spotify(
    spotify: SpotifyClient,
    state: SharedPlaybackState,
    state_lock: threading.Lock,
    stop_event: threading.Event,
    poll_seconds: float,
) -> None:
    last_status: str | None = None

    while not stop_event.is_set():
        try:
            playback = spotify.get_currently_playing()
            art = playback_art_from_response(playback)

            if art:
                with state_lock:
                    needs_download = art.key != state.art_key or art.image_url != state.image_url

                image = download_image(art.image_url) if needs_download else None

                with state_lock:
                    state.art_key = art.key
                    state.image_url = art.image_url
                    state.is_playing = art.is_playing
                    if image is not None:
                        state.image = image

                status = f"art found, is_playing={art.is_playing}"
            else:
                with state_lock:
                    state.art_key = None
                    state.image_url = None
                    state.image = None
                    state.is_playing = False
                status = "no currently playing item"

            if status != last_status:
                print(f"Spotify: {status}", flush=True)
                last_status = status
        except Exception as exc:
            print(f"Spotify poll failed: {exc}", flush=True)

        stop_event.wait(poll_seconds)


def run(args: argparse.Namespace) -> None:
    if args.preview_frames:
        render_preview_frames(args.preview_frames)
        return

    load_dotenv()
    config = load_json_config(args.config_path)
    apply_config_defaults(args, config)

    if args.auth_only:
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
        spotify.authorize()
        print(f"Spotify token cached at {args.token_cache}")
        return

    display: MatrixDisplay | MockDisplay
    if args.mock_output:
        display = MockDisplay(args.mock_output)
    else:
        display = MatrixDisplay(args)

    size = min(args.rows, args.cols)

    if args.display_mode == "test_pattern" or args.test_pattern:
        try:
            offset = 0
            while True:
                display.show(render_test_pattern(size, offset))
                offset = (offset + 1) % size
                time.sleep(1.0 / args.fps)
        except KeyboardInterrupt:
            pass
        finally:
            display.clear()
        return

    if args.display_mode == "image":
        try:
            while True:
                display.show(render_uploaded_image(args.image_path, size))
                if args.once:
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            display.clear()
        return

    if args.display_mode == "calendar":
        try:
            while True:
                display.show(render_calendar(size, args.calendar_title))
                if args.once:
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            display.clear()
        return

    if args.display_mode == "weather":
        try:
            while True:
                display.show(render_weather(size, args.weather_location, args.weather_temperature, args.weather_condition))
                if args.once:
                    break
                time.sleep(30.0)
        except KeyboardInterrupt:
            pass
        finally:
            display.clear()
        return

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

    idle = render_idle(size)
    playback_state = SharedPlaybackState()
    playback_lock = threading.Lock()
    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=poll_spotify,
        args=(spotify, playback_state, playback_lock, stop_event, args.poll_seconds),
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

            if is_playing and current_art_image is not None:
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
    parser = argparse.ArgumentParser(description="Spin Spotify album art on a 64x64 RGB matrix.")
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
    parser.add_argument("--config-path", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--token-cache", type=Path, default=DEFAULT_TOKEN_CACHE)
    parser.add_argument(
        "--display-mode",
        choices=("spotify", "image", "calendar", "weather", "test_pattern"),
        default="spotify",
        help="Matrix content mode.",
    )
    parser.add_argument("--image-path", default="", help="Image file to show in image display mode.")
    parser.add_argument("--weather-location", default="", help="Weather mode location label.")
    parser.add_argument("--weather-temperature", default="", help="Weather mode temperature label.")
    parser.add_argument("--weather-condition", default="", help="Weather mode condition label.")
    parser.add_argument("--calendar-title", default="", help="Calendar mode top-line label.")
    parser.add_argument("--mock-output", type=Path, help="Write the current frame PNG instead of using RGB matrix hardware.")
    parser.add_argument("--preview-frames", type=Path, help="Render sample spinning-album-art disk frames and exit.")
    parser.add_argument("--auth-only", action="store_true", help="Authorize Spotify, cache the token, and exit without using the matrix.")
    parser.add_argument("--test-pattern", action="store_true", help="Show a bright moving color test pattern without using Spotify.")
    parser.add_argument("--once", action="store_true", help="Render one frame and exit.")
    parser.add_argument("--no-browser", action="store_true", help="Print the Spotify auth URL without trying to open a browser.")
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
