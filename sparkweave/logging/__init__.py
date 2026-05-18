"""Small NG-owned logging facade for migrated API boundaries."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys
from types import MethodType
from typing import Any

from .handlers import (
    ConsoleFormatter,
    FileFormatter,
    FileHandler,
    JSONFileHandler,
    LogInterceptor,
    RotatingFileHandler,
    WebSocketLogHandler,
    create_task_logger,
)


def _custom_log(logger: logging.Logger, display_level: str, message: str, *args: Any, **kwargs: Any) -> None:
    extra = dict(kwargs.pop("extra", {}) or {})
    extra.setdefault("display_level", display_level)
    extra.setdefault("module_name", logger.name.rsplit(".", 1)[-1])
    logger.info(message, *args, extra=extra, **kwargs)


def _install_compat_methods(logger: logging.Logger) -> logging.Logger:
    if not hasattr(logger, "success"):
        logger.success = MethodType(  # type: ignore[attr-defined]
            lambda self, message, *args, **kwargs: _custom_log(
                self, "SUCCESS", message, *args, **kwargs
            ),
            logger,
        )
    if not hasattr(logger, "progress"):
        logger.progress = MethodType(  # type: ignore[attr-defined]
            lambda self, message, *args, **kwargs: _custom_log(
                self, "PROGRESS", message, *args, **kwargs
            ),
            logger,
        )
    if not hasattr(logger, "complete"):
        logger.complete = MethodType(  # type: ignore[attr-defined]
            lambda self, message, *args, **kwargs: _custom_log(
                self, "COMPLETE", message, *args, **kwargs
            ),
            logger,
        )
    return logger


def get_logger(
    name: str,
    *,
    level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
    log_dir: str | Path | None = None,
    service_prefix: str | None = None,
) -> logging.Logger:
    """Return a configured stdlib logger with SparkWeave-compatible helpers."""
    logger = logging.getLogger(f"sparkweave.{name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if console_output and not any(getattr(handler, "_sparkweave_console", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        handler.setFormatter(ConsoleFormatter(service_prefix=service_prefix))
        handler._sparkweave_console = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    if file_output and log_dir is not None and not any(getattr(handler, "_sparkweave_file", False) for handler in logger.handlers):
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / f"sparkweave_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(FileFormatter())
        file_handler._sparkweave_file = True  # type: ignore[attr-defined]
        logger.addHandler(file_handler)

    return _install_compat_methods(logger)


__all__ = [
    "ConsoleFormatter",
    "FileFormatter",
    "FileHandler",
    "JSONFileHandler",
    "LogInterceptor",
    "RotatingFileHandler",
    "WebSocketLogHandler",
    "create_task_logger",
    "get_logger",
]

