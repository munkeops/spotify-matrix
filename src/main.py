"""Spotify Matrix service entrypoint."""

from __future__ import annotations

import asyncio
import os

import uvicorn

from configs import base_config
from src.domain.services.runtime_service import runtime_service
from src.server import create_app

http_configs = base_config["http"]


async def _run_service() -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=os.environ.get("HOST", str(http_configs["host"])),
            port=int(os.environ.get("PORT", str(http_configs["port"]))),
            log_level="info",
            access_log=True,
            log_config=None,
        )
    )
    try:
        await server.serve()
    finally:
        runtime_service.stop()


def main() -> None:
    try:
        asyncio.run(_run_service())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
