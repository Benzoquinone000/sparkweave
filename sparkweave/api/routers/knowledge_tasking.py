"""Background task helpers for knowledge-base API jobs."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import logging
import os
import threading
from typing import Any, Awaitable, Callable
from uuid import uuid4

from sparkweave.api.utils.task_id_manager import TaskIDManager
from sparkweave.api.utils.task_log_stream import get_task_stream_manager

logger = logging.getLogger("Knowledge")

_kb_task_executor: ThreadPoolExecutor | None = None
_kb_task_executor_lock = threading.Lock()


def kb_background_workers() -> int:
    raw = os.getenv("SPARKWEAVE_KB_BACKGROUND_WORKERS", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(1, min(value, 4))


def get_kb_task_executor() -> ThreadPoolExecutor:
    """Return the dedicated KB worker pool.

    Keep knowledge-base indexing away from the FastAPI event loop. The default
    is one worker because OCR, embedding and Milvus writes are resource-heavy
    and LlamaIndex uses process-global Settings.
    """
    global _kb_task_executor
    if _kb_task_executor is None:
        with _kb_task_executor_lock:
            if _kb_task_executor is None:
                _kb_task_executor = ThreadPoolExecutor(
                    max_workers=kb_background_workers(),
                    thread_name_prefix="sparkweave-kb",
                )
    return _kb_task_executor


def run_kb_coroutine_in_worker(
    task_id: str,
    coroutine_factory: Callable[..., Awaitable[Any]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    task_manager = TaskIDManager.get_instance()
    task_stream_manager = get_task_stream_manager()
    task_stream_manager.ensure_task(task_id)
    task_manager.update_task_status(task_id, "running")
    task_stream_manager.emit_status(task_id, "running", "Background knowledge-base worker started.")
    task_stream_manager.emit_log(task_id, "Background knowledge-base worker started.")
    try:
        asyncio.run(coroutine_factory(*args, **kwargs))
        metadata = task_manager.get_task_metadata(task_id) or {}
        if metadata.get("status") in {"queued", "running"}:
            task_manager.update_task_status(task_id, "completed")
            task_stream_manager.emit_complete(task_id, "Background knowledge-base task completed.")
    except Exception as exc:
        error_msg = f"Knowledge-base background worker crashed: {exc}"
        logger.exception(error_msg)
        task_manager.update_task_status(task_id, "error", error=error_msg)
        task_stream_manager.emit_failed(task_id, error_msg)


def schedule_kb_task(
    job_id: str,
    coroutine_factory: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Future:
    """Submit a KB job to the dedicated worker pool and return immediately."""
    task_manager = TaskIDManager.get_instance()
    task_stream_manager = get_task_stream_manager()
    task_stream_manager.ensure_task(job_id)
    task_manager.update_task_status(job_id, "queued")
    task_stream_manager.emit_status(job_id, "queued", "Queued knowledge-base background task.")
    task_stream_manager.emit_log(job_id, "Queued knowledge-base background task.")

    future = get_kb_task_executor().submit(
        run_kb_coroutine_in_worker,
        job_id,
        coroutine_factory,
        args,
        kwargs,
    )

    def _log_unhandled_failure(completed: Future) -> None:
        try:
            completed.result()
        except Exception as exc:
            logger.exception("Unhandled KB background task failure: %s", exc)

    future.add_done_callback(_log_unhandled_failure)
    return future


def build_unique_task_id(task_type: str, task_key_prefix: str) -> str:
    task_manager = TaskIDManager.get_instance()
    task_key = f"{task_key_prefix}_{datetime.now().isoformat()}_{uuid4().hex[:8]}"
    return task_manager.generate_task_id(task_type, task_key)


def task_log(task_id: str, message: str, level: str = "info") -> None:
    manager = get_task_stream_manager()
    manager.ensure_task(task_id)
    manager.emit_log(task_id, message)

    log_method = getattr(logger, level, None)
    if callable(log_method):
        log_method(f"[{task_id}] {message}")
    else:
        logger.info(f"[{task_id}] {message}")
