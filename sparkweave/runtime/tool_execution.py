"""Shared tool execution helpers for capability graphs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from sparkweave.core.contracts import StreamBus, UnifiedContext
from sparkweave.core.tool_protocol import ToolResult

ToolArgAugmenter = Callable[[str, dict[str, Any], UnifiedContext | None], dict[str, Any]]
RetrieveMetadataBuilder = Callable[..., dict[str, Any] | None]


class ToolRegistryExecutor(Protocol):
    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        ...


class GraphToolExecutor:
    """Execute one graph tool call with SparkWeave stream events."""

    def __init__(
        self,
        registry: ToolRegistryExecutor,
        *,
        source: str,
        stage: str,
        arg_augmenter: ToolArgAugmenter | None = None,
        retrieve_metadata_builder: RetrieveMetadataBuilder | None = None,
        result_metadata_tools: set[str] | None = None,
    ) -> None:
        self.registry = registry
        self.source = source
        self.stage = stage
        self.arg_augmenter = arg_augmenter
        self.retrieve_metadata_builder = retrieve_metadata_builder
        self.result_metadata_tools = result_metadata_tools or {"rag"}

    async def execute(
        self,
        call: dict[str, Any],
        context: UnifiedContext | None,
        stream: StreamBus,
        *,
        tool_index: int = 0,
    ) -> dict[str, Any]:
        name = str(call.get("name") or "").strip()
        args = dict(call.get("args") or {})
        tool_call_id = str(call.get("id") or name or "tool-call")
        if self.arg_augmenter is not None:
            args = self.arg_augmenter(name, args, context)
        retrieve_meta = self._retrieve_metadata(
            name=name,
            args=args,
            tool_call_id=tool_call_id,
            tool_index=tool_index,
            context=context,
        )

        await stream.tool_call(
            tool_name=name,
            args=args,
            source=self.source,
            stage=self.stage,
            metadata={
                "trace_kind": "tool_call",
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "tool_index": tool_index,
            },
        )

        try:
            execute_args = dict(args)
            if retrieve_meta is not None:
                await self._emit_retrieve_running(stream, retrieve_meta)
                execute_args["event_sink"] = self._event_sink(stream, retrieve_meta)

            result = await self.registry.execute(name, **execute_args)
            result_text = result.content or "(empty tool result)"
            success = result.success
            sources = result.sources
            metadata = result.metadata
            if retrieve_meta is not None:
                await self._emit_retrieve_complete(stream, retrieve_meta, result_text)
        except Exception as exc:
            result_text = f"Error executing {name}: {exc}"
            success = False
            sources = []
            metadata = {"error": str(exc)}
            if retrieve_meta is not None:
                await stream.error(
                    f"Retrieve failed: {exc}",
                    source=self.source,
                    stage=self.stage,
                    metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "error"},
                )

        await stream.tool_result(
            tool_name=name,
            result=result_text,
            source=self.source,
            stage=self.stage,
            metadata={
                "trace_kind": "tool_result",
                "tool_call_id": tool_call_id,
                "tool_name": name,
                "tool_index": tool_index,
                "success": success,
                "sources": sources,
                "result_metadata": metadata if name in self.result_metadata_tools else {},
            },
        )
        return {
            "id": tool_call_id,
            "name": name,
            "arguments": args,
            "result": result_text,
            "success": success,
            "sources": sources,
            "metadata": metadata,
        }

    def _retrieve_metadata(
        self,
        *,
        name: str,
        args: dict[str, Any],
        tool_call_id: str,
        tool_index: int,
        context: UnifiedContext | None,
    ) -> dict[str, Any] | None:
        if self.retrieve_metadata_builder is None:
            return None
        return self.retrieve_metadata_builder(
            name=name,
            args=args,
            tool_call_id=tool_call_id,
            tool_index=tool_index,
            context=context,
        )

    async def _emit_retrieve_running(
        self,
        stream: StreamBus,
        retrieve_meta: dict[str, Any],
    ) -> None:
        await stream.progress(
            f"Query: {retrieve_meta.get('query')}"
            if retrieve_meta.get("query")
            else "Retrieving from the knowledge base...",
            source=self.source,
            stage=self.stage,
            metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "running"},
        )

    async def _emit_retrieve_complete(
        self,
        stream: StreamBus,
        retrieve_meta: dict[str, Any],
        result_text: str,
    ) -> None:
        await stream.progress(
            f"Retrieve complete ({len(result_text)} chars)",
            source=self.source,
            stage=self.stage,
            metadata={**retrieve_meta, "trace_kind": "call_status", "call_state": "complete"},
        )

    def _event_sink(
        self,
        stream: StreamBus,
        retrieve_meta: dict[str, Any],
    ) -> Callable[[str, str, dict[str, Any] | None], Awaitable[None]]:
        async def _sink(
            event_type: str,
            message: str = "",
            metadata: dict[str, Any] | None = None,
        ) -> None:
            if not message:
                return
            await stream.progress(
                message,
                source=self.source,
                stage=self.stage,
                metadata={
                    **retrieve_meta,
                    "trace_kind": str(event_type or "tool_log"),
                    **(metadata or {}),
                },
            )

        return _sink


__all__ = ["GraphToolExecutor", "ToolRegistryExecutor"]
