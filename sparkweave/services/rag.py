"""RAG service facade for NG tools."""

from __future__ import annotations

from typing import Any

from sparkweave.services.rag_support import RAGService
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER as DEFAULT_RAG_PROVIDER


async def rag_search(
    *,
    query: str,
    kb_name: str | None = None,
    provider: str | None = None,
    kb_base_dir: str | None = None,
    event_sink: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Query a knowledge base using the NG-owned RAG service."""
    service = RAGService(kb_base_dir=kb_base_dir, provider=provider)

    try:
        return await service.search(
            query=query,
            kb_name=kb_name,
            event_sink=event_sink,
            **kwargs,
        )
    except Exception as exc:
        raise Exception(f"RAG search failed: {exc}") from exc


async def initialize_rag(
    kb_name: str,
    documents: list[str],
    provider: str | None = None,
    kb_base_dir: str | None = None,
    **kwargs: Any,
) -> bool:
    """Initialize a knowledge base with documents."""
    service = RAGService(kb_base_dir=kb_base_dir, provider=provider)
    return await service.initialize(kb_name=kb_name, file_paths=documents, **kwargs)


async def delete_rag(
    kb_name: str,
    provider: str | None = None,
    kb_base_dir: str | None = None,
) -> bool:
    """Delete a knowledge base."""
    service = RAGService(kb_base_dir=kb_base_dir, provider=provider)
    return await service.delete(kb_name=kb_name)


def get_available_providers() -> list[dict[str, str]]:
    """Return available RAG pipelines."""
    return RAGService.list_providers()


def get_current_provider() -> str:
    """Return the currently configured RAG provider."""
    return RAGService.get_current_provider()


get_available_plugins = get_available_providers
list_providers = RAGService.list_providers


__all__ = [
    "DEFAULT_RAG_PROVIDER",
    "RAGService",
    "delete_rag",
    "get_available_plugins",
    "get_available_providers",
    "get_current_provider",
    "initialize_rag",
    "list_providers",
    "rag_search",
]

