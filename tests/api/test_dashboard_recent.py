from __future__ import annotations

import asyncio
from threading import Event, Thread

import pytest

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

from sparkweave.api.routers import dashboard
from sparkweave.core.contracts import StreamEvent, StreamEventType
from sparkweave.runtime import LangGraphTurnRuntimeManager
from sparkweave.services.session import create_session_store


class FakeMemory:
    def build_memory_context(self) -> str:
        return ""

    async def refresh_from_turn(self, **_kwargs) -> None:
        return None


class FakeLangGraphRunner:
    async def handle(self, _context):  # noqa: ANN001, ANN202
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content="Hello from NG dashboard session.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source="chat",
            metadata={
                "response": "Hello from NG dashboard session.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class GateBeforeDashboardRunner:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    async def handle(self, _context):  # noqa: ANN001, ANN202
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        yield StreamEvent(
            type=StreamEventType.CONTENT,
            source="chat",
            stage="responding",
            content="Hello from a running NG dashboard session.",
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source="chat",
            metadata={
                "response": "Hello from a running NG dashboard session.",
                "runtime": "langgraph",
            },
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class BlockingCancelDashboardRunner:
    def __init__(self) -> None:
        self.started = Event()

    async def handle(self, _context):  # noqa: ANN001, ANN202
        self.started.set()
        await asyncio.Future()
        if False:
            yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


class FailingDashboardRunner:
    async def handle(self, _context):  # noqa: ANN001, ANN202
        if False:
            yield StreamEvent(type=StreamEventType.DONE, source="langgraph")
        raise RuntimeError("Dashboard runner failed")


class RecordingLegacyRuntime:
    def __init__(self, store) -> None:  # noqa: ANN001
        self.store = store

    async def start_turn(self, payload):  # noqa: ANN001, ANN201
        requested = str(payload.get("session_id") or "").strip() or "legacy-dashboard"
        session = await self.store.get_session(requested)
        if session is None:
            session = await self.store.create_session(
                title=str(payload.get("content") or "Legacy dashboard turn"),
                session_id=requested,
            )
        capability = str(payload.get("capability") or "chat")
        turn = await self.store.create_turn(session["id"], capability=capability)
        content = "Hello from legacy dashboard session."
        await self.store.add_message(
            session_id=session["id"],
            role="user",
            content=str(payload.get("content") or ""),
            capability=capability,
        )
        await self.store.add_message(
            session_id=session["id"],
            role="assistant",
            content=content,
            capability=capability,
        )
        await self.store.update_turn_status(turn["id"], "completed")
        return session, turn


class MinimalContextBuilder:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def build(self, **_kwargs):  # noqa: ANN003
        return type(
            "History",
            (),
            {
                "conversation_history": [],
                "conversation_summary": "",
                "context_text": "",
                "token_count": 0,
                "budget": 0,
            },
        )()


def _build_app():
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1/dashboard")
    return app


def _install_dashboard_runtime_patches(
    monkeypatch: pytest.MonkeyPatch,
    store,
) -> None:
    monkeypatch.setattr("sparkweave.api.routers.dashboard.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.get_llm_config",
        lambda: type("Cfg", (), {"max_tokens": 4096})(),
    )
    monkeypatch.setattr(
        "sparkweave.runtime.context_enrichment.ContextBuilder",
        MinimalContextBuilder,
    )


def _start_ng_turn_in_background(runtime, payload):  # noqa: ANN001, ANN201
    state: dict[str, object] = {}
    ready = Event()
    finished = Event()

    def _run_turn_in_background() -> None:
        async def _main() -> None:
            session, turn = await runtime.start_turn(payload)
            state["session"] = session
            state["turn"] = turn
            execution = runtime._executions.get(turn["id"])
            if execution is None or execution.task is None:
                raise AssertionError(f"missing execution for turn {turn['id']}")
            ready.set()
            try:
                await execution.task
            except asyncio.CancelledError:
                state["cancelled"] = True

        try:
            asyncio.run(_main())
        except Exception as exc:  # pragma: no cover - surfaced below
            state["error"] = exc
            ready.set()
        finally:
            finished.set()

    thread = Thread(target=_run_turn_in_background, daemon=True)
    thread.start()
    return state, ready, finished, thread


def _raise_background_error(state: dict[str, object]) -> None:
    if "error" in state:
        raise state["error"]  # type: ignore[misc]


def test_dashboard_recent_lists_legacy_and_ng_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_recent.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    legacy = RecordingLegacyRuntime(store)
    asyncio.run(
        legacy.start_turn(
            {
                "content": "legacy dashboard activity",
                "session_id": "dashboard-legacy",
                "capability": "chat",
            }
        )
    )

    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeLangGraphRunner(),
        memory_service=FakeMemory(),
    )
    asyncio.run(
        ng_runtime.run_turn(
            {
                "content": "ng dashboard activity",
                "session_id": "dashboard-ng",
                "capability": "chat",
                "config": {"_runtime": "langgraph"},
            }
        )
    )

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/dashboard/recent", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload}
    assert "dashboard-legacy" in ids
    assert "dashboard-ng" in ids

    by_id = {item["id"]: item for item in payload}
    assert by_id["dashboard-legacy"]["status"] == "completed"
    assert by_id["dashboard-ng"]["status"] == "completed"
    assert by_id["dashboard-legacy"]["summary"].startswith("Hello from legacy")
    assert by_id["dashboard-ng"]["summary"].startswith("Hello from NG")


def test_dashboard_recent_refreshes_running_ng_session_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_recent_refresh.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    runner = GateBeforeDashboardRunner()
    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=runner,
        memory_service=FakeMemory(),
    )
    payload = {
        "content": "dashboard should live refresh",
        "session_id": "dashboard-running-ng",
        "capability": "chat",
        "config": {"_runtime": "langgraph"},
    }
    state, ready, finished, thread = _start_ng_turn_in_background(ng_runtime, payload)
    assert ready.wait(timeout=2)
    _raise_background_error(state)
    session = state["session"]
    turn = state["turn"]
    assert isinstance(session, dict)
    assert isinstance(turn, dict)
    assert runner.started.wait(timeout=2)

    with TestClient(_build_app()) as client:
        running_recent = client.get("/api/v1/dashboard/recent", params={"limit": 10})
        running_detail = client.get(f"/api/v1/dashboard/{session['id']}")

    assert running_recent.status_code == 200
    running_item = next(
        item for item in running_recent.json() if item["id"] == "dashboard-running-ng"
    )
    assert running_item["status"] == "running"
    assert running_item["active_turn_id"] == turn["id"]
    assert running_item["summary"] == "dashboard should live refresh"

    assert running_detail.status_code == 200
    running_payload = running_detail.json()
    assert running_payload["id"] == "dashboard-running-ng"
    assert running_payload["content"]["status"] == "running"
    assert [item["id"] for item in running_payload["content"]["active_turns"]] == [turn["id"]]
    assert [message["role"] for message in running_payload["content"]["messages"]] == ["user"]

    runner.release.set()
    assert finished.wait(timeout=2)
    thread.join(timeout=1)
    _raise_background_error(state)

    with TestClient(_build_app()) as client:
        completed_recent = client.get("/api/v1/dashboard/recent", params={"limit": 10})
        completed_detail = client.get(f"/api/v1/dashboard/{session['id']}")

    assert completed_recent.status_code == 200
    completed_item = next(
        item for item in completed_recent.json() if item["id"] == "dashboard-running-ng"
    )
    assert completed_item["status"] == "completed"
    assert completed_item["active_turn_id"] == ""
    assert completed_item["summary"].startswith("Hello from a running NG")

    assert completed_detail.status_code == 200
    completed_payload = completed_detail.json()
    assert completed_payload["content"]["status"] == "completed"
    assert completed_payload["content"]["active_turns"] == []
    assert [message["role"] for message in completed_payload["content"]["messages"]] == [
        "user",
        "assistant",
    ]


def test_dashboard_recent_refreshes_multiple_running_ng_sessions_independently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_recent_multi_refresh.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    async def _seed_running_sessions():  # noqa: ANN202
        first_session = await store.create_session(
            "first dashboard live session",
            session_id="dashboard-running-ng-a",
        )
        second_session = await store.create_session(
            "second dashboard live session",
            session_id="dashboard-running-ng-b",
        )
        for session in (first_session, second_session):
            await store.update_session_preferences(
                session["id"],
                {"capability": "chat", "language": "en"},
            )
        first_turn = await store.create_turn(first_session["id"], capability="chat")
        second_turn = await store.create_turn(second_session["id"], capability="chat")
        await store.add_message(
            first_session["id"],
            "user",
            "first dashboard live session",
            capability="chat",
        )
        await store.add_message(
            second_session["id"],
            "user",
            "second dashboard live session",
            capability="chat",
        )
        return first_turn, second_turn

    first_turn, second_turn = asyncio.run(_seed_running_sessions())

    with TestClient(_build_app()) as client:
        running_response = client.get("/api/v1/dashboard/recent", params={"limit": 10})

    assert running_response.status_code == 200
    running_by_id = {item["id"]: item for item in running_response.json()}
    assert running_by_id["dashboard-running-ng-a"]["status"] == "running"
    assert running_by_id["dashboard-running-ng-b"]["status"] == "running"
    assert running_by_id["dashboard-running-ng-a"]["active_turn_id"]
    assert running_by_id["dashboard-running-ng-b"]["active_turn_id"]

    async def _complete_first_session() -> None:
        await store.add_message(
            "dashboard-running-ng-a",
            "assistant",
            "Dashboard stream completed for dashboard-running-ng-a.",
            capability="chat",
        )
        await store.update_turn_status(first_turn["id"], "completed")

    asyncio.run(_complete_first_session())

    with TestClient(_build_app()) as client:
        mixed_response = client.get("/api/v1/dashboard/recent", params={"limit": 10})
        first_detail = client.get("/api/v1/dashboard/dashboard-running-ng-a")
        second_detail = client.get("/api/v1/dashboard/dashboard-running-ng-b")

    assert mixed_response.status_code == 200
    mixed_by_id = {item["id"]: item for item in mixed_response.json()}
    assert mixed_by_id["dashboard-running-ng-a"]["status"] == "completed"
    assert mixed_by_id["dashboard-running-ng-a"]["active_turn_id"] == ""
    assert mixed_by_id["dashboard-running-ng-a"]["summary"].startswith(
        "Dashboard stream completed for dashboard-running-ng-a."
    )
    assert mixed_by_id["dashboard-running-ng-b"]["status"] == "running"
    assert mixed_by_id["dashboard-running-ng-b"]["active_turn_id"]

    assert first_detail.status_code == 200
    assert first_detail.json()["content"]["status"] == "completed"
    assert first_detail.json()["content"]["active_turns"] == []
    assert second_detail.status_code == 200
    assert second_detail.json()["content"]["status"] == "running"
    assert len(second_detail.json()["content"]["active_turns"]) == 1

    async def _complete_second_session() -> None:
        await store.add_message(
            "dashboard-running-ng-b",
            "assistant",
            "Dashboard stream completed for dashboard-running-ng-b.",
            capability="chat",
        )
        await store.update_turn_status(second_turn["id"], "completed")

    asyncio.run(_complete_second_session())

    with TestClient(_build_app()) as client:
        completed_response = client.get("/api/v1/dashboard/recent", params={"limit": 10})

    assert completed_response.status_code == 200
    completed_by_id = {item["id"]: item for item in completed_response.json()}
    assert completed_by_id["dashboard-running-ng-a"]["status"] == "completed"
    assert completed_by_id["dashboard-running-ng-b"]["status"] == "completed"
    assert completed_by_id["dashboard-running-ng-b"]["summary"].startswith(
        "Dashboard stream completed for dashboard-running-ng-b."
    )


def test_dashboard_entry_detail_supports_legacy_and_ng_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_detail.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    legacy = RecordingLegacyRuntime(store)
    asyncio.run(
        legacy.start_turn(
            {
                "content": "legacy dashboard detail",
                "session_id": "dashboard-detail-legacy",
                "capability": "chat",
            }
        )
    )

    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeLangGraphRunner(),
        memory_service=FakeMemory(),
    )
    asyncio.run(
        ng_runtime.run_turn(
            {
                "content": "ng dashboard detail",
                "session_id": "dashboard-detail-ng",
                "capability": "chat",
                "config": {"_runtime": "langgraph"},
            }
        )
    )

    with TestClient(_build_app()) as client:
        legacy_detail = client.get("/api/v1/dashboard/dashboard-detail-legacy")
        ng_detail = client.get("/api/v1/dashboard/dashboard-detail-ng")

    assert legacy_detail.status_code == 200
    legacy_payload = legacy_detail.json()
    assert legacy_payload["id"] == "dashboard-detail-legacy"
    assert legacy_payload["capability"] == "chat"
    assert legacy_payload["content"]["status"] == "completed"
    assert legacy_payload["content"]["active_turns"] == []
    assert [message["role"] for message in legacy_payload["content"]["messages"]] == [
        "user",
        "assistant",
    ]
    assert legacy_payload["content"]["messages"][-1]["content"].startswith("Hello from legacy")

    assert ng_detail.status_code == 200
    ng_payload = ng_detail.json()
    assert ng_payload["id"] == "dashboard-detail-ng"
    assert ng_payload["capability"] == "chat"
    assert ng_payload["content"]["status"] == "completed"
    assert ng_payload["content"]["active_turns"] == []
    assert [message["role"] for message in ng_payload["content"]["messages"]] == [
        "user",
        "assistant",
    ]
    assert ng_payload["content"]["messages"][-1]["content"].startswith("Hello from NG")


def test_dashboard_recent_surfaces_cancelled_and_failed_ng_sessions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_terminal_statuses.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    failed_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FailingDashboardRunner(),
        memory_service=FakeMemory(),
    )
    asyncio.run(
        failed_runtime.run_turn(
            {
                "content": "failed dashboard activity",
                "session_id": "dashboard-failed-ng",
                "capability": "chat",
                "config": {"_runtime": "langgraph"},
            }
        )
    )

    cancel_runner = BlockingCancelDashboardRunner()
    cancel_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=cancel_runner,
        memory_service=FakeMemory(),
    )

    async def _start_and_cancel():  # noqa: ANN202
        session, turn = await cancel_runtime.start_turn(
            {
                "content": "cancelled dashboard activity",
                "session_id": "dashboard-cancelled-ng",
                "capability": "chat",
                "config": {"_runtime": "langgraph"},
            }
        )
        execution = cancel_runtime._executions.get(turn["id"])
        if execution is None or execution.task is None:
            raise AssertionError(f"missing execution for turn {turn['id']}")
        started = await asyncio.to_thread(cancel_runner.started.wait, 2)
        if not started:
            raise AssertionError("cancel runner did not start")
        cancelled = await cancel_runtime.cancel_turn(turn["id"])
        if not cancelled:
            raise AssertionError(f"failed to cancel turn {turn['id']}")
        try:
            await execution.task
        except asyncio.CancelledError:
            pass
        return session, turn

    _, turn = asyncio.run(_start_and_cancel())

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/dashboard/recent", params={"limit": 10})
        failed_detail = client.get("/api/v1/dashboard/dashboard-failed-ng")
        cancelled_detail = client.get("/api/v1/dashboard/dashboard-cancelled-ng")

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}

    assert by_id["dashboard-failed-ng"]["status"] == "failed"
    assert by_id["dashboard-failed-ng"]["active_turn_id"] == ""
    assert by_id["dashboard-failed-ng"]["summary"] == "failed dashboard activity"
    assert by_id["dashboard-failed-ng"]["message_count"] == 1

    assert by_id["dashboard-cancelled-ng"]["status"] == "cancelled"
    assert by_id["dashboard-cancelled-ng"]["active_turn_id"] == ""
    assert by_id["dashboard-cancelled-ng"]["summary"] == "cancelled dashboard activity"
    assert by_id["dashboard-cancelled-ng"]["message_count"] == 1

    assert failed_detail.status_code == 200
    failed_payload = failed_detail.json()
    assert failed_payload["content"]["status"] == "failed"
    assert failed_payload["content"]["active_turns"] == []
    assert [message["role"] for message in failed_payload["content"]["messages"]] == ["user"]

    assert cancelled_detail.status_code == 200
    cancelled_payload = cancelled_detail.json()
    assert cancelled_payload["content"]["status"] == "cancelled"
    assert cancelled_payload["content"]["active_turns"] == []
    assert [message["role"] for message in cancelled_payload["content"]["messages"]] == ["user"]


def test_dashboard_recent_type_filter_maps_capability_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "dashboard_type_filter.db")
    _install_dashboard_runtime_patches(monkeypatch, store)

    legacy = RecordingLegacyRuntime(store)
    asyncio.run(
        legacy.start_turn(
            {
                "content": "chat dashboard activity",
                "session_id": "dashboard-chat",
                "capability": "chat",
            }
        )
    )

    ng_runtime = LangGraphTurnRuntimeManager(
        store=store,
        runner=FakeLangGraphRunner(),
        memory_service=FakeMemory(),
    )
    asyncio.run(
        ng_runtime.run_turn(
            {
                "content": "solve dashboard activity",
                "session_id": "dashboard-solve",
                "capability": "deep_solve",
                "config": {"_runtime": "langgraph"},
            }
        )
    )

    with TestClient(_build_app()) as client:
        solve_response = client.get("/api/v1/dashboard/recent", params={"limit": 10, "type": "solve"})
        chat_response = client.get("/api/v1/dashboard/recent", params={"limit": 10, "type": "chat"})

    assert solve_response.status_code == 200
    solve_payload = solve_response.json()
    assert [item["id"] for item in solve_payload] == ["dashboard-solve"]
    assert solve_payload[0]["type"] == "solve"
    assert solve_payload[0]["capability"] == "deep_solve"

    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    assert [item["id"] for item in chat_payload] == ["dashboard-chat"]
    assert chat_payload[0]["type"] == "chat"
    assert chat_payload[0]["capability"] == "chat"


