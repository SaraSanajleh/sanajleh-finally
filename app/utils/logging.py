"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys

from app.config.settings import get_app_settings


def setup_logging() -> None:
    """Configure application-wide logging."""
    settings = get_app_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
