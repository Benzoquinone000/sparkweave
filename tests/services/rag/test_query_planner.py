from __future__ import annotations

import pytest

import sparkweave.services.rag_support.query_planner as planner_module
from sparkweave.services.rag_support.query_planner import (
    normalize_agentic_mode,
    plan_rag_queries,
    should_use_agentic_rag,
)


def test_normalize_agentic_mode() -> None:
    assert normalize_agentic_mode("on") == "force"
    assert normalize_agentic_mode("gated-agentic") == "auto"
    assert normalize_agentic_mode("false") == "off"
    assert normalize_agentic_mode("unknown") == "off"


def test_should_use_agentic_rag_keeps_simple_query_fast() -> None:
    enabled, reason = should_use_agentic_rag("什么是 DPO？", mode="auto")

    assert enabled is False
    assert reason == "simple_query_fast_path"


def test_should_use_agentic_rag_detects_complex_query() -> None:
    enabled, reason = should_use_agentic_rag("对比 DPO 和 PPO 的区别，同时总结适用场景", mode="auto")

    assert enabled is True
    assert reason.startswith("multi_intent_terms")


@pytest.mark.asyncio
async def test_plan_rag_queries_off_returns_disabled_plan() -> None:
    plan = await plan_rag_queries("对比 DPO 和 PPO", mode="off")

    assert plan.enabled is False
    assert plan.subqueries == []
    assert plan.reason == "agentic_rag_disabled"


@pytest.mark.asyncio
async def test_plan_rag_queries_uses_llm_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_llm_plan(query: str, *, max_subqueries: int):
        assert query == "对比 DPO 和 PPO"
        assert max_subqueries == 2
        return [
            planner_module.RagSubQuery("DPO 核心思想", "concept"),
            planner_module.RagSubQuery("PPO 与 KL 约束", "contrast"),
        ]

    monkeypatch.setattr(planner_module, "_llm_plan_subqueries", _fake_llm_plan)

    plan = await plan_rag_queries("对比 DPO 和 PPO", mode="force", max_subqueries=2, timeout_seconds=1)

    assert plan.enabled is True
    assert plan.reason == "forced_by_caller"
    assert [item.query for item in plan.subqueries] == ["DPO 核心思想", "PPO 与 KL 约束"]


@pytest.mark.asyncio
async def test_plan_rag_queries_falls_back_to_rule_split(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fail(query: str, *, max_subqueries: int):
        del query, max_subqueries
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(planner_module, "_llm_plan_subqueries", _fail)

    plan = await plan_rag_queries(
        "解释梯度下降？同时说明学习率如何影响收敛？",
        mode="force",
        max_subqueries=3,
        timeout_seconds=1,
    )

    assert plan.enabled is True
    assert "fallback_rule_split" in plan.reason
    assert [item.query for item in plan.subqueries] == ["解释梯度下降", "说明学习率如何影响收敛"]
