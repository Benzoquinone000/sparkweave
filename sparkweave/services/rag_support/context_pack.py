"""Context packing helpers for RAG retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from sparkweave.services.rag_support.rerank import tokenize_text


@dataclass(frozen=True)
class ContextPack:
    content: str
    sources: list[dict[str, Any]]
    trace: dict[str, Any]


def build_context_pack(
    *,
    query: str,
    nodes: list[Any],
    max_context_chars: int,
    score_threshold: float | None = None,
) -> ContextPack:
    query_tokens = tokenize_text(query)
    parts: list[str] = []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped_duplicate = 0
    skipped_threshold = 0
    skipped_budget = 0

    for index, node in enumerate(nodes):
        score = _node_score(node)
        if score_threshold is not None and score is not None and score < score_threshold:
            skipped_threshold += 1
            continue

        full_text = _node_text(node).strip()
        if not full_text:
            continue
        dedup_key = _dedup_key(node, full_text)
        if dedup_key in seen:
            skipped_duplicate += 1
            continue
        seen.add(dedup_key)

        used_chars = sum(len(part) for part in parts)
        if max_context_chars and used_chars >= max_context_chars:
            skipped_budget += 1
            break
        remaining = max_context_chars - used_chars if max_context_chars else len(full_text)
        context_text = full_text[:remaining] if remaining > 0 else ""
        if not context_text:
            skipped_budget += 1
            continue

        parts.append(context_text)
        sources.append(_source_payload(node, index, context_text, query_tokens, score))

    content = "\n\n".join(parts)
    return ContextPack(
        content=content,
        sources=sources,
        trace={
            "context_chars": len(content),
            "source_count": len(sources),
            "skipped_duplicate": skipped_duplicate,
            "skipped_threshold": skipped_threshold,
            "skipped_budget": skipped_budget,
        },
    )


def _source_payload(
    node: Any,
    index: int,
    content: str,
    query_tokens: set[str],
    score: float | None,
) -> dict[str, Any]:
    inner = getattr(node, "node", node)
    meta = getattr(inner, "metadata", None) or {}
    matched = sorted((query_tokens & tokenize_text(content)), key=lambda item: (len(item), item))[:8]
    title = meta.get("file_name", meta.get("title", f"Document {index + 1}"))
    source = meta.get("file_path", meta.get("file_name", ""))
    section_title = meta.get("section_title", "")
    return {
        "title": title,
        "content": content[:240],
        "source": source,
        "page": meta.get("page_label", meta.get("page", "")),
        "section_title": section_title,
        "chunk_id": getattr(inner, "node_id", None) or str(index),
        "score": round(score, 4) if score is not None else "",
        "matched_keywords": matched,
        "evidence_reason": _evidence_reason(matched, score, title),
        "context_chars": len(content),
    }


def _evidence_reason(matched: list[str], score: float | None, title: str) -> str:
    if matched:
        preview = "、".join(matched[:3])
        return f"命中问题关键词：{preview}。"
    if score is not None:
        return f"该片段在向量检索中与问题相似度较高，来自 {title}。"
    return f"该片段来自 {title}，可作为补充参考。"


def _node_score(node: Any) -> float | None:
    score = getattr(node, "score", None)
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


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


def _dedup_key(node: Any, text: str) -> str:
    inner = getattr(node, "node", node)
    node_id = getattr(inner, "node_id", None)
    if node_id:
        return str(node_id)
    normalized = " ".join(text.lower().split())
    return hashlib.sha1(normalized[:1000].encode("utf-8")).hexdigest()


__all__ = ["ContextPack", "build_context_pack"]
