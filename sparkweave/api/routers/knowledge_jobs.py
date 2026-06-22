"""Background job implementations for knowledge-base API workflows."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sparkweave.api.utils.task_id_manager import TaskIDManager
from sparkweave.api.utils.task_log_stream import capture_task_logs, get_task_stream_manager
from sparkweave.knowledge.add_documents import DocumentIndexingError
from sparkweave.knowledge.progress_tracker import ProgressStage, ProgressTracker

TaskLogger = Callable[[str, str, str], None]


def _call_task_log(task_log: TaskLogger, task_id: str, message: str, level: str = "info") -> None:
    task_log(task_id, message, level)


async def run_initialization_job(
    initializer: Any,
    task_id: str,
    *,
    manager_factory: Callable[[], Any],
    task_log: TaskLogger,
) -> None:
    """Process a newly created knowledge base outside the HTTP request path."""
    task_manager = TaskIDManager.get_instance()
    task_stream_manager = get_task_stream_manager()
    task_stream_manager.ensure_task(task_id)

    with capture_task_logs(task_id):
        try:
            if not initializer.progress_tracker:
                initializer.progress_tracker = ProgressTracker(
                    initializer.kb_name, initializer.base_dir
                )

            initializer.progress_tracker.task_id = task_id

            _call_task_log(task_log, task_id, f"Initializing knowledge base '{initializer.kb_name}'")

            await initializer.process_documents()
            _call_task_log(task_log, task_id, "Document processing complete")
            _call_task_log(task_log, task_id, "Finalizing initialization")

            initializer.progress_tracker.update(
                ProgressStage.COMPLETED,
                "Knowledge base initialization complete!",
                current=1,
                total=1,
            )

            manager = manager_factory()
            manager.update_kb_status(
                name=initializer.kb_name,
                status="ready",
                progress={
                    "stage": "completed",
                    "message": "Knowledge base initialization complete!",
                    "percent": 100,
                    "current": 1,
                    "total": 1,
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            _call_task_log(
                task_log,
                task_id,
                f"Knowledge base '{initializer.kb_name}' initialized",
                level="success",
            )
            task_manager.update_task_status(task_id, "completed")
            task_stream_manager.emit_complete(
                task_id, f"Knowledge base '{initializer.kb_name}' initialization complete"
            )
        except Exception as exc:
            error_msg = str(exc)

            _call_task_log(task_log, task_id, f"Initialization failed: {error_msg}", level="error")

            task_manager.update_task_status(task_id, "error", error=error_msg)

            manager = manager_factory()
            manager.update_kb_status(
                name=initializer.kb_name,
                status="error",
                progress={
                    "stage": "error",
                    "message": f"Initialization failed: {error_msg}",
                    "percent": 0,
                    "error": error_msg,
                    "task_id": task_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            if initializer.progress_tracker:
                initializer.progress_tracker.update(
                    ProgressStage.ERROR,
                    f"Initialization failed: {error_msg}",
                    error=error_msg,
                )
            task_stream_manager.emit_failed(task_id, error_msg)


async def run_upload_processing_job(
    kb_name: str,
    base_dir: str,
    uploaded_file_paths: list[str],
    task_id: str,
    *,
    manager_factory: Callable[[], Any],
    document_adder_cls: Callable[..., Any],
    cleanup_upload_staging: Callable[[list[str], str, str], None],
    task_log: TaskLogger,
    rag_provider: str | None = None,
    folder_id: str | None = None,
) -> None:
    """Index uploaded or synced files and update task/progress state."""
    task_manager = TaskIDManager.get_instance()
    task_stream_manager = get_task_stream_manager()
    task_stream_manager.ensure_task(task_id)

    progress_tracker = ProgressTracker(kb_name, Path(base_dir))
    progress_tracker.task_id = task_id

    with capture_task_logs(task_id):
        try:
            _call_task_log(
                task_log, task_id, f"Processing {len(uploaded_file_paths)} file(s) for KB '{kb_name}'"
            )
            progress_tracker.update(
                ProgressStage.PROCESSING_DOCUMENTS,
                f"Processing {len(uploaded_file_paths)} files...",
                current=0,
                total=len(uploaded_file_paths),
            )

            adder = document_adder_cls(
                kb_name=kb_name,
                base_dir=base_dir,
                progress_tracker=progress_tracker,
                rag_provider=rag_provider,
            )

            staged_files = adder.add_documents(uploaded_file_paths, allow_duplicates=False)
            _call_task_log(task_log, task_id, f"Staged {len(staged_files)} new file(s)")
            progress_tracker.update(
                ProgressStage.PROCESSING_DOCUMENTS,
                f"Staged {len(staged_files)} new file(s), starting indexing...",
                current=0,
                total=max(len(staged_files), 1),
            )

            if not staged_files:
                _call_task_log(task_log, task_id, "No new files to process (all duplicates or invalid)")
                progress_tracker.update(
                    ProgressStage.COMPLETED,
                    "No new files to process (all duplicates or invalid)",
                    current=0,
                    total=0,
                )
                task_manager.update_task_status(task_id, "completed")
                task_stream_manager.emit_complete(
                    task_id, "No new files to process (all duplicates or invalid)"
                )
                return

            processed_files = await adder.process_new_documents(staged_files)
            _call_task_log(task_log, task_id, f"Indexed {len(processed_files)} file(s)")
            if staged_files and not processed_files:
                raise DocumentIndexingError("No staged files were indexed successfully.")
            progress_tracker.update(
                ProgressStage.PROCESSING_DOCUMENTS,
                "Finalizing document inventory and metadata...",
                current=len(processed_files),
                total=max(len(staged_files), 1),
            )

            adder.update_metadata(len(processed_files) if processed_files else 0)

            if folder_id and processed_files:
                try:
                    manager = manager_factory()
                    manager.update_folder_sync_state(
                        kb_name, folder_id, [str(file_path) for file_path in processed_files]
                    )
                    _call_task_log(task_log, task_id, f"Updated folder sync state: {folder_id}")
                except Exception as sync_err:
                    _call_task_log(
                        task_log,
                        task_id,
                        f"Folder sync state update failed: {sync_err}",
                        level="warning",
                    )

            num_processed = len(processed_files) if processed_files else 0
            progress_tracker.update(
                ProgressStage.COMPLETED,
                f"Successfully processed {num_processed} files!",
                current=num_processed,
                total=num_processed,
            )

            _call_task_log(
                task_log,
                task_id,
                f"Processed {num_processed} file(s) for '{kb_name}'",
                level="success",
            )
            task_manager.update_task_status(task_id, "completed")
            task_stream_manager.emit_complete(
                task_id, f"Successfully processed {num_processed} files for '{kb_name}'"
            )
        except Exception as exc:
            error_msg = f"Upload processing failed (KB '{kb_name}'): {exc}"
            _call_task_log(task_log, task_id, error_msg, level="error")

            task_manager.update_task_status(task_id, "error", error=error_msg)

            progress_tracker.update(
                ProgressStage.ERROR, f"Processing failed: {error_msg}", error=error_msg
            )
            task_stream_manager.emit_failed(task_id, error_msg)
        finally:
            cleanup_upload_staging(uploaded_file_paths, base_dir, kb_name)


async def run_reindex_processing_job(
    kb_name: str,
    base_dir: str,
    task_id: str,
    rag_provider: str,
    *,
    rebuild_index: Callable[..., Awaitable[int]],
    task_log: TaskLogger,
    backup: bool = True,
) -> None:
    """Rebuild an existing knowledge-base index outside the HTTP request path."""
    task_manager = TaskIDManager.get_instance()
    task_stream_manager = get_task_stream_manager()
    task_stream_manager.ensure_task(task_id)

    progress_tracker = ProgressTracker(kb_name, Path(base_dir))
    progress_tracker.task_id = task_id

    with capture_task_logs(task_id):
        try:
            _call_task_log(task_log, task_id, f"Rebuilding knowledge base '{kb_name}' with {rag_provider}")
            rebuilt_count = await rebuild_index(
                kb_name,
                base_dir=base_dir,
                rag_provider=rag_provider,
                backup=backup,
                progress_tracker=progress_tracker,
                task_id=task_id,
            )
            _call_task_log(
                task_log,
                task_id,
                f"Rebuilt index for '{kb_name}' from {rebuilt_count} raw file(s)",
                level="success",
            )
            task_manager.update_task_status(task_id, "completed")
            task_stream_manager.emit_complete(
                task_id,
                f"Knowledge base '{kb_name}' index rebuilt",
            )
        except Exception as exc:
            error_msg = str(exc)
            _call_task_log(task_log, task_id, f"Reindex failed: {error_msg}", level="error")
            task_manager.update_task_status(task_id, "error", error=error_msg)
            progress_tracker.update(
                ProgressStage.ERROR,
                f"Reindex failed: {error_msg}",
                error=error_msg,
            )
            task_stream_manager.emit_failed(task_id, error_msg)
