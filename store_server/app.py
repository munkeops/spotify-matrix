"""Self-hosted app store server.

Hosts publishable Assistant Matrix app packages: serves a store index and
the package archives/previews, and accepts publishes. The main app installs
apps from here via its existing store index URL + install flow.

Run: python -m store_server.app   (or as a separate container in compose)
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import tarfile
import tomllib
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

STORE_DIR = Path(os.environ.get("STORE_DATA_DIR", "store-data")).resolve()
PUBLIC_URL = os.environ.get("STORE_PUBLIC_URL", "http://localhost:8080").rstrip("/")
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024


def apps_dir() -> Path:
    return STORE_DIR / "apps"


class PublishRequest(BaseModel):
    archive: str  # base64-encoded .tar.gz of the packaged app (contains app.toml)
    matrixPng: str | None = None  # optional base64 preview
    cardGif: str | None = None  # optional base64 preview


def _decode(data: str, label: str) -> bytes:
    try:
        raw = base64.b64decode(data.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"{label} must be base64.") from error
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=400, detail=f"{label} is too large.")
    return raw


def _read_manifest_bytes(raw: bytes) -> tuple[dict, bytes]:
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            member = next((m for m in tar.getmembers() if Path(m.name).name == "app.toml" and m.isfile()), None)
            if member is None:
                raise HTTPException(status_code=400, detail="Archive is missing app.toml.")
            extracted = tar.extractfile(member)
            toml_bytes = extracted.read() if extracted else b""
    except tarfile.TarError as error:
        raise HTTPException(status_code=400, detail="Archive is not a valid .tar.gz.") from error
    try:
        manifest = tomllib.loads(toml_bytes.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="app.toml is not valid TOML.") from error
    return manifest, toml_bytes


def _builtin_entries() -> list[dict]:
    seed = Path(__file__).resolve().parent / "builtins.json"
    if not seed.exists():
        return []
    try:
        entries = json.loads(seed.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    for entry in entries:
        entry.setdefault("runtime", "builtin")
        entry.setdefault("author", "Assistant Matrix")
        for key in ("manifestUrl", "archiveUrl", "previewGifUrl", "matrixPreviewUrl", "sha256"):
            entry.setdefault(key, "")
    return entries


def rebuild_index() -> dict:
    apps = list(_builtin_entries())
    for toml_path in sorted(apps_dir().glob("*/*/app.toml")):
        manifest = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        meta = manifest.get("app", {})
        wid = meta.get("id", "")
        ver = str(meta.get("version", ""))
        if not wid or not ver:
            continue
        version_dir = toml_path.parent
        base = f"{PUBLIC_URL}/apps/{wid}/{ver}"
        archive = version_dir / f"{wid}-{ver}.tar.gz"
        sha = hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else ""
        card = version_dir / "previews" / "card.gif"
        matrix = version_dir / "previews" / "matrix-64.png"
        apps.append({
            "id": wid,
            "name": meta.get("name", wid),
            "version": ver,
            "summary": meta.get("summary", ""),
            "category": meta.get("category", "custom"),
            "author": meta.get("author", "Assistant Matrix"),
            "manifestUrl": f"{base}/app.toml",
            "archiveUrl": f"{base}/{wid}-{ver}.tar.gz",
            "previewGifUrl": f"{base}/previews/card.gif" if card.exists() else "",
            "matrixPreviewUrl": f"{base}/previews/matrix-64.png" if matrix.exists() else "",
            "sha256": sha,
        })
    index = {"schemaVersion": 1, "apps": apps}
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    (STORE_DIR / "store-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


app = FastAPI(title="Assistant Matrix Store")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/store-index.json")
def store_index() -> JSONResponse:
    path = STORE_DIR / "store-index.json"
    if path.exists():
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))
    return JSONResponse(rebuild_index())


@app.post("/api/store/publish")
def publish(body: PublishRequest) -> dict:
    raw = _decode(body.archive, "archive")
    manifest, toml_bytes = _read_manifest_bytes(raw)
    meta = manifest.get("app", {})
    wid = str(meta.get("id", ""))
    ver = str(meta.get("version", ""))
    if not wid or not ver:
        raise HTTPException(status_code=400, detail="app.toml is missing id or version.")
    version_dir = apps_dir() / wid / ver
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / f"{wid}-{ver}.tar.gz").write_bytes(raw)
    (version_dir / "app.toml").write_bytes(toml_bytes)
    if body.matrixPng or body.cardGif:
        (version_dir / "previews").mkdir(exist_ok=True)
        if body.matrixPng:
            (version_dir / "previews" / "matrix-64.png").write_bytes(_decode(body.matrixPng, "matrixPng"))
        if body.cardGif:
            (version_dir / "previews" / "card.gif").write_bytes(_decode(body.cardGif, "cardGif"))
    rebuild_index()
    return {"ok": True, "id": wid, "version": ver}


@app.get("/apps/{path:path}")
def app_file(path: str) -> FileResponse:
    target = (apps_dir() / path).resolve()
    root = apps_dir().resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found.")
    return FileResponse(str(target))


def main() -> None:
    apps_dir().mkdir(parents=True, exist_ok=True)
    rebuild_index()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("STORE_PORT", "8080")))


if __name__ == "__main__":
    main()
