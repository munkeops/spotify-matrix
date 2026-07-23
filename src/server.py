"""Spotify Matrix FastAPI application factory."""

from __future__ import annotations

from time import perf_counter

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from configs import base_config
from src.api.http.rest import assets, auth, bluetooth, commands, config, display, runtime, status, widgets
from src.domain.models.response import ErrorResponse, SuccessResponse
from src.utils.logging_setup import initialize_logging


def create_app() -> FastAPI:
    initialize_logging()

    app = FastAPI(
        title="Assistant Matrix Service",
        version="0.2.0",
        docs_url="/api/v1/spotify-matrix/docs",
        redoc_url="/api/v1/spotify-matrix/redoc",
        openapi_url="/api/v1/spotify-matrix/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_logger(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = perf_counter()
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("[spotify-matrix] {} {} failed {:.1f}ms", request.method, target, (perf_counter() - start) * 1000)
            raise
        logger.info("[spotify-matrix] {} {} {} {:.1f}ms", request.method, target, response.status_code, (perf_counter() - start) * 1000)
        return response

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        msg = str(exc)
        logger.warning("[spotify-matrix] {} {} 400 {}", request.method, request.url.path, msg)
        return JSONResponse(status_code=400, content=ErrorResponse(message="invalid request", detail=msg).model_dump())

    @app.exception_handler(Exception)
    async def _generic_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("[spotify-matrix] {} {} 500", request.method, request.url.path)
        return JSONResponse(status_code=500, content=ErrorResponse(message="internal server error", detail="internal server error").model_dump())

    @app.get("/healthz", response_model=SuccessResponse)
    async def healthz() -> dict[str, object]:
        return SuccessResponse(data={"status": "ok"}).model_dump()

    app.include_router(config.router)
    app.include_router(status.router)
    app.include_router(auth.router)
    app.include_router(commands.router)
    app.include_router(runtime.router)
    app.include_router(widgets.router)
    app.include_router(display.router)
    app.include_router(assets.router)
    app.include_router(bluetooth.router)

    # React + MUI app (built into web-dist) served at /app, with SPA fallback.
    web_dist = Path("web-dist")
    if (web_dist / "index.html").exists():
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/app/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

        @app.get("/app")
        async def _web_root() -> FileResponse:
            return FileResponse(str(web_dist / "index.html"))

        @app.get("/app/{full_path:path}")
        async def _web_spa(full_path: str) -> FileResponse:
            return FileResponse(str(web_dist / "index.html"))

    public_dir = str(base_config["paths"]["public_dir"])
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
    return app
