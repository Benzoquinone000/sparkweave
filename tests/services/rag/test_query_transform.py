from __future__ import annotations

import pytest

import sparkweave.services.rag_support.query_transform as query_transform_module
from sparkweave.services.rag_support.query_transform import (
    normalize_query_transform,
    transform_rag_query,
)


def test_normalize_query_transform() -> None:
    assert normalize_query_transform(None) == "none"
    assert normalize_query_transform("off") == "none"
    assert normalize_query_transform("hypothetical-document") == "hyde"
    assert normalize_query_transform("unknown") == "none"


@pytest.mark.asyncio
async def test_transform_rag_query_none_returns_original() -> None:
    result = await transform_rag_query("什么是梯度下降？", strategy="none")

    assert result.retrieval_query == "什么是梯度下降？"
    assert result.strategy == "none"
    assert result.applied is False


@pytest.mark.asyncio
async def test_transform_rag_query_hyde_appends_hypothetical_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_complete(query: str, *, max_chars: int) -> str:
        assert query == "解释 DPO"
        assert max_chars == 32
        return "答案：DPO 使用偏好对直接优化策略。"

    monkeypatch.setattr(query_transform_module, "_complete_hypothetical_answer", _fake_complete)

    result = await transform_rag_query("解释 DPO", strategy="hyde", max_chars=32, timeout_seconds=1)

    assert result.strategy == "hyde"
    assert result.applied is True
    assert result.hypothetical_answer == "DPO 使用偏好对直接优化策略。"
    assert "解释 DPO" in result.retrieval_query
    assert "检索假设答案" in result.retrieval_query


@pytest.mark.asyncio
async def test_transform_rag_query_hyde_falls_back_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fail(query: str, *, max_chars: int) -> str:
        del query, max_chars
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(query_transform_module, "_complete_hypothetical_answer", _fail)

    result = await transform_rag_query("解释 DPO", strategy="hyde", timeout_seconds=1)

    assert result.retrieval_query == "解释 DPO"
    assert result.strategy == "hyde"
    assert result.applied is False
    assert "llm unavailable" in result.error
