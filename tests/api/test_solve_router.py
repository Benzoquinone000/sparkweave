from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient
solve_module = importlib.import_module("sparkweave.api.routers.solve")
router = solve_module.router
DeepSolveCapability = solve_module.DeepSolveCapability

from sparkweave.services.session import create_session_store


class _DummyLogInterceptor:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def test_solve_router_uses_ng_solve_facade() -> None:
    assert solve_module.MainSolver.__module__ == "sparkweave.services.solve_generation"
    assert solve_module.SolverSessionManager.__module__ == "sparkweave.services.solve_generation"
    assert solve_module.DeepSolveCapability.__module__ == "sparkweave.services.solve_generation"


def test_solve_router_uses_explicit_default_tools(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeMainSolver:
        def __init__(self, **kwargs) -> None:
            captured["init"] = kwargs
            self.logger = SimpleNamespace(logger=SimpleNamespace(), display_manager=None)
            self.token_tracker = None

        async def ainit(self) -> None:
            captured["ainit"] = True

        async def solve(self, *_args, **_kwargs):
            return {"final_answer": "done", "output_dir": str(tmp_path / "solve"), "metadata": {}}

    monkeypatch.setattr("sparkweave.api.routers.solve.MainSolver", FakeMainSolver)
    monkeypatch.setattr("sparkweave.api.routers.solve.LogInterceptor", _DummyLogInterceptor)
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_llm_config",
        lambda: SimpleNamespace(api_key="k", base_url="u", api_version="v1"),
    )
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_path_service",
        lambda: SimpleNamespace(get_solve_dir=lambda: Path(tmp_path)),
    )
    monkeypatch.setattr("sparkweave.api.routers.solve.get_ui_language", lambda default="en": default)

    app = _build_app()

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/solve") as websocket:
            websocket.send_json({"question": "Solve x^2=4"})
            messages = [websocket.receive_json() for _ in range(4)]

    assert [message["type"] for message in messages] == ["session", "task_id", "status", "result"]
    assert captured["init"]["enabled_tools"] == list(DeepSolveCapability.manifest.tools_used)
    assert captured["init"]["kb_name"] == "ai-textbook"
    assert captured["init"]["disable_planner_retrieve"] is False


def test_solve_router_respects_disabled_tools(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeMainSolver:
        def __init__(self, **kwargs) -> None:
            captured["init"] = kwargs
            self.logger = SimpleNamespace(logger=SimpleNamespace(), display_manager=None)
            self.token_tracker = None

        async def ainit(self) -> None:
            captured["ainit"] = True

        async def solve(self, *_args, **_kwargs):
            return {"final_answer": "done", "output_dir": str(tmp_path / "solve"), "metadata": {}}

    monkeypatch.setattr("sparkweave.api.routers.solve.MainSolver", FakeMainSolver)
    monkeypatch.setattr("sparkweave.api.routers.solve.LogInterceptor", _DummyLogInterceptor)
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_llm_config",
        lambda: SimpleNamespace(api_key="k", base_url="u", api_version="v1"),
    )
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_path_service",
        lambda: SimpleNamespace(get_solve_dir=lambda: Path(tmp_path)),
    )
    monkeypatch.setattr("sparkweave.api.routers.solve.get_ui_language", lambda default="en": default)

    app = _build_app()

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/solve") as websocket:
            websocket.send_json(
                {
                    "question": "Solve x^2=4",
                    "tools": [],
                    "kb_name": "algebra",
                }
            )
            messages = [websocket.receive_json() for _ in range(4)]

    assert [message["type"] for message in messages] == ["session", "task_id", "status", "result"]
    assert captured["init"]["enabled_tools"] == []
    assert captured["init"]["kb_name"] is None
    assert captured["init"]["disable_planner_retrieve"] is True


def test_solve_websocket_persists_session_to_shared_store(monkeypatch, tmp_path) -> None:
    store = create_session_store(tmp_path / "solve_router_shared.db")
    captured: dict[str, object] = {}

    class FakeLegacySolveManager:
        def get_session(self, _session_id: str):  # noqa: ANN201
            return None

        def create_session(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN201
            raise AssertionError("legacy solve session manager should not create new sessions")

        def add_message(self, **_kwargs):  # noqa: ANN003, ANN201
            raise AssertionError("legacy solve session manager should not store messages")

        def update_token_stats(self, **_kwargs):  # noqa: ANN003, ANN201
            raise AssertionError("legacy solve session manager should not update token stats")

    class FakeMainSolver:
        def __init__(self, **kwargs) -> None:
            captured["init"] = kwargs
            self.logger = SimpleNamespace(logger=SimpleNamespace(), display_manager=None)
            self.token_tracker = None

        async def ainit(self) -> None:
            captured["ainit"] = True

        async def solve(self, *_args, **_kwargs):
            return {
                "final_answer": "shared solve answer",
                "output_dir": str(tmp_path / "solve" / "solve_123"),
                "metadata": {"kind": "demo"},
            }

    monkeypatch.setattr("sparkweave.api.routers.solve.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr("sparkweave.api.routers.solve.solver_session_manager", FakeLegacySolveManager())
    monkeypatch.setattr("sparkweave.api.routers.solve.MainSolver", FakeMainSolver)
    monkeypatch.setattr("sparkweave.api.routers.solve.LogInterceptor", _DummyLogInterceptor)
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_llm_config",
        lambda: SimpleNamespace(api_key="k", base_url="u", api_version="v1"),
    )
    monkeypatch.setattr(
        "sparkweave.api.routers.solve.get_path_service",
        lambda: SimpleNamespace(get_solve_dir=lambda: Path(tmp_path)),
    )
    monkeypatch.setattr("sparkweave.api.routers.solve.get_ui_language", lambda default="en": "en")

    app = _build_app()

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/solve") as websocket:
            websocket.send_json(
                {
                    "question": "Solve x^2=4",
                    "tools": ["rag", "code_execution"],
                    "kb_name": "math-kb",
                }
            )
            messages = [websocket.receive_json() for _ in range(4)]
        session_id = messages[0]["session_id"]
        detail_response = client.get(f"/api/v1/solve/sessions/{session_id}")

    assert [message["type"] for message in messages] == ["session", "task_id", "status", "result"]
    assert session_id.startswith("solve_")
    assert captured["init"]["enabled_tools"] == ["rag", "code_execution"]
    assert captured["init"]["kb_name"] == "math-kb"

    detail = asyncio.run(store.get_session_with_messages(session_id))
    turn = asyncio.run(store.get_latest_turn(session_id))
    events = asyncio.run(store.get_turn_events(turn["id"])) if turn is not None else []
    assert detail is not None
    assert detail["status"] == "completed"
    assert detail["preferences"]["capability"] == "deep_solve"
    assert detail["preferences"]["tools"] == ["rag", "code_execution"]
    assert detail["preferences"]["knowledge_bases"] == ["math-kb"]
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["events"][0]["metadata"]["output_dir_name"] == "solve_123"
    assert turn is not None
    assert turn["status"] == "completed"
    assert [event["type"] for event in events] == ["session", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "ng_service"
    assert events[0]["metadata"]["entrypoint"] == "solve_ws"
    assert events[1]["metadata"]["response"] == "shared solve answer"
    assert events[1]["metadata"]["output_dir_name"] == "solve_123"
    assert events[2]["metadata"]["status"] == "completed"

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["kb_name"] == "math-kb"
    assert payload["token_stats"]["model"] == "Unknown"
    assert payload["messages"][1]["output_dir"] == "solve_123"


