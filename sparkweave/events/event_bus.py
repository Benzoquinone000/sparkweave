"""Asynchronous event bus for NG runtime lifecycle events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Supported application event types."""

    SOLVE_COMPLETE = "SOLVE_COMPLETE"
    QUESTION_COMPLETE = "QUESTION_COMPLETE"
    CAPABILITY_COMPLETE = "CAPABILITY_COMPLETE"


@dataclass
class Event:
    """Event data structure passed through the application event bus."""

    type: EventType
    task_id: str
    user_input: str
    agent_output: str = ""
    tools_used: list[str] = field(default_factory=list)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        event_type = self.type.value if isinstance(self.type, EventType) else self.type
        return {
            "type": event_type,
            "task_id": self.task_id,
            "user_input": self.user_input,
            "agent_output": self.agent_output,
            "tools_used": self.tools_used,
            "success": self.success,
            "metadata": self.metadata,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
        }


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Singleton asynchronous publish/subscribe bus."""

    _instance: EventBus | None = None
    _initialized: bool = False

    def __new__(cls) -> EventBus:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if EventBus._initialized:
            return
        self._subscribers: dict[EventType, list[EventHandler]] = {
            event_type: [] for event_type in EventType
        }
        self._task_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None
        self._running = False
        EventBus._initialized = True

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        await self._task_queue.put(event)
        if not self._running:
            await self.start()

    async def flush(self, timeout: float = 60.0) -> None:
        if not self._running or self._task_queue.empty():
            return
        try:
            await asyncio.wait_for(self._task_queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "EventBus flush timeout after %.0fs; %d events may still be pending",
                timeout,
                self._task_queue.qsize(),
            )

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())

    async def stop(self) -> None:
        if not self._running:
            return
        try:
            await asyncio.wait_for(self._task_queue.join(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("EventBus shutdown timeout; pending events may be lost")
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def _process_events(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                for handler in self._subscribers.get(event.type, []):
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception(
                            "EventBus handler failed for %s (task_id=%s)",
                            event.type.value,
                            event.task_id,
                        )
            finally:
                self._task_queue.task_done()

    @classmethod
    def reset(cls) -> None:
        global _event_bus
        if cls._instance is not None:
            cls._instance._running = False
            if cls._instance._processor_task:
                cls._instance._processor_task.cancel()
        cls._instance = None
        cls._initialized = False
        _event_bus = None


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


__all__ = ["Event", "EventBus", "EventHandler", "EventType", "get_event_bus"]
