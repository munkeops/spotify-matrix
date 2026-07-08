"""Spotify Matrix logging setup."""

from __future__ import annotations

import sys

from loguru import logger

from configs import base_config

logging_config = base_config["logging"]


def _configure_file_logging() -> None:
    logger.add(
        "logs/{time:YYYY-MM-DD_HH-mm-ss}.log",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        serialize=True,
        level="DEBUG",
        format="{time} {level} {name} {file}: {line} {message}",
        backtrace=True,
        diagnose=False,
    )
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {message}")


def _configure_cloud_logging() -> None:
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <5} | {message}", colorize=False)


def initialize_logging() -> None:
    logging_mode = str(logging_config.get("mode", "file")).strip().lower()
    logger.remove()
    if logging_mode == "file":
        _configure_file_logging()
    else:
        _configure_cloud_logging()
    logger.info("Logger is configured in '{}' mode.", logging_mode)
