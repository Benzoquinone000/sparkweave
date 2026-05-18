"""Lightweight reranking utilities for RAG retrieval results.

The module intentionally avoids importing LlamaIndex types. A reranker only
needs node text, metadata and optional initial scores, so keeping this generic
makes it safe to unit-test on Windows environments where some vector runtime
imports can be fragile.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import re
from typing import Any
import urllib.error
import urllib.request


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
    error: str = ""


def normalize_reranker(provider: Any) -> str:
    raw = str(provider or "").strip().lower().replace("-", "_")
    if raw in {"", "none", "off", "false", "0", "disabled"}:
        return "none"
    if raw in {"keyword", "lexical", "simple", "bm25_lite"}:
        return "keyword"
    if raw in {"cross_encoder", "crossencoder", "external", "provider"}:
        return "cross_encoder"
    if raw in {"jina", "jina_rerank", "jina_reranker"}:
        return "jina"
    if raw in {"cohere", "cohere_rerank", "cohere_reranker"}:
        return "cohere"
    return raw


def rerank_nodes(query: str, nodes: list[Any], config: RerankConfig | None = None) -> tuple[list[Any], RerankTrace]:
    cfg = config or RerankConfig()
    provider = normalize_reranker(cfg.provider)
    input_count = len(nodes)
    if provider == "none" or input_count <= 1:
        output = _limit_nodes(nodes, cfg.top_n if provider != "none" else None)
        return output, RerankTrace(provider=provider, applied=False, input_count=input_count, output_count=len(output), top_n=None)
    if provider in {"cross_encoder", "jina", "cohere"}:
        output, error = _external_rerank(query, nodes, provider=provider, top_n=cfg.top_n)
        if output is not None:
            return output, RerankTrace(provider=provider, applied=True, input_count=input_count, output_count=len(output), top_n=cfg.top_n)
        keyword_output, keyword_trace = _keyword_rerank(query, nodes, cfg)
        if keyword_trace.applied:
            return keyword_output, RerankTrace(
                provider=f"{provider}:keyword_fallback",
                applied=True,
                input_count=input_count,
                output_count=len(keyword_output),
                top_n=cfg.top_n,
                error=error,
            )
        return keyword_output, RerankTrace(
            provider=provider,
            applied=False,
            input_count=input_count,
            output_count=len(keyword_output),
            top_n=cfg.top_n,
            error=error,
        )
    if provider != "keyword":
        output = _limit_nodes(nodes, cfg.top_n)
        return output, RerankTrace(provider=provider, applied=False, input_count=input_count, output_count=len(output), top_n=cfg.top_n)

    return _keyword_rerank(query, nodes, cfg)


def _keyword_rerank(query: str, nodes: list[Any], cfg: RerankConfig) -> tuple[list[Any], RerankTrace]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        output = _limit_nodes(nodes, cfg.top_n)
        return output, RerankTrace(provider="keyword", applied=False, input_count=len(nodes), output_count=len(output), top_n=cfg.top_n)

    scored: list[tuple[float, int, Any]] = []
    input_count = len(nodes)
    denominator = max(input_count - 1, 1)
    for index, node in enumerate(nodes):
        vector_rank_score = 1 - (index / denominator)
        lexical_score = _lexical_score(query_tokens, _tokenize(_node_text(node)))
        combined = cfg.vector_weight * vector_rank_score + cfg.lexical_weight * lexical_score
        scored.append((combined, index, node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    output = [item[2] for item in scored]
    output = _limit_nodes(output, cfg.top_n)
    return output, RerankTrace(provider="keyword", applied=True, input_count=input_count, output_count=len(output), top_n=cfg.top_n)


def _external_rerank(
    query: str,
    nodes: list[Any],
    *,
    provider: str,
    top_n: int | None,
) -> tuple[list[Any] | None, str]:
    resolved = _resolve_external_provider(provider)
    if not resolved:
        return None, "external_reranker_not_configured"
    provider_name, url, api_key, model = resolved
    documents = [_node_text(node) for node in nodes]
    if not any(documents):
        return None, "empty_documents"

    payload = _external_payload(provider_name, query=query, documents=documents, model=model, top_n=top_n or len(nodes))
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        timeout = _env_float("RAG_RERANKER_TIMEOUT_SECONDS", 8.0)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return None, f"http_{exc.code}:{body[:160]}"
    except Exception as exc:
        return None, str(exc)

    order = _external_order(data)
    if not order:
        return None, "empty_rerank_response"
    ranked = [nodes[index] for index in order if 0 <= index < len(nodes)]
    if not ranked:
        return None, "invalid_rerank_indexes"
    return _limit_nodes(ranked, top_n), ""


def _resolve_external_provider(provider: str) -> tuple[str, str, str, str] | None:
    selected = provider
    if selected == "cross_encoder":
        selected = _env("RAG_CROSS_ENCODER_PROVIDER", _env("RAG_RERANKER_PROVIDER", "jina")).strip().lower()
    if selected == "jina":
        api_key = _env("RAG_RERANKER_API_KEY", _env("JINA_API_KEY", ""))
        custom_base_url = _env("RAG_RERANKER_BASE_URL", "")
        if not api_key and not custom_base_url:
            return None
        base_url = (custom_base_url or "https://api.jina.ai/v1").rstrip("/")
        model = _env("RAG_RERANKER_MODEL", "jina-reranker-v2-base-multilingual")
        return "jina", _endpoint(base_url, "rerank"), api_key, model
    if selected == "cohere":
        api_key = _env("RAG_RERANKER_API_KEY", _env("COHERE_API_KEY", ""))
        custom_base_url = _env("RAG_RERANKER_BASE_URL", "")
        if not api_key and not custom_base_url:
            return None
        base_url = (custom_base_url or "https://api.cohere.com").rstrip("/")
        model = _env("RAG_RERANKER_MODEL", "rerank-v3.5")
        return "cohere", _endpoint(base_url, "v2/rerank"), api_key, model
    return None


def _external_payload(provider: str, *, query: str, documents: list[str], model: str, top_n: int) -> dict[str, Any]:
    if provider == "cohere":
        return {"model": model, "query": query, "documents": documents, "top_n": top_n}
    return {"model": model, "query": query, "documents": documents, "top_n": top_n}


def _external_order(data: dict[str, Any]) -> list[int]:
    results = data.get("results")
    if not isinstance(results, list):
        results = data.get("data") if isinstance(data.get("data"), list) else []
    ordered: list[tuple[float, int]] = []
    for rank, item in enumerate(results):
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        raw_score = item.get("relevance_score", item.get("score"))
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = float(len(results) - rank)
        ordered.append((score, index))
    ordered.sort(key=lambda item: (-item[0], item[1]))
    return [index for _score, index in ordered]


def _endpoint(base_url: str, suffix: str) -> str:
    if base_url.rstrip("/").endswith(suffix):
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/{suffix}"


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _env_float(name: str, default: float) -> float:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


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
