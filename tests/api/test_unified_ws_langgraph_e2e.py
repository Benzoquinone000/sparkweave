from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from sparkweave.api.routers import unified_ws
from sparkweave.core.contracts import StreamEvent, StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphTurnRuntimeManager, RuntimeRoutingTurnManager
from sparkweave.services.session import CompatibilityRuntimeUnavailable, create_session_store


class FakeMemory:
    def __init__(self) -> None:
        self.refresh_calls: list[dict[str, Any]] = []

    def build_memory_context(self) -> str:
        return "## Memory\n- Use short answers."

    async def refresh_from_turn(self, **kwargs: Any) -> None:
        self.refresh_calls.append(kwargs)


class MinimalContextBuilder:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def build(self, **_kwargs):  # noqa: ANN003
        return SimpleNamespace(
            conversation_history=[],
            conversation_summary="",
            context_text="",
            token_count=0,
            budget=0,
        )


class StoreReadingContextBuilder:
    def __init__(self, session_store, *_args, **_kwargs) -> None:
        self.store = session_store

    async def build(self, **kwargs):  # noqa: ANN003
        messages = await self.store.get_messages_for_context(kwargs["session_id"])
        return SimpleNamespace(
            conversation_history=[
                {"role": item["role"], "content": item["content"]} for item in messages
            ],
            conversation_summary="",
            context_text="",
            token_count=0,
            budget=0,
        )


class FakeLangGraphRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content="Hello from /api/v1/ws via NG.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source="chat",
            metadata={
                "response": "Hello from /api/v1/ws via NG.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class SequencedRunner:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        response = self.responses[len(self.contexts) - 1]
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content=response,
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": response,
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class BlockingCancelRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []
        self.started = Event()

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        self.started.set()
        await asyncio.Future()
        if False:
            yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class CapturingAnswerNowRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        answer_now = dict(context.config_overrides.get("answer_now_context") or {})
        partial = str(answer_now.get("partial_response") or "").strip()
        original = str(answer_now.get("original_user_message") or "").strip()
        response = f"Answer-now resume for: {original} | partial: {partial}"
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content=response,
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": response,
                "runtime": "langgraph",
                "answer_now": True,
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class PauseAfterContentRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []
        self.release = Event()

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content="Streaming chunk from NG.",
        )
        await asyncio.to_thread(self.release.wait)
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": "Streaming chunk from NG.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class GateBeforeContentRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []
        self.started = Event()
        self.release = Event()

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content="Session subscriber saw this.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": "Session subscriber saw this.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class FollowupContextRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content="Let's discuss this question.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": "Let's discuss this question.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class NotebookContextRunner:
    def __init__(self) -> None:
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source=context.active_capability,
            stage="responding",
            content="Use the saved context.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source=context.active_capability,
            metadata={
                "response": "Use the saved context.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class FakeNotebookManager:
    def get_records_by_references(self, _references):  # noqa: ANN001
        return [
            {
                "id": "rec-1",
                "notebook_id": "nb1",
                "notebook_name": "Notebook",
                "title": "Saved linear algebra note",
                "summary": "Eigenvectors and diagonalization.",
                "output": "A matrix is diagonalizable when it has enough eigenvectors.",
            }
        ]


class FailingLegacyRuntime:
    async def start_turn(self, _payload: dict[str, Any]):  # noqa: ANN201
        raise AssertionError("legacy runtime should not handle _runtime=langgraph")

    async def subscribe_turn(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        if False:
            yield {}

    async def subscribe_session(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        if False:
            yield {}

    async def cancel_turn(self, _turn_id: str) -> bool:
        return False


class RecordingLegacyRuntime:
    def __init__(self, store) -> None:  # noqa: ANN001
        self.store = store
        self.start_payloads: list[dict[str, Any]] = []

    async def start_turn(self, payload: dict[str, Any]):  # noqa: ANN201
        self.start_payloads.append(dict(payload))
        requested = str(payload.get("session_id") or "").strip() or "legacy-session"
        session = await self.store.get_session(requested)
        if session is None:
            session = await self.store.create_session(
                title=str(payload.get("content") or "Legacy turn"),
                session_id=requested,
            )
        capability = str(payload.get("capability") or "chat")
        turn = await self.store.create_turn(session["id"], capability=capability)
        content = "Hello from legacy runtime."
        await self.store.add_message(
            session_id=session["id"],
            role="user",
            content=str(payload.get("content") or ""),
            capability=capability,
        )
        await self.store.append_turn_event(
            turn["id"],
            {
                "type": "session",
                "source": "turn_runtime",
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"runtime": "legacy"},
            },
        )
        await self.store.append_turn_event(
            turn["id"],
            {
                "type": "content",
                "source": capability,
                "stage": "responding",
                "content": content,
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"runtime": "legacy"},
            },
        )
        await self.store.append_turn_event(
            turn["id"],
            {
                "type": "result",
                "source": capability,
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"response": content, "runtime": "legacy"},
            },
        )
        await self.store.append_turn_event(
            turn["id"],
            {
                "type": "done",
                "source": capability,
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"status": "completed"},
            },
        )
        await self.store.add_message(
            session_id=session["id"],
            role="assistant",
            content=content,
            capability=capability,
        )
        await self.store.update_turn_status(turn["id"], "completed")
        return session, turn

    async def subscribe_turn(self, turn_id: str, after_seq: int = 0):  # noqa: ANN201
        for event in await self.store.get_turn_events(turn_id, after_seq=after_seq):
            yield event

    async def subscribe_session(self, session_id: str, after_seq: int = 0):  # noqa: ANN201
        turn = await self.store.get_active_turn(session_id)
        if turn is None:
            turn = await self.store.get_latest_turn(session_id)
        if turn is None:
            return
        async for event in self.subscribe_turn(turn["id"], after_seq=after_seq):
            yield event

    async def cancel_turn(self, _turn_id: str) -> bool:
        return False


class StreamingLegacyRuntime:
    def __init__(self, store) -> None:  # noqa: ANN001
        self.store = store
        self.started = Event()
        self.release = Event()
        self.start_payloads: list[dict[str, Any]] = []
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any] | None]]] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start_turn(self, payload: dict[str, Any]):  # noqa: ANN201
        self.start_payloads.append(dict(payload))
        requested = str(payload.get("session_id") or "").strip() or "legacy-stream-session"
        session = await self.store.get_session(requested)
        if session is None:
            session = await self.store.create_session(
                title=str(payload.get("content") or "Legacy stream turn"),
                session_id=requested,
            )
        capability = str(payload.get("capability") or "chat")
        turn = await self.store.create_turn(session["id"], capability=capability)
        await self.store.add_message(
            session_id=session["id"],
            role="user",
            content=str(payload.get("content") or ""),
            capability=capability,
        )
        self._subscribers[turn["id"]] = []
        await self._append_event(
            turn["id"],
            {
                "type": "session",
                "source": "turn_runtime",
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"runtime": "legacy"},
            },
        )
        self._tasks[turn["id"]] = asyncio.create_task(
            self._run_turn(
                turn_id=turn["id"],
                session_id=session["id"],
                capability=capability,
            )
        )
        return session, turn

    async def _run_turn(self, *, turn_id: str, session_id: str, capability: str) -> None:
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        content = "Streaming from legacy runtime."
        await self._append_event(
            turn_id,
            {
                "type": "content",
                "source": capability,
                "stage": "responding",
                "content": content,
                "session_id": session_id,
                "turn_id": turn_id,
                "metadata": {"runtime": "legacy"},
            },
        )
        await self._append_event(
            turn_id,
            {
                "type": "result",
                "source": capability,
                "session_id": session_id,
                "turn_id": turn_id,
                "metadata": {"response": content, "runtime": "legacy"},
            },
        )
        await self._append_event(
            turn_id,
            {
                "type": "done",
                "source": capability,
                "session_id": session_id,
                "turn_id": turn_id,
                "metadata": {"status": "completed"},
            },
        )
        await self.store.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            capability=capability,
        )
        await self.store.update_turn_status(turn_id, "completed")
        for queue in self._subscribers.pop(turn_id, []):
            queue.put_nowait(None)
        self._tasks.pop(turn_id, None)

    async def _append_event(self, turn_id: str, event: dict[str, Any]) -> dict[str, Any]:
        persisted = await self.store.append_turn_event(turn_id, event)
        for queue in list(self._subscribers.get(turn_id, [])):
            queue.put_nowait(persisted)
        return persisted

    async def subscribe_turn(self, turn_id: str, after_seq: int = 0):  # noqa: ANN201
        seen: set[int] = set()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._subscribers.setdefault(turn_id, []).append(queue)
        try:
            for event in await self.store.get_turn_events(turn_id, after_seq=after_seq):
                seq = int(event.get("seq") or 0)
                seen.add(seq)
                yield event

            if turn_id not in self._tasks:
                return

            while True:
                event = await queue.get()
                if event is None:
                    break
                seq = int(event.get("seq") or 0)
                if seq <= after_seq or seq in seen:
                    continue
                seen.add(seq)
                yield event
        finally:
            subscribers = self._subscribers.get(turn_id, [])
            self._subscribers[turn_id] = [item for item in subscribers if item is not queue]

    async def subscribe_session(self, session_id: str, after_seq: int = 0):  # noqa: ANN201
        turn = await self.store.get_active_turn(session_id)
        if turn is None:
            turn = await self.store.get_latest_turn(session_id)
        if turn is None:
            return
        async for event in self.subscribe_turn(turn["id"], after_seq=after_seq):
            yield event

    async def cancel_turn(self, _turn_id: str) -> bool:
        return False


def _build_app():
    app = FastAPI()
    app.include_router(unified_ws.router, prefix="/api/v1")
    return app


def _install_runtime_manager(
    monkeypatch: pytest.MonkeyPatch,
    router: RuntimeRoutingTurnManager,
    *,
    context_builder_cls: type = MinimalContextBuilder,
) -> None:
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.get_llm_config",
        lambda: SimpleNamespace(max_tokens=4096),
    )
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.ContextBuilder",
        context_builder_cls,
    )
    monkeypatch.setattr("sparkweave.services.session.get_runtime_manager", lambda: router)


def test_unified_ws_start_turn_routes_langgraph_to_ng_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history.db")
    memory = FakeMemory()
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "hello ws",
                    "session_id": "ws-ng-session",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert events[0]["source"] == "langgraph"
    assert events[0]["session_id"] == "ws-ng-session"
    assert events[0]["metadata"]["runtime"] == "langgraph"
    assert events[1]["content"] == "Hello from /api/v1/ws via NG."
    assert events[2]["metadata"]["runtime"] == "langgraph"
    assert events[-1]["metadata"]["status"] == "completed"
    assert [event["seq"] for event in events] == [1, 2, 3, 4]

    assert len(runner.contexts) == 1
    context = runner.contexts[0]
    assert context.session_id == "ws-ng-session"
    assert context.user_message == "hello ws"
    assert context.config_overrides == {"_runtime": "langgraph"}
    assert context.memory_context == "## Memory\n- Use short answers."

    detail = asyncio.run(store.get_session_with_messages("ws-ng-session"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Hello from /api/v1/ws via NG."


def test_unified_ws_start_turn_uses_ng_runtime_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("SPARKWEAVE_RUNTIME", raising=False)
    monkeypatch.delenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", raising=False)
    store = create_session_store(tmp_path / "chat_history_ng_default.db")
    legacy = FailingLegacyRuntime()
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=legacy,
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "ng please",
                    "session_id": "ws-ng-default",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "langgraph"
    assert events[2]["metadata"]["runtime"] == "langgraph"
    assert len(runner.contexts) == 1

    detail = asyncio.run(store.get_session_with_messages("ws-ng-default"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Hello from /api/v1/ws via NG."


def test_unified_ws_legacy_env_falls_back_to_ng_when_legacy_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "legacy")
    monkeypatch.delenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", raising=False)
    store = create_session_store(tmp_path / "chat_history_legacy_env_fallback.db")
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=CompatibilityRuntimeUnavailable(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "legacy env should not break replacement runtime",
                    "session_id": "ws-legacy-env-fallback",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "langgraph"
    assert events[2]["metadata"]["runtime"] == "langgraph"
    assert len(runner.contexts) == 1
    assert runner.contexts[0].config_overrides == {}


def test_unified_ws_start_turn_uses_ng_under_auto_rollout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history_auto_rollout.db")
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "auto rollout",
                    "session_id": "ws-auto-rollout",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "langgraph"
    assert len(runner.contexts) == 1
    assert runner.contexts[0].config_overrides == {}


def test_unified_ws_auto_rollout_keeps_non_allowlisted_capability_on_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history_auto_non_allowlisted.db")
    legacy = RecordingLegacyRuntime(store)
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=legacy,
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "draw this via legacy",
                    "session_id": "ws-auto-non-allowlisted",
                    "capability": "visualize",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "legacy"
    assert events[2]["metadata"]["runtime"] == "legacy"
    assert len(legacy.start_payloads) == 1
    assert runner.contexts == []
    assert legacy.start_payloads[0]["capability"] == "visualize"


def test_unified_ws_auto_all_routes_migrated_capability_to_ng(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "all")
    store = create_session_store(tmp_path / "chat_history_auto_all.db")
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "solve with auto all",
                    "session_id": "ws-auto-all-deep-solve",
                    "capability": "deep_solve",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "content", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "langgraph"
    assert events[2]["metadata"]["runtime"] == "langgraph"
    assert len(runner.contexts) == 1
    assert runner.contexts[0].active_capability == "deep_solve"
    assert runner.contexts[0].config_overrides == {"detailed_answer": True}


def test_unified_ws_explicit_legacy_turn_supports_turn_and_session_subscribers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("SPARKWEAVE_RUNTIME", raising=False)
    monkeypatch.delenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", raising=False)
    store = create_session_store(tmp_path / "chat_history_legacy_stream.db")
    legacy = StreamingLegacyRuntime(store)
    router = RuntimeRoutingTurnManager(
        legacy=legacy,
        langgraph=LangGraphTurnRuntimeManager(
            store=store,
            runner=FakeLangGraphRunner(),
            memory_service=FakeMemory(),
        ),
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with (
            client.websocket_connect("/api/v1/ws") as primary,
            client.websocket_connect("/api/v1/ws") as turn_subscriber,
            client.websocket_connect("/api/v1/ws") as session_subscriber,
        ):
            primary.send_json(
                {
                    "type": "start_turn",
                    "content": "legacy mixed subscribers",
                    "session_id": "ws-legacy-stream",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "legacy"},
                }
            )
            primary_events = [primary.receive_json()]
            assert primary_events[0]["type"] == "session"
            turn_id = primary_events[0]["turn_id"]
            assert legacy.started.wait(timeout=2)

            turn_subscriber.send_json(
                {
                    "type": "subscribe_turn",
                    "turn_id": turn_id,
                    "after_seq": 1,
                }
            )
            session_subscriber.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-legacy-stream",
                    "after_seq": 1,
                }
            )

            legacy.release.set()
            for _ in range(3):
                primary_events.append(primary.receive_json())

            turn_events = [turn_subscriber.receive_json() for _ in range(3)]
            session_events = [session_subscriber.receive_json() for _ in range(3)]

    assert [event["type"] for event in primary_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["type"] for event in turn_events] == ["content", "result", "done"]
    assert [event["type"] for event in session_events] == ["content", "result", "done"]
    assert [event["seq"] for event in primary_events] == [1, 2, 3, 4]
    assert [event["seq"] for event in turn_events] == [2, 3, 4]
    assert [event["seq"] for event in session_events] == [2, 3, 4]
    assert turn_events[1]["metadata"]["runtime"] == "legacy"
    assert session_events[1]["metadata"]["runtime"] == "legacy"
    assert len(legacy.start_payloads) == 1


def test_unified_ws_start_turn_preserves_answer_now_context_for_ng_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_answer_now.db")
    memory = FakeMemory()
    runner = CapturingAnswerNowRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    answer_now_context = {
        "original_user_message": "Solve x^2 = 4",
        "partial_response": "We know x^2 = 4.",
        "events": [{"type": "stage_start", "stage": "solving", "content": ""}],
    }

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "answer now",
                    "session_id": "ws-ng-answer-now",
                    "capability": "deep_solve",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {
                        "_runtime": "langgraph",
                        "_persist_user_message": False,
                        "answer_now_context": answer_now_context,
                    },
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert events[2]["metadata"]["runtime"] == "langgraph"
    assert events[2]["metadata"]["answer_now"] is True
    assert "Solve x^2 = 4" in events[1]["content"]
    assert [event["seq"] for event in events] == [1, 2, 3, 4]

    assert len(runner.contexts) == 1
    context = runner.contexts[0]
    assert context.active_capability == "deep_solve"
    assert context.user_message == "answer now"
    assert context.config_overrides["_runtime"] == "langgraph"
    assert context.config_overrides["answer_now_context"] == answer_now_context
    assert context.memory_context == "## Memory\n- Use short answers."

    detail = asyncio.run(store.get_session_with_messages("ws-ng-answer-now"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["assistant"]
    assert "Solve x^2 = 4" in detail["messages"][0]["content"]


def test_unified_ws_cancel_turn_cancels_running_ng_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_cancel.db")
    memory = FakeMemory()
    runner = BlockingCancelRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "cancel me",
                    "session_id": "ws-ng-cancel",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            session_event = websocket.receive_json()
            assert session_event["type"] == "session"
            assert runner.started.wait(timeout=2)

            websocket.send_json(
                {"type": "cancel_turn", "turn_id": session_event["turn_id"]}
            )

            events = [session_event]
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == ["session", "error", "done"]
    assert events[1]["content"] == "Turn cancelled"
    assert events[1]["metadata"]["status"] == "cancelled"
    assert events[1]["metadata"]["turn_terminal"] is True
    assert events[2]["metadata"]["status"] == "cancelled"
    assert [event["seq"] for event in events] == [1, 2, 3]

    detail = asyncio.run(store.get_session_with_messages("ws-ng-cancel"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user"]
    turn = asyncio.run(store.get_turn(session_event["turn_id"]))
    assert turn is not None
    assert turn["status"] == "cancelled"


def test_unified_ws_resume_from_replays_remaining_ng_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_resume.db")
    memory = FakeMemory()
    runner = PauseAfterContentRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "resume me",
                    "session_id": "ws-ng-resume",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            session_event = websocket.receive_json()
            content_event = websocket.receive_json()
            assert session_event["type"] == "session"
            assert content_event["type"] == "content"
            assert content_event["seq"] == 2

            websocket.send_json({"type": "unsubscribe", "turn_id": session_event["turn_id"]})
            websocket.send_json(
                {
                    "type": "resume_from",
                    "turn_id": session_event["turn_id"],
                    "seq": 2,
                }
            )
            runner.release.set()

            replayed = []
            while True:
                event = websocket.receive_json()
                replayed.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in replayed] == ["result", "done"]
    assert [event["seq"] for event in replayed] == [3, 4]
    assert replayed[0]["metadata"]["runtime"] == "langgraph"
    assert replayed[1]["metadata"]["status"] == "completed"


def test_unified_ws_subscribe_session_receives_active_ng_turn_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_session_subscribe.db")
    memory = FakeMemory()
    runner = GateBeforeContentRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with (
            client.websocket_connect("/api/v1/ws") as primary,
            client.websocket_connect("/api/v1/ws") as session_subscriber,
        ):
            primary.send_json(
                {
                    "type": "start_turn",
                    "content": "session fanout",
                    "session_id": "ws-ng-session-subscribe",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            primary_events = [primary.receive_json()]
            assert primary_events[0]["type"] == "session"
            assert runner.started.wait(timeout=2)

            session_subscriber.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-ng-session-subscribe",
                    "after_seq": 0,
                }
            )
            subscriber_events = [session_subscriber.receive_json()]
            assert subscriber_events[0]["type"] == "session"
            assert subscriber_events[0]["turn_id"] == primary_events[0]["turn_id"]

            runner.release.set()
            for _ in range(3):
                primary_events.append(primary.receive_json())
                subscriber_events.append(session_subscriber.receive_json())

    assert [event["type"] for event in primary_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["type"] for event in subscriber_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["seq"] for event in primary_events] == [1, 2, 3, 4]
    assert [event["seq"] for event in subscriber_events] == [1, 2, 3, 4]
    assert subscriber_events[1]["content"] == "Session subscriber saw this."


def test_unified_ws_start_turn_bootstraps_followup_context_for_ng_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_followup.db")
    memory = FakeMemory()
    runner = FollowupContextRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(
        monkeypatch,
        router,
        context_builder_cls=StoreReadingContextBuilder,
    )

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "Why is my answer wrong?",
                    "session_id": "ws-ng-followup",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {
                        "_runtime": "langgraph",
                        "followup_question_context": {
                            "parent_quiz_session_id": "quiz_session_1",
                            "question_id": "q_2",
                            "question_type": "choice",
                            "difficulty": "hard",
                            "concentration": "density",
                            "question": "Which criterion best describes density?",
                            "options": {
                                "A": "Coverage",
                                "B": "Informative value",
                                "C": "Relevant content without redundancy",
                            },
                            "user_answer": "B",
                            "correct_answer": "C",
                            "explanation": "Density focuses on relevant non-redundant content.",
                        },
                    },
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["seq"] for event in events] == [1, 2, 3, 4]
    assert events[2]["metadata"]["runtime"] == "langgraph"

    assert len(runner.contexts) == 1
    context = runner.contexts[0]
    assert context.memory_context == "## Memory\n- Use short answers."
    assert context.metadata["question_followup_context"]["question_id"] == "q_2"
    assert "followup_question_context" not in context.config_overrides
    assert context.config_overrides["_runtime"] == "langgraph"
    assert context.conversation_history[0]["role"] == "system"
    assert "Question Follow-up Context" in context.conversation_history[0]["content"]
    assert "Which criterion best describes density?" in context.conversation_history[0]["content"]

    detail = asyncio.run(store.get_session_with_messages("ws-ng-followup"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["system", "user", "assistant"]
    assert "Question Follow-up Context" in detail["messages"][0]["content"]
    assert "User answer: B" in detail["messages"][0]["content"]


def test_unified_ws_start_turn_injects_notebook_and_history_context_for_ng_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_notebook_history.db")
    history = asyncio.run(store.create_session("Old lesson", session_id="session-old"))
    asyncio.run(store.add_message(history["id"], "user", "What is diagonalization?"))
    asyncio.run(
        store.add_message(
            history["id"],
            "assistant",
            "Diagonalization rewrites a matrix using eigenvectors.",
        )
    )

    calls: list[dict[str, Any]] = []

    class FakeNotebookAnalysisAgent:
        def __init__(self, language: str = "en") -> None:
            self.language = language

        async def analyze(self, *, user_question, records, emit=None):  # noqa: ANN001
            calls.append(
                {
                    "language": self.language,
                    "user_question": user_question,
                    "records": records,
                }
            )
            if emit is not None:
                await emit(
                    StreamEvent(
                        type=StreamEventType.PROGRESS,
                        source="notebook_analysis",
                        stage="observing",
                        content="grounding context",
                    )
                )
            if records[0].get("notebook_id") == "__history__":
                return "History says diagonalization depends on eigenvectors."
            return "Notebook says eigenvectors can simplify matrix powers."

    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.NotebookAnalysisAgent",
        FakeNotebookAnalysisAgent,
    )

    memory = FakeMemory()
    runner = NotebookContextRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
        notebook_manager=FakeNotebookManager(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "Explain matrix powers",
                    "session_id": "ws-ng-notebook-history",
                    "capability": "chat",
                    "tools": ["rag"],
                    "knowledge_bases": ["math-kb"],
                    "attachments": [],
                    "language": "en",
                    "notebook_references": [{"notebook_id": "nb1", "record_ids": ["rec-1"]}],
                    "history_references": ["session-old"],
                    "config": {"_runtime": "langgraph"},
                }
            )
            events = []
            while True:
                event = websocket.receive_json()
                events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in events] == [
        "session",
        "progress",
        "progress",
        "content",
        "result",
        "done",
    ]
    assert [event["source"] for event in events].count("notebook_analysis") == 2
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5, 6]

    assert len(calls) == 2
    assert len(runner.contexts) == 1
    context = runner.contexts[0]
    assert context.notebook_context == "Notebook says eigenvectors can simplify matrix powers."
    assert context.history_context == "History says diagonalization depends on eigenvectors."
    assert "[Notebook Context]" in context.user_message
    assert "[History Context]" in context.user_message
    assert "[User Question]\nExplain matrix powers" in context.user_message
    assert context.metadata["notebook_references"] == [
        {"notebook_id": "nb1", "record_ids": ["rec-1"]}
    ]
    assert context.metadata["history_references"] == ["session-old"]
    assert context.config_overrides == {"_runtime": "langgraph"}

    detail = asyncio.run(store.get_session_with_messages("ws-ng-notebook-history"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Use the saved context."


def test_unified_ws_multi_turn_followup_session_preserves_bootstrap_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_multiturn_followup.db")
    memory = FakeMemory()
    runner = SequencedRunner(
        [
            "Let's discuss this question.",
            "We can continue from the same quiz item.",
        ]
    )
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(
        monkeypatch,
        router,
        context_builder_cls=StoreReadingContextBuilder,
    )

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "Why is my answer wrong?",
                    "session_id": "ws-ng-multiturn-followup",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {
                        "_runtime": "langgraph",
                        "followup_question_context": {
                            "parent_quiz_session_id": "quiz_session_1",
                            "question_id": "q_2",
                            "question_type": "choice",
                            "difficulty": "hard",
                            "concentration": "density",
                            "question": "Which criterion best describes density?",
                            "options": {
                                "A": "Coverage",
                                "B": "Informative value",
                                "C": "Relevant content without redundancy",
                            },
                            "user_answer": "B",
                            "correct_answer": "C",
                            "explanation": "Density focuses on relevant non-redundant content.",
                        },
                    },
                }
            )
            first_events = []
            while True:
                event = websocket.receive_json()
                first_events.append(event)
                if event["type"] == "done":
                    break

            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "Can you explain the correct answer?",
                    "session_id": "ws-ng-multiturn-followup",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            second_events = []
            while True:
                event = websocket.receive_json()
                second_events.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in first_events] == ["session", "content", "result", "done"]
    assert [event["type"] for event in second_events] == ["session", "content", "result", "done"]

    assert len(runner.contexts) == 2
    first_context, second_context = runner.contexts
    assert first_context.metadata["question_followup_context"]["question_id"] == "q_2"
    assert second_context.metadata["question_followup_context"] == {}
    assert second_context.conversation_history[0]["role"] == "system"
    assert "Question Follow-up Context" in second_context.conversation_history[0]["content"]
    assert [item["role"] for item in second_context.conversation_history] == [
        "system",
        "user",
        "assistant",
    ]

    detail = asyncio.run(store.get_session_with_messages("ws-ng-multiturn-followup"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert sum(1 for message in detail["messages"] if message["role"] == "system") == 1
    assert detail["messages"][-1]["content"] == "We can continue from the same quiz item."


def test_unified_ws_resume_after_enrichment_events_replays_remaining_ng_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_enriched_reconnect.db")
    calls: list[dict[str, Any]] = []

    class FakeNotebookAnalysisAgent:
        def __init__(self, language: str = "en") -> None:
            self.language = language

        async def analyze(self, *, user_question, records, emit=None):  # noqa: ANN001
            calls.append(
                {
                    "language": self.language,
                    "user_question": user_question,
                    "records": records,
                }
            )
            if emit is not None:
                await emit(
                    StreamEvent(
                        type=StreamEventType.PROGRESS,
                        source="notebook_analysis",
                        stage="observing",
                        content="grounding context",
                    )
                )
            if records[0].get("notebook_id") == "__history__":
                return "History says diagonalization depends on eigenvectors."
            return "Notebook says eigenvectors can simplify matrix powers."

    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.NotebookAnalysisAgent",
        FakeNotebookAnalysisAgent,
    )

    history = asyncio.run(store.create_session("Old lesson", session_id="session-old"))
    asyncio.run(store.add_message(history["id"], "user", "What is diagonalization?"))
    asyncio.run(
        store.add_message(
            history["id"],
            "assistant",
            "Diagonalization rewrites a matrix using eigenvectors.",
        )
    )

    memory = FakeMemory()
    runner = GateBeforeContentRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
        notebook_manager=FakeNotebookManager(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as first_ws:
            first_ws.send_json(
                {
                    "type": "start_turn",
                    "content": "Explain matrix powers",
                    "session_id": "ws-ng-enriched-reconnect",
                    "capability": "chat",
                    "tools": ["rag"],
                    "knowledge_bases": ["math-kb"],
                    "attachments": [],
                    "language": "en",
                    "notebook_references": [{"notebook_id": "nb1", "record_ids": ["rec-1"]}],
                    "history_references": ["session-old"],
                    "config": {"_runtime": "langgraph"},
                }
            )
            first_events = [first_ws.receive_json(), first_ws.receive_json(), first_ws.receive_json()]

        turn_id = first_events[0]["turn_id"]

        with client.websocket_connect("/api/v1/ws") as second_ws:
            second_ws.send_json({"type": "resume_from", "turn_id": turn_id, "seq": 3})
            runner.release.set()
            replayed = []
            while True:
                event = second_ws.receive_json()
                replayed.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in first_events] == ["session", "progress", "progress"]
    assert [event["source"] for event in first_events].count("notebook_analysis") == 2
    assert [event["seq"] for event in first_events] == [1, 2, 3]
    assert [event["type"] for event in replayed] == ["content", "result", "done"]
    assert [event["seq"] for event in replayed] == [4, 5, 6]
    assert replayed[1]["metadata"]["runtime"] == "langgraph"
    assert len(calls) == 2

    detail = asyncio.run(store.get_session_with_messages("ws-ng-enriched-reconnect"))
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Session subscriber saw this."


def test_unified_ws_subscribe_session_replays_latest_completed_ng_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_completed_session_replay.db")
    memory = FakeMemory()
    runner = FakeLangGraphRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(
                {
                    "type": "start_turn",
                    "content": "replay this session",
                    "session_id": "ws-ng-completed-session-replay",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            first_run = []
            while True:
                event = websocket.receive_json()
                first_run.append(event)
                if event["type"] == "done":
                    break

        with client.websocket_connect("/api/v1/ws") as replay_ws:
            replay_ws.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-ng-completed-session-replay",
                    "after_seq": 1,
                }
            )
            replay = []
            while True:
                event = replay_ws.receive_json()
                replay.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in first_run] == ["session", "content", "result", "done"]
    assert [event["type"] for event in replay] == ["content", "result", "done"]
    assert [event["seq"] for event in replay] == [2, 3, 4]
    assert replay[1]["metadata"]["runtime"] == "langgraph"
    assert replay[2]["metadata"]["status"] == "completed"


def test_unified_ws_mixed_turn_and_session_subscribers_share_running_ng_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_mixed_subscribers.db")
    memory = FakeMemory()
    runner = GateBeforeContentRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with (
            client.websocket_connect("/api/v1/ws") as primary,
            client.websocket_connect("/api/v1/ws") as turn_subscriber,
            client.websocket_connect("/api/v1/ws") as session_subscriber,
        ):
            primary.send_json(
                {
                    "type": "start_turn",
                    "content": "mixed subscribers",
                    "session_id": "ws-ng-mixed-subscribers",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            primary_events = [primary.receive_json()]
            assert primary_events[0]["type"] == "session"
            turn_id = primary_events[0]["turn_id"]
            assert runner.started.wait(timeout=2)

            turn_subscriber.send_json(
                {
                    "type": "subscribe_turn",
                    "turn_id": turn_id,
                    "after_seq": 1,
                }
            )
            session_subscriber.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-ng-mixed-subscribers",
                    "after_seq": 1,
                }
            )

            runner.release.set()
            for _ in range(3):
                primary_events.append(primary.receive_json())

            turn_events = []
            session_events = []
            while len(turn_events) < 3:
                turn_events.append(turn_subscriber.receive_json())
            while len(session_events) < 3:
                session_events.append(session_subscriber.receive_json())

    assert [event["type"] for event in primary_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["type"] for event in turn_events] == ["content", "result", "done"]
    assert [event["type"] for event in session_events] == ["content", "result", "done"]
    assert [event["seq"] for event in primary_events] == [1, 2, 3, 4]
    assert [event["seq"] for event in turn_events] == [2, 3, 4]
    assert [event["seq"] for event in session_events] == [2, 3, 4]
    assert turn_events[0]["content"] == "Session subscriber saw this."
    assert session_events[0]["content"] == "Session subscriber saw this."


def test_unified_ws_resume_after_cancel_replays_cancelled_ng_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_cancel_reconnect.db")
    runner = BlockingCancelRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as first_ws:
            first_ws.send_json(
                {
                    "type": "start_turn",
                    "content": "cancel then replay",
                    "session_id": "ws-cancel-reconnect",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            first_event = first_ws.receive_json()
            assert first_event["type"] == "session"
            assert runner.started.wait(timeout=2)

        turn_id = first_event["turn_id"]

        with client.websocket_connect("/api/v1/ws") as cancel_ws:
            cancel_ws.send_json({"type": "cancel_turn", "turn_id": turn_id})

        with client.websocket_connect("/api/v1/ws") as replay_ws:
            replay_ws.send_json({"type": "resume_from", "turn_id": turn_id, "seq": 1})
            replay = []
            while True:
                event = replay_ws.receive_json()
                replay.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in replay] == ["error", "done"]
    assert [event["seq"] for event in replay] == [2, 3]
    assert replay[0]["content"] == "Turn cancelled"
    assert replay[0]["metadata"]["status"] == "cancelled"
    assert replay[1]["metadata"]["status"] == "cancelled"


def test_unified_ws_cancel_detached_running_ng_turn_replays_terminal_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_detached_cancel.db")
    session = asyncio.run(
        store.create_session(
            "Detached cancel",
            session_id="ws-detached-cancel",
        )
    )
    turn = asyncio.run(store.create_turn(session["id"], capability="chat"))
    asyncio.run(
        store.append_turn_event(
            turn["id"],
            {
                "type": "session",
                "source": "langgraph",
                "session_id": session["id"],
                "turn_id": turn["id"],
                "metadata": {"runtime": "langgraph"},
            },
        )
    )

    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeLangGraphRunner(),
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json({"type": "cancel_turn", "turn_id": turn["id"]})
            websocket.send_json({"type": "resume_from", "turn_id": turn["id"], "seq": 1})
            replay = []
            while True:
                event = websocket.receive_json()
                replay.append(event)
                if event["type"] == "done":
                    break

    stored_turn = asyncio.run(store.get_turn(turn["id"]))

    assert stored_turn is not None
    assert stored_turn["status"] == "cancelled"
    assert stored_turn["error"] == "Turn cancelled"
    assert [event["seq"] for event in replay] == [2, 3]
    assert [event["type"] for event in replay] == ["error", "done"]
    assert replay[0]["content"] == "Turn cancelled"
    assert replay[0]["metadata"]["status"] == "cancelled"
    assert replay[1]["metadata"]["status"] == "cancelled"


def test_unified_ws_resume_connection_receives_cancelled_ng_turn_live(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_cancel_race.db")
    runner = BlockingCancelRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as start_ws:
            start_ws.send_json(
                {
                    "type": "start_turn",
                    "content": "cancel while resumed subscriber waits",
                    "session_id": "ws-cancel-race",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            first_event = start_ws.receive_json()
            assert first_event["type"] == "session"
            assert runner.started.wait(timeout=2)

        turn_id = first_event["turn_id"]

        with (
            client.websocket_connect("/api/v1/ws") as replay_ws,
            client.websocket_connect("/api/v1/ws") as cancel_ws,
        ):
            replay_ws.send_json({"type": "resume_from", "turn_id": turn_id, "seq": 1})
            cancel_ws.send_json({"type": "cancel_turn", "turn_id": turn_id})

            replay = []
            while True:
                event = replay_ws.receive_json()
                replay.append(event)
                if event["type"] == "done":
                    break

    assert [event["type"] for event in replay] == ["error", "done"]
    assert [event["seq"] for event in replay] == [2, 3]
    assert replay[0]["metadata"]["status"] == "cancelled"
    assert replay[1]["metadata"]["status"] == "cancelled"


def test_unified_ws_concurrent_legacy_and_ng_sessions_do_not_cross_streams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_multi_session.db")
    legacy = StreamingLegacyRuntime(store)
    ng_runner = GateBeforeContentRunner()
    router = RuntimeRoutingTurnManager(
        legacy=legacy,
        langgraph=LangGraphTurnRuntimeManager(
            store=store,
            runner=ng_runner,
            memory_service=FakeMemory(),
        ),
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with (
            client.websocket_connect("/api/v1/ws") as legacy_primary,
            client.websocket_connect("/api/v1/ws") as ng_primary,
            client.websocket_connect("/api/v1/ws") as legacy_session_subscriber,
            client.websocket_connect("/api/v1/ws") as ng_session_subscriber,
        ):
            legacy_primary.send_json(
                {
                    "type": "start_turn",
                    "content": "legacy session stream",
                    "session_id": "ws-legacy-multi",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "legacy"},
                }
            )
            ng_primary.send_json(
                {
                    "type": "start_turn",
                    "content": "ng session stream",
                    "session_id": "ws-ng-multi",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )

            legacy_first = legacy_primary.receive_json()
            ng_first = ng_primary.receive_json()
            assert legacy_first["type"] == "session"
            assert ng_first["type"] == "session"
            assert legacy.started.wait(timeout=2)
            assert ng_runner.started.wait(timeout=2)

            legacy_session_subscriber.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-legacy-multi",
                    "after_seq": 1,
                }
            )
            ng_session_subscriber.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-ng-multi",
                    "after_seq": 1,
                }
            )

            legacy.release.set()
            ng_runner.release.set()

            legacy_primary_events = [legacy_first] + [legacy_primary.receive_json() for _ in range(3)]
            ng_primary_events = [ng_first] + [ng_primary.receive_json() for _ in range(3)]
            legacy_session_events = [legacy_session_subscriber.receive_json() for _ in range(3)]
            ng_session_events = [ng_session_subscriber.receive_json() for _ in range(3)]

    assert [event["type"] for event in legacy_primary_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["type"] for event in ng_primary_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    assert [event["type"] for event in legacy_session_events] == ["content", "result", "done"]
    assert [event["type"] for event in ng_session_events] == ["content", "result", "done"]
    assert legacy_session_events[0]["content"] == "Streaming from legacy runtime."
    assert ng_session_events[0]["content"] == "Session subscriber saw this."
    assert legacy_session_events[1]["metadata"]["runtime"] == "legacy"
    assert ng_session_events[1]["metadata"]["runtime"] == "langgraph"


def test_unified_ws_cancel_broadcasts_to_turn_session_and_resume_subscribers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_history_cancel_multi_subscribers.db")
    runner = BlockingCancelRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    router = RuntimeRoutingTurnManager(
        legacy=FailingLegacyRuntime(),
        langgraph=ng_runtime,
        store=store,
    )
    _install_runtime_manager(monkeypatch, router)

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/ws") as start_ws:
            start_ws.send_json(
                {
                    "type": "start_turn",
                    "content": "cancel all subscribers",
                    "session_id": "ws-cancel-all-subscribers",
                    "capability": "chat",
                    "tools": [],
                    "knowledge_bases": [],
                    "attachments": [],
                    "language": "en",
                    "config": {"_runtime": "langgraph"},
                }
            )
            first_event = start_ws.receive_json()
            assert first_event["type"] == "session"
            assert runner.started.wait(timeout=2)

        turn_id = first_event["turn_id"]

        with (
            client.websocket_connect("/api/v1/ws") as turn_ws,
            client.websocket_connect("/api/v1/ws") as session_ws,
            client.websocket_connect("/api/v1/ws") as resume_ws,
            client.websocket_connect("/api/v1/ws") as cancel_ws,
        ):
            turn_ws.send_json({"type": "subscribe_turn", "turn_id": turn_id, "after_seq": 1})
            session_ws.send_json(
                {
                    "type": "subscribe_session",
                    "session_id": "ws-cancel-all-subscribers",
                    "after_seq": 1,
                }
            )
            resume_ws.send_json({"type": "resume_from", "turn_id": turn_id, "seq": 1})
            cancel_ws.send_json({"type": "cancel_turn", "turn_id": turn_id})

            turn_events = []
            session_events = []
            resume_events = []
            while len(turn_events) < 2:
                turn_events.append(turn_ws.receive_json())
            while len(session_events) < 2:
                session_events.append(session_ws.receive_json())
            while len(resume_events) < 2:
                resume_events.append(resume_ws.receive_json())

    for events in (turn_events, session_events, resume_events):
        assert [event["type"] for event in events] == ["error", "done"]
        assert [event["seq"] for event in events] == [2, 3]
        assert events[0]["content"] == "Turn cancelled"
        assert events[0]["metadata"]["status"] == "cancelled"
        assert events[1]["metadata"]["status"] == "cancelled"



