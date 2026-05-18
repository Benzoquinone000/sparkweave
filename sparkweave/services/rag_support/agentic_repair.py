"""Repair policy helpers for Agentic RAG branch fallback."""

from __future__ import annotations

import os
from typing import Any

from .agentic_quality import result_has_evidence


def should_attempt_agentic_branch_repair(quality: dict[str, Any]) -> bool:
    """Return whether weak evidence should be repaired before global fallback."""
    reasons = set(quality.get("reasons") or [])
    if not reasons.intersection({"low_subquery_coverage", "low_relevance_coverage", "low_context_chars"}):
        return False
    return int(quality.get("covered_subqueries") or 0) > 0


def agentic_branch_repair_indexes(
    quality: dict[str, Any],
    results: list[dict[str, Any]],
) -> list[int]:
    """Return zero-based branch indexes that should be retried with fallback retrieval."""
    reports = quality.get("subquery_relevance")
    indexes: list[int] = []
    for index, result in enumerate(results):
        report = reports[index] if isinstance(reports, list) and index < len(reports) else {}
        relevant = bool(report.get("relevant")) if isinstance(report, dict) else False
        if not result_has_evidence(result) or not relevant:
            indexes.append(index)
    return indexes[: _coerce_positive_int(_env_value("RAG_AGENTIC_MAX_REPAIR_BRANCHES"), 3)]


def should_accept_agentic_repair(
    *,
    original: dict[str, Any],
    candidate: dict[str, Any],
    original_report: dict[str, Any],
    candidate_report: dict[str, Any],
) -> bool:
    """Return whether a repaired branch is stronger than the original branch."""
    if not bool(candidate.get("success", True)) or not result_has_evidence(candidate):
        return False
    original_has_evidence = result_has_evidence(original)
    candidate_relevant = bool(candidate_report.get("relevant"))
    if not original_has_evidence:
        return candidate_relevant
    original_relevant = bool(original_report.get("relevant"))
    if candidate_relevant and not original_relevant:
        return True
    try:
        candidate_score = float(candidate_report.get("score") or 0)
        original_score = float(original_report.get("score") or 0)
    except (TypeError, ValueError):
        candidate_score = 0.0
        original_score = 0.0
    return candidate_relevant and candidate_score > original_score


def _env_value(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
