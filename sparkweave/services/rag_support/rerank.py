"""Lightweight reranking utilities for RAG retrieval results.

The module intentionally avoids importing LlamaIndex types. A reranker only
needs node text, metadata and optional initial scores, so keeping this generic
makes it safe to unit-test on Windows environments where some vector runtime
imports can be fragile.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any


@dataclass(frozen=True)
class RerankConfig:
    provider: str = "none"
    top_n: int | None = None
    lexical_weight: float = 0.35
    vector_weight: float = 0.65


@dataclass(frozen=True)
class RerankTrace:
    provider: str
    applied: bool
    input_count: int
    output_count: int
    top_n: int | None


def normalize_reranker(provider: Any) -> str:
    raw = str(provider or "").strip().lower().replace("-", "_")
    if raw in {"", "none", "off", "false", "0", "disabled"}:
        return "none"
    if raw in {"keyword", "lexical", "simple", "bm25_lite"}:
        return "keyword"
    return raw


def rerank_nodes(query: str, nodes: list[Any], config: RerankConfig | None = None) -> tuple[list[Any], RerankTrace]:
    cfg = config or RerankConfig()
    provider = normalize_reranker(cfg.provider)
    input_count = len(nodes)
    if provider == "none" or input_count <= 1:
        output = _limit_nodes(nodes, cfg.top_n if provider != "none" else None)
        return output, RerankTrace(provider=provider, applied=False, input_count=input_count, output_count=len(output), top_n=None)
    if provider != "keyword":
        output = _limit_nodes(nodes, cfg.top_n)
        return output, RerankTrace(provider=provider, applied=False, input_count=input_count, output_count=len(output), top_n=cfg.top_n)

    query_tokens = _tokenize(query)
    if not query_tokens:
        output = _limit_nodes(nodes, cfg.top_n)
        return output, RerankTrace(provider=provider, applied=False, input_count=input_count, output_count=len(output), top_n=cfg.top_n)

    scored: list[tuple[float, int, Any]] = []
    denominator = max(input_count - 1, 1)
    for index, node in enumerate(nodes):
        vector_rank_score = 1 - (index / denominator)
        lexical_score = _lexical_score(query_tokens, _tokenize(_node_text(node)))
        combined = cfg.vector_weight * vector_rank_score + cfg.lexical_weight * lexical_score
        scored.append((combined, index, node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    output = [item[2] for item in scored]
    output = _limit_nodes(output, cfg.top_n)
    return output, RerankTrace(provider=provider, applied=True, input_count=input_count, output_count=len(output), top_n=cfg.top_n)


def _limit_nodes(nodes: list[Any], top_n: int | None) -> list[Any]:
    if top_n is None or top_n <= 0:
        return list(nodes)
    return list(nodes[:top_n])


def _node_text(node: Any) -> str:
    inner = getattr(node, "node", node)
    text = getattr(inner, "text", None)
    if text:
        return str(text)
    get_content = getattr(inner, "get_content", None)
    if callable(get_content):
        try:
            return str(get_content() or "")
        except Exception:
            return ""
    return str(inner or "")


def tokenize_text(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z_][a-z0-9_:<>.#-]{1,}|[0-9]+(?:\.[0-9]+)?", lowered))
    for cjk_run in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(cjk_run) == 1:
            tokens.add(cjk_run)
            continue
        tokens.update(cjk_run[i : i + 2] for i in range(len(cjk_run) - 1))
        if len(cjk_run) <= 8:
            tokens.add(cjk_run)
    return {token for token in tokens if token.strip()}


def _lexical_score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = len(query_tokens & doc_tokens)
    if overlap == 0:
        return 0.0
    return overlap / math.sqrt(len(query_tokens) * len(doc_tokens))


_tokenize = tokenize_text


__all__ = [
    "RerankConfig",
    "RerankTrace",
    "normalize_reranker",
    "rerank_nodes",
    "tokenize_text",
]
