"""End-to-end readiness checks for one knowledge base.

The regular knowledge routes expose documents, vector rows, diagnostics, and
retrieval tests separately. This module composes those signals into one
user-facing report so the UI and acceptance scripts can answer a simpler
question: can this knowledge base be used for grounded answers right now?
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.concurrency import run_in_threadpool

from sparkweave.api.routers.knowledge_models import RagSearchTestRequest
from sparkweave.api.routers.knowledge_rag_ops import run_rag_search_test

DocumentLister = Callable[..., Awaitable[dict[str, Any]]]
VectorLister = Callable[..., Awaitable[dict[str, Any]]]
ProviderValidator = Callable[[str | None], str]
DiagnosticFn = Callable[..., dict[str, Any]]
RagServiceFactory = Callable[..., Any]


async def build_knowledge_acceptance_report(
    *,
    manager: Any,
    kb_name: str,
    kb_entry: dict[str, Any],
    default_provider: str,
    validate_provider: ProviderValidator,
    rag_service_cls: RagServiceFactory,
    diagnose_rag: DiagnosticFn,
    list_documents_for_kb: DocumentLister,
    list_vectors_for_kb: VectorLister,
    query: str | None = None,
    run_search: bool = True,
    check_connection: bool = False,
    sample_limit: int = 3,
) -> dict[str, Any]:
    """Build a compact, product-facing RAG acceptance report."""

    provider = validate_provider(kb_entry.get("rag_provider") or default_provider)
    limit = max(1, min(int(sample_limit or 3), 8))
    documents = await list_documents_for_kb(
        manager=manager,
        kb_name=kb_name,
        kb_entry=kb_entry,
        include_vectors=True,
        validate_provider=validate_provider,
        default_provider=default_provider,
    )
    vectors = await list_vectors_for_kb(
        manager=manager,
        kb_name=kb_name,
        kb_entry=kb_entry,
        document_id=None,
        limit=limit,
        offset=0,
        validate_provider=validate_provider,
        default_provider=default_provider,
    )
    diagnostic = await run_in_threadpool(
        diagnose_rag,
        kb_base_dir=manager.base_dir,
        kb_name=kb_name,
        check_connection=check_connection,
    )

    document_items = documents.get("documents") if isinstance(documents.get("documents"), list) else []
    vector_chunks = vectors.get("chunks") if isinstance(vectors.get("chunks"), list) else []
    document_count = _coerce_int(documents.get("document_count"), len(document_items))
    vector_count = _resolve_vector_count(documents, vectors, diagnostic, vector_chunks)
    vectors_available = bool(documents.get("vectors_available") or vectors.get("available"))
    vector_error = str(documents.get("vector_error") or vectors.get("error") or "").strip()
    sample_chunks = _sample_vector_chunks(vector_chunks, document_items, limit=limit)
    retrieval_query = _choose_acceptance_query(query, sample_chunks, document_items)

    retrieval = await _run_acceptance_retrieval(
        kb_name=kb_name,
        kb_entry=kb_entry,
        manager=manager,
        provider=provider,
        default_provider=default_provider,
        validate_provider=validate_provider,
        rag_service_cls=rag_service_cls,
        query=retrieval_query,
        enabled=bool(run_search and retrieval_query and _has_positive_count(vector_count)),
    )
    checks = _build_acceptance_checks(
        document_count=document_count,
        vector_count=vector_count,
        vectors_available=vectors_available,
        vector_error=vector_error,
        diagnostic=diagnostic,
        retrieval=retrieval,
        run_search=run_search,
    )
    status = _resolve_acceptance_status(
        document_count=document_count,
        vector_count=vector_count,
        diagnostic=diagnostic,
        retrieval=retrieval,
        checks=checks,
        run_search=run_search,
    )

    return {
        "kb_name": kb_name,
        "provider": provider,
        "status": status,
        "summary": _status_summary(status),
        "document_count": document_count,
        "vector_count": vector_count,
        "vectors_available": vectors_available,
        "vector_error": vector_error,
        "sample_chunks": sample_chunks,
        "retrieval": retrieval,
        "diagnostic": diagnostic,
        "checks": checks,
        "next_actions": _next_actions_for_status(status, checks),
    }


async def _run_acceptance_retrieval(
    *,
    kb_name: str,
    kb_entry: dict[str, Any],
    manager: Any,
    provider: str,
    default_provider: str,
    validate_provider: ProviderValidator,
    rag_service_cls: RagServiceFactory,
    query: str,
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {
            "attempted": False,
            "success": False,
            "query": query,
            "provider": provider,
            "source_count": 0,
            "content_chars": 0,
            "sources": [],
            "error": "",
        }

    request = RagSearchTestRequest(
        query=query,
        provider=provider,
        retrieval_profile="auto",
        retrieval_mode="hybrid",
        top_k=5,
        candidate_top_k=15,
        reranker="keyword",
        agentic_rag="auto",
        max_context_chars=5000,
    )
    try:
        result = await run_rag_search_test(
            kb_name=kb_name,
            request=request,
            manager=manager,
            kb_entry=kb_entry,
            default_provider=default_provider,
            validate_provider=validate_provider,
            rag_service_cls=rag_service_cls,
        )
    except Exception as exc:
        return {
            "attempted": True,
            "success": False,
            "query": query,
            "provider": provider,
            "source_count": 0,
            "content_chars": 0,
            "sources": [],
            "error": str(exc),
        }

    content = str(result.get("content") or result.get("answer") or "")
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    source_count = _coerce_int(result.get("source_count"), len(sources))
    success = bool(result.get("success", True)) and source_count > 0 and bool(content.strip())
    return {
        "attempted": True,
        "success": success,
        "query": query,
        "provider": result.get("provider") or provider,
        "source_count": source_count,
        "content_chars": len(content),
        "sources": [_compact_source(source) for source in sources[:5] if isinstance(source, dict)],
        "error": str(result.get("error") or ""),
        "error_code": result.get("error_code"),
        "readiness": result.get("readiness"),
    }


def _build_acceptance_checks(
    *,
    document_count: int,
    vector_count: int | None,
    vectors_available: bool,
    vector_error: str,
    diagnostic: dict[str, Any],
    retrieval: dict[str, Any],
    run_search: bool,
) -> list[dict[str, Any]]:
    checks = [
        {
            "id": "documents",
            "label": "资料文件",
            "status": "ok" if document_count > 0 else "failed",
            "detail": f"已保存 {document_count} 个文件。" if document_count > 0 else "还没有可用于学习问答的资料。",
            "action": "" if document_count > 0 else "上传课程资料、笔记或论文。",
        },
        {
            "id": "vectors",
            "label": "引用片段",
            "status": "ok" if _has_positive_count(vector_count) else "failed",
            "detail": (
                f"向量库中可见 {vector_count} 条片段。"
                if _has_positive_count(vector_count)
                else vector_error or "尚未看到可检索的向量片段。"
            ),
            "action": "" if _has_positive_count(vector_count) else "重新整理资料，确认解析后的文档不为空。",
        },
        _diagnostic_check(diagnostic),
    ]
    if not vectors_available and vector_error:
        checks[1]["status"] = "failed"

    if run_search:
        checks.append(
            {
                "id": "retrieval",
                "label": "试问检索",
                "status": "ok" if retrieval.get("success") else ("skipped" if not retrieval.get("attempted") else "failed"),
                "detail": _retrieval_detail(retrieval),
                "action": "" if retrieval.get("success") else "用真实问题重试，或重新整理资料后再验证。",
            }
        )
    return checks


def _diagnostic_check(diagnostic: dict[str, Any]) -> dict[str, Any]:
    status = str(diagnostic.get("status") or "unknown").lower()
    readiness = diagnostic.get("readiness") if isinstance(diagnostic.get("readiness"), dict) else {}
    if status in {"ok", "configured"}:
        check_status = "ok"
    elif status == "warning":
        check_status = "warning"
    elif status == "error":
        check_status = "failed"
    else:
        check_status = "warning"
    return {
        "id": "diagnostic",
        "label": "运行环境",
        "status": check_status,
        "detail": str(readiness.get("summary") or diagnostic.get("message") or "已完成 RAG 运行环境检查。"),
        "action": "" if check_status == "ok" else str(readiness.get("primary_action") or "检查向量库和 Embedding 配置。"),
    }


def _resolve_acceptance_status(
    *,
    document_count: int,
    vector_count: int | None,
    diagnostic: dict[str, Any],
    retrieval: dict[str, Any],
    checks: list[dict[str, Any]],
    run_search: bool,
) -> str:
    if document_count <= 0:
        return "empty"
    if str(diagnostic.get("status") or "").lower() == "error":
        return "failed"
    if not _has_positive_count(vector_count):
        return "failed"
    if run_search and retrieval.get("attempted") and not retrieval.get("success"):
        return "failed"
    if any(item.get("status") == "warning" for item in checks):
        return "degraded"
    return "ready"


def _status_summary(status: str) -> str:
    if status == "ready":
        return "资料库已经有可检索片段，并且试问能找到来源。"
    if status == "degraded":
        return "资料库基本可用，但仍有配置或运行项需要关注。"
    if status == "empty":
        return "资料库还没有可用于学习问答的文件。"
    return "资料库暂时还不能稳定用于问答。"


def _next_actions_for_status(status: str, checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    if status == "ready":
        return [
            {"id": "ask", "label": "问资料", "detail": "进入聊天并带上当前资料库。"},
            {"id": "test", "label": "再试问", "detail": "用一个真实学习问题复查来源。"},
            {"id": "upload", "label": "继续上传", "detail": "补充新的课程资料。"},
        ]
    if status == "empty":
        return [
            {"id": "upload", "label": "上传资料", "detail": "先放入课程资料、笔记或论文。"},
            {"id": "folders", "label": "同步文件夹", "detail": "资料集中在本地目录时使用。"},
        ]
    failed_ids = {str(item.get("id")) for item in checks if item.get("status") == "failed"}
    actions = []
    if "vectors" in failed_ids:
        actions.append({"id": "reindex", "label": "重新整理资料", "detail": "重新解析文件并写入向量库。"})
    if "retrieval" in failed_ids:
        actions.append({"id": "test", "label": "打开试问", "detail": "查看检索返回和来源。"})
    if "diagnostic" in failed_ids:
        actions.append({"id": "diagnostics", "label": "检查连接", "detail": "检查向量库和模型配置。"})
    if not actions:
        actions.append({"id": "recovery", "label": "打开整理向导", "detail": "按步骤恢复资料库可用性。"})
    return actions


def _resolve_vector_count(
    documents: dict[str, Any],
    vectors: dict[str, Any],
    diagnostic: dict[str, Any],
    vector_chunks: list[Any],
) -> int | None:
    for value in (
        documents.get("vector_count"),
        vectors.get("total"),
        diagnostic.get("vector_row_count"),
        len(vector_chunks) if vector_chunks else None,
    ):
        parsed = _coerce_optional_int(value)
        if parsed is not None:
            return parsed
    return None


def _choose_acceptance_query(
    query: str | None,
    sample_chunks: list[dict[str, Any]],
    documents: list[Any],
) -> str:
    requested = str(query or "").strip()
    if requested:
        return requested[:500]
    for chunk in sample_chunks:
        text = str(chunk.get("text_preview") or "").strip()
        if len(text) >= 8:
            return text[:120]
    for document in documents:
        if not isinstance(document, dict):
            continue
        name = str(document.get("name") or "").strip()
        if name:
            return f"请根据资料概括 {name} 的核心内容"
    return "请概括这个资料库中的核心内容"


def _sample_vector_chunks(
    vector_chunks: list[Any],
    documents: list[Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for chunk in vector_chunks:
        if isinstance(chunk, dict):
            samples.append(_compact_chunk(chunk))
            if len(samples) >= limit:
                return samples
    for document in documents:
        if not isinstance(document, dict):
            continue
        for chunk in document.get("sample_chunks") or []:
            if isinstance(chunk, dict):
                samples.append(_compact_chunk(chunk))
                if len(samples) >= limit:
                    return samples
    return samples


def _compact_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    text = str(chunk.get("text_preview") or chunk.get("content") or "").strip()
    return {
        "id": chunk.get("id") or chunk.get("node_id"),
        "document": chunk.get("file_name") or chunk.get("source") or chunk.get("title"),
        "text_preview": text[:300],
        "score": chunk.get("score"),
    }


def _compact_source(source: dict[str, Any]) -> dict[str, Any]:
    content = str(source.get("content") or source.get("text") or "").strip()
    return {
        "title": source.get("title") or source.get("source") or source.get("file_name"),
        "chunk_id": source.get("chunk_id") or source.get("node_id") or source.get("id"),
        "score": source.get("score"),
        "content": content[:360],
    }


def _retrieval_detail(retrieval: dict[str, Any]) -> str:
    if retrieval.get("success"):
        return f"试问找到 {retrieval.get('source_count') or 0} 条来源，返回 {retrieval.get('content_chars') or 0} 个字符。"
    if not retrieval.get("attempted"):
        return "还没有足够的向量片段，暂未执行试问。"
    return str(retrieval.get("error") or "试问没有找到可引用来源。")


def _coerce_int(value: Any, default: int = 0) -> int:
    parsed = _coerce_optional_int(value)
    return parsed if parsed is not None else default


def _coerce_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_positive_count(value: int | None) -> bool:
    return value is not None and value > 0
