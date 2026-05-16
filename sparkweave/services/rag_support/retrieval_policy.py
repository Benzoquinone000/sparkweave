"""Adaptive retrieval policy for education-oriented RAG.

The policy layer keeps strategy selection deterministic and explainable. It is
not a replacement for a retriever; it only fills safe defaults when callers do
not explicitly provide retrieval parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


@dataclass(frozen=True)
class RetrievalPolicy:
    """One explainable retrieval-policy decision."""

    profile: str
    reason: str
    params: dict[str, Any]

    def trace(self) -> dict[str, Any]:
        return {
            "retrieval_profile": self.profile,
            "retrieval_policy_reason": self.reason,
            "retrieval_policy_params": dict(self.params),
        }


def normalize_retrieval_profile(value: Any, default: str = "auto") -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "balanced": "concept",
        "default": "auto",
        "dense": "fast",
        "direct": "fast",
        "exact_match": "exact",
        "keyword": "exact",
        "learning_path": "guide",
        "plan": "guide",
        "precise": "exact",
        "semantic": "concept",
    }
    raw = aliases.get(raw, raw)
    if raw in {"auto", "fast", "concept", "exact", "code", "formula", "guide", "broad", "off", "none"}:
        return raw
    return default


def infer_retrieval_profile(query: str) -> tuple[str, str]:
    """Infer a retrieval profile from the user query."""
    text = str(query or "").strip()
    lowered = text.lower()
    if not text:
        return "fast", "empty_query"

    if _looks_like_formula_query(text, lowered):
        return "formula", "formula_or_derivation_terms"
    if _looks_like_code_query(text, lowered):
        return "code", "code_or_identifier_terms"
    if _looks_like_guide_query(text, lowered):
        return "guide", "learning_path_or_weakness_terms"
    if _looks_like_exact_query(text, lowered):
        return "exact", "exact_source_or_keyword_terms"
    if _looks_like_broad_query(text, lowered):
        return "broad", "multi_hop_or_comparison_terms"
    return "concept", "conceptual_question"


def build_retrieval_policy(
    query: str,
    *,
    profile: str | None = None,
    explicit_params: dict[str, Any] | None = None,
) -> RetrievalPolicy:
    """Build defaults for retrieval without overwriting explicit caller params."""
    selected = normalize_retrieval_profile(profile or _env("RAG_RETRIEVAL_PROFILE", "auto"), "auto")
    if selected in {"off", "none"}:
        return RetrievalPolicy(profile="off", reason="retrieval_policy_disabled", params={})

    inferred_profile, reason = infer_retrieval_profile(query)
    active_profile = inferred_profile if selected == "auto" else selected
    defaults = _profile_defaults(active_profile)
    explicit = explicit_params or {}
    params = {key: value for key, value in defaults.items() if key not in explicit or explicit.get(key) in {None, ""}}
    return RetrievalPolicy(profile=active_profile, reason=reason if selected == "auto" else "forced_profile", params=params)


def _profile_defaults(profile: str) -> dict[str, Any]:
    defaults: dict[str, dict[str, Any]] = {
        "fast": {
            "retrieval_mode": "dense",
            "top_k": 5,
            "candidate_top_k": 5,
            "reranker": "none",
        },
        "concept": {
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "candidate_top_k": 16,
            "reranker": "keyword",
            "rerank_top_n": 5,
            "hybrid_ranker": "weighted",
            "dense_weight": 1.0,
            "sparse_weight": 0.55,
        },
        "exact": {
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "candidate_top_k": 20,
            "reranker": "keyword",
            "rerank_top_n": 5,
            "hybrid_ranker": "weighted",
            "dense_weight": 0.75,
            "sparse_weight": 1.1,
        },
        "code": {
            "retrieval_mode": "hybrid",
            "top_k": 6,
            "candidate_top_k": 24,
            "reranker": "keyword",
            "rerank_top_n": 6,
            "hybrid_ranker": "weighted",
            "dense_weight": 0.65,
            "sparse_weight": 1.25,
        },
        "formula": {
            "retrieval_mode": "hybrid",
            "top_k": 6,
            "candidate_top_k": 24,
            "reranker": "keyword",
            "rerank_top_n": 6,
            "hybrid_ranker": "weighted",
            "dense_weight": 0.7,
            "sparse_weight": 1.2,
        },
        "guide": {
            "retrieval_mode": "hybrid",
            "top_k": 6,
            "candidate_top_k": 24,
            "reranker": "keyword",
            "rerank_top_n": 6,
            "query_transform": "hyde",
            "agentic_rag": "auto",
            "hybrid_ranker": "weighted",
            "dense_weight": 1.0,
            "sparse_weight": 0.75,
        },
        "broad": {
            "retrieval_mode": "hybrid",
            "top_k": 8,
            "candidate_top_k": 28,
            "reranker": "keyword",
            "rerank_top_n": 8,
            "query_transform": "hyde",
            "agentic_rag": "auto",
            "hybrid_ranker": "weighted",
            "dense_weight": 1.0,
            "sparse_weight": 0.8,
        },
    }
    return dict(defaults.get(profile, defaults["concept"]))


def _looks_like_code_query(text: str, lowered: str) -> bool:
    if re.search(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\s*(?:\(|::|->|=)", text):
        return True
    code_terms = [
        ".py",
        ".cpp",
        ".java",
        "api",
        "bug",
        "class",
        "error",
        "function",
        "import",
        "python",
        "typescript",
        "代码",
        "函数",
        "报错",
        "类",
        "接口",
    ]
    return any(term in lowered or term in text for term in code_terms)


def _looks_like_formula_query(text: str, lowered: str) -> bool:
    if re.search(r"(\\frac|\\sum|\\lim|\\nabla|[=<>]\s*[-+*/]?\w|\b[a-z]\^\d)", text):
        return True
    formula_terms = ["公式", "推导", "证明", "梯度", "损失函数", "导数", "矩阵", "概率", "latex"]
    return any(term in lowered or term in text for term in formula_terms)


def _looks_like_guide_query(text: str, lowered: str) -> bool:
    guide_terms = [
        "路线",
        "计划",
        "导学",
        "推荐",
        "先学",
        "怎么学",
        "学不会",
        "薄弱",
        "补基",
        "复习",
        "learning path",
    ]
    return any(term in lowered or term in text for term in guide_terms)


def _looks_like_exact_query(text: str, lowered: str) -> bool:
    if re.search(r"[\"'“”《》`].{2,}?[\"'“”《》`]", text):
        return True
    exact_terms = ["第几章", "哪一节", "在哪", "原文", "文件", "标题", "定义是", "source", "chapter"]
    return any(term in lowered or term in text for term in exact_terms)


def _looks_like_broad_query(text: str, lowered: str) -> bool:
    if len(text) >= 80:
        return True
    broad_terms = [
        "对比",
        "比较",
        "区别",
        "联系",
        "同时",
        "结合",
        "总结",
        "为什么",
        "如何",
        "compare",
        "summarize",
    ]
    hits = sum(1 for term in broad_terms if term in lowered or term in text)
    return hits >= 2


__all__ = [
    "RetrievalPolicy",
    "build_retrieval_policy",
    "infer_retrieval_profile",
    "normalize_retrieval_profile",
]
