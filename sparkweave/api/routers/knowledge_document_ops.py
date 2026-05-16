"""Document and vector management operations for knowledge-base routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.concurrency import run_in_threadpool

from sparkweave.knowledge.document_inventory import (
    delete_document,
    delete_vector_chunk,
    list_documents,
    list_vector_chunks,
    preview_document,
)


async def list_documents_for_kb(
    *,
    manager: Any,
    kb_name: str,
    kb_entry: dict[str, Any],
    include_vectors: bool,
    validate_provider: Callable[[str | None], str],
    default_provider: str,
) -> dict[str, Any]:
    try:
        return await run_in_threadpool(
            list_documents,
            manager,
            kb_name,
            include_vectors=include_vectors,
        )
    except ValueError as exc:
        return {
            "kb_name": kb_name,
            "documents": [],
            "document_count": 0,
            "vector_count": None,
            "vectors_available": False,
            "vector_error": str(exc),
            "provider": validate_provider(kb_entry.get("rag_provider") or default_provider),
        }


async def preview_document_for_kb(
    *,
    manager: Any,
    kb_name: str,
    document_id: str,
    max_chars: int,
    force_refresh: bool,
) -> dict[str, Any]:
    return await run_in_threadpool(
        preview_document,
        manager,
        kb_name,
        document_id,
        max_chars=max_chars,
        force_refresh=force_refresh,
    )


async def list_vectors_for_kb(
    *,
    manager: Any,
    kb_name: str,
    kb_entry: dict[str, Any],
    document_id: str | None,
    limit: int,
    offset: int,
    validate_provider: Callable[[str | None], str],
    default_provider: str,
) -> dict[str, Any]:
    try:
        return await run_in_threadpool(
            list_vector_chunks,
            manager,
            kb_name,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        return {
            "kb_name": kb_name,
            "provider": validate_provider(kb_entry.get("rag_provider") or default_provider),
            "document_id": document_id,
            "chunks": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "collection": "",
            "available": False,
            "error": str(exc),
        }


async def delete_document_for_kb(
    *,
    manager: Any,
    kb_name: str,
    document_id: str,
    remove_raw: bool,
    remove_vectors: bool,
) -> dict[str, Any]:
    result = await run_in_threadpool(
        delete_document,
        manager,
        kb_name,
        document_id,
        remove_raw=remove_raw,
        remove_vectors=remove_vectors,
    )
    manager.update_kb_status(
        kb_name,
        "ready",
        {
            "stage": "document_management",
            "message": f"Deleted document {result.get('document_name')}",
            "percent": 100,
        },
    )
    return result


async def delete_vector_for_kb(*, manager: Any, kb_name: str, node_id: str) -> dict[str, Any]:
    return await run_in_threadpool(delete_vector_chunk, manager, kb_name, node_id)
