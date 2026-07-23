"""Storage and gallery for user image assets (PNG plus animated GIF)."""

from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.domain.services.config_service import config_service

MAX_SOURCE_DIMENSION = 512
MAX_DECODED_BYTES = 12 * 1024 * 1024
GALLERY_SUFFIXES = (".png", ".gif", ".jpg", ".jpeg", ".webp")


class AssetService:
    @property
    def assets_dir(self) -> Path:
        return config_service.data_dir / "widgets" / "assets"

    def safe_asset_name(self, name: str) -> str:
        candidate = Path(name).name
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        if not candidate or any(character not in allowed for character in candidate):
            raise ValueError("Invalid asset name.")
        return candidate

    def asset_path(self, name: str) -> Path:
        path = self.assets_dir / self.safe_asset_name(name)
        if not path.exists():
            raise ValueError(f"Asset {name} not found.")
        return path

    def list_assets(self) -> list[dict[str, object]]:
        directory = self.assets_dir
        if not directory.exists():
            return []
        entries = []
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in GALLERY_SUFFIXES:
                entries.append((path.stat().st_mtime, path.name))
        entries.sort(reverse=True)
        return [{"name": name, "url": f"/api/assets/{name}", "animated": name.lower().endswith(".gif")} for _, name in entries]

    def delete_asset(self, name: str) -> None:
        path = self.assets_dir / self.safe_asset_name(name)
        if path.exists():
            path.unlink()

    def save_upload(self, data: str, original_name: str = "") -> str:
        raw = self._decode(data)
        try:
            source = Image.open(BytesIO(raw))
            source.load()
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("Uploaded file is not a readable image.") from error

        self.assets_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(raw).hexdigest()[:16]

        if (source.format or "").upper() == "GIF":
            name = f"{digest}.gif"
            (self.assets_dir / name).write_bytes(raw)
            return name

        image = source.convert("RGB")
        if max(image.size) > MAX_SOURCE_DIMENSION:
            image.thumbnail((MAX_SOURCE_DIMENSION, MAX_SOURCE_DIMENSION), Image.LANCZOS)
        name = f"{digest}.png"
        image.save(self.assets_dir / name, format="PNG")
        return name

    def _decode(self, data: str) -> bytes:
        payload = data.strip()
        if payload.startswith("data:"):
            _, _, payload = payload.partition(",")
        try:
            raw = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("Asset data must be base64 encoded.") from error
        if not raw:
            raise ValueError("Asset data is empty.")
        if len(raw) > MAX_DECODED_BYTES:
            raise ValueError("Uploaded image is too large.")
        return raw


asset_service = AssetService()
