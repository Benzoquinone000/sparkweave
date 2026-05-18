"""Lightweight logging handlers owned by ``sparkweave``."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler as BaseRotatingFileHandler
from pathlib import Path
from typing import Optional


class ConsoleFormatter(logging.Formatter):
    """Compact formatter compatible with the legacy Web/CLI log shape."""

    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[37m",
        "SUCCESS": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "PROGRESS": "\033[36m",
        "COMPLETE": "\033[32m",
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def __init__(self, service_prefix: str | None = None):
        super().__init__()
        self.service_prefix = service_prefix
        self.use_colors = False

    def format(self, record: logging.LogRecord) -> str:
        display_level = getattr(record, "display_level", record.levelname)
        module = getattr(record, "module_name", record.name)
        color = self.COLORS.get(display_level, self.COLORS["INFO"]) if self.use_colors else ""
        dim = self.DIM if self.use_colors else ""
        reset = self.RESET if self.use_colors else ""
        module_tag = f"[{module}]"
        level_tag = f"{display_level}:"
        prefix = f"{dim}[{self.service_prefix}]{reset} " if self.service_prefix else ""
        return f"{prefix}{dim}{module_tag}{reset} {color}{level_tag}{reset} {record.getMessage()}"


class FileFormatter(logging.Formatter):
    """Detailed file formatter for task logs."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)-8s] [%(module_name)-12s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "module_name"):
            record.module_name = record.name
        return super().format(record)


class FileHandler(logging.FileHandler):
    """File handler with SparkWeave-compatible formatting."""

    def __init__(
        self,
        filename: str,
        level: int = logging.DEBUG,
        encoding: str = "utf-8",
    ):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename, encoding=encoding)
        self.setLevel(level)
        self.setFormatter(FileFormatter())


class RotatingFileHandler(BaseRotatingFileHandler):
    """Size-rotating file handler with SparkWeave-compatible formatting."""

    def __init__(
        self,
        filename: str,
        level: int = logging.DEBUG,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
    ):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(
            filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )
        self.setLevel(level)
        self.setFormatter(FileFormatter())


class JSONFileHandler(logging.Handler):
    """Write structured JSONL log entries."""

    def __init__(
        self,
        filepath: str,
        level: int = logging.DEBUG,
        encoding: str = "utf-8",
    ):
        super().__init__()
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self.filepath = filepath
        self.encoding = encoding
        self.setLevel(level)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "module": getattr(record, "module_name", record.name),
                "message": self.format(record),
            }
            for key in ["display_level", "tool_name", "elapsed_ms", "tokens"]:
                if hasattr(record, key):
                    entry[key] = getattr(record, key)
            with open(self.filepath, "a", encoding=self.encoding) as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)


class WebSocketLogHandler(logging.Handler):
    """Stream log records into an asyncio queue for WebSocket/SSE consumers."""

    def __init__(
        self,
        queue: asyncio.Queue,
        include_module: bool = True,
        service_prefix: Optional[str] = None,
    ):
        super().__init__()
        self.queue = queue
        self.include_module = include_module
        self.service_prefix = service_prefix
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            display_level = getattr(record, "display_level", record.levelname)
            module_name = getattr(record, "module_name", record.name)
            level_tag = display_level
            if self.service_prefix:
                service_tag = f"[{self.service_prefix}]"
                if self.include_module:
                    content = f"{service_tag} {level_tag} [{module_name}] {msg}"
                else:
                    content = f"{service_tag} {level_tag} {msg}"
            elif self.include_module:
                content = f"{level_tag} [{module_name}] {msg}"
            else:
                content = f"{level_tag} {msg}"

            self.queue.put_nowait(
                {
                    "type": "log",
                    "level": display_level,
                    "module": module_name,
                    "content": content,
                    "message": msg,
                    "timestamp": record.created,
                }
            )
        except asyncio.QueueFull:
            pass
        except Exception:
            self.handleError(record)


class LogInterceptor:
    """Temporarily attach a WebSocketLogHandler to a logger."""

    def __init__(
        self,
        logger: logging.Logger,
        queue: asyncio.Queue,
        include_module: bool = True,
    ):
        self.logger = logger
        self.handler = WebSocketLogHandler(queue, include_module)

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self.handler

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.removeHandler(self.handler)


def create_task_logger(
    task_id: str,
    module_name: str,
    log_dir: str,
    queue: Optional["asyncio.Queue"] = None,
) -> logging.Logger:
    """Create a task logger with file output and optional queue streaming."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"sparkweave.{module_name}.{task_id}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"{module_name}_{task_id}_{timestamp}.log"
    logger.addHandler(FileHandler(str(log_file)))

    if queue is not None:
        ws_handler = WebSocketLogHandler(queue)
        ws_handler.setLevel(logging.INFO)
        logger.addHandler(ws_handler)

    return logger


__all__ = [
    "ConsoleFormatter",
    "FileFormatter",
    "FileHandler",
    "JSONFileHandler",
    "LogInterceptor",
    "RotatingFileHandler",
    "WebSocketLogHandler",
    "create_task_logger",
]

