"""Shared RAG override handling for graph entry points."""

from __future__ import annotations

from typing import Any

RAG_OVERRIDE_KEYS = (
    "retrieval_profile",
    "retrieval_mode",
    "top_k",
    "candidate_top_k",
    "reranker",
    "rerank_top_n",
    "max_context_chars",
    "score_threshold",
    "agentic_rag",
    "agentic_mode",
    "query_planning",
    "agentic_max_subqueries",
    "agentic_timeout_seconds",
    "agentic_max_concurrency",
    "agentic_fallback_to_single",
    "agentic_max_context_chars",
    "agentic_max_sources",
    "agentic_min_sources",
    "agentic_min_coverage_ratio",
    "agentic_min_relevant_coverage_ratio",
    "agentic_min_context_chars",
    "agentic_min_score",
    "query_transform",
    "hyde_max_chars",
    "hyde_timeout_seconds",
    "hybrid_ranker",
    "dense_weight",
    "sparse_weight",
    "rrf_k",
)


def apply_rag_overrides(args: dict[str, Any], overrides: dict[str, Any] | None) -> None:
    """Apply validated RAG config overrides without clobbering explicit tool args."""
    for key in RAG_OVERRIDE_KEYS:
        value = (overrides or {}).get(key)
        if value is not None and value != "":
            args.setdefault(key, value)
