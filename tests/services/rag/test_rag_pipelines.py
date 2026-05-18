"""RAGService end-to-end behavior tests (with a fake pipeline)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.services.rag_support.query_planner import RagQueryPlan, RagSubQuery
from sparkweave.services.rag_support.query_transform import QueryTransformResult
import sparkweave.services.rag_support.service as rag_service_module
from sparkweave.services.rag_support.service import RAGService


class _FakePipeline:
    """Minimal pipeline stub that records calls and returns canned results."""

    def __init__(self, search_result: dict[str, Any] | None = None) -> None:
        self.calls: list[dict] = []
        self.search_result = search_result or {
            "answer": "fake answer",
            "sources": [{"id": 1}],
            "provider": "lightrag",  # deliberately wrong; service must overwrite
        }

    async def initialize(self, kb_name: str, file_paths, **kwargs) -> bool:
        self.calls.append({"op": "initialize", "kb_name": kb_name, "files": list(file_paths)})
        return True

    async def search(self, query: str, kb_name: str, **kwargs) -> dict[str, Any]:
        self.calls.append({"op": "search", "query": query, "kb_name": kb_name, "kwargs": kwargs})
        return dict(self.search_result)

    async def delete(self, kb_name: str) -> bool:
        self.calls.append({"op": "delete", "kb_name": kb_name})
        return True


@pytest.fixture
def fake_service(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[RAGService, _FakePipeline]:
    monkeypatch.setattr(rag_service_module, "_env_value", lambda _name, default="": default)
    pipeline = _FakePipeline()
    service = RAGService(kb_base_dir=str(tmp_path))
    service._pipeline = pipeline  # type: ignore[attr-defined]
    return service, pipeline


def test_provider_argument_is_silently_ignored(tmp_path) -> None:
    """Constructor accepts provider and normalizes it to a supported backend."""
    service = RAGService(kb_base_dir=str(tmp_path), provider="lightrag")
    assert service.provider == "milvus"

    local_service = RAGService(kb_base_dir=str(tmp_path), provider="llamaindex")
    assert local_service.provider == "llamaindex"


def test_default_provider_uses_config_store_before_process_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("RAG_PROVIDER", "milvus")
    monkeypatch.setattr(
        rag_service_module,
        "_env_value",
        lambda name, default="": "llamaindex" if name == "RAG_PROVIDER" else default,
    )

    service = RAGService(kb_base_dir=str(tmp_path))

    assert service.provider == "llamaindex"
    assert RAGService.get_current_provider() == "llamaindex"


@pytest.mark.asyncio
async def test_search_uses_kb_provider_when_constructor_has_no_explicit_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "kb_config.json").write_text(
        json.dumps({
            "knowledge_bases": {
                "demo": {
                    "path": "demo",
                    "rag_provider": "llamaindex",
                    "status": "ready",
                }
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        rag_service_module,
        "_env_value",
        lambda name, default="": "milvus" if name == "RAG_PROVIDER" else default,
    )
    calls: list[tuple[str, str | None]] = []
    pipelines = {
        "milvus": _FakePipeline({"answer": "milvus", "sources": []}),
        "llamaindex": _FakePipeline({"answer": "local", "sources": []}),
    }

    def _fake_get_pipeline(name: str, kb_base_dir: str | None = None):
        calls.append((name, kb_base_dir))
        return pipelines[name]

    monkeypatch.setattr(rag_service_module, "get_pipeline", _fake_get_pipeline)

    service = RAGService(kb_base_dir=str(tmp_path))
    result = await service.search(query="hello", kb_name="demo")

    assert calls == [("llamaindex", str(tmp_path))]
    assert pipelines["llamaindex"].calls[-1]["op"] == "search"
    assert result["provider"] == "llamaindex"
    assert result["answer"] == "local"


@pytest.mark.asyncio
async def test_explicit_provider_wins_over_kb_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "kb_config.json").write_text(
        json.dumps({
            "knowledge_bases": {
                "demo": {
                    "path": "demo",
                    "rag_provider": "llamaindex",
                    "status": "ready",
                }
            }
        }),
        encoding="utf-8",
    )
    calls: list[str] = []

    def _fake_get_pipeline(name: str, kb_base_dir: str | None = None):
        del kb_base_dir
        calls.append(name)
        return _FakePipeline({"answer": name, "sources": []})

    monkeypatch.setattr(rag_service_module, "get_pipeline", _fake_get_pipeline)

    service = RAGService(kb_base_dir=str(tmp_path), provider="milvus")
    result = await service.search(query="hello", kb_name="demo")

    assert calls == ["milvus"]
    assert result["provider"] == "milvus"


@pytest.mark.asyncio
async def test_search_force_overwrites_provider_in_result(fake_service) -> None:
    """Even if the underlying pipeline lies about its provider, RAGService normalizes."""
    service, pipeline = fake_service
    pipeline.search_result = {"answer": "x", "provider": "raganything"}

    result = await service.search(query="hello", kb_name="kb")
    assert result["provider"] == "milvus"


@pytest.mark.asyncio
async def test_search_drops_mode_kwarg_before_calling_pipeline(fake_service) -> None:
    """The legacy ``mode`` kwarg is normalized before reaching the pipeline."""
    service, pipeline = fake_service
    await service.search(query="hi", kb_name="kb", mode="hybrid", top_k=5)

    last = pipeline.calls[-1]
    assert last["op"] == "search"
    assert "mode" not in last["kwargs"]
    assert last["kwargs"].get("retrieval_mode") == "hybrid"
    assert last["kwargs"].get("top_k") == 5


@pytest.mark.asyncio
async def test_search_applies_adaptive_retrieval_policy(fake_service) -> None:
    service, pipeline = fake_service

    result = await service.search(query="DataLoader 报错应该看哪个代码文件？", kb_name="kb")

    last = pipeline.calls[-1]
    assert last["kwargs"].get("retrieval_mode") == "hybrid"
    assert last["kwargs"].get("reranker") == "keyword"
    assert last["kwargs"].get("sparse_weight") > last["kwargs"].get("dense_weight")
    assert result["retrieval_profile"] == "code"


@pytest.mark.asyncio
async def test_search_explicit_top_k_caps_policy_rerank_top_n(fake_service) -> None:
    service, pipeline = fake_service

    await service.search(
        query="compare two concepts",
        kb_name="kb",
        retrieval_profile="broad",
        top_k=2,
        candidate_top_k=8,
        reranker="keyword",
    )

    last = pipeline.calls[-1]
    assert last["kwargs"].get("top_k") == 2
    assert last["kwargs"].get("rerank_top_n") == 2


@pytest.mark.asyncio
async def test_search_aliases_answer_and_content(fake_service) -> None:
    """Pipelines that only return ``content`` should still expose ``answer`` and vice versa."""
    service, pipeline = fake_service

    pipeline.search_result = {"content": "only-content", "provider": "x"}
    result = await service.search(query="q", kb_name="kb")
    assert result["answer"] == "only-content"
    assert result["content"] == "only-content"
    assert result["query"] == "q"

    pipeline.search_result = {"answer": "only-answer", "provider": "x"}
    result = await service.search(query="q2", kb_name="kb")
    assert result["content"] == "only-answer"
    assert result["answer"] == "only-answer"


@pytest.mark.asyncio
async def test_search_applies_query_transform(fake_service, monkeypatch: pytest.MonkeyPatch) -> None:
    service, pipeline = fake_service

    async def _fake_transform(query: str, **_kwargs):
        return QueryTransformResult(
            original_query=query,
            retrieval_query="expanded retrieval query",
            strategy="hyde",
            applied=True,
            hypothetical_answer="hypothetical answer",
        )

    monkeypatch.setattr(rag_service_module, "transform_rag_query", _fake_transform)

    result = await service.search(query="raw question", kb_name="kb", query_transform="hyde")

    last = pipeline.calls[-1]
    assert last["query"] == "expanded retrieval query"
    assert result["query"] == "raw question"
    assert result["retrieval_query"] == "expanded retrieval query"
    assert result["query_transform"] == "hyde"
    assert result["query_transform_applied"] is True
    assert result["hypothetical_answer"] == "hypothetical answer"


@pytest.mark.asyncio
async def test_search_agentic_rag_plans_and_merges_subqueries(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("what is gradient descent", "concept"),
                RagSubQuery("gradient descent learning rate", "hyperparameter"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        del kb_name, kwargs
        return {
            "answer": f"context for {query}",
            "content": f"context for {query}",
            "sources": [{"title": query, "source": f"{query}.md", "content": "same evidence"}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="explain and compare gradient descent", kb_name="kb", agentic_rag="force")

    assert result["agentic_rag"] is True
    assert result["query"] == "explain and compare gradient descent"
    assert result["query_plan"]["agentic_enabled"] is True
    assert len(result["subquery_results"]) == 2
    assert result["agentic_activity_plan"]["step_count"] == 2
    assert result["agentic_activity_plan"]["merged_source_count"] == 2
    assert result["agentic_evidence_groups"][0]["purpose"] == "concept"
    assert "what is gradient descent" in result["content"]
    assert "gradient descent learning rate" in result["content"]
    assert len(result["sources"]) == 2
    assert result["sources"][0]["subquery_purpose"] == "concept"


@pytest.mark.asyncio
async def test_search_agentic_rag_respects_merged_context_budget(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("alpha topic", "concept"),
                RagSubQuery("beta topic", "detail"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        del kb_name, kwargs
        text = (f"{query} evidence. " * 80).strip()
        return {
            "answer": text,
            "content": text,
            "sources": [{"title": query, "source": f"{query}.md", "content": text[:160]}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(
        query="complex query",
        kb_name="kb",
        agentic_rag="force",
        max_context_chars=220,
        agentic_min_context_chars=0,
    )

    assert result["agentic_rag"] is True
    assert len(result["content"]) <= 220
    assert result["agentic_context_pack"]["max_context_chars"] == 220
    assert result["agentic_context_pack"]["truncated"] is True
    assert result["agentic_context_pack"]["included_subqueries"] == 2
    assert result["agentic_quality"]["content_chars"] == len(result["content"])


@pytest.mark.asyncio
async def test_search_agentic_rag_falls_back_when_no_sources(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    call_count = 0

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[RagSubQuery("missing branch", "probe")],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        nonlocal call_count
        del kb_name, kwargs
        call_count += 1
        if query == "missing branch":
            return {"answer": "", "content": "", "sources": [], "success": True}
        return {
            "answer": "fallback evidence",
            "content": "fallback evidence",
            "sources": [{"title": "fallback", "source": "fallback.md", "content": "fallback evidence"}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="complex query", kb_name="kb", agentic_rag="force")

    assert call_count == 2
    assert result["agentic_rag"] is False
    assert result["agentic_fallback"] is True
    assert result["failed_query_plan"]["agentic_enabled"] is True
    assert result["agentic_activity_plan"]["merged_source_count"] == 0
    assert result["agentic_context_pack"]["context_chars"] == 0
    assert result["source_count"] == 1
    assert "no_sources" in result["agentic_quality"]["reasons"]
    assert result["agentic_explanation"]["user_facing"]["fallback_used"] is True
    assert result["agentic_explanation"]["user_facing"]["fallback_reason"] == "No usable sources were found in the planned branches."
    assert result["agentic_explanation"]["user_facing"]["next_action"] == "Review the fallback sources before relying on the answer."


@pytest.mark.asyncio
async def test_search_agentic_rag_repairs_low_subquery_coverage(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    calls: list[str] = []

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("covered branch", "concept"),
                RagSubQuery("missing branch one", "detail"),
                RagSubQuery("missing branch two", "detail"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        del kb_name, kwargs
        calls.append(query)
        if query == "covered branch":
            return {
                "answer": "covered evidence " * 20,
                "content": "covered evidence " * 20,
                "sources": [{"title": "covered", "source": "covered.md", "content": "covered evidence"}],
                "success": True,
            }
        if query == "complex query":
            return {
                "answer": "fallback evidence " * 20,
                "content": "fallback evidence " * 20,
                "sources": [{"title": "fallback", "source": "fallback.md", "content": "fallback evidence"}],
                "success": True,
            }
        return {"answer": "", "content": "", "sources": [], "success": True}

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="complex query", kb_name="kb", agentic_rag="force")

    assert calls == [
        "covered branch",
        "missing branch one",
        "missing branch two",
        "missing branch one",
        "missing branch two",
        "complex query",
    ]
    assert result["agentic_rag"] is False
    assert result["agentic_fallback"] is True
    assert result["agentic_quality"]["covered_subqueries"] == 1
    assert result["agentic_quality"]["total_subqueries"] == 3
    assert "low_subquery_coverage" in result["agentic_quality"]["reasons"]
    assert result["agentic_activity_plan"]["quality_status"] == "weak"
    assert result["source_count"] == 1


@pytest.mark.asyncio
async def test_search_agentic_rag_repairs_low_relevance_coverage(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    calls: list[str] = []

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("alpha topic", "concept"),
                RagSubQuery("beta topic", "detail"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        del kb_name, kwargs
        calls.append(query)
        if query == "alpha topic":
            text = "alpha topic evidence " * 20
            title = "alpha topic"
            source = "alpha.md"
        elif query == "beta topic":
            text = "unrelated weather evidence " * 20
            title = "weather"
            source = "weather.md"
        else:
            text = "alpha topic and beta topic fallback evidence " * 20
            title = "fallback"
            source = "fallback.md"
        return {
            "answer": text,
            "content": text,
            "sources": [{"title": title, "source": source, "content": text[:120]}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="complex query", kb_name="kb", agentic_rag="force")

    assert calls == ["alpha topic", "beta topic", "beta topic", "complex query"]
    assert result["agentic_rag"] is False
    assert result["agentic_fallback"] is True
    assert "low_relevance_coverage" in result["agentic_quality"]["reasons"]
    assert result["agentic_quality"]["covered_subqueries"] == 2
    assert result["agentic_quality"]["relevant_subqueries"] == 1
    assert result["subquery_results"][1]["relevant"] is False


@pytest.mark.asyncio
async def test_search_agentic_rag_keeps_repaired_subquery_evidence(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    calls: list[str] = []
    beta_calls = 0

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("alpha topic", "concept"),
                RagSubQuery("beta topic", "detail"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        nonlocal beta_calls
        del kb_name, kwargs
        calls.append(query)
        if query == "beta topic":
            beta_calls += 1
            if beta_calls == 1:
                return {
                    "answer": "unrelated weather evidence " * 20,
                    "content": "unrelated weather evidence " * 20,
                    "sources": [{"title": "weather", "source": "weather.md", "content": "unrelated weather"}],
                    "success": True,
                }
        text = f"{query} evidence " * 20
        return {
            "answer": text,
            "content": text,
            "sources": [{"title": query, "source": f"{query}.md", "content": text[:120]}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="complex query", kb_name="kb", agentic_rag="force")

    assert calls == ["alpha topic", "beta topic", "beta topic"]
    assert result["agentic_rag"] is True
    assert result["agentic_repaired"] is True
    assert result["agentic_repair"]["strategy"] == "subquery_repair"
    assert result["agentic_repair"]["accepted_branches"] == 1
    assert result["agentic_quality"]["needs_fallback"] is False
    assert result["subquery_results"][1]["relevant"] is True
    assert "beta topic evidence" in result["content"]


@pytest.mark.asyncio
async def test_search_agentic_rag_keeps_sufficient_evidence(
    fake_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    calls: list[str] = []

    async def _fake_plan(query: str, **_kwargs):
        return RagQueryPlan(
            original_query=query,
            mode="force",
            enabled=True,
            reason="test",
            subqueries=[
                RagSubQuery("concept branch", "concept"),
                RagSubQuery("detail branch", "detail"),
            ],
        )

    async def _identity_transform(query: str, **_kwargs):
        return QueryTransformResult(original_query=query, retrieval_query=query, strategy="none")

    async def _search(query: str, kb_name: str, **kwargs):
        del kb_name, kwargs
        calls.append(query)
        return {
            "answer": f"{query} evidence " * 20,
            "content": f"{query} evidence " * 20,
            "sources": [{"title": query, "source": f"{query}.md", "content": f"{query} evidence"}],
            "success": True,
        }

    monkeypatch.setattr(rag_service_module, "plan_rag_queries", _fake_plan)
    monkeypatch.setattr(rag_service_module, "transform_rag_query", _identity_transform)
    pipeline.search = _search  # type: ignore[method-assign]

    result = await service.search(query="complex query", kb_name="kb", agentic_rag="force")

    assert calls == ["concept branch", "detail branch"]
    assert result["agentic_rag"] is True
    assert "agentic_fallback" not in result
    assert result["agentic_quality"]["needs_fallback"] is False
    assert result["agentic_quality"]["status"] == "sufficient"
    assert result["agentic_activity_plan"]["quality_status"] == "sufficient"
    assert result["agentic_activity_plan"]["coverage_ratio"] == 1.0
    assert result["agentic_explanation"]["decision"] == "multi_query"
    assert result["agentic_explanation"]["plan"]["subquery_count"] == 2
    assert result["agentic_explanation"]["evidence"]["quality_status"] == "sufficient"
    assert result["agentic_explanation"]["user_facing"]["title"] == "Used multi-step retrieval"
    assert result["agentic_explanation"]["user_facing"]["trigger_reason"] == "Multi-step retrieval was selected for this request."
    assert result["agentic_explanation"]["user_facing"]["next_action"] == "Open the cited sources to verify the important claims."
    assert [item["code"] for item in result["agentic_explanation"]["quality_checks"]] == [
        "source_count",
        "subquery_coverage",
        "relevance_coverage",
        "context_chars",
        "score",
    ]
    assert result["agentic_explanation"]["steps"][0]["action"] == "use_evidence"


@pytest.mark.asyncio
async def test_smart_retrieve_aggregates_passages_with_query_hints(
    fake_service, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    pipeline.search_result = {"answer": "PASSAGE", "content": "PASSAGE", "provider": "x"}

    async def _fake_aggregate(_self, _ctx, passages):
        return "AGG:" + "|".join(passages)

    monkeypatch.setattr(RAGService, "_aggregate", _fake_aggregate, raising=True)

    out = await service.smart_retrieve(
        context="anything",
        kb_name="kb",
        query_hints=["q1", "q2"],
    )
    assert out["answer"].startswith("AGG:")
    assert out["answer"].count("PASSAGE") == 2
    assert len(out["sources"]) == 2
    queries = [c["query"] for c in pipeline.calls if c["op"] == "search"]
    assert queries == ["q1", "q2"]


@pytest.mark.asyncio
async def test_smart_retrieve_returns_empty_when_no_passages(
    fake_service, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, pipeline = fake_service
    pipeline.search_result = {"answer": "", "content": "", "provider": "x"}

    out = await service.smart_retrieve(
        context="anything",
        kb_name="kb",
        query_hints=["q"],
    )
    assert out == {"answer": "", "sources": []}


@pytest.mark.asyncio
async def test_delete_removes_kb_directory_when_pipeline_lacks_delete(tmp_path) -> None:
    """Fallback path: delete the KB dir directly if the pipeline does not implement delete."""
    kb_dir = tmp_path / "demo"
    (kb_dir / "raw").mkdir(parents=True)
    (kb_dir / "raw" / "f.txt").write_text("hi")

    class _NoDeletePipeline:
        async def initialize(self, *a, **k):
            return True

        async def search(self, *a, **k):
            return {}

    service = RAGService(kb_base_dir=str(tmp_path))
    service._pipeline = _NoDeletePipeline()  # type: ignore[attr-defined]

    assert await service.delete(kb_name="demo") is True
    assert not kb_dir.exists()

