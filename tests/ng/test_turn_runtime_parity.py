from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from sparkweave.core.contracts import StreamEvent, StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphTurnRuntimeManager
from sparkweave.services.session import create_session_store
from sparkweave.services.session_store import SQLiteSessionStore


class FakeMemory:
    def __init__(self, context: str = "") -> None:
        self.context = context
        self.refresh_calls: list[dict[str, Any]] = []

    def build_memory_context(self) -> str:
        return self.context

    async def refresh_from_turn(self, **kwargs: Any) -> None:
        self.refresh_calls.append(kwargs)


class FakeContextBuilder:
    def __init__(self, store: SQLiteSessionStore, *_args: Any, **_kwargs: Any) -> None:
        self.store = store

    async def build(self, **kwargs: Any) -> SimpleNamespace:
        messages = await self.store.get_messages_for_context(kwargs["session_id"])
        on_event = kwargs.get("on_event")
        if on_event is not None:
            await on_event(
                StreamEvent(
                    type=StreamEventType.PROGRESS,
                    source="context_builder",
                    stage="build_context",
                    content="bounded history ready",
                )
            )
        conversation_history = [
            {"role": item["role"], "content": item["content"]}
            for item in messages
            if str(item.get("content", "") or "").strip()
        ]
        return SimpleNamespace(
            conversation_history=conversation_history,
            conversation_summary="Summary snapshot",
            context_text="Context text snapshot",
            token_count=12,
            budget=256,
        )


class FakeNotebookManager:
    def get_records_by_references(self, _references: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "rec-1",
                "notebook_id": "nb1",
                "notebook_name": "Notebook",
                "title": "Saved matrix note",
                "summary": "Eigenvectors and matrix powers.",
                "output": "Matrix powers are easier after diagonalization.",
            }
        ]


class FakeNotebookAnalysisAgent:
    def __init__(self, language: str = "en") -> None:
        self.language = language

    async def analyze(
        self,
        *,
        user_question: str,
        records: list[dict[str, Any]],
        emit: Any = None,
    ) -> str:
        if emit is not None:
            await emit(
                StreamEvent(
                    type=StreamEventType.PROGRESS,
                    source="notebook_analysis",
                    stage="observing",
                    content="analysis ready",
                    metadata={"record_count": len(records)},
                )
            )
        if records and records[0].get("notebook_id") == "__history__":
            return "History context: diagonalization came up earlier."
        return "Notebook context: matrix powers use eigenvectors."


class CapturingNgRunner:
    def __init__(self, contexts: list[UnifiedContext]) -> None:
        self.contexts = contexts

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content="Parity reply.",
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


def _install_ng_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.ContextBuilder",
        FakeContextBuilder,
    )
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.get_llm_config",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.NotebookAnalysisAgent",
        FakeNotebookAnalysisAgent,
    )


async def _run_ng_turn(
    *,
    store: SQLiteSessionStore,
    payload: dict[str, Any],
    memory: FakeMemory,
    captured_contexts: list[UnifiedContext],
) -> dict[str, Any]:
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=CapturingNgRunner(captured_contexts),
        memory_service=memory,
        notebook_manager=FakeNotebookManager(),
    )
    result = await runtime.run_turn(deepcopy(payload))
    detail = await store.get_session_with_messages(result.session["id"])
    assert captured_contexts
    assert detail is not None
    return {
        "context": captured_contexts[-1],
        "detail": detail,
        "events": result.events,
        "runtime": runtime,
        "turn": result.turn,
        "turn_id": result.turn["id"],
    }


def _context_snapshot(context: UnifiedContext) -> dict[str, Any]:
    return {
        "user_message": context.user_message,
        "conversation_history": context.conversation_history,
        "config_overrides": context.config_overrides,
        "notebook_context": context.notebook_context,
        "history_context": context.history_context,
        "memory_context": context.memory_context,
        "question_followup_context": context.metadata.get("question_followup_context"),
        "notebook_references": context.metadata.get("notebook_references"),
        "history_references": context.metadata.get("history_references"),
        "conversation_context_text": context.metadata.get("conversation_context_text"),
        "history_token_count": context.metadata.get("history_token_count"),
        "history_budget": context.metadata.get("history_budget"),
    }


def _message_snapshot(detail: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (str(message["role"]), str(message["content"]))
        for message in detail["messages"]
    ]


def _replay_snapshot(events: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [
        (
            str(event.get("type") or ""),
            str(event.get("stage") or ""),
            str(event.get("content") or ""),
        )
        for event in events
    ]


async def _collect_until_done(runtime: Any, turn_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async for event in runtime.subscribe_turn(turn_id, after_seq=0):
        events.append(event)
        if event["type"] == "done":
            break
    return events


@pytest.mark.asyncio
async def test_ng_turn_runtime_preserves_followup_memory_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _install_ng_fakes(monkeypatch)
    ng_contexts: list[UnifiedContext] = []
    payload = {
        "type": "start_turn",
        "content": "Why is my answer wrong?",
        "session_id": None,
        "capability": "chat",
        "tools": [],
        "knowledge_bases": [],
        "attachments": [],
        "language": "en",
        "config": {
            "followup_question_context": {
                "parent_quiz_session_id": "quiz-session-1",
                "question_id": "q-2",
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
                "is_correct": False,
                "explanation": "Density focuses on relevant non-redundant content.",
                "knowledge_context": "Density means relevant content without repetition.",
            }
        },
    }

    ng = await _run_ng_turn(
        store=create_session_store(tmp_path / "ng_followup.db"),
        payload=payload,
        memory=FakeMemory("## Memory\n- Prefer concise examples."),
        captured_contexts=ng_contexts,
    )

    snapshot = _context_snapshot(ng["context"])
    assert snapshot["user_message"] == "Why is my answer wrong?"
    assert [item["role"] for item in snapshot["conversation_history"]] == ["system"]
    assert "Which criterion best describes density?" in snapshot["conversation_history"][0]["content"]
    assert snapshot["config_overrides"] == {}
    assert snapshot["memory_context"] == "## Memory\n- Prefer concise examples."
    assert snapshot["question_followup_context"]["question_id"] == "q-2"
    assert snapshot["question_followup_context"]["options"] == {
        "A": "Coverage",
        "B": "Informative value",
        "C": "Relevant content without redundancy",
    }
    assert snapshot["notebook_references"] == []
    assert snapshot["history_references"] == []
    assert snapshot["conversation_context_text"] == "Context text snapshot"
    assert snapshot["history_token_count"] == 12
    assert snapshot["history_budget"] == 256
    assert ng["turn"]["status"] == "completed"
    assert "followup_question_context" not in ng["context"].config_overrides
    assert "Question Follow-up Context" in ng["detail"]["messages"][0]["content"]
    assert _message_snapshot(ng["detail"])[-1] == ("assistant", "Parity reply.")


@pytest.mark.asyncio
async def test_ng_turn_runtime_preserves_notebook_history_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _install_ng_fakes(monkeypatch)
    ng_contexts: list[UnifiedContext] = []
    payload = {
        "type": "start_turn",
        "content": "Explain matrix powers",
        "session_id": None,
        "capability": "chat",
        "tools": ["rag"],
        "knowledge_bases": ["math-kb"],
        "attachments": [],
        "language": "en",
        "notebook_references": [{"notebook_id": "nb1", "record_ids": ["rec-1"]}],
        "history_references": ["history-session"],
        "config": {},
    }
    ng_store = create_session_store(tmp_path / "ng_notebook_history.db")
    history = await ng_store.create_session("Old matrix lesson", session_id="history-session")
    await ng_store.add_message(history["id"], "user", "What is diagonalization?")
    await ng_store.add_message(
        history["id"],
        "assistant",
        "Diagonalization rewrites a matrix using eigenvectors.",
    )

    ng = await _run_ng_turn(
        store=ng_store,
        payload=payload,
        memory=FakeMemory("## Memory\n- Use saved course notes."),
        captured_contexts=ng_contexts,
    )

    assert ng["context"].conversation_history == []
    assert ng["detail"]["preferences"] == {
        "capability": "chat",
        "language": "en",
        "tools": ["rag"],
        "knowledge_bases": ["math-kb"],
    }
    assert [event["source"] for event in ng["events"]].count("notebook_analysis") == 2
    assert "[Notebook Context]" in ng["context"].user_message
    assert "[History Context]" in ng["context"].user_message
    assert ng["context"].notebook_context == "Notebook context: matrix powers use eigenvectors."
    assert ng["context"].history_context == "History context: diagonalization came up earlier."


@pytest.mark.asyncio
async def test_ng_turn_runtime_preserves_answer_now_context_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _install_ng_fakes(monkeypatch)
    ng_contexts: list[UnifiedContext] = []
    answer_now_context = {
        "original_user_message": "Solve x^2 = 4",
        "partial_response": "We know x^2 = 4.",
        "events": [
            {
                "type": "stage_start",
                "stage": "solving",
                "content": "",
            }
        ],
    }
    payload = {
        "type": "start_turn",
        "content": "answer now",
        "session_id": None,
        "capability": "deep_solve",
        "tools": [],
        "knowledge_bases": [],
        "attachments": [],
        "language": "en",
        "config": {
            "answer_now_context": answer_now_context,
            "_persist_user_message": False,
        },
    }

    ng = await _run_ng_turn(
        store=create_session_store(tmp_path / "ng_answer_now.db"),
        payload=payload,
        memory=FakeMemory(),
        captured_contexts=ng_contexts,
    )

    assert ng["context"].config_overrides["answer_now_context"] == answer_now_context
    assert [role for role, _content in _message_snapshot(ng["detail"])] == ["assistant"]
    assert ng["turn"]["status"] == "completed"


@pytest.mark.asyncio
async def test_ng_turn_runtime_completed_turn_replay_after_seq(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _install_ng_fakes(monkeypatch)
    ng_contexts: list[UnifiedContext] = []
    payload = {
        "type": "start_turn",
        "content": "Replay this turn",
        "session_id": None,
        "capability": "chat",
        "tools": [],
        "knowledge_bases": [],
        "attachments": [],
        "language": "en",
        "config": {},
    }
    ng = await _run_ng_turn(
        store=create_session_store(tmp_path / "ng_replay.db"),
        payload=payload,
        memory=FakeMemory(),
        captured_contexts=ng_contexts,
    )

    replay = [
        event
        async for event in ng["runtime"].subscribe_turn(ng["turn_id"], after_seq=1)
    ]

    assert _replay_snapshot(replay) == [
        ("progress", "build_context", "bounded history ready"),
        ("content", "responding", "Parity reply."),
        ("done", "", ""),
    ]
    assert [event["seq"] for event in replay] == [2, 3, 4]


@pytest.mark.asyncio
async def test_ng_turn_runtime_cancelled_live_turn_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _install_ng_fakes(monkeypatch)
    ng_started = asyncio.Event()
    ng_contexts: list[UnifiedContext] = []

    class BlockingNgRunner:
        async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
            ng_contexts.append(context)
            yield StreamEvent(
                type=StreamEventType.SESSION,
                source="langgraph",
                metadata={"runtime": "langgraph"},
            )
            ng_started.set()
            await asyncio.Event().wait()
            yield StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="unreachable",
            )

    payload = {
        "type": "start_turn",
        "content": "cancel me",
        "session_id": None,
        "capability": "chat",
        "tools": [],
        "knowledge_bases": [],
        "attachments": [],
        "language": "en",
        "config": {},
    }
    ng_store = create_session_store(tmp_path / "ng_cancel.db")
    ng_runtime = LangGraphTurnRuntimeManager(
        store=ng_store,
        runner=BlockingNgRunner(),
        memory_service=FakeMemory(),
    )
    ng_session, ng_turn = await ng_runtime.start_turn(deepcopy(payload))
    await asyncio.wait_for(ng_started.wait(), timeout=2)

    assert await ng_runtime.cancel_turn(ng_turn["id"]) is True
    ng_events = await asyncio.wait_for(
        _collect_until_done(ng_runtime, ng_turn["id"]),
        timeout=2,
    )

    ng_detail = await ng_store.get_session_with_messages(ng_session["id"])
    ng_persisted_turn = await ng_store.get_turn(ng_turn["id"])

    assert ng_contexts
    assert ng_persisted_turn is not None
    assert ng_persisted_turn["status"] == "cancelled"
    assert ng_persisted_turn["error"] == "Turn cancelled"
    assert [event["type"] for event in ng_events][-2:] == ["error", "done"]
    assert ng_events[-2]["content"] == "Turn cancelled"
    assert ng_events[-2]["metadata"]["status"] == "cancelled"
    assert ng_events[-1]["metadata"]["status"] == "cancelled"
    assert ng_detail is not None
    assert _message_snapshot(ng_detail) == [("user", "cancel me")]

