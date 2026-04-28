"""MCP tool support for the NG SparkBot agent loop."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import AsyncExitStack
import logging
from typing import Any

import httpx

from sparkweave.core.tool_protocol import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)
from sparkweave.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_SUPPORTED_PARAMETER_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


class MCPToolWrapper(BaseTool):
    """Wrap one remote MCP tool as an NG SparkBot tool."""

    def __init__(
        self,
        session: Any,
        *,
        server_name: str,
        tool_def: Any,
        tool_timeout: int = 30,
    ) -> None:
        self._session = session
        self._original_name = str(getattr(tool_def, "name", ""))
        self._name = f"mcp_{server_name}_{self._original_name}"
        self._description = str(
            getattr(tool_def, "description", None) or self._original_name or self._name
        )
        self._input_schema = getattr(tool_def, "inputSchema", None) or {
            "type": "object",
            "properties": {},
        }
        self._tool_timeout = max(1, int(tool_timeout or 30))

    def get_definition(self) -> ToolDefinition:
        schema = self._input_schema if isinstance(self._input_schema, Mapping) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
        required = set(schema.get("required") if isinstance(schema.get("required"), list) else [])
        parameters: list[ToolParameter] = []
        for name, raw_spec in properties.items():
            spec = raw_spec if isinstance(raw_spec, Mapping) else {}
            parameter_type = spec.get("type") or "string"
            if isinstance(parameter_type, list):
                parameter_type = next((item for item in parameter_type if item != "null"), "string")
            if parameter_type not in _SUPPORTED_PARAMETER_TYPES:
                parameter_type = "object"
            enum = spec.get("enum") if isinstance(spec.get("enum"), list) else None
            parameters.append(
                ToolParameter(
                    name=str(name),
                    type=str(parameter_type),
                    description=str(spec.get("description") or ""),
                    required=str(name) in required,
                    enum=[str(item) for item in enum] if enum else None,
                )
            )
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=parameters,
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '%s' timed out after %ss", self._name, self._tool_timeout)
            return ToolResult(
                content=f"(MCP tool call timed out after {self._tool_timeout}s)",
                success=False,
            )
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            logger.warning("MCP tool '%s' was cancelled by server/SDK", self._name)
            return ToolResult(content="(MCP tool call was cancelled)", success=False)
        except Exception as exc:
            logger.exception("MCP tool '%s' failed", self._name)
            return ToolResult(
                content=f"(MCP tool call failed: {type(exc).__name__})",
                success=False,
            )

        text = _mcp_result_to_text(result)
        return ToolResult(
            content=text or "(no output)",
            metadata={"server_tool": self._original_name},
        )


async def connect_mcp_servers(
    mcp_servers: Mapping[str, Any],
    registry: ToolRegistry,
    stack: AsyncExitStack,
) -> dict[str, Any]:
    """Connect configured MCP servers and register their exposed tools."""

    status: dict[str, Any] = {"connected": [], "errors": {}}
    if not mcp_servers:
        return status
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        status["errors"]["mcp"] = f"MCP SDK is not installed: {exc}"
        logger.warning("MCP SDK is not installed; skipping SparkBot MCP tools")
        return status

    for server_name, raw_config in mcp_servers.items():
        cfg = _config_mapping(raw_config)
        try:
            transport_type = str(cfg.get("type") or "")
            command = str(cfg.get("command") or "")
            url = str(cfg.get("url") or "")
            if not transport_type:
                if command:
                    transport_type = "stdio"
                elif url:
                    transport_type = "sse" if url.rstrip("/").endswith("/sse") else "streamableHttp"
            if transport_type == "stdio":
                params = StdioServerParameters(
                    command=command,
                    args=list(cfg.get("args") or []),
                    env=dict(cfg.get("env") or {}) or None,
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif transport_type == "sse":
                read, write = await stack.enter_async_context(
                    sse_client(
                        url,
                        httpx_client_factory=_http_client_factory(dict(cfg.get("headers") or {})),
                    )
                )
            elif transport_type == "streamableHttp":
                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=dict(cfg.get("headers") or {}) or None,
                        follow_redirects=True,
                        timeout=None,
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(url, http_client=http_client)
                )
            else:
                status["errors"][server_name] = f"Unknown MCP transport type '{transport_type}'"
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools_result = await session.list_tools()
            tool_defs = list(getattr(tools_result, "tools", []) or [])
            registered = _register_mcp_tools(
                registry,
                server_name=str(server_name),
                session=session,
                tool_defs=tool_defs,
                enabled_tools=set(cfg.get("enabled_tools") or cfg.get("enabledTools") or ["*"]),
                tool_timeout=int(cfg.get("tool_timeout") or cfg.get("toolTimeout") or 30),
            )
            status["connected"].append({"server": str(server_name), "tools": registered})
        except Exception as exc:
            logger.exception("MCP server '%s' failed to connect", server_name)
            status["errors"][str(server_name)] = f"{type(exc).__name__}: {exc}"
    return status


def _register_mcp_tools(
    registry: ToolRegistry,
    *,
    server_name: str,
    session: Any,
    tool_defs: list[Any],
    enabled_tools: set[Any],
    tool_timeout: int,
) -> int:
    enabled = {str(item) for item in enabled_tools}
    allow_all = "*" in enabled
    registered = 0
    for tool_def in tool_defs:
        raw_name = str(getattr(tool_def, "name", ""))
        wrapped_name = f"mcp_{server_name}_{raw_name}"
        if not allow_all and raw_name not in enabled and wrapped_name not in enabled:
            continue
        registry.register(
            MCPToolWrapper(
                session,
                server_name=server_name,
                tool_def=tool_def,
                tool_timeout=tool_timeout,
            )
        )
        registered += 1
    return registered


def _config_mapping(config: Any) -> dict[str, Any]:
    if isinstance(config, Mapping):
        return dict(config)
    dump = getattr(config, "model_dump", None)
    if callable(dump):
        return dict(dump(mode="python", by_alias=False))
    return {
        key: getattr(config, key)
        for key in (
            "type",
            "command",
            "args",
            "env",
            "url",
            "headers",
            "tool_timeout",
            "enabled_tools",
        )
        if hasattr(config, key)
    }


def _http_client_factory(extra_headers: dict[str, str]) -> Any:
    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        merged_headers = {**extra_headers, **(headers or {})}
        return httpx.AsyncClient(
            headers=merged_headers or None,
            follow_redirects=True,
            timeout=timeout,
            auth=auth,
        )

    return factory


def _mcp_result_to_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        return str(dict(content))
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        parts.append(str(text if text is not None else block))
    return "\n".join(parts)


__all__ = ["MCPToolWrapper", "connect_mcp_servers"]

