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
from src.api.http.rest import assets, audio, auth, bindings, bluetooth, commands, config, display, gamepad, games, joystick, runtime, scores, status, system_controls, tetris, apps
from src.domain.models.response import ErrorResponse, SuccessResponse
from src.utils.logging_setup import initialize_logging


def _alias_routes(app, router, current: str, legacy: str) -> None:
    """Serve a router's paths under an older prefix as well."""
    from fastapi.routing import APIRoute

    for route in list(router.routes):
        if not isinstance(route, APIRoute) or not route.path.startswith(current):
            continue
        app.add_api_route(
            legacy + route.path[len(current):],
            route.endpoint,
            methods=list(route.methods or []),
            response_model=route.response_model,
            # Kept out of the docs: one canonical name for each thing.
            include_in_schema=False,
        )


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

    @app.on_event("startup")
    async def _start_joystick() -> None:
        # An optional peripheral must never stop the service from booting.
        try:
            from src.domain.services.joystick_service import joystick_service

            if joystick_service.enabled():
                joystick_service.start()

            from src.domain.services.gamepad_service import gamepad_service

            if gamepad_service.enabled():
                gamepad_service.start()
        except Exception:
            logger.exception("[spotify-matrix] joystick startup failed, continuing without it")

        try:
            # BlueZ does not necessarily power the adapter at boot, and a soft
            # rfkill block survives a reboot, so the matrix could come up with
            # working hardware that finds nothing.
            from src.domain.services.bluetooth_service import bluetooth_service

            powered, why = bluetooth_service.ensure_powered()
            if not powered and why:
                logger.info("[spotify-matrix] bluetooth adapter not on: {}", why)
        except Exception:
            logger.exception("[spotify-matrix] bluetooth startup failed, continuing without it")

        try:
            # Without this a paired speaker is connected but silent, because
            # ALSA has no way to reach it.
            from matrix_audio import bluealsa

            started, why = bluealsa.start()
            if not started and why:
                logger.info("[spotify-matrix] bluetooth audio unavailable: {}", why)
        except Exception:
            logger.exception("[spotify-matrix] bluealsa startup failed, continuing without it")

    @app.on_event("shutdown")
    async def _stop_joystick() -> None:
        try:
            from src.domain.services.joystick_service import joystick_service

            joystick_service.stop()

            from src.domain.services.gamepad_service import gamepad_service

            gamepad_service.stop()

            from matrix_audio import bluealsa

            bluealsa.stop()
        except Exception:
            logger.exception("[spotify-matrix] controller shutdown failed")

    @app.get("/healthz", response_model=SuccessResponse)
    async def healthz() -> dict[str, object]:
        return SuccessResponse(data={"status": "ok"}).model_dump()

    app.include_router(config.router)
    app.include_router(status.router)
    app.include_router(auth.router)
    app.include_router(commands.router)
    app.include_router(runtime.router)
    app.include_router(apps.router)
    # /api/widgets/... was the route before apps were called apps. Anything
    # holding an old URL - a script, a bookmarked call, a cached bundle -
    # keeps working rather than getting a 404.
    _alias_routes(app, apps.router, "/api/apps", "/api/widgets")
    app.include_router(display.router)
    app.include_router(assets.router)
    app.include_router(bluetooth.router)
    app.include_router(tetris.router)
    app.include_router(games.router)
    app.include_router(scores.router)
    app.include_router(bindings.router)
    app.include_router(joystick.router)
    app.include_router(system_controls.router)
    app.include_router(gamepad.router)
    app.include_router(audio.router)

    public_dir = str(base_config["paths"]["public_dir"])
    web_dist = Path("web-dist")

    if (web_dist / "index.html").exists():
        # React + MUI app is the primary UI, served at the site root with SPA fallback.
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

        studio_dir = Path(public_dir) / "studio"
        if studio_dir.exists():
            app.mount("/studio", StaticFiles(directory=str(studio_dir), html=True), name="studio")

        @app.get("/")
        async def _spa_root() -> FileResponse:
            return FileResponse(str(web_dist / "index.html"))

        @app.get("/{full_path:path}")
        async def _spa(full_path: str) -> FileResponse:
            candidate = web_dist / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(web_dist / "index.html"))
    else:
        # Fallback to the classic UI when the React bundle has not been built.
        app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")

    return app
