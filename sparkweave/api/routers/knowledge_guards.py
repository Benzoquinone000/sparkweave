"""Guard helpers for knowledge-base API routes."""

from __future__ import annotations

from fastapi import HTTPException

from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name


def validate_registered_provider(raw_provider: str | None) -> str:
    """Normalize provider names while keeping the API field backward-compatible."""
    return normalize_provider_name(raw_provider or DEFAULT_PROVIDER)


def load_kb_entry_or_404(manager: KnowledgeBaseManager, kb_name: str) -> dict:
    manager.config = manager._load_config()
    kb_entry = manager.config.get("knowledge_bases", {}).get(kb_name)
    if kb_entry is None:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    return kb_entry


def assert_kb_writable_or_409(kb_name: str, kb_entry: dict) -> None:
    if bool(kb_entry.get("needs_reindex", False)):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Knowledge base '{kb_name}' uses legacy index format and needs reindex "
                "before accepting incremental uploads."
            ),
        )
