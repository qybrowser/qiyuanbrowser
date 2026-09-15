"""Consistent console and daily file logging for the admin server."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler


def configure_logging(data_dir: str) -> str:
    log_dir = os.path.join(data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "qiyuan.log")
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    file = TimedRotatingFileHandler(
        log_path, when="midnight", interval=1, backupCount=6, encoding="utf-8"
    )
    for handler in (console, file):
        handler.setFormatter(formatter)

    # Uvicorn installs its own handlers before ASGI startup; replace them so
    # access and error messages have exactly the same console/file output.
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for old_handler in logger.handlers[:]:
            logger.removeHandler(old_handler)
            old_handler.close()
        logger.addHandler(console)
        logger.addHandler(file)
        logger.setLevel(logging.INFO)
        if name:
            logger.propagate = False
    return log_path
