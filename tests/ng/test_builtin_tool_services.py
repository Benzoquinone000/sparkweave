from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sparkweave.services.code_execution import run_python_code
import sparkweave.services.reasoning as reasoning_service
import sparkweave.services.vision as vision_service
from sparkweave.tools.builtin import (
    BrainstormTool,
    CodeExecutionTool,
    GeoGebraAnalysisTool,
    PaperSearchToolWrapper,
    RAGTool,
    ReasonTool,
    WebSearchTool,
)


@pytest.mark.asyncio
async def test_rag_tool_uses_ng_rag_service(monkeypatch):
    calls: list[dict] = []

    async def fake_rag_search(**kwargs):
        calls.append(kwargs)
        return {"answer": "RAG answer", "content": "", "provider": "fake"}

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)

    result = await RAGTool().execute(query="what", kb_name="kb", mode="hybrid")

    assert result.content == "RAG answer"
    assert result.metadata["provider"] == "fake"
    assert calls == [
        {
            "query": "what",
            "kb_name": "kb",
            "event_sink": None,
            "mode": "hybrid",
        }
    ]


@pytest.mark.asyncio
async def test_web_search_tool_uses_ng_search_service(monkeypatch):
    calls: list[dict] = []

    async def fake_web_search(**kwargs):
        calls.append(kwargs)
        return {
            "answer": "Search answer",
            "citations": [{"url": "https://example.test", "title": "Example"}],
        }

    monkeypatch.setattr("sparkweave.services.search.web_search", fake_web_search)

    result = await WebSearchTool().execute(query="langgraph", output_dir="out", verbose=True)

    assert result.content == "Search answer"
    assert result.sources == [
        {"type": "web", "url": "https://example.test", "title": "Example"}
    ]
    assert calls == [{"query": "langgraph", "output_dir": "out", "verbose": True}]


@pytest.mark.asyncio
async def test_code_execution_tool_uses_ng_code_execution_service(monkeypatch):
    calls: list[dict] = []

    async def fake_run_python_code(**kwargs):
        calls.append(kwargs)
        return {"stdout": "2\n", "stderr": "", "exit_code": 0, "artifacts": []}

    monkeypatch.setattr(
        "sparkweave.services.code_execution.run_python_code",
        fake_run_python_code,
    )

    result = await CodeExecutionTool().execute(code="print(1+1)", timeout=2)

    assert result.content == "2"
    assert result.success is True
    assert result.metadata["code"] == "print(1+1)"
    assert calls[0]["code"] == "print(1+1)"
    assert calls[0]["timeout"] == 2


@pytest.mark.asyncio
async def test_run_python_code_executes_in_ng_workspace(tmp_path):
    result = await run_python_code(
        code="print('ng-code')",
        timeout=5,
        workspace_dir=tmp_path / "runs",
    )

    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "ng-code"
    assert Path(result["source_file"]).is_file()
    assert Path(result["output_log"]).is_file()


@pytest.mark.asyncio
async def test_paper_search_tool_uses_ng_paper_service(monkeypatch):
    async def fake_search_arxiv_papers(**_kwargs):
        return [
            {
                "title": "Agentic RAG",
                "year": "2025",
                "authors": ["A. Researcher"],
                "arxiv_id": "2501.00001",
                "url": "https://arxiv.org/abs/2501.00001",
                "abstract": "A paper about agentic RAG.",
            }
        ]

    monkeypatch.setattr(
        "sparkweave.services.papers.search_arxiv_papers",
        fake_search_arxiv_papers,
    )

    result = await PaperSearchToolWrapper().execute(query="agentic rag")

    assert "**Agentic RAG**" in result.content
    assert result.sources[0]["arxiv_id"] == "2501.00001"
    assert result.metadata["provider"] == "arxiv"


def test_arxiv_search_tool_helpers_are_ng_owned():
    from sparkweave.services.papers import ArxivSearchTool

    tool = ArxivSearchTool()

    assert type(tool).__module__ == "sparkweave.services.papers"
    assert tool.format_paper_citation({"authors": ["Ada Lovelace"], "year": 1843}) == (
        "(Lovelace, 1843)"
    )
    assert tool.extract_arxiv_id_from_url("https://arxiv.org/abs/2501.00001") == "2501.00001"


@pytest.mark.asyncio
async def test_reasoning_services_use_ng_llm_stream(monkeypatch):
    calls: list[dict] = []

    async def fake_stream(**kwargs):
        calls.append(kwargs)
        yield "reasoned"

    monkeypatch.setattr(
        reasoning_service,
        "get_llm_config",
        lambda: SimpleNamespace(
            model="demo",
            api_key="key",
            base_url="https://example.test",
        ),
    )
    monkeypatch.setattr(
        reasoning_service,
        "get_token_limit_kwargs",
        lambda _model, max_tokens: {"max_tokens": max_tokens},
    )
    monkeypatch.setattr(reasoning_service, "llm_stream", fake_stream)

    brainstorm_result = await reasoning_service.brainstorm(topic="topic")
    reason_result = await reasoning_service.reason(
        query="query",
        context="context",
        max_tokens=123,
    )

    assert brainstorm_result == {"topic": "topic", "answer": "reasoned", "model": "demo"}
    assert reason_result == {"query": "query", "answer": "reasoned", "model": "demo"}
    assert calls[0]["max_tokens"] == 2048
    assert calls[0]["temperature"] == 0.8
    assert calls[1]["max_tokens"] == 123
    assert calls[1]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_geogebra_tool_uses_ng_vision_service(monkeypatch):
    async def fake_analyze_geogebra_image(**kwargs):
        assert kwargs["question"] == "Find angle A"
        assert kwargs["image_base64"] == "abc"
        return {
            "ggb_block": "```ggb\nA=(0,0)\n```",
            "result": {
                "has_image": True,
                "final_ggb_commands": ["A=(0,0)"],
                "analysis_output": {
                    "constraints": [{"kind": "point"}],
                    "geometric_relations": [{"description": "A is a point"}],
                },
                "bbox_output": {"elements": [{}]},
                "reflection_output": {"issues_found": []},
            },
        }

    monkeypatch.setattr(
        "sparkweave.services.vision.analyze_geogebra_image",
        fake_analyze_geogebra_image,
    )

    result = await GeoGebraAnalysisTool().execute(
        question="Find angle A",
        image_base64="abc",
    )

    assert "```ggb" in result.content
    assert result.metadata["commands_count"] == 1
    assert result.metadata["constraints_count"] == 1


@pytest.mark.asyncio
async def test_vision_solver_agent_uses_ng_llm_stream(monkeypatch):
    responses = iter(
        [
            '{"elements":[{"type":"point","label":"A"}]}',
            '{"image_reference_detected":false,"constraints":[{"kind":"point"}],"geometric_relations":[{"description":"A is a point"}]}',
            '{"commands":[{"sequence":1,"command":"A=(0,0)","description":"point A"}]}',
            '{"issues_found":[],"corrected_commands":[{"sequence":1,"command":"A=(0,0)","description":"point A"}]}',
        ]
    )
    calls: list[dict] = []

    async def fake_stream(**kwargs):
        calls.append(kwargs)
        yield next(responses)

    monkeypatch.setattr(
        vision_service,
        "get_llm_config",
        lambda: SimpleNamespace(
            model="vision-demo",
            api_key="key",
            base_url="https://example.test/v1",
            api_version=None,
            binding="openai",
        ),
    )
    monkeypatch.setattr(vision_service, "llm_stream", fake_stream)

    result = await vision_service.analyze_geogebra_image(
        question="Locate point A",
        image_base64="data:image/png;base64,abc",
        language="en",
    )

    assert type(vision_service.VisionSolverAgent()).__module__ == "sparkweave.services.vision"
    assert result["result"]["final_ggb_commands"][0]["command"] == "A=(0,0)"
    assert "```ggbscript" in result["ggb_block"]
    assert len(calls) == 4
    assert calls[0]["model"] == "vision-demo"
    assert calls[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image")


@pytest.mark.asyncio
async def test_brainstorm_and_reason_tools_use_ng_reasoning_service(monkeypatch):
    async def fake_brainstorm(**kwargs):
        assert kwargs["topic"] == "topic"
        return {"answer": "ideas"}

    async def fake_reason(**kwargs):
        assert kwargs["query"] == "query"
        return {"answer": "reasoned"}

    monkeypatch.setattr("sparkweave.services.reasoning.brainstorm", fake_brainstorm)
    monkeypatch.setattr("sparkweave.services.reasoning.reason", fake_reason)

    brainstorm_result = await BrainstormTool().execute(topic="topic")
    reason_result = await ReasonTool().execute(query="query")

    assert brainstorm_result.content == "ideas"
    assert reason_result.content == "reasoned"


