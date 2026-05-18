"""Rebuild knowledge-base indexes with the active RAG provider."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sparkweave.knowledge.initializer import KnowledgeBaseInitializer
from sparkweave.knowledge.manager import KnowledgeBaseManager
from sparkweave.knowledge.progress_tracker import ProgressStage, ProgressTracker
from sparkweave.services.rag_support.factory import DEFAULT_PROVIDER, normalize_provider_name
from sparkweave.services.rag_support.file_routing import FileTypeRouter


def collect_raw_documents(kb_dir: Path) -> list[Path]:
    """Return supported raw documents for a knowledge base."""
    raw_dir = kb_dir / "raw"
    if not raw_dir.exists():
        return []

    files: list[Path] = []
    for pattern in FileTypeRouter.get_glob_patterns():
        files.extend(path for path in raw_dir.glob(pattern) if path.is_file())
    return sorted({path.resolve() for path in files}, key=lambda path: str(path).lower())


def _set_kb_reindex_state(
    manager: KnowledgeBaseManager,
    kb_name: str,
    *,
    provider: str,
    needs_reindex: bool,
) -> None:
    manager.config = manager._load_config()
    entry = manager.config.setdefault("knowledge_bases", {}).setdefault(
        kb_name,
        {
            "path": kb_name,
            "description": f"Knowledge base: {kb_name}",
        },
    )
    entry["rag_provider"] = normalize_provider_name(provider)
    entry["needs_reindex"] = needs_reindex
    entry["updated_at"] = datetime.now().isoformat()
    manager._save_config()


async def reindex_knowledge_base(
    kb_name: str,
    *,
    base_dir: str | Path = "./data/knowledge_bases",
    rag_provider: str | None = None,
    backup: bool = True,
    progress_tracker: ProgressTracker | None = None,
    task_id: str | None = None,
) -> int:
    """Rebuild the active index from raw documents.

    The original raw files remain the source of truth. Existing Milvus metadata
    or local LlamaIndex storage is cleaned first, then the selected provider
    builds a fresh index.
    """
    manager = KnowledgeBaseManager(base_dir=str(base_dir))
    if kb_name not in manager.list_knowledge_bases():
        raise ValueError(f"Knowledge base '{kb_name}' not found")

    kb_dir = manager.get_knowledge_base_path(kb_name)
    manager.config = manager._load_config()
    entry = manager.config.get("knowledge_bases", {}).get(kb_name, {})
    provider = normalize_provider_name(rag_provider or entry.get("rag_provider") or DEFAULT_PROVIDER)

    tracker = progress_tracker or ProgressTracker(kb_name, Path(base_dir))
    tracker.task_id = task_id

    raw_documents = collect_raw_documents(kb_dir)
    if not raw_documents:
        message = "No raw documents found. Upload files before rebuilding the index."
        tracker.update(ProgressStage.ERROR, message, error=message)
        manager.update_kb_status(
            name=kb_name,
            status="error",
            progress={
                "stage": "error",
                "message": message,
                "percent": 0,
                "error": message,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        _set_kb_reindex_state(manager, kb_name, provider=provider, needs_reindex=True)
        raise ValueError(message)

    manager.update_kb_status(
        name=kb_name,
        status="processing",
        progress={
            "stage": "reindexing",
            "message": f"Rebuilding index from {len(raw_documents)} raw file(s).",
            "percent": 0,
            "current": 0,
            "total": len(raw_documents),
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
        },
    )
    tracker.update(
        ProgressStage.PROCESSING_DOCUMENTS,
        f"Rebuilding index from {len(raw_documents)} raw file(s)...",
        current=0,
        total=len(raw_documents),
    )

    try:
        manager.clean_rag_storage(kb_name, backup=backup)
        initializer = KnowledgeBaseInitializer(
            kb_name=kb_name,
            base_dir=str(base_dir),
            progress_tracker=tracker,
            rag_provider=provider,
        )
        initializer.raw_dir.mkdir(parents=True, exist_ok=True)
        initializer._storage_dir().mkdir(parents=True, exist_ok=True)

        await initializer.process_documents()

        tracker.update(
            ProgressStage.COMPLETED,
            "Knowledge base index rebuilt.",
            current=len(raw_documents),
            total=len(raw_documents),
        )
        manager.update_kb_status(
            name=kb_name,
            status="ready",
            progress={
                "stage": "completed",
                "message": "Knowledge base index rebuilt.",
                "percent": 100,
                "current": len(raw_documents),
                "total": len(raw_documents),
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        _set_kb_reindex_state(manager, kb_name, provider=provider, needs_reindex=False)
        return len(raw_documents)
    except Exception as exc:
        message = str(exc)
        tracker.update(
            ProgressStage.ERROR,
            "Knowledge base reindex failed.",
            error=message,
        )
        manager.update_kb_status(
            name=kb_name,
            status="error",
            progress={
                "stage": "error",
                "message": "Knowledge base reindex failed.",
                "percent": 0,
                "error": message,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        _set_kb_reindex_state(manager, kb_name, provider=provider, needs_reindex=True)
        raise


__all__ = ["collect_raw_documents", "reindex_knowledge_base"]
