"""Focused tests for Agentic RAG support modules."""

from __future__ import annotations

from sparkweave.services.rag_support.agentic_activity import build_agentic_activity_plan
from sparkweave.services.rag_support.agentic_explanation import build_agentic_explanation
from sparkweave.services.rag_support.agentic_merge import (
    fallback_search_kwargs,
    merge_agentic_results,
)
from sparkweave.services.rag_support.agentic_quality import (
    attach_agentic_quality,
    build_agentic_quality_report,
)
from sparkweave.services.rag_support.agentic_repair import (
    agentic_branch_repair_indexes,
    should_accept_agentic_repair,
    should_attempt_agentic_branch_repair,
)
from sparkweave.services.rag_support.query_planner import RagQueryPlan, RagSubQuery


def _plan() -> RagQueryPlan:
    return RagQueryPlan(
        original_query="Compare alpha and beta",
        mode="force",
        enabled=True,
        reason="test",
        subqueries=[
            RagSubQuery("alpha concept", "Find alpha"),
            RagSubQuery("beta concept", "Find beta"),
        ],
    )


def test_activity_plan_summarizes_branch_statuses() -> None:
    activity = build_agentic_activity_plan(
        plan=_plan(),
        results=[
            {
                "query": "alpha concept",
                "success": True,
                "content": "alpha concept evidence",
                "sources": [{"content": "alpha concept evidence"}],
            },
            {
                "query": "beta concept",
                "success": False,
                "error": "backend timeout",
                "sources": [],
            },
        ],
        source_count=1,
    )

    assert activity["step_count"] == 2
    assert activity["failed_steps"] == 1
    assert activity["weak_steps"] == 0
    assert activity["steps"][0]["status"] == "ok"
    assert activity["steps"][1]["status"] == "failed"


def test_quality_report_and_explanation_keep_user_contract_stable() -> None:
    plan = _plan()
    results = [
        {
            "query": "alpha concept",
            "success": True,
            "content": "alpha concept evidence",
            "sources": [{"content": "alpha concept evidence", "score": 0.91}],
        },
        {
            "query": "beta concept",
            "success": True,
            "content": "",
            "sources": [],
        },
    ]
    merged = {
        "content": "alpha concept evidence",
        "sources": [{"content": "alpha concept evidence", "score": 0.91}],
        "source_count": 1,
        "query_plan": plan.trace(),
        "agentic_rag": True,
        "agentic_activity_plan": build_agentic_activity_plan(
            plan=plan,
            results=results,
            source_count=1,
        ),
        "subquery_results": [
            {"query": "alpha concept", "source_count": 1, "content_chars": 22},
            {"query": "beta concept", "source_count": 0, "content_chars": 0},
        ],
    }

    quality = build_agentic_quality_report(
        plan=plan,
        results=results,
        merged=merged,
        options={
            "min_sources": 1,
            "min_coverage_ratio": 1.0,
            "min_relevant_coverage_ratio": 1.0,
            "min_context_chars": 1,
        },
    )
    attach_agentic_quality(merged, quality)
    explanation = build_agentic_explanation(result=merged, quality=quality)

    assert quality["status"] == "weak"
    assert quality["reasons"] == ["low_subquery_coverage", "low_relevance_coverage"]
    assert merged["agentic_activity_plan"]["weak_steps"] == 1
    assert merged["subquery_results"][1]["relevant"] is False
    assert explanation["decision"] == "weak_multi_query"
    assert explanation["user_facing"]["title"] == "Found evidence that needs review"
    assert explanation["quality_checks"][1]["status"] == "failed"


def test_merge_agentic_results_deduplicates_and_traces_context_pack() -> None:
    plan = _plan()
    merged = merge_agentic_results(
        query="Compare alpha and beta",
        provider="milvus",
        plan=plan,
        results=[
            {
                "query": "alpha concept",
                "subquery_index": 1,
                "subquery_purpose": "Find alpha",
                "success": True,
                "content": "alpha evidence " * 20,
                "sources": [{"source": "doc.md", "title": "A", "content": "same"}],
            },
            {
                "query": "beta concept",
                "subquery_index": 2,
                "subquery_purpose": "Find beta",
                "success": True,
                "content": "beta evidence " * 20,
                "sources": [{"source": "doc.md", "title": "A", "content": "same"}],
            },
        ],
        merge_options={"max_context_chars": 120, "max_sources": 4},
    )

    assert merged["provider"] == "milvus"
    assert merged["source_count"] == 1
    assert merged["agentic_context_pack"]["truncated"] is True
    assert merged["agentic_activity_plan"]["step_count"] == 2
    assert merged["subquery_results"][0]["purpose"] == "Find alpha"


def test_fallback_search_kwargs_preserves_explicit_values() -> None:
    kwargs = fallback_search_kwargs({"top_k": 2, "retrieval_mode": "vector"})

    assert kwargs["top_k"] == 2
    assert kwargs["retrieval_mode"] == "vector"
    assert kwargs["candidate_top_k"] == 18
    assert kwargs["reranker"] == "keyword"


def test_repair_policy_targets_weak_branches_and_accepts_better_candidate() -> None:
    quality = {
        "reasons": ["low_relevance_coverage"],
        "covered_subqueries": 1,
        "subquery_relevance": [{"relevant": True}, {"relevant": False}],
    }
    results = [
        {"content": "alpha evidence", "sources": [{"content": "alpha evidence"}]},
        {"content": "", "sources": []},
    ]

    assert should_attempt_agentic_branch_repair(quality) is True
    assert agentic_branch_repair_indexes(quality, results) == [1]
    assert should_accept_agentic_repair(
        original={"content": "", "sources": []},
        candidate={"content": "beta evidence", "sources": [{"content": "beta evidence"}]},
        original_report={"relevant": False, "score": 0},
        candidate_report={"relevant": True, "score": 0.8},
    ) is True
    assert should_accept_agentic_repair(
        original={"content": "beta evidence", "sources": [{"content": "beta evidence"}]},
        candidate={"content": "", "sources": []},
        original_report={"relevant": True, "score": 0.8},
        candidate_report={"relevant": False, "score": 0},
    ) is False
