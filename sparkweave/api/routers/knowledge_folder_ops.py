"""Linked-folder operations for knowledge-base routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException


def link_folder_for_kb(manager: Any, kb_name: str, folder_path: str) -> dict[str, Any]:
    return manager.link_folder(kb_name, folder_path)


def get_linked_folders_for_kb(manager: Any, kb_name: str) -> list[dict[str, Any]]:
    return manager.get_linked_folders(kb_name)


def unlink_folder_for_kb(manager: Any, kb_name: str, folder_id: str) -> dict[str, str]:
    success = manager.unlink_folder(kb_name, folder_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Folder '{folder_id}' not found")
    return {"message": "Folder unlinked successfully", "folder_id": folder_id}


def prepare_folder_sync_plan(
    *,
    manager: Any,
    kb_name: str,
    folder_id: str,
    kb_entry: dict[str, Any],
    validate_provider: Callable[[str | None], str],
    default_provider: str,
    build_task_id: Callable[[str, str], str],
    ensure_task: Callable[[str], None],
    logger: Any,
) -> dict[str, Any]:
    kb_provider = validate_provider(kb_entry.get("rag_provider") or default_provider)
    folders = manager.get_linked_folders(kb_name)
    folder_info = next((item for item in folders if item["id"] == folder_id), None)

    if not folder_info:
        raise HTTPException(status_code=404, detail=f"Linked folder '{folder_id}' not found")

    folder_path = folder_info["path"]
    changes = manager.detect_folder_changes(kb_name, folder_id)
    files_to_process = changes["new_files"] + changes["modified_files"]

    if not files_to_process:
        return {
            "should_schedule": False,
            "response": {"message": "No new or modified files to sync", "files": [], "file_count": 0},
        }

    logger.info(
        "Syncing %s files from folder '%s' to KB '%s'",
        len(files_to_process),
        folder_path,
        kb_name,
    )
    task_id = build_task_id("kb_upload", f"{kb_name}_folder_{folder_id}")
    ensure_task(task_id)

    return {
        "should_schedule": True,
        "task_id": task_id,
        "kb_provider": kb_provider,
        "files_to_process": files_to_process,
        "response": {
            "message": f"Syncing {len(files_to_process)} files from linked folder",
            "folder_path": folder_path,
            "new_files": changes["new_count"],
            "modified_files": changes["modified_count"],
            "file_count": len(files_to_process),
            "task_id": task_id,
        },
    }
