from __future__ import annotations

import asyncio
import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkweave.services.notebook import NotebookManager
from sparkweave.services.session_store import SQLiteSessionStore

notebook_router_module = importlib.import_module("sparkweave.api.routers.notebook")
sessions_router_module = importlib.import_module("sparkweave.api.routers.sessions")


class _EvidenceRecorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_events(self, events: list[dict], *, dedupe: bool = True):
        self.events.extend(events)
        return {"added": len(events), "skipped": 0, "events": events}


def test_session_quiz_results_write_learner_evidence(tmp_path, monkeypatch) -> None:
    store = SQLiteSessionStore(db_path=tmp_path / "sessions.db")
    session = asyncio.run(store.create_session(title="Quiz Session"))
    recorder = _EvidenceRecorder()
    monkeypatch.setattr(sessions_router_module, "get_sqlite_session_store", lambda: store)
    monkeypatch.setattr(sessions_router_module, "get_learner_evidence_service", lambda: recorder)

    app = FastAPI()
    app.include_router(sessions_router_module.router, prefix="/api/v1/sessions")

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/sessions/{session['id']}/quiz-results",
            json={
                "answers": [
                    {
                        "question_id": "q1",
                        "question": "学习率过大可能发生什么？",
                        "question_type": "choice",
                        "user_answer": "更稳定",
                        "correct_answer": "震荡",
                        "explanation": "学习率过大会越过最优点。",
                        "difficulty": "easy",
                        "is_correct": False,
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert len(recorder.events) == 1
    assert recorder.events[0]["source"] == "question_notebook"
    assert recorder.events[0]["verb"] == "answered"
    assert recorder.events[0]["score"] == 0.0


def test_notebook_add_record_writes_learner_evidence(tmp_path, monkeypatch) -> None:
    manager = NotebookManager(base_dir=str(tmp_path / "notebooks"))
    notebook = manager.create_notebook("学习笔记")
    recorder = _EvidenceRecorder()
    monkeypatch.setattr(notebook_router_module, "notebook_manager", manager)
    monkeypatch.setattr(notebook_router_module, "get_learner_evidence_service", lambda: recorder)

    app = FastAPI()
    app.include_router(notebook_router_module.router, prefix="/api/v1/notebook")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/notebook/add_record",
            json={
                "notebook_ids": [notebook["id"]],
                "record_type": "chat",
                "title": "梯度下降复盘",
                "summary": "记录了学习率和梯度方向。",
                "user_query": "复盘梯度下降",
                "output": "学习率过大可能震荡。",
                "metadata": {"source": "chat"},
            },
        )

    assert response.status_code == 200
    assert len(recorder.events) == 1
    assert recorder.events[0]["source"] == "chat"
    assert recorder.events[0]["verb"] == "saved"
    assert recorder.events[0]["object_type"] == "resource"
    assert recorder.events[0]["resource_type"] == "note"
    assert recorder.events[0]["metadata"]["record_object_type"] == "notebook_record"
