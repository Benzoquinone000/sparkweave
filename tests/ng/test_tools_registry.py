from __future__ import annotations

import pytest

from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolAlias,
    ToolDefinition,
    ToolParameter,
    ToolPromptHints,
    ToolResult,
)
from sparkweave.tools.builtin import BUILTIN_TOOL_NAMES
from sparkweave.tools.registry import (
    LangChainToolRegistry,
    ToolRegistry,
    build_args_schema,
    get_tool_registry,
)


def test_build_args_schema_from_sparkweave_tool_definition():
    schema = build_args_schema(
        ToolDefinition(
            name="web_search",
            description="Search the web.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query."),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results.",
                    required=False,
                    default=3,
                ),
            ],
        )
    )

    value = schema(query="langgraph")

    assert value.query == "langgraph"
    assert value.max_results == 3
    assert "query" in schema.model_json_schema()["required"]


def test_ng_default_tool_registry_loads_builtin_tools():
    registry = get_tool_registry()

    assert set(BUILTIN_TOOL_NAMES).issubset(set(registry.list_tools()))
    assert registry.get("rag").__class__.__module__ == "sparkweave.tools.builtin"
    assert registry.get("rag_hybrid").name == "rag"


def test_langchain_tool_registry_uses_ng_registry_by_default():
    registry = LangChainToolRegistry()

    assert isinstance(registry.registry, ToolRegistry)


class _CaptureTool(BaseTool):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="code_execution",
            description="Capture code execution args.",
            parameters=[
                ToolParameter(name="intent", type="string", description="Intent."),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Timeout.",
                    required=False,
                    default=30,
                ),
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        self.calls.append(dict(kwargs))
        return ToolResult(content="captured", metadata=dict(kwargs))


class _HintTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="rag",
            description="Search the uploaded knowledge base.",
            parameters=[ToolParameter(name="query", type="string")],
        )

    def get_prompt_hints(self, language: str = "en") -> ToolPromptHints:
        return ToolPromptHints(
            short_description="Search the uploaded knowledge base.",
            when_to_use="Use when local notes are needed.",
            input_format="Natural language query.",
            guideline="ground the answer in retrieved passages.",
            phase="exploration",
            aliases=[
                ToolAlias(
                    name="rag_hybrid",
                    description="Hybrid retrieval.",
                    input_format="Question text.",
                    when_to_use="Use for broad recall.",
                    phase="verification",
                )
            ],
        )

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(content="ok", metadata=dict(kwargs))


def test_ng_tool_registry_builds_prompt_text_compatibility_formats():
    registry = ToolRegistry()
    registry.register(_HintTool())

    list_text = registry.build_prompt_text(["rag"], format="list", kb_name="algebra")
    table_text = registry.build_prompt_text(
        ["rag"],
        format="table",
        control_actions=[
            {
                "name": "done",
                "when_to_use": "When enough evidence is available.",
                "input_format": "Empty string.",
            }
        ],
    )
    aliases_text = registry.build_prompt_text(["rag"], format="aliases")
    phased_text = registry.build_prompt_text(["rag"], format="phased", language="zh")

    assert '- rag: Search the knowledge base "algebra".' in list_text
    assert "| `rag` | Use when local notes are needed. | Natural language query. |" in table_text
    assert "| `done` | When enough evidence is available. | Empty string. |" in table_text
    assert "- rag_hybrid: Hybrid retrieval. | Query format: Question text." in aliases_text
    assert "**阶段 4：验证核查**" in phased_text
    assert "`rag_hybrid`: Use for broad recall." in phased_text


def test_ng_tool_registry_rejects_unknown_prompt_format():
    registry = ToolRegistry()
    registry.register(_HintTool())

    with pytest.raises(ValueError, match="Unsupported prompt format"):
        registry.build_prompt_text(["rag"], format="xml")


@pytest.mark.asyncio
async def test_ng_tool_registry_resolves_aliases_and_query_compatibility():
    tool = _CaptureTool()
    registry = ToolRegistry()
    registry.register(tool)

    result = await registry.execute("run_code", query="print(1)", timeout=2)

    assert result.content == "captured"
    assert tool.calls == [{"timeout": 2, "intent": "print(1)"}]


