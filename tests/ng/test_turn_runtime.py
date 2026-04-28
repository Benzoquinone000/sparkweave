from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from sparkweave.core.contracts import StreamEvent, StreamEventType, UnifiedContext
from sparkweave.runtime import LangGraphTurnRuntimeManager
from sparkweave.services.session import create_session_store


class FakeMemory:
    def __init__(self, context: str = "") -> None:
        self.calls: list[dict] = []
        self.context = context

    def build_memory_context(self) -> str:
        return self.context

    async def refresh_from_turn(self, **kwargs) -> None:
        self.calls.append(kwargs)


class FakeRunner:
    def __init__(self, events: list[StreamEvent]) -> None:
        self.events = events
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        for event in self.events:
            yield event


class StreamingRunner:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext) -> AsyncIterator[StreamEvent]:
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.SESSION,
            source="langgraph",
            metadata={"runtime": "langgraph"},
        )
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content="first",
        )
        await self.release.wait()
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content=" second",
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


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_persists_successful_turn(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    memory = FakeMemory()
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.SESSION,
                source="langgraph",
                metadata={"runtime": "langgraph"},
            ),
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Hello from NG.",
            ),
            StreamEvent(
                type=StreamEventType.RESULT,
                source="chat",
                metadata={"response": "Hello from NG.", "runtime": "langgraph"},
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )

    result = await runtime.run_turn(
        {
            "content": "hello",
            "session_id": "session-ng",
            "capability": "chat",
            "tools": ["rag"],
            "knowledge_bases": ["kb"],
            "attachments": [{"type": "image", "filename": "frame.png"}],
            "language": "zh",
            "config": {"_runtime": "langgraph"},
        }
    )

    detail = await store.get_session_with_messages("session-ng")
    persisted_events = await store.get_turn_events(result.turn["id"])

    assert result.turn["status"] == "completed"
    assert result.assistant_content == "Hello from NG."
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["events"][0]["type"] == "content"
    assert [event["type"] for event in persisted_events] == [
        "session",
        "content",
        "result",
        "done",
    ]
    context = runner.contexts[0]
    assert context.session_id == "session-ng"
    assert context.metadata["turn_id"] == result.turn["id"]
    assert context.metadata["runtime"] == "langgraph"
    assert context.enabled_tools == ["rag"]
    assert context.knowledge_bases == ["kb"]
    assert context.attachments[0].filename == "frame.png"
    assert context.config_overrides == {"_runtime": "langgraph"}
    assert memory.calls[0]["assistant_message"] == "Hello from NG."
    assert memory.calls[0]["language"] == "zh"


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_persists_delegated_result_only_artifact(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    memory = FakeMemory()
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.STAGE_START,
                source="dialogue_coordinator",
                stage="coordinating",
                metadata={
                    "trace_kind": "coordinator_decision",
                    "capability": "math_animator",
                    "delegated": True,
                },
            ),
            StreamEvent(
                type=StreamEventType.PROGRESS,
                source="dialogue_coordinator",
                stage="coordinating",
                content="Awakened Math Animation Agent.",
                metadata={
                    "trace_kind": "agent_handoff",
                    "target_capability": "math_animator",
                },
            ),
            StreamEvent(
                type=StreamEventType.RESULT,
                source="math_animator",
                metadata={
                    "response": "动画已生成。",
                    "output_mode": "video",
                    "artifacts": [
                        {
                            "type": "video",
                            "url": "/media/math/demo.mp4",
                            "filename": "demo.mp4",
                        }
                    ],
                    "code": {"language": "python", "content": "from manim import *"},
                    "runtime": "langgraph",
                },
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )

    result = await runtime.run_turn(
        {
            "content": "请生成一个极限动画讲解",
            "session_id": "session-delegated-artifact",
            "capability": "chat",
        }
    )

    detail = await store.get_session_with_messages("session-delegated-artifact")

    assert result.assistant_content == "动画已生成。"
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "动画已生成。"
    assert detail["messages"][1]["capability"] == "math_animator"
    assert detail["messages"][1]["events"][-1]["source"] == "math_animator"
    assert detail["messages"][1]["events"][-1]["metadata"]["artifacts"][0]["filename"] == "demo.mp4"
    assert memory.calls[0]["capability"] == "math_animator"


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_marks_error_turn_failed(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.ERROR,
                source="langgraph",
                content="boom",
            ),
            StreamEvent(
                type=StreamEventType.DONE,
                source="langgraph",
                metadata={"status": "failed"},
            ),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(store=store, runner=runner, memory_service=FakeMemory())

    result = await runtime.run_turn({"content": "hello", "capability": "chat"})

    assert result.turn["status"] == "failed"
    assert result.turn["error"] == "boom"
    assert result.assistant_content == ""
    detail = await store.get_session_with_messages(result.session["id"])
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user"]


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_passes_prior_history_to_context(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    session = await store.create_session("Existing", session_id="session-history")
    await store.add_message(session["id"], "user", "first question")
    await store.add_message(session["id"], "assistant", "first answer")
    runner = FakeRunner([StreamEvent(type=StreamEventType.DONE, source="langgraph")])
    runtime = LangGraphTurnRuntimeManager(store=store, runner=runner, memory_service=FakeMemory())

    await runtime.run_turn(
        {
            "session_id": "session-history",
            "content": "second question",
            "capability": "chat",
            "config": {"_persist_user_message": False},
        }
    )

    assert runner.contexts[0].conversation_history == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    detail = await store.get_session_with_messages("session-history")
    assert detail is not None
    assert [message["content"] for message in detail["messages"]] == [
        "first question",
        "first answer",
    ]


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_bootstraps_followup_and_memory_context(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    memory = FakeMemory(context="## Memory\n- Prefer concise examples.")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Let's inspect the quiz item.",
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=memory,
    )

    result = await runtime.run_turn(
        {
            "content": "Why is my answer wrong?",
            "session_id": "session-followup",
            "capability": "chat",
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
                    "is_correct": False,
                    "explanation": "Density focuses on relevant non-redundant content.",
                },
            },
        }
    )

    context = runner.contexts[0]
    detail = await store.get_session_with_messages("session-followup")

    assert result.turn["status"] == "completed"
    assert context.memory_context == "## Memory\n- Prefer concise examples."
    assert context.metadata["memory_context"] == "## Memory\n- Prefer concise examples."
    assert context.metadata["question_followup_context"]["question_id"] == "q_2"
    assert "followup_question_context" not in context.config_overrides
    assert context.config_overrides["_runtime"] == "langgraph"
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == [
        "system",
        "user",
        "assistant",
    ]
    assert "Question Follow-up Context" in detail["messages"][0]["content"]
    assert "Which criterion best describes density?" in detail["messages"][0]["content"]


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_injects_notebook_and_history_context(
    monkeypatch,
    tmp_path,
):
    store = create_session_store(tmp_path / "chat_history.db")
    history_session = await store.create_session("Old lesson", session_id="session-old")
    await store.add_message(history_session["id"], "user", "What is diagonalization?")
    await store.add_message(
        history_session["id"],
        "assistant",
        "Diagonalization rewrites a matrix using eigenvectors.",
    )
    calls: list[dict] = []

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
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Use the saved context.",
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
        notebook_manager=FakeNotebookManager(),
    )

    result = await runtime.run_turn(
        {
            "content": "Explain matrix powers",
            "session_id": "session-with-context",
            "capability": "chat",
            "notebook_references": [{"notebook_id": "nb1", "record_ids": ["rec-1"]}],
            "history_references": ["session-old"],
            "config": {"_runtime": "langgraph"},
        }
    )

    context = runner.contexts[0]

    assert len(calls) == 2
    assert context.notebook_context == "Notebook says eigenvectors can simplify matrix powers."
    assert context.history_context == "History says diagonalization depends on eigenvectors."
    assert "[Notebook Context]" in context.user_message
    assert "[History Context]" in context.user_message
    assert "[User Question]\nExplain matrix powers" in context.user_message
    assert context.metadata["notebook_references"] == [
        {"notebook_id": "nb1", "record_ids": ["rec-1"]}
    ]
    assert context.metadata["history_references"] == ["session-old"]
    assert [event["source"] for event in result.events].count("notebook_analysis") == 2


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_start_turn_streams_live_events(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    runner = StreamingRunner()
    runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )

    session, turn = await runtime.start_turn(
        {
            "content": "go live",
            "session_id": "session-live",
            "capability": "chat",
        }
    )

    async def collect_events() -> list[dict]:
        events: list[dict] = []
        async for event in runtime.subscribe_turn(turn["id"], after_seq=0):
            events.append(event)
            if event["type"] == "content" and event["content"] == "first":
                runner.release.set()
            if event["type"] == "done":
                break
        return events

    events = await asyncio.wait_for(collect_events(), timeout=2)

    stored_turn = await store.get_turn(turn["id"])
    for _ in range(20):
        if stored_turn is not None and stored_turn["status"] == "completed":
            break
        await asyncio.sleep(0.01)
        stored_turn = await store.get_turn(turn["id"])

    assert session["id"] == "session-live"
    assert runner.contexts[0].metadata["turn_id"] == turn["id"]
    assert [event["type"] for event in events] == [
        "session",
        "content",
        "content",
        "done",
    ]
    assert [event["content"] for event in events if event["type"] == "content"] == [
        "first",
        " second",
    ]
    assert [event["seq"] for event in events] == [1, 2, 3, 4]
    assert stored_turn is not None
    assert stored_turn["status"] == "completed"
    detail = await store.get_session_with_messages("session-live")
    assert detail is not None
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "first second"


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_subscribe_replays_completed_events(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.SESSION,
                source="langgraph",
                metadata={"runtime": "langgraph"},
            ),
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Replay me.",
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(store=store, runner=runner, memory_service=FakeMemory())

    result = await runtime.run_turn({"content": "hello", "capability": "chat"})

    replay = [
        event
        async for event in runtime.subscribe_turn(result.turn["id"], after_seq=1)
    ]

    assert [event["seq"] for event in replay] == [2, 3]
    assert [event["type"] for event in replay] == ["content", "done"]


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_subscribe_session_replays_latest_completed_turn(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    runner = FakeRunner(
        [
            StreamEvent(
                type=StreamEventType.SESSION,
                source="langgraph",
                metadata={"runtime": "langgraph"},
            ),
            StreamEvent(
                type=StreamEventType.CONTENT,
                source="chat",
                stage="responding",
                content="Replay latest session turn.",
            ),
            StreamEvent(
                type=StreamEventType.RESULT,
                source="chat",
                metadata={"response": "Replay latest session turn.", "runtime": "langgraph"},
            ),
            StreamEvent(type=StreamEventType.DONE, source="langgraph"),
        ]
    )
    runtime = LangGraphTurnRuntimeManager(store=store, runner=runner, memory_service=FakeMemory())

    result = await runtime.run_turn(
        {"content": "hello", "session_id": "session-replay", "capability": "chat"}
    )

    replay = [
        event
        async for event in runtime.subscribe_session(result.session["id"], after_seq=1)
    ]

    assert [event["seq"] for event in replay] == [2, 3, 4]
    assert [event["type"] for event in replay] == ["content", "result", "done"]


@pytest.mark.asyncio
async def test_langgraph_turn_runtime_cancel_detached_running_turn_persists_terminal_replay(
    tmp_path,
):
    store = create_session_store(tmp_path / "chat_history.db")
    session = await store.create_session("Detached turn", session_id="session-detached-cancel")
    turn = await store.create_turn(session["id"], capability="chat")
    await store.append_turn_event(
        turn["id"],
        {
            "type": "session",
            "source": "langgraph",
            "metadata": {"runtime": "langgraph"},
        },
    )
    runtime = LangGraphTurnRuntimeManager(store=store, runner=FakeRunner([]), memory_service=FakeMemory())

    cancelled = await runtime.cancel_turn(turn["id"])
    replay = [
        event
        async for event in runtime.subscribe_turn(turn["id"], after_seq=1)
    ]
    stored_turn = await store.get_turn(turn["id"])
    detail = await store.get_session_with_messages("session-detached-cancel")

    assert cancelled is True
    assert stored_turn is not None
    assert stored_turn["status"] == "cancelled"
    assert stored_turn["error"] == "Turn cancelled"
    assert [event["seq"] for event in replay] == [2, 3]
    assert [event["type"] for event in replay] == ["error", "done"]
    assert replay[0]["content"] == "Turn cancelled"
    assert replay[0]["metadata"]["status"] == "cancelled"
    assert replay[1]["metadata"]["status"] == "cancelled"
    assert detail is not None
    assert detail["active_turns"] == []


