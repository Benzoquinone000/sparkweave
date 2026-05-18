"""Catalog helpers for knowledge-base API routes."""

from __future__ import annotations

import traceback
from typing import Any

from fastapi import HTTPException

from sparkweave.api.routers.knowledge_models import KnowledgeBaseInfo


def list_knowledge_base_summaries(manager: Any, logger: Any) -> list[KnowledgeBaseInfo]:
    """Return resilient knowledge-base summary cards for the UI."""
    kb_names = manager.list_knowledge_bases()

    logger.debug("Found %s knowledge bases: %s", len(kb_names), kb_names)

    if not kb_names:
        logger.debug("No knowledge bases found, returning empty list")
        return []

    result: list[KnowledgeBaseInfo] = []
    errors: list[str] = []

    for name in kb_names:
        try:
            info = manager.get_info(name)
            logger.debug("Successfully got info for KB '%s': %s", name, info.get("statistics", {}))
            result.append(
                KnowledgeBaseInfo(
                    name=info["name"],
                    is_default=info["is_default"],
                    statistics=info.get("statistics", {}),
                    status=info.get("status"),
                    progress=info.get("progress"),
                )
            )
        except Exception as exc:
            error_msg = f"Error getting info for KB '{name}': {exc}"
            errors.append(error_msg)
            logger.warning("%s\n%s", error_msg, traceback.format_exc())
            try:
                kb_dir = manager.base_dir / name
                if kb_dir.exists():
                    logger.debug("KB '%s' directory exists, creating fallback info", name)
                    result.append(
                        KnowledgeBaseInfo(
                            name=name,
                            is_default=name == manager.get_default(),
                            statistics={
                                "raw_documents": 0,
                                "images": 0,
                                "content_lists": 0,
                                "rag_initialized": False,
                            },
                            status="unknown",
                            progress=None,
                        )
                    )
            except Exception as fallback_err:
                logger.error("Fallback also failed for KB '%s': %s", name, fallback_err)

    if errors and not result:
        error_detail = f"Failed to load knowledge bases. Errors: {'; '.join(errors)}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

    if errors:
        logger.warning("Some KBs had errors, returning %s results. Errors: %s", len(result), errors)

    logger.debug("Returning %s knowledge bases", len(result))
    return result
