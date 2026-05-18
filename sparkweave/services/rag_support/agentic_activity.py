"""Activity traces for Agentic RAG planning and branch execution."""

from __future__ import annotations

from typing import Any

from .agentic_quality import result_has_evidence
from .query_planner import RagQueryPlan


def build_agentic_activity_plan(
    *,
    plan: RagQueryPlan,
    results: list[dict[str, Any]],
    source_count: int,
) -> dict[str, Any]:
    """Build a compact execution trace for Agentic RAG UI and diagnostics."""
    steps = []
    for index, (subquery, result) in enumerate(zip(plan.subqueries, results), start=1):
        steps.append(
            {
                "index": index,
                "query": subquery.query,
                "purpose": subquery.purpose,
                "status": _agentic_step_status(result),
                "source_count": len(result.get("sources") or []),
                "content_chars": len(str(result.get("content") or result.get("answer") or "")),
                "error": result.get("error") or "",
            }
        )
    failed = sum(1 for item in steps if item["status"] == "failed")
    weak = sum(1 for item in steps if item["status"] == "weak")
    if not steps:
        recommendation = "Use the fast RAG path; no planning step was needed."
    elif source_count <= 0:
        recommendation = "No evidence was found. Check indexing coverage or widen candidate_top_k."
    elif weak:
        recommendation = "Some subqueries returned thin evidence. Consider baseline repair before answering."
    elif failed:
        recommendation = "Some subqueries failed. Keep the successful evidence and retry failed branches with baseline retrieval."
    else:
        recommendation = "Use the merged evidence as grounded context, then answer with citations."
    return {
        "mode": plan.mode,
        "reason": plan.reason,
        "step_count": len(steps),
        "failed_steps": failed,
        "weak_steps": weak,
        "merged_source_count": source_count,
        "steps": steps,
        "recommendation": recommendation,
    }


def _agentic_step_status(result: dict[str, Any]) -> str:
    if not bool(result.get("success", True)):
        return "failed"
    return "ok" if result_has_evidence(result) else "weak"
