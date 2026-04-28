"""Runner facade for LangGraph-backed SparkWeave capabilities."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator
import uuid

from sparkweave.core.contracts import (
    StreamBus,
    StreamEvent,
    StreamEventType,
    UnifiedContext,
)


class LangGraphRunner:
    """Execute next-generation graphs while preserving SparkWeave events."""

    supported_capabilities = {
        "chat",
        "deep_question",
        "deep_research",
        "deep_solve",
        "math_animator",
        "visualize",
    }

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        capability = context.active_capability or "chat"
        if capability == "chat":
            from sparkweave.graphs.chat import ChatGraph

            graph = ChatGraph()
            await graph.run(context, stream)
            return

        if capability == "deep_solve":
            from sparkweave.graphs.deep_solve import DeepSolveGraph

            graph = DeepSolveGraph()
            await graph.run(context, stream)
            return

        if capability == "deep_question":
            from sparkweave.graphs.deep_question import DeepQuestionGraph

            graph = DeepQuestionGraph()
            await graph.run(context, stream)
            return

        if capability == "deep_research":
            from sparkweave.graphs.deep_research import DeepResearchGraph

            graph = DeepResearchGraph()
            await graph.run(context, stream)
            return

        if capability == "visualize":
            from sparkweave.graphs.visualize import VisualizeGraph

            graph = VisualizeGraph()
            await graph.run(context, stream)
            return

        if capability == "math_animator":
            from sparkweave.graphs.math_animator import MathAnimatorGraph

            graph = MathAnimatorGraph()
            await graph.run(context, stream)
            return

        if capability not in self.supported_capabilities:
            await stream.error(
                f"LangGraph runtime has not migrated capability `{capability}` yet.",
                source="langgraph",
            )
            return

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        if not context.session_id:
            context.session_id = str(uuid.uuid4())

        yield StreamEvent(
            type=StreamEventType.SESSION,
            source="langgraph",
            metadata={
                "session_id": context.session_id,
                "turn_id": str(context.metadata.get("turn_id", "")),
                "runtime": "langgraph",
            },
        )

        bus = StreamBus()

        async def _run() -> None:
            try:
                await self.run(context, bus)
            except Exception as exc:
                await bus.error(str(exc), source="langgraph")
            finally:
                await bus.emit(StreamEvent(type=StreamEventType.DONE, source="langgraph"))
                await bus.close()

        stream = bus.subscribe()
        task = asyncio.create_task(_run())
        async for event in stream:
            yield event
        await task

    def list_capabilities(self) -> list[str]:
        return sorted(self.supported_capabilities)

