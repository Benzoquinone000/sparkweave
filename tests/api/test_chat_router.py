from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient
router = importlib.import_module("sparkweave.api.routers.chat").router

from sparkweave.services.session import create_session_store


class _LegacyChatManager:
    def __init__(self, sessions: list[dict] | None = None) -> None:
        self.sessions = {session["session_id"]: dict(session) for session in sessions or []}
        self.add_calls: list[dict] = []

    def list_sessions(self, limit: int = 20, include_messages: bool = False):  # noqa: ANN001
        sessions = list(self.sessions.values())[:limit]
        if include_messages:
            return sessions
        return [{key: value for key, value in session.items() if key != "messages"} for session in sessions]

    def get_session(self, session_id: str):  # noqa: ANN201
        session = self.sessions.get(session_id)
        return dict(session) if session is not None else None

    def create_session(self, *_args, **_kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AssertionError("legacy session manager should not create new chat sessions")

    def add_message(self, **kwargs):  # noqa: ANN003, ANN201
        self.add_calls.append(kwargs)
        return None

    def delete_session(self, session_id: str) -> bool:
        self.sessions.pop(session_id, None)
        return True


class _FakeChatAgent:
    history_calls: list[list[dict]] = []

    def __init__(self, **_kwargs) -> None:
        pass

    async def process(self, *, history, **_kwargs):  # noqa: ANN003, ANN202
        self.__class__.history_calls.append(history)

        async def _generator():
            yield {"type": "chunk", "content": "Shared "}
            yield {
                "type": "complete",
                "response": "Shared store answer",
                "sources": {
                    "rag": [{"title": "KB"}],
                    "web": [{"title": "Web"}],
                },
            }

        return _generator()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def test_chat_router_uses_ng_chat_facade() -> None:
    chat_module = importlib.import_module("sparkweave.api.routers.chat")

    assert chat_module.ChatAgent.__module__ == "sparkweave.services.chat_generation"
    assert chat_module.SessionManager.__module__ == "sparkweave.services.chat_generation"


def test_chat_websocket_persists_new_session_to_shared_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_router_shared.db")
    legacy = _LegacyChatManager()
    monkeypatch.setattr("sparkweave.api.routers.chat.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr("sparkweave.api.routers.chat.session_manager", legacy)
    monkeypatch.setattr("sparkweave.api.routers.chat.ChatAgent", _FakeChatAgent)
    monkeypatch.setattr(
        "sparkweave.api.routers.chat.get_llm_config",
        lambda: SimpleNamespace(api_key="k", base_url="u", api_version="v1"),
    )
    monkeypatch.setattr("sparkweave.api.routers.chat.get_ui_language", lambda default="en": "en")
    _FakeChatAgent.history_calls.clear()

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/chat") as websocket:
            websocket.send_json(
                {
                    "message": "Explain vectors",
                    "kb_name": "linear-algebra",
                    "enable_rag": True,
                    "enable_web_search": True,
                }
            )
            events = [websocket.receive_json() for _ in range(7)]
        session_id = events[0]["session_id"]
        detail_response = client.get(f"/api/v1/chat/sessions/{session_id}")

    assert [event["type"] for event in events] == [
        "session",
        "status",
        "status",
        "status",
        "stream",
        "sources",
        "result",
    ]
    assert session_id.startswith("chat_")
    assert _FakeChatAgent.history_calls == [[]]

    detail = asyncio.run(store.get_session_with_messages(session_id))
    turn = asyncio.run(store.get_latest_turn(session_id))
    events = asyncio.run(store.get_turn_events(turn["id"])) if turn is not None else []
    assert detail is not None
    assert detail["status"] == "completed"
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]
    assert detail["preferences"]["capability"] == "chat"
    assert detail["preferences"]["tools"] == ["rag", "web_search"]
    assert detail["preferences"]["knowledge_bases"] == ["linear-algebra"]
    assert detail["messages"][1]["events"][0]["metadata"]["sources"]["rag"][0]["title"] == "KB"
    assert turn is not None
    assert turn["status"] == "completed"
    assert [event["type"] for event in events] == ["session", "content", "sources", "result", "done"]
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5]
    assert events[0]["metadata"]["runtime"] == "ng_service"
    assert events[0]["metadata"]["entrypoint"] == "chat_ws"
    assert events[3]["metadata"]["response"] == "Shared store answer"
    assert events[4]["metadata"]["status"] == "completed"
    assert legacy.add_calls == []

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["settings"]["kb_name"] == "linear-algebra"
    assert payload["settings"]["enable_rag"] is True
    assert payload["settings"]["enable_web_search"] is True
    assert payload["messages"][1]["sources"]["web"][0]["title"] == "Web"


def test_chat_websocket_migrates_legacy_session_into_shared_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = create_session_store(tmp_path / "chat_router_migrate.db")
    legacy = _LegacyChatManager(
        [
            {
                "session_id": "legacy-chat-session",
                "title": "Legacy Chat Session",
                "messages": [
                    {"role": "user", "content": "old question", "timestamp": 1.0},
                    {
                        "role": "assistant",
                        "content": "old answer",
                        "timestamp": 2.0,
                        "sources": {"rag": [{"title": "Old KB"}], "web": []},
                    },
                ],
                "settings": {
                    "kb_name": "legacy-kb",
                    "enable_rag": True,
                    "enable_web_search": False,
                },
                "created_at": 1.0,
                "updated_at": 2.0,
            }
        ]
    )
    monkeypatch.setattr("sparkweave.api.routers.chat.get_sqlite_session_store", lambda: store)
    monkeypatch.setattr("sparkweave.api.routers.chat.session_manager", legacy)
    monkeypatch.setattr("sparkweave.api.routers.chat.ChatAgent", _FakeChatAgent)
    monkeypatch.setattr(
        "sparkweave.api.routers.chat.get_llm_config",
        lambda: SimpleNamespace(api_key="k", base_url="u", api_version="v1"),
    )
    monkeypatch.setattr("sparkweave.api.routers.chat.get_ui_language", lambda default="en": "en")
    _FakeChatAgent.history_calls.clear()

    with TestClient(_build_app()) as client:
        with client.websocket_connect("/api/v1/chat") as websocket:
            websocket.send_json(
                {
                    "message": "new follow-up",
                    "session_id": "legacy-chat-session",
                    "kb_name": "legacy-kb",
                    "enable_rag": True,
                    "enable_web_search": False,
                }
            )
            events = [websocket.receive_json() for _ in range(6)]
        detail_response = client.get("/api/v1/chat/sessions/legacy-chat-session")

    assert [event["type"] for event in events] == [
        "session",
        "status",
        "status",
        "stream",
        "sources",
        "result",
    ]
    assert _FakeChatAgent.history_calls == [[
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "old answer"},
    ]]

    detail = asyncio.run(store.get_session_with_messages("legacy-chat-session"))
    turn = asyncio.run(store.get_latest_turn("legacy-chat-session"))
    events = asyncio.run(store.get_turn_events(turn["id"])) if turn is not None else []
    assert detail is not None
    assert detail["status"] == "completed"
    assert [message["content"] for message in detail["messages"]] == [
        "old question",
        "old answer",
        "new follow-up",
        "Shared store answer",
    ]
    assert detail["preferences"]["knowledge_bases"] == ["legacy-kb"]
    assert turn is not None
    assert [event["type"] for event in events] == ["session", "content", "sources", "result", "done"]
    assert events[0]["metadata"]["runtime"] == "ng_service"
    assert events[0]["metadata"]["knowledge_base"] == "legacy-kb"
    assert events[2]["metadata"]["sources"]["rag"][0]["title"] == "KB"
    assert events[4]["metadata"]["status"] == "completed"
    assert legacy.add_calls == []

    assert detail_response.status_code == 200
    assert [message["content"] for message in detail_response.json()["messages"]] == [
        "old question",
        "old answer",
        "new follow-up",
        "Shared store answer",
    ]


