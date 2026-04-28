"""Core runtime contracts owned by the NG runtime."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from typing import Any, AsyncIterator

from sparkweave.core.trace import merge_trace_metadata


@dataclass
class Attachment:
    """A file or image attached to the user message."""

    type: str
    url: str = ""
    base64: str = ""
    filename: str = ""
    mime_type: str = ""


@dataclass
class UnifiedContext:
    """Everything a capability or tool needs to process one user turn."""

    session_id: str = ""
    user_message: str = ""
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    enabled_tools: list[str] | None = None
    active_capability: str | None = None
    knowledge_bases: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    notebook_context: str = ""
    history_context: str = ""
    memory_context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class StreamEventType(str, Enum):
    """All event types in a streaming session."""

    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    THINKING = "thinking"
    OBSERVATION = "observation"
    CONTENT = "content"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PROGRESS = "progress"
    SOURCES = "sources"
    RESULT = "result"
    ERROR = "error"
    SESSION = "session"
    DONE = "done"


@dataclass
class StreamEvent:
    """A single streaming event emitted during a turn."""

    type: StreamEventType
    source: str = ""
    stage: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    seq: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        event_type = self.type.value if isinstance(self.type, Enum) else str(self.type)
        return {
            "type": event_type,
            "source": self.source,
            "stage": self.stage,
            "content": self.content,
            "metadata": self.metadata,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
        }


class StreamBus:
    """Fan-out async event bus for a single turn."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[StreamEvent | None]] = []
        self._closed = False
        self._history: list[StreamEvent] = []

    async def emit(self, event: StreamEvent) -> None:
        if self._closed:
            return
        self._history.append(event)
        for queue in self._subscribers:
            await queue.put(event)

    async def subscribe(self) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            for event in self._history:
                yield event
            if self._closed and queue.empty():
                return
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._subscribers.remove(queue)

    async def close(self) -> None:
        self._closed = True
        for queue in self._subscribers:
            await queue.put(None)

    @asynccontextmanager
    async def stage(
        self,
        name: str,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        await self.emit(
            StreamEvent(
                type=StreamEventType.STAGE_START,
                source=source,
                stage=name,
                metadata=metadata or {},
            )
        )
        try:
            yield
        finally:
            await self.emit(
                StreamEvent(
                    type=StreamEventType.STAGE_END,
                    source=source,
                    stage=name,
                    metadata=metadata or {},
                )
            )

    async def content(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.CONTENT,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def thinking(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.THINKING,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def observation(
        self,
        text: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.OBSERVATION,
                source=source,
                stage=stage,
                content=text,
                metadata=metadata or {},
            )
        )

    async def tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.TOOL_CALL,
                source=source,
                stage=stage,
                content=tool_name,
                metadata=merge_trace_metadata({"args": args}, metadata),
            )
        )

    async def tool_result(
        self,
        tool_name: str,
        result: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                source=source,
                stage=stage,
                content=result,
                metadata=merge_trace_metadata({"tool": tool_name}, metadata),
            )
        )

    async def progress(
        self,
        message: str,
        current: int = 0,
        total: int = 0,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.PROGRESS,
                source=source,
                stage=stage,
                content=message,
                metadata=merge_trace_metadata(
                    {"current": current, "total": total},
                    metadata,
                ),
            )
        )

    async def sources(
        self,
        sources: list[dict[str, Any]],
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.SOURCES,
                source=source,
                stage=stage,
                metadata=merge_trace_metadata({"sources": sources}, metadata),
            )
        )

    async def result(
        self,
        data: dict[str, Any],
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.RESULT,
                source=source,
                metadata=merge_trace_metadata(data, metadata),
            )
        )

    async def error(
        self,
        message: str,
        source: str = "",
        stage: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.emit(
            StreamEvent(
                type=StreamEventType.ERROR,
                source=source,
                stage=stage,
                content=message,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def event_to_json(event: StreamEvent) -> str:
        return json.dumps(event.to_dict(), ensure_ascii=False)

__all__ = [
    "Attachment",
    "StreamBus",
    "StreamEvent",
    "StreamEventType",
    "UnifiedContext",
]

