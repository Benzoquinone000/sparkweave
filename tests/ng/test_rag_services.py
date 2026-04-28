from __future__ import annotations

import pytest

from sparkweave.services import rag as rag_service


@pytest.mark.asyncio
async def test_rag_search_uses_ng_rag_service(monkeypatch):
    calls: dict[str, object] = {}

    class FakeRAGService:
        def __init__(self, *, kb_base_dir=None, provider=None):
            calls["kb_base_dir"] = kb_base_dir
            calls["provider"] = provider

        async def search(self, **kwargs):
            calls["search"] = kwargs
            return {"answer": "grounded", "content": "grounded"}

    monkeypatch.setattr(rag_service, "RAGService", FakeRAGService)

    result = await rag_service.rag_search(
        query="what is rag",
        kb_name="demo",
        provider="llamaindex",
        kb_base_dir="kb-root",
        top_k=2,
    )

    assert result["answer"] == "grounded"
    assert calls["kb_base_dir"] == "kb-root"
    assert calls["provider"] == "llamaindex"
    assert calls["search"] == {
        "query": "what is rag",
        "kb_name": "demo",
        "event_sink": None,
        "top_k": 2,
    }

