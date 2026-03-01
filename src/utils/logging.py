"""Logging configuration for xray-client."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from src.core.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure loguru based on application settings."""
    # Remove default handler
    logger.remove()

    # Определяем уровни для разных выводов
    console_level = (settings.log_console_level or settings.log_level).upper()
    file_level = (settings.log_file_level or settings.log_level).upper()

    # Console logging (stderr with simplified format)
    if settings.log_console_enabled:
        logger.add(
            sys.stderr,
            format="[<level>{level}</level>] {message}",
            level=console_level,
            colorize=True,
            enqueue=True,  # Thread-safe
        )

    # File logging
    if settings.log_file_enabled:
        if settings.log_file_path:
            log_file = Path(settings.log_file_path)
        else:
            log_file = Path.home() / ".xray-client" / "logs" / "main.log"

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=file_level,
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

    # If no handlers added (both disabled), add a null handler to avoid "No handlers" warning
    if not settings.log_console_enabled and not settings.log_file_enabled:
        logger.add(lambda msg: None, level="INFO")  # Null sink

    logger.debug("Logging configured: console={}, file={} (console_level={}, file_level={})",
                 settings.log_console_enabled, settings.log_file_enabled,
                 console_level, file_level)