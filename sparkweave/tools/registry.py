"""Native NG tool registry and LangChain adapters."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from pydantic import BaseModel, Field, create_model

from sparkweave.core.dependencies import dependency_error
from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolPromptHints,
    ToolResult,
)
from sparkweave.services.prompting import ToolPromptComposer
from sparkweave.tools.builtin import BUILTIN_TOOL_TYPES, TOOL_ALIASES

logger = logging.getLogger(__name__)

_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": float,
    "array": list[Any],
    "object": dict[str, Any],
}


def build_args_schema(definition: ToolDefinition) -> type[BaseModel]:
    """Build a Pydantic input schema from SparkWeave tool metadata."""
    fields: dict[str, tuple[Any, Any]] = {}
    for parameter in definition.parameters:
        field_type = _TYPE_MAP.get(parameter.type, Any)
        default = ... if parameter.required else parameter.default
        fields[parameter.name] = (
            field_type,
            _field(parameter, default),
        )
    model_name = f"{_class_name(definition.name)}Input"
    return create_model(model_name, **fields)


@dataclass
class ToolRegistry:
    """Registry of NG-owned tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.debug("Registered NG tool: %s", tool.name)

    def load_builtins(self) -> None:
        for tool_type in BUILTIN_TOOL_TYPES:
            try:
                tool = tool_type()
            except Exception:
                logger.warning("Failed to instantiate NG built-in tool %s", tool_type, exc_info=True)
                continue
            if tool.name not in self._tools:
                self.register(tool)

    def names(self) -> list[str]:
        return self.list_tools()

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> BaseTool | None:
        resolved_name, _ = self._resolve_request(name)
        return self._tools.get(resolved_name)

    def get_enabled(self, names: list[str]) -> list[BaseTool]:
        enabled: list[BaseTool] = []
        seen: set[str] = set()
        for name in names:
            tool = self.get(name)
            if tool is None or tool.name in seen:
                continue
            enabled.append(tool)
            seen.add(tool.name)
        return enabled

    def get_definitions(self, names: list[str] | None = None) -> list[ToolDefinition]:
        tools = self._tools.values() if names is None else self.get_enabled(names)
        return [tool.get_definition() for tool in tools]

    def get_prompt_hints(
        self,
        names: list[str],
        language: str = "en",
    ) -> list[tuple[str, ToolPromptHints]]:
        return [
            (tool.name, tool.get_prompt_hints(language=language))
            for tool in self.get_enabled(names)
        ]

    def build_prompt_text(
        self,
        names: list[str],
        format: str = "list",
        language: str = "en",
        **opts: Any,
    ) -> str:
        """Compose prompt text for enabled tools using NG prompt hints."""
        composer = ToolPromptComposer(language=language)
        hints = self.get_prompt_hints(names, language=language)
        if format == "list":
            return composer.format_list(hints, kb_name=str(opts.get("kb_name") or ""))
        if format == "table":
            return composer.format_table(
                hints,
                control_actions=opts.get("control_actions"),
            )
        if format == "aliases":
            return composer.format_aliases(hints)
        if format == "phased":
            return composer.format_phased(hints)
        raise ValueError(f"Unsupported prompt format: {format}")

    def build_openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        return [definition.to_openai_schema() for definition in self.get_definitions(names)]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        resolved_name, resolved_kwargs = self._resolve_request(name, kwargs)
        tool = self._tools.get(resolved_name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.execute(**resolved_kwargs)

    @staticmethod
    def _resolve_request(
        name: str,
        kwargs: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        resolved_name, default_kwargs = TOOL_ALIASES.get(name, (name, {}))
        merged_kwargs = {**default_kwargs, **(kwargs or {})}
        if resolved_name == "code_execution" and "query" in merged_kwargs:
            merged_kwargs.setdefault("intent", merged_kwargs.pop("query"))
        return resolved_name, merged_kwargs


_default_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the NG default tool registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        _default_registry.load_builtins()
    return _default_registry


@dataclass
class LangChainToolRegistry:
    """Expose NG ``ToolRegistry`` entries as LangChain tools."""

    registry: Any | None = None
    include_metadata: bool = False

    def __post_init__(self) -> None:
        if self.registry is None:
            self.registry = get_tool_registry()

    def names(self) -> list[str]:
        return list(self.registry.list_tools())

    def get_tools(self, names: list[str] | None = None) -> list[Any]:
        requested = names if names is not None else self.names()
        return [
            self._to_langchain_tool(definition)
            for definition in self.registry.get_definitions(requested)
        ]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        return await self.registry.execute(name, **kwargs)

    def _to_langchain_tool(self, definition: ToolDefinition) -> Any:
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise dependency_error("langchain-core") from exc

        async def _arun(**kwargs: Any) -> str:
            result = await self.execute(definition.name, **kwargs)
            if not self.include_metadata:
                return result.content
            return json.dumps(
                {
                    "content": result.content,
                    "success": result.success,
                    "sources": result.sources,
                    "metadata": result.metadata,
                },
                ensure_ascii=False,
            )

        return StructuredTool.from_function(
            coroutine=_arun,
            name=definition.name,
            description=definition.description,
            args_schema=build_args_schema(definition),
        )


def _field(parameter: ToolParameter, default: Any) -> Any:
    extra: dict[str, Any] = {}
    if parameter.enum:
        extra["json_schema_extra"] = {"enum": parameter.enum}
    return Field(default, description=parameter.description, **extra)


def _class_name(tool_name: str) -> str:
    return "".join(part.capitalize() for part in tool_name.replace("-", "_").split("_"))

