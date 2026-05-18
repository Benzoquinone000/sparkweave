"""Compatibility orchestrator backed entirely by ``sparkweave``."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import logging
from typing import Any
import uuid

from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.events.event_bus import Event, EventType, get_event_bus
from sparkweave.runtime.policy import select_runtime
from sparkweave.runtime.registry.capability_registry import get_capability_registry
from sparkweave.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """Route one user turn to NG LangGraph runtime or a capability wrapper."""

    def __init__(self) -> None:
        self._cap_registry = get_capability_registry()
        self._tool_registry = get_tool_registry()

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        """Execute a single user turn and yield streaming events."""
        if not context.session_id:
            context.session_id = str(uuid.uuid4())

        cap_name = context.active_capability or "chat"
        if self._should_use_langgraph(context):
            from sparkweave.runtime import LangGraphRunner

            async for event in LangGraphRunner().handle(context):
                yield event
            await self._publish_completion(context, cap_name)
            return

        capability = self._cap_registry.get(cap_name)
        is_answer_now = bool(
            isinstance(context.config_overrides, dict)
            and context.config_overrides.get("answer_now_context")
        )
        if capability is None and is_answer_now:
            fallback = self._cap_registry.get("chat")
            if fallback is not None:
                logger.info(
                    "Capability %s missing for answer_now; falling back to chat.",
                    cap_name,
                )
                cap_name = "chat"
                capability = fallback

        if capability is None:
            yield self._session_event(context)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                source="orchestrator",
                content=(
                    f"Unknown capability: {cap_name}. "
                    f"Available: {self._cap_registry.list_capabilities()}"
                ),
            )
            yield StreamEvent(type=StreamEventType.DONE, source="orchestrator")
            return

        yield self._session_event(context)

        bus = StreamBus()

        async def _run() -> None:
            try:
                await capability.run(context, bus)
            except Exception as exc:
                logger.error("Capability %s failed: %s", cap_name, exc, exc_info=True)
                await bus.error(str(exc), source=cap_name)
            finally:
                await bus.emit(StreamEvent(type=StreamEventType.DONE, source=cap_name))
                await bus.close()

        stream = bus.subscribe()
        task = asyncio.create_task(_run())

        async for event in stream:
            yield event

        await task
        await self._publish_completion(context, cap_name)

    async def _publish_completion(self, context: UnifiedContext, cap_name: str) -> None:
        """Publish a capability completion event for observers."""
        try:
            await get_event_bus().publish(
                Event(
                    type=EventType.CAPABILITY_COMPLETE,
                    task_id=str(context.metadata.get("turn_id") or context.session_id),
                    user_input=context.user_message,
                    metadata={
                        "capability": cap_name,
                        "session_id": context.session_id,
                        "turn_id": str(context.metadata.get("turn_id", "")),
                    },
                )
            )
        except Exception:
            logger.debug("EventBus publish failed; continuing turn shutdown.", exc_info=True)

    def list_tools(self) -> list[str]:
        return self._tool_registry.list_tools()

    def list_capabilities(self) -> list[str]:
        return self._cap_registry.list_capabilities()

    def get_capability_manifests(self) -> list[dict[str, Any]]:
        return self._cap_registry.get_manifests()

    def get_tool_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        return self._tool_registry.build_openai_schemas(names)

    @staticmethod
    def _should_use_langgraph(context: UnifiedContext) -> bool:
        override = ""
        if isinstance(context.config_overrides, dict):
            override = str(context.config_overrides.get("_runtime") or "").strip().lower()
        return (
            select_runtime(
                capability=context.active_capability or "chat",
                explicit_runtime=override,
            )
            == "langgraph"
        )

    @staticmethod
    def _session_event(context: UnifiedContext) -> StreamEvent:
        return StreamEvent(
            type=StreamEventType.SESSION,
            source="orchestrator",
            metadata={
                "session_id": context.session_id,
                "turn_id": str(context.metadata.get("turn_id", "")),
            },
        )


__all__ = ["ChatOrchestrator"]

