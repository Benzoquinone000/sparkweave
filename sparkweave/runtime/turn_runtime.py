"""NG-owned turn runtime for LangGraph capabilities."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import contextlib
from dataclasses import dataclass, field
from typing import Any

from sparkweave.core.contracts import StreamEventType, UnifiedContext
from sparkweave.runtime.context_enrichment import build_turn_context
from sparkweave.runtime.runner import LangGraphRunner
from sparkweave.services.memory import get_memory
from sparkweave.services.session import SQLiteSessionStore, get_session_store
from sparkweave.services.validation import validate_capability_config

_RESULT_TEXT_KEYS = ("response", "final_answer", "answer", "output", "result", "text", "content")
_ASSISTANT_CAPABILITIES = {
    "chat",
    "deep_solve",
    "deep_question",
    "deep_research",
    "visualize",
    "math_animator",
}


@dataclass
class TurnRunResult:
    session: dict[str, Any]
    turn: dict[str, Any]
    events: list[dict[str, Any]]
    assistant_content: str


@dataclass
class _PreparedTurn:
    session: dict[str, Any]
    turn: dict[str, Any]
    capability: str
    raw_content: str
    payload: dict[str, Any]
    context: UnifiedContext | None = None


@dataclass
class _LiveSubscriber:
    queue: asyncio.Queue[dict[str, Any] | None] = field(default_factory=asyncio.Queue)


@dataclass
class _TurnExecution:
    session_id: str
    turn_id: str
    subscribers: list[_LiveSubscriber] = field(default_factory=list)
    task: asyncio.Task[TurnRunResult] | None = None


class LangGraphTurnRuntimeManager:
    """Run LangGraph turns and persist session state.

    ``run_turn`` keeps the convenient complete-turn API. ``start_turn`` and
    ``subscribe_turn`` add the live fan-out surface needed by WebSocket/API
    entry points while preserving replay from the SQLite event store.
    """

    def __init__(
        self,
        *,
        store: SQLiteSessionStore | None = None,
        runner: LangGraphRunner | None = None,
        memory_service: Any | None = None,
        notebook_manager: Any | None = None,
    ) -> None:
        self.store = store or get_session_store()
        self.runner = runner or LangGraphRunner()
        self.memory_service = memory_service
        self.notebook_manager = notebook_manager
        self._lock = asyncio.Lock()
        self._executions: dict[str, _TurnExecution] = {}

    async def run_turn(self, payload: dict[str, Any]) -> TurnRunResult:
        prepared = await self._prepare_turn(payload)
        return await self._run_prepared_turn(prepared)

    async def start_turn(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Start a LangGraph turn in the background and return session/turn records."""
        prepared = await self._prepare_turn(payload)
        execution = _TurnExecution(
            session_id=prepared.session["id"],
            turn_id=prepared.turn["id"],
        )
        async with self._lock:
            self._executions[prepared.turn["id"]] = execution
        execution.task = asyncio.create_task(self._run_background(prepared, execution))
        return prepared.session, prepared.turn

    async def cancel_turn(self, turn_id: str) -> bool:
        """Cancel a running LangGraph turn when it is owned by this process."""
        async with self._lock:
            execution = self._executions.get(turn_id)
        if execution is None or execution.task is None or execution.task.done():
            turn = await self.store.get_turn(turn_id)
            if turn is None or turn.get("status") != "running":
                return False
            await self.store.update_turn_status(turn_id, "cancelled", "Turn cancelled")
            await self._persist_detached_cancel_events(turn)
            return True
        execution.task.cancel()
        return True

    async def subscribe_turn(
        self,
        turn_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Replay persisted events, then stream live events for an active turn."""
        subscriber = _LiveSubscriber()
        async with self._lock:
            execution = self._executions.get(turn_id)
            if execution is not None:
                execution.subscribers.append(subscriber)

        seen: set[int] = set()
        try:
            for event in await self.store.get_turn_events(turn_id, after_seq=after_seq):
                seq = int(event.get("seq") or 0)
                seen.add(seq)
                yield event

            if execution is None:
                return

            while True:
                event = await subscriber.queue.get()
                if event is None:
                    break
                seq = int(event.get("seq") or 0)
                if seq <= after_seq or seq in seen:
                    continue
                seen.add(seq)
                yield event
        finally:
            if execution is not None:
                async with self._lock:
                    current = self._executions.get(turn_id)
                    if current is not None:
                        current.subscribers = [
                            item for item in current.subscribers if item is not subscriber
                        ]

    async def subscribe_session(
        self,
        session_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to the active or latest completed turn for a session."""
        turn = await self.store.get_active_turn(session_id)
        if turn is None:
            turn = await self.store.get_latest_turn(session_id)
        if turn is None:
            return
        async for event in self.subscribe_turn(turn["id"], after_seq=after_seq):
            yield event

    async def _prepare_turn(self, payload: dict[str, Any]) -> _PreparedTurn:
        session = await self._resolve_session(payload)
        capability = str(payload.get("capability") or "chat").strip() or "chat"
        payload = self._validated_payload(payload, capability=capability)
        await self.store.update_session_preferences(
            session["id"],
            {
                "capability": capability,
                "tools": list(payload.get("tools") or []),
                "knowledge_bases": list(payload.get("knowledge_bases") or []),
                "language": str(payload.get("language") or "en"),
            },
        )
        turn = await self.store.create_turn(session["id"], capability=capability)

        raw_content = str(payload.get("content") or "")
        return _PreparedTurn(
            session=session,
            turn=turn,
            capability=capability,
            raw_content=raw_content,
            payload=payload,
        )

    async def _run_background(
        self,
        prepared: _PreparedTurn,
        execution: _TurnExecution,
    ) -> TurnRunResult:
        try:
            return await self._run_prepared_turn(prepared, execution=execution)
        except asyncio.CancelledError:
            await self.store.update_turn_status(prepared.turn["id"], "cancelled", "Turn cancelled")
            await self._persist_event(
                prepared,
                self._event(
                    StreamEventType.ERROR,
                    source=prepared.capability,
                    content="Turn cancelled",
                    metadata={"turn_terminal": True, "status": "cancelled"},
                ),
                execution,
            )
            await self._persist_event(
                prepared,
                self._event(
                    StreamEventType.DONE,
                    source=prepared.capability,
                    metadata={"status": "cancelled"},
                ),
                execution,
            )
            raise
        finally:
            await self._close_execution(execution.turn_id)

    async def _run_prepared_turn(
        self,
        prepared: _PreparedTurn,
        *,
        execution: _TurnExecution | None = None,
    ) -> TurnRunResult:
        events: list[dict[str, Any]] = []
        assistant_events: list[dict[str, Any]] = []
        assistant_content = ""
        saw_error = False

        try:
            session_event = await self._persist_event(
                prepared,
                self._event(
                    StreamEventType.SESSION,
                    source="langgraph",
                    metadata={
                        "session_id": prepared.session["id"],
                        "turn_id": prepared.turn["id"],
                        "runtime": "langgraph",
                    },
                ),
                execution,
            )
            events.append(session_event)

            if prepared.context is None:
                prepared.context = await self._build_context(
                    prepared,
                    execution=execution,
                    events=events,
                )

            async for event in self.runner.handle(prepared.context):
                if event.type == StreamEventType.SESSION:
                    continue
                persisted = await self._persist_event(prepared, event, execution)
                events.append(persisted)
                if persisted.get("type") not in {"done", "session"}:
                    assistant_events.append(persisted)
                if _should_capture_assistant_content(event):
                    assistant_content += event.content
                if event.type == StreamEventType.ERROR:
                    saw_error = True
        except Exception as exc:
            saw_error = True
            error_event = StreamEventType.ERROR
            persisted = await self._persist_event(
                prepared,
                self._event(error_event, source="langgraph", content=str(exc)),
                execution,
            )
            events.append(persisted)
            assistant_events.append(persisted)
            done = await self._persist_event(
                prepared,
                self._event(
                    StreamEventType.DONE,
                    source="langgraph",
                    metadata={"status": "failed"},
                ),
                execution,
            )
            events.append(done)

        if not assistant_content:
            assistant_content = _assistant_content_from_result_events(assistant_events)

        assistant_capability = _infer_assistant_capability(
            prepared.capability,
            assistant_events,
        )

        if assistant_content or _has_result_event(assistant_events):
            await self.store.add_message(
                session_id=prepared.session["id"],
                role="assistant",
                content=assistant_content,
                capability=assistant_capability,
                events=assistant_events,
            )

        status = "failed" if saw_error else "completed"
        error = self._error_text(events) if saw_error else ""
        await self.store.update_turn_status(prepared.turn["id"], status, error)
        await self._refresh_memory(
            payload=prepared.payload,
            session_id=prepared.session["id"],
            capability=assistant_capability,
            user_message=prepared.raw_content,
            assistant_message=assistant_content,
        )
        updated_turn = await self.store.get_turn(prepared.turn["id"])
        return TurnRunResult(
            session=prepared.session,
            turn=updated_turn or prepared.turn,
            events=events,
            assistant_content=assistant_content,
        )

    async def _build_context(
        self,
        prepared: _PreparedTurn,
        *,
        execution: _TurnExecution | None,
        events: list[dict[str, Any]],
    ) -> UnifiedContext:
        async def emit(event: Any) -> None:
            persisted = await self._persist_event(prepared, event, execution)
            events.append(persisted)

        return await build_turn_context(
            payload=prepared.payload,
            store=self.store,
            session_id=prepared.session["id"],
            turn_id=prepared.turn["id"],
            capability=prepared.capability,
            memory_service=self.memory_service,
            notebook_manager=self.notebook_manager,
            emit=emit,
        )

    @staticmethod
    def _validated_payload(payload: dict[str, Any], *, capability: str) -> dict[str, Any]:
        raw_config = dict(payload.get("config", {}) or {})
        runtime_only_keys = (
            "_persist_user_message",
            "_runtime",
            "followup_question_context",
            "answer_now_context",
        )
        runtime_only_config = {
            key: raw_config.pop(key) for key in runtime_only_keys if key in raw_config
        }
        try:
            validated_public_config = validate_capability_config(capability, raw_config)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        return {
            **payload,
            "capability": capability,
            "config": {**validated_public_config, **runtime_only_config},
        }

    async def _persist_event(
        self,
        prepared: _PreparedTurn,
        event: Any,
        execution: _TurnExecution | None = None,
    ) -> dict[str, Any]:
        if event.type == StreamEventType.DONE and not event.metadata.get("status"):
            event.metadata = {**event.metadata, "status": "completed"}
        event.session_id = prepared.session["id"]
        event.turn_id = prepared.turn["id"]
        persisted = await self.store.append_turn_event(prepared.turn["id"], event.to_dict())
        if execution is not None:
            async with self._lock:
                subscribers = list(
                    self._executions.get(execution.turn_id, execution).subscribers
                )
            for subscriber in subscribers:
                with contextlib.suppress(asyncio.QueueFull):
                    subscriber.queue.put_nowait(persisted)
        return persisted

    async def _close_execution(self, turn_id: str) -> None:
        async with self._lock:
            execution = self._executions.pop(turn_id, None)
            subscribers = list(execution.subscribers) if execution is not None else []
        for subscriber in subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                subscriber.queue.put_nowait(None)

    async def _persist_detached_cancel_events(self, turn: dict[str, Any]) -> None:
        turn_id = str(turn.get("id") or turn.get("turn_id") or "")
        if not turn_id:
            return
        existing = await self.store.get_turn_events(turn_id, after_seq=0)
        if any(event.get("type") == "done" for event in existing):
            return
        source = str(turn.get("capability") or "langgraph")
        await self.store.append_turn_event(
            turn_id,
            {
                "type": "error",
                "source": source,
                "content": "Turn cancelled",
                "metadata": {"turn_terminal": True, "status": "cancelled"},
            },
        )
        await self.store.append_turn_event(
            turn_id,
            {
                "type": "done",
                "source": source,
                "metadata": {"status": "cancelled"},
            },
        )

    async def _resolve_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        requested = str(payload.get("session_id") or "").strip()
        if requested:
            existing = await self.store.get_session(requested)
            if existing is not None:
                return existing
            return await self.store.create_session(
                title=self._title_from_payload(payload),
                session_id=requested,
            )
        return await self.store.create_session(title=self._title_from_payload(payload))

    async def _refresh_memory(
        self,
        *,
        payload: dict[str, Any],
        session_id: str,
        capability: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        if not user_message.strip() or not assistant_message.strip():
            return
        memory = self.memory_service or get_memory()
        try:
            await memory.refresh_from_turn(
                user_message=user_message,
                assistant_message=assistant_message,
                session_id=session_id,
                capability=capability,
                language=str(payload.get("language") or "en"),
            )
        except Exception:
            return

    @staticmethod
    def _title_from_payload(payload: dict[str, Any]) -> str:
        content = str(payload.get("content") or "").strip()
        return content[:80] or "New conversation"

    @staticmethod
    def _error_text(events: list[dict[str, Any]]) -> str:
        for event in events:
            if event.get("type") == "error":
                return str(event.get("content") or "")
        return ""

    @staticmethod
    def _event(
        event_type: StreamEventType,
        *,
        source: str = "",
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        from sparkweave.core.contracts import StreamEvent

        return StreamEvent(
            type=event_type,
            source=source,
            content=content,
            metadata=metadata or {},
        )


def _has_result_event(events: list[dict[str, Any]]) -> bool:
    return any(str(event.get("type") or "") == StreamEventType.RESULT.value for event in events)


def _assistant_content_from_result_events(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if str(event.get("type") or "") != StreamEventType.RESULT.value:
            continue
        text = _text_from_record(_as_dict(event.get("metadata")))
        if text:
            return text
    return ""


def _infer_assistant_capability(default: str, events: list[dict[str, Any]]) -> str:
    fallback = _normalize_capability(default) or "chat"
    for event in reversed(events):
        source = _normalize_capability(event.get("source"))
        if source in _ASSISTANT_CAPABILITIES and source != "chat":
            return source
        metadata = _as_dict(event.get("metadata"))
        target = _normalize_capability(metadata.get("target_capability") if metadata else "")
        if target in _ASSISTANT_CAPABILITIES and target != "chat":
            return target
        capability = _normalize_capability(metadata.get("capability") if metadata else "")
        if capability in _ASSISTANT_CAPABILITIES and capability != "chat":
            return capability
    return fallback


def _normalize_capability(value: Any) -> str:
    return str(value or "").strip().lower()


def _text_from_record(record: dict[str, Any] | None) -> str:
    if not record:
        return ""
    for key in _RESULT_TEXT_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = _as_dict(record.get("metadata"))
    return _text_from_record(nested) if nested is not None else ""


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _should_capture_assistant_content(event: Any) -> bool:
    """Return whether a stream event should become assistant message text."""
    if event.type != StreamEventType.CONTENT:
        return False
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    if not metadata.get("call_id"):
        return True
    return metadata.get("call_kind") == "llm_final_response"


__all__ = ["LangGraphTurnRuntimeManager", "TurnRunResult"]

