from __future__ import annotations

import asyncio
import importlib

import pytest

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient

chat_module = importlib.import_module("sparkweave.api.routers.chat")
solve_module = importlib.import_module("sparkweave.api.routers.solve")

from sparkweave.services.session import create_session_store


class _FakeLegacyManager:
    def __init__(self, sessions: list[dict]) -> None:
        self._sessions = {session["session_id"]: dict(session) for session in sessions}
        self.deleted: list[str] = []

    def list_sessions(self, limit: int = 20, include_messages: bool = False):  # noqa: ANN001
        sessions = list(self._sessions.values())[:limit]
        if include_messages:
            return sessions
        return [
            {
                key: value
                for key, value in session.items()
                if key != "messages"
            }
            for session in sessions
        ]

    def get_session(self, session_id: str):  # noqa: ANN201
        session = self._sessions.get(session_id)
        return dict(session) if session is not None else None

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        self.deleted.append(session_id)
        del self._sessions[session_id]
        return True


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_module.router, prefix="/api/v1")
    app.include_router(solve_module.router, prefix="/api/v1")
    return app


async def _create_shared_session(  # noqa: ANN202
    store,
    *,
    session_id: str,
    capability: str,
    user_content: str,
    assistant_content: str,
    tools: list[str] | None = None,
    knowledge_bases: list[str] | None = None,
) -> None:
    session = await store.create_session(title=user_content, session_id=session_id)
    await store.update_session_preferences(
        session["id"],
        {
            "capability": capability,
            "tools": list(tools or []),
            "knowledge_bases": list(knowledge_bases or []),
            "language": "en",
        },
    )
    turn = await store.create_turn(session["id"], capability=capability)
    await store.add_message(
        session_id=session["id"],
        role="user",
        content=user_content,
        capability=capability,
    )
    await store.add_message(
        session_id=session["id"],
        role="assistant",
        content=assistant_content,
        capability=capability,
        events=[{"type": "result", "metadata": {"runtime": "langgraph"}}],
    )
    await store.update_turn_status(turn["id"], "completed")


def test_chat_sessions_rest_routes_bridge_shared_store_and_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_sessions_bridge.db")
    asyncio.run(
        _create_shared_session(
            store,
            session_id="shared-chat",
            capability="chat",
            user_content="shared chat question",
            assistant_content="shared chat answer",
            tools=["rag", "web_search"],
            knowledge_bases=["chat-kb"],
        )
    )
    asyncio.run(
        _create_shared_session(
            store,
            session_id="shared-solve-hidden-from-chat",
            capability="deep_solve",
            user_content="solve question",
            assistant_content="solve answer",
            tools=["rag"],
            knowledge_bases=["solve-kb"],
        )
    )

    legacy = _FakeLegacyManager(
        [
            {
                "session_id": "legacy-chat",
                "title": "Legacy Chat",
                "messages": [
                    {
                        "role": "user",
                        "content": "legacy chat question",
                        "timestamp": 1.0,
                    },
                    {
                        "role": "assistant",
                        "content": "legacy chat answer",
                        "timestamp": 2.0,
                    },
                ],
                "settings": {
                    "kb_name": "",
                    "enable_rag": False,
                    "enable_web_search": False,
                },
                "created_at": 1.0,
                "updated_at": 2.0,
                "message_count": 2,
                "last_message": "legacy chat answer",
            }
        ]
    )
    monkeypatch.setattr("sparkweave.api.routers.chat.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr("sparkweave.api.routers.chat.session_manager", legacy)

    with TestClient(_build_app()) as client:
        list_response = client.get("/api/v1/chat/sessions", params={"limit": 10})
        shared_detail = client.get("/api/v1/chat/sessions/shared-chat")
        legacy_detail = client.get("/api/v1/chat/sessions/legacy-chat")
        delete_shared = client.delete("/api/v1/chat/sessions/shared-chat")
        delete_legacy = client.delete("/api/v1/chat/sessions/legacy-chat")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert [item["session_id"] for item in payload] == ["shared-chat", "legacy-chat"]
    assert payload[0]["settings"] == {
        "kb_name": "chat-kb",
        "enable_rag": True,
        "enable_web_search": True,
        "language": "en",
    }
    assert payload[0]["status"] == "completed"
    assert payload[0]["last_message"] == "shared chat answer"

    assert shared_detail.status_code == 200
    shared_payload = shared_detail.json()
    assert shared_payload["session_id"] == "shared-chat"
    assert shared_payload["settings"]["kb_name"] == "chat-kb"
    assert [message["role"] for message in shared_payload["messages"]] == ["user", "assistant"]
    assert shared_payload["messages"][0]["timestamp"] == shared_payload["messages"][0]["created_at"]
    assert shared_payload["status"] == "completed"

    assert legacy_detail.status_code == 200
    assert legacy_detail.json()["session_id"] == "legacy-chat"

    assert delete_shared.status_code == 200
    assert asyncio.run(store.get_session("shared-chat")) is None
    assert delete_legacy.status_code == 200
    assert legacy.deleted == ["legacy-chat"]


def test_solve_sessions_rest_routes_bridge_shared_store_and_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "solve_sessions_bridge.db")
    asyncio.run(
        _create_shared_session(
            store,
            session_id="shared-solve",
            capability="deep_solve",
            user_content="shared solve question",
            assistant_content="shared solve answer",
            tools=["rag", "code_execution"],
            knowledge_bases=["math-kb"],
        )
    )
    asyncio.run(
        _create_shared_session(
            store,
            session_id="shared-chat-hidden-from-solve",
            capability="chat",
            user_content="chat question",
            assistant_content="chat answer",
            tools=["web_search"],
            knowledge_bases=["chat-kb"],
        )
    )

    legacy = _FakeLegacyManager(
        [
            {
                "session_id": "legacy-solve",
                "title": "Legacy Solve",
                "messages": [
                    {
                        "role": "user",
                        "content": "legacy solve question",
                        "timestamp": 1.0,
                    },
                    {
                        "role": "assistant",
                        "content": "legacy solve answer",
                        "timestamp": 2.0,
                        "output_dir": "solve_legacy",
                    },
                ],
                "kb_name": "legacy-kb",
                "token_stats": {
                    "model": "legacy-model",
                    "calls": 1,
                    "tokens": 10,
                    "input_tokens": 5,
                    "output_tokens": 5,
                    "cost": 0.01,
                },
                "created_at": 1.0,
                "updated_at": 2.0,
                "message_count": 2,
                "last_message": "legacy solve answer",
            }
        ]
    )
    monkeypatch.setattr("sparkweave.api.routers.solve.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr("sparkweave.api.routers.solve.solver_session_manager", legacy)

    with TestClient(_build_app()) as client:
        list_response = client.get("/api/v1/solve/sessions", params={"limit": 10})
        shared_detail = client.get("/api/v1/solve/sessions/shared-solve")
        legacy_detail = client.get("/api/v1/solve/sessions/legacy-solve")
        delete_shared = client.delete("/api/v1/solve/sessions/shared-solve")
        delete_legacy = client.delete("/api/v1/solve/sessions/legacy-solve")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert [item["session_id"] for item in payload] == ["shared-solve", "legacy-solve"]
    assert payload[0]["kb_name"] == "math-kb"
    assert payload[0]["status"] == "completed"
    assert payload[0]["token_stats"]["model"] == "Unknown"

    assert shared_detail.status_code == 200
    shared_payload = shared_detail.json()
    assert shared_payload["session_id"] == "shared-solve"
    assert shared_payload["kb_name"] == "math-kb"
    assert shared_payload["token_stats"]["calls"] == 0
    assert [message["role"] for message in shared_payload["messages"]] == ["user", "assistant"]
    assert shared_payload["messages"][1]["timestamp"] == shared_payload["messages"][1]["created_at"]
    assert shared_payload["status"] == "completed"

    assert legacy_detail.status_code == 200
    assert legacy_detail.json()["session_id"] == "legacy-solve"

    assert delete_shared.status_code == 200
    assert asyncio.run(store.get_session("shared-solve")) is None
    assert delete_legacy.status_code == 200
    assert legacy.deleted == ["legacy-solve"]


