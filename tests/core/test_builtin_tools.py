"""Tests for built-in tools and unified tool registry behavior."""

from __future__ import annotations

from typing import Any

import pytest

from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from sparkweave.tools.builtin import (
    BrainstormTool,
    CodeExecutionTool,
    GeoGebraAnalysisTool,
    PaperSearchToolWrapper,
    RAGTool,
    ReasonTool,
    WebSearchTool,
)
from sparkweave.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_brainstorm_tool_passes_llm_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_brainstorm(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"answer": "## 1. Test idea\n- Rationale: worth exploring"}

    monkeypatch.setattr("sparkweave.services.reasoning.brainstorm", fake_brainstorm)

    result = await BrainstormTool().execute(
        topic="agent-native tutoring",
        context="Focus on fast ideation",
        model="gpt-test",
    )

    assert "Test idea" in result.content
    assert captured["topic"] == "agent-native tutoring"
    assert captured["context"] == "Focus on fast ideation"
    assert captured["model"] == "gpt-test"


@pytest.mark.asyncio
async def test_rag_tool_forwards_query_and_extra_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_rag_search(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "answer": "grounded answer",
            "provider": "fake",
            "sources": [{"title": "Demo", "source": "demo.txt"}],
        }

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)

    result = await RAGTool().execute(
        query="what is a tensor",
        kb_name="demo-kb",
        mode="hybrid",
        only_need_context=True,
    )

    assert result.content == "grounded answer"
    assert captured["query"] == "what is a tensor"
    assert captured["kb_name"] == "demo-kb"
    assert captured["mode"] == "hybrid"
    assert captured["only_need_context"] is True
    assert result.sources == [{"title": "Demo", "source": "demo.txt"}]
    assert result.success is True


@pytest.mark.asyncio
async def test_rag_tool_skips_when_no_kb_selected() -> None:
    result = await RAGTool().execute(query="what is a tensor")

    assert result.success is False
    assert result.metadata["reason"] == "no_kb_selected"
    assert "no knowledge base" in result.content.lower()


@pytest.mark.asyncio
async def test_rag_tool_propagates_backend_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_rag_search(**_kwargs: Any) -> dict[str, Any]:
        return {
            "answer": "Search failed: boom",
            "content": "",
            "provider": "fake",
            "success": False,
            "error": "boom",
            "sources": [{"title": "Demo", "source": "demo.txt"}],
        }

    monkeypatch.setattr("sparkweave.services.rag.rag_search", fake_rag_search)

    result = await RAGTool().execute(query="what is a tensor", kb_name="demo-kb")

    assert result.success is False
    assert result.metadata["error"] == "boom"
    assert result.sources == [{"title": "Demo", "source": "demo.txt"}]


@pytest.mark.asyncio
async def test_web_search_tool_wraps_sync_function(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_web_search(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "answer": "web summary",
            "citations": [{"url": "https://example.com", "title": "Example"}],
        }

    monkeypatch.setattr("sparkweave.services.search.web_search", fake_web_search)

    result = await WebSearchTool().execute(query="latest benchmark", output_dir="/tmp/out")

    assert result.content == "web summary"
    assert captured["query"] == "latest benchmark"
    assert captured["output_dir"] == "/tmp/out"
    assert result.sources[0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_code_execution_tool_uses_direct_code_path(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_code(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["code"] == "print(2 + 2)"
        assert kwargs["timeout"] == 5
        assert kwargs["workspace_dir"] == "/tmp/code-runs"
        return {
            "stdout": "4\n",
            "stderr": "",
            "exit_code": 0,
            "artifacts": [],
            "artifact_paths": [],
        }

    monkeypatch.setattr("sparkweave.services.code_execution.run_python_code", fake_run_code)

    tool = CodeExecutionTool()
    result = await tool.execute(code="print(2 + 2)", timeout=5, workspace_dir="/tmp/code-runs")

    assert result.success is True
    assert result.content == "4"
    assert result.metadata["code"] == "print(2 + 2)"


@pytest.mark.asyncio
async def test_code_execution_tool_generates_code_from_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: dict[str, Any] = {}

    async def fake_run_code(**kwargs: Any) -> dict[str, Any]:
        executed.update(kwargs)
        return {
            "stdout": "42\n",
            "stderr": "",
            "exit_code": 0,
            "artifacts": ["plot.png"],
            "artifact_paths": ["/tmp/plot.png"],
        }

    monkeypatch.setattr("sparkweave.services.code_execution.run_python_code", fake_run_code)
    tool = CodeExecutionTool()

    async def fake_generate_code(intent: str) -> str:
        assert intent == "compute the answer"
        return "print(42)"

    monkeypatch.setattr(tool, "_generate_code", fake_generate_code)

    result = await tool.execute(intent="compute the answer")

    assert executed["code"] == "print(42)"
    assert "42" in result.content
    assert result.sources[0]["file"] == "plot.png"


def test_code_execution_tool_strips_markdown_fences() -> None:
    fenced = "```python\nprint(7)\n```"
    assert CodeExecutionTool._strip_markdown_fences(fenced) == "print(7)"


@pytest.mark.asyncio
async def test_reason_tool_passes_llm_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_reason(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"answer": "reasoned"}

    monkeypatch.setattr("sparkweave.services.reasoning.reason", fake_reason)

    result = await ReasonTool().execute(
        query="derive the formula",
        context="prior work",
        api_key="key",
        base_url="url",
        model="gpt-test",
    )

    assert result.content == "reasoned"
    assert captured["model"] == "gpt-test"
    assert captured["context"] == "prior work"


@pytest.mark.asyncio
async def test_paper_search_tool_formats_papers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search_arxiv_papers(**kwargs: Any) -> list[dict[str, Any]]:
        assert kwargs["query"] == "graph learning"
        return [
            {
                "title": "Graph Learning 101",
                "year": 2024,
                "authors": ["Ada", "Grace"],
                "arxiv_id": "1234.5678",
                "url": "https://arxiv.org/abs/1234.5678",
                "abstract": "A compact abstract.",
            }
        ]

    monkeypatch.setattr("sparkweave.services.papers.search_arxiv_papers", fake_search_arxiv_papers)

    result = await PaperSearchToolWrapper().execute(query="graph learning")

    assert "Graph Learning 101" in result.content
    assert result.sources[0]["provider"] == "arxiv"


@pytest.mark.asyncio
async def test_geogebra_analysis_tool_handles_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze_geogebra_image(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["question"] == "analyze this"
        return {
            "ggb_block": "A=(0,0)\nB=(1,0)",
            "result": {
                "has_image": True,
                "final_ggb_commands": ["A=(0,0)", "B=(1,0)"],
                "analysis_output": {
                    "constraints": ["AB = 1"],
                    "geometric_relations": [{"description": "A and B are on x-axis"}],
                },
                "bbox_output": {"elements": [1, 2]},
                "reflection_output": {"issues_found": []},
            },
        }

    monkeypatch.setattr(
        "sparkweave.services.vision.analyze_geogebra_image",
        fake_analyze_geogebra_image,
    )

    result = await GeoGebraAnalysisTool().execute(
        question="analyze this",
        image_base64="ZmFrZQ==",
        language="en",
    )

    assert result.success is True
    assert "A=(0,0)" in result.content
    assert result.metadata["commands_count"] == 2


@pytest.mark.asyncio
async def test_tool_registry_resolves_aliases_and_argument_mapping() -> None:
    class DummyTool(BaseTool):
        def __init__(self, tool_name: str) -> None:
            self._tool_name = tool_name
            self.calls: list[dict[str, Any]] = []

        def get_definition(self) -> ToolDefinition:
            param_name = {
                "rag": "query",
                "code_execution": "intent",
            }[self._tool_name]
            return ToolDefinition(
                name=self._tool_name,
                description="dummy",
                parameters=[ToolParameter(name=param_name, type="string")],
            )

        async def execute(self, **kwargs: Any) -> ToolResult:
            self.calls.append(kwargs)
            return ToolResult(content=self._tool_name)

    rag = DummyTool("rag")
    code = DummyTool("code_execution")

    registry = ToolRegistry()
    registry.register(rag)
    registry.register(code)

    rag_result = await registry.execute("rag_hybrid", query="find this")
    code_result = await registry.execute("run_code", query="compute this")

    assert rag_result.content == "rag"
    assert rag.calls[0]["mode"] == "hybrid"
    assert rag.calls[0]["query"] == "find this"
    assert code.calls[0]["intent"] == "compute this"

