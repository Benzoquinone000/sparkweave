"""
Tests for RAG safety in the deep-research pipeline.

These tests pin two contracts:

* The deprecated ``DE-all`` placeholder fallback is gone — when no
  knowledge base is configured, ``ResearchPipeline._call_tool``
  short-circuits with a structured ``status: skipped`` JSON instead of
  invoking the RAG service against a non-existent KB.
* ``DecomposeAgent`` defensively disables RAG when no ``kb_name`` is
  available, even when the runtime config still says
  ``enable_rag: True``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sparkweave.agents.research import DecomposeAgent, ResearchPipeline
from sparkweave.core.contracts import StreamBus, UnifiedContext


def _minimal_pipeline_config() -> dict[str, Any]:
    return {
        "system": {"language": "en", "verbose": False},
        "planning": {
            "rephrase": {"enabled": False, "max_iterations": 1},
            "decompose": {
                "mode": "manual",
                "initial_subtopics": 1,
                "auto_max_subtopics": 1,
            },
        },
        "researching": {
            "max_iterations": 1,
            "iteration_mode": "fixed",
            "execution_mode": "series",
            "max_parallel_topics": 1,
            "new_topic_min_score": 0.9,
            "enable_rag": True,
            "enable_web_search": False,
            "enable_paper_search": False,
            "enable_run_code": False,
            "enabled_tools": ["rag"],
            "tool_timeout": 5,
            "tool_max_retries": 0,
        },
        "reporting": {
            "min_section_length": 10,
            "report_single_pass_threshold": 1,
            "enable_citation_list": False,
            "enable_inline_citations": False,
            "deduplicate_enabled": False,
            "style": "report",
            "mode": "report",
            "depth": "quick",
        },
        "queue": {"max_length": 2},
        "rag": {},
        "intent": {
            "mode": "report",
            "depth": "quick",
            "sources": [],
            "manual_subtopics": None,
            "manual_max_iterations": None,
            "confirmed_outline": None,
        },
        "tools": {"web_search": {"enabled": False}},
        "paths": {},
    }


def _build_bare_pipeline(config: dict[str, Any]) -> ResearchPipeline:
    """Build a ``ResearchPipeline`` skeleton with just the attributes
    ``_call_tool`` reads — avoids the heavy agent-initialisation tree."""
    pipeline = ResearchPipeline.__new__(ResearchPipeline)
    pipeline.config = config
    pipeline.research_id = "test"
    pipeline.cache_dir = "/tmp/test"  # type: ignore[assignment]
    pipeline.trace_callback = None
    pipeline._stage_events = {"planning": [], "reporting": [], "researching": []}
    return pipeline


@pytest.mark.asyncio
async def test_research_pipeline_call_tool_rag_without_kb_returns_skipped_json() -> None:
    """The DE-all fallback is gone: ``rag`` without a ``kb_name`` must be a no-op."""
    pipeline = _build_bare_pipeline(_minimal_pipeline_config())

    raw = await pipeline._call_tool("rag", "What is convolution?")
    payload = json.loads(raw)

    assert payload["status"] == "skipped"
    assert payload["reason"] == "no_kb_selected"
    assert payload["tool"] == "rag"


@pytest.mark.asyncio
async def test_research_pipeline_call_tool_unknown_tool_returns_failed_not_rag() -> None:
    """Unknown tool types must not silently fall through to RAG anymore."""
    pipeline = _build_bare_pipeline(_minimal_pipeline_config())

    raw = await pipeline._call_tool("not_a_real_tool", "anything")
    payload = json.loads(raw)

    assert payload["status"] == "failed"
    assert payload["reason"] == "unknown_tool"
    assert payload["tool"] == "not_a_real_tool"


def test_decompose_agent_disables_rag_when_no_kb_name() -> None:
    """Defensive guard at the agent layer: no ``kb_name`` ⇒ ``enable_rag = False``."""
    config = _minimal_pipeline_config()
    config["rag"] = {"kb_name": None}
    config["researching"]["enable_rag"] = True

    agent = DecomposeAgent(config=config, api_key="sk-test", kb_name=None)

    assert agent.kb_name is None
    assert agent.enable_rag is False


def test_decompose_agent_keeps_rag_when_kb_name_provided_via_kwarg() -> None:
    config = _minimal_pipeline_config()
    config["rag"] = {}
    config["researching"]["enable_rag"] = True

    agent = DecomposeAgent(config=config, api_key="sk-test", kb_name="my-kb")

    assert agent.kb_name == "my-kb"
    assert agent.enable_rag is True


def test_decompose_agent_no_longer_falls_back_to_ai_textbook() -> None:
    """The hardcoded ``ai_textbook`` fallback was removed."""
    config = _minimal_pipeline_config()
    config["rag"] = {}
    config["researching"]["enable_rag"] = True

    agent = DecomposeAgent(config=config, api_key="sk-test", kb_name=None)

    assert agent.kb_name is None  # NOT "ai_textbook"
    assert agent.enable_rag is False


@pytest.mark.asyncio
async def test_research_pipeline_run_delegates_to_ng_graph(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = _minimal_pipeline_config()
    config["system"]["output_base_dir"] = str(tmp_path / "cache")
    config["system"]["reports_dir"] = str(tmp_path / "reports")
    progress_events: list[dict[str, Any]] = []
    captured_contexts: list[UnifiedContext] = []

    class _FakeDeepResearchGraph:
        async def run(self, context: UnifiedContext, stream: StreamBus) -> dict[str, Any]:
            captured_contexts.append(context)
            await stream.progress("researching", source="deep_research", stage="researching")
            await stream.content("# Report", source="deep_research", stage="reporting")
            await stream.result(
                {
                    "response": "# Report",
                    "metadata": {"runtime": "langgraph", "mode": "report"},
                },
                source="deep_research",
            )
            return {"final_answer": "# Report", "artifacts": {"research": {"mode": "report"}}}

    monkeypatch.setattr(
        "sparkweave.agents.research.research_pipeline.DeepResearchGraph",
        _FakeDeepResearchGraph,
    )

    pipeline = ResearchPipeline(
        config=config,
        api_key="sk-test",
        base_url="https://example.test",
        research_id="research_unit",
        kb_name="kb-main",
        progress_callback=progress_events.append,
    )

    result = await pipeline.run("Convolution")

    assert result["research_id"] == "research_unit"
    assert result["report"] == "# Report"
    assert Path(result["final_report_path"]).read_text(encoding="utf-8") == "# Report"
    assert result["metadata"]["runtime"] == "langgraph"
    assert captured_contexts[0].active_capability == "deep_research"
    assert captured_contexts[0].knowledge_bases == ["kb-main"]
    assert captured_contexts[0].enabled_tools == ["rag"]
    assert captured_contexts[0].config_overrides["topic"] == "Convolution"
    assert any(event["type"] == "progress" for event in progress_events)


@pytest.mark.asyncio
async def test_decompose_agent_process_without_rag_returns_legacy_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _minimal_pipeline_config()
    config["rag"] = {}
    agent = DecomposeAgent(config=config, api_key="sk-test", kb_name=None)

    async def _fake_call_llm(**kwargs: Any) -> str:
        assert kwargs["response_format"] == {"type": "json_object"}
        assert "Main Topic: convolution" in kwargs["user_prompt"]
        return json.dumps(
            {
                "sub_topics": [
                    {"title": "Definition", "overview": "Define convolution."},
                    {"title": "Examples", "overview": "Work through examples."},
                ]
            }
        )

    monkeypatch.setattr(agent, "call_llm", _fake_call_llm)

    result = await agent.process("convolution", num_subtopics=2)

    assert result["main_topic"] == "convolution"
    assert result["sub_queries"] == []
    assert result["rag_context"] == ""
    assert result["mode"] == "manual_no_rag"
    assert result["total_subtopics"] == 2
    assert result["sub_topics"][0] == {
        "title": "Definition",
        "overview": "Define convolution.",
    }


@pytest.mark.asyncio
async def test_decompose_agent_process_with_rag_uses_retrieved_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _minimal_pipeline_config()
    agent = DecomposeAgent(config=config, api_key="sk-test", kb_name="signals")
    seen_prompts: list[str] = []

    async def _fake_retrieve(topic: str) -> tuple[str, str]:
        return f"retrieved background for {topic}", topic

    async def _fake_call_llm(**kwargs: Any) -> str:
        seen_prompts.append(kwargs["user_prompt"])
        return json.dumps(
            {"sub_topics": [{"title": "Theory", "overview": "Use retrieved context."}]}
        )

    monkeypatch.setattr(agent, "_retrieve_background_knowledge", _fake_retrieve)
    monkeypatch.setattr(agent, "call_llm", _fake_call_llm)

    result = await agent.process("Fourier transform", num_subtopics=3, mode="auto")

    assert result["sub_queries"] == ["Fourier transform"]
    assert result["rag_context"] == "retrieved background for Fourier transform"
    assert result["mode"] == "auto"
    assert result["total_subtopics"] == 1
    assert any("retrieved background" in prompt for prompt in seen_prompts)

