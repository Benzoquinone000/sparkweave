from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkweave.api.routers import learner_profile


class _Service:
    def __init__(self) -> None:
        self.refreshed = False
        self.cleared = False

    async def read_profile(self, *, auto_refresh: bool = True):
        return {
            "version": 1,
            "generated_at": "2026-04-27T10:00:00+08:00",
            "confidence": 0.6,
            "overview": {"current_focus": "学习梯度下降"},
            "stable_profile": {"preferences": ["图解"]},
            "learning_state": {"weak_points": [], "mastery": []},
            "recommendations": [],
            "sources": [],
            "evidence_preview": [],
            "data_quality": {"source_count": 0, "evidence_count": 0, "read_only": True},
        }

    async def refresh(self, *, include_sources=None, force: bool = True):
        self.refreshed = True
        return {
            "version": 1,
            "generated_at": "2026-04-27T10:01:00+08:00",
            "confidence": 0.7,
            "overview": {"current_focus": "刷新后的画像", "include_sources": include_sources, "force": force},
            "stable_profile": {},
            "learning_state": {},
            "recommendations": [],
            "sources": [],
            "evidence_preview": [],
            "data_quality": {},
        }

    async def list_evidence_preview(self, *, source=None, limit: int = 30):
        return {"items": [{"source_id": source or "memory", "title": "证据"}], "total": 1}

    def clear_snapshot(self):
        self.cleared = True
        return {"cleared": True, "profile_cache_cleared": True}


class _EvidenceService:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.cleared = False

    def list_events(self, **kwargs):
        source = kwargs.get("source")
        items = [item for item in self.events if not source or item.get("source") == source]
        return {"items": items, "total": len(items), "summary": {"event_count": len(items)}}

    def append_event(self, payload):
        event = {"id": "ev_1", **payload}
        self.events.append(event)
        return event

    def append_events(self, payloads, *, dedupe=True):
        events = [{"id": f"ev_{index}", **payload} for index, payload in enumerate(payloads, 1)]
        self.events.extend(events)
        return {"added": len(events), "skipped": 0, "events": events}

    def rebuild_from_profile(self, profile, *, clear=False):
        if clear:
            self.events.clear()
        self.events.append({"id": "ev_rebuilt", "source": "memory", "title": profile["overview"]["current_focus"]})
        return {"added": 1, "skipped": 0, "events": self.events[-1:]}

    def clear(self):
        self.cleared = True
        self.events.clear()
        return {"cleared": True}


def _client(service: _Service, monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(learner_profile.router, prefix="/api/v1/learner-profile")
    monkeypatch.setattr(learner_profile, "get_learner_profile_service", lambda: service)
    return TestClient(app)


def test_learner_profile_router_get_refresh_and_evidence(monkeypatch) -> None:
    service = _Service()
    with _client(service, monkeypatch) as client:
        get_response = client.get("/api/v1/learner-profile")
        assert get_response.status_code == 200
        assert get_response.json()["overview"]["current_focus"] == "学习梯度下降"

        refresh_response = client.post(
            "/api/v1/learner-profile/refresh",
            json={"include_sources": ["memory"], "force": False},
        )
        assert refresh_response.status_code == 200
        body = refresh_response.json()
        assert service.refreshed is True
        assert body["overview"]["include_sources"] == ["memory"]
        assert body["overview"]["force"] is False

        evidence_response = client.get("/api/v1/learner-profile/evidence-preview?source=memory&limit=3")
        assert evidence_response.status_code == 200
        assert evidence_response.json()["items"][0]["source_id"] == "memory"


def test_learner_profile_router_evidence_ledger(monkeypatch) -> None:
    service = _Service()
    evidence_service = _EvidenceService()
    app = FastAPI()
    app.include_router(learner_profile.router, prefix="/api/v1/learner-profile")
    monkeypatch.setattr(learner_profile, "get_learner_profile_service", lambda: service)
    monkeypatch.setattr(learner_profile, "get_learner_evidence_service", lambda: evidence_service)

    with TestClient(app) as client:
        append_response = client.post(
            "/api/v1/learner-profile/evidence",
            json={
                "source": "question_notebook",
                "verb": "answered",
                "object_type": "quiz",
                "title": "学习率判断",
                "score": 0,
                "is_correct": False,
            },
        )
        assert append_response.status_code == 200
        assert append_response.json()["event"]["source"] == "question_notebook"

        list_response = client.get("/api/v1/learner-profile/evidence?source=question_notebook")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        rebuild_response = client.post("/api/v1/learner-profile/evidence/rebuild", json={"clear": True})
        assert rebuild_response.status_code == 200
        assert rebuild_response.json()["added"] == 1


def test_learner_profile_router_calibrates_profile(monkeypatch) -> None:
    service = _Service()
    evidence_service = _EvidenceService()
    app = FastAPI()
    app.include_router(learner_profile.router, prefix="/api/v1/learner-profile")
    monkeypatch.setattr(learner_profile, "get_learner_profile_service", lambda: service)
    monkeypatch.setattr(learner_profile, "get_learner_evidence_service", lambda: evidence_service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/learner-profile/calibrations",
            json={
                "action": "reject",
                "claim_type": "weak_point",
                "value": "linear algebra",
                "note": "not relevant",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert service.refreshed is True
    assert body["event"]["source"] == "profile_calibration"
    assert body["event"]["verb"] == "rejected_profile"


def test_learner_profile_router_accepts_overview_correction(monkeypatch) -> None:
    service = _Service()
    evidence_service = _EvidenceService()
    app = FastAPI()
    app.include_router(learner_profile.router, prefix="/api/v1/learner-profile")
    monkeypatch.setattr(learner_profile, "get_learner_profile_service", lambda: service)
    monkeypatch.setattr(learner_profile, "get_learner_evidence_service", lambda: evidence_service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/learner-profile/calibrations",
            json={
                "action": "correct",
                "claim_type": "profile_overview",
                "value": "The system thinks I need basics.",
                "corrected_value": "I mainly need help understanding formulas and application scenarios.",
                "note": "Quick correction from learner profile overview",
                "source_id": "profile_overview",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert service.refreshed is True
    assert body["event"]["verb"] == "corrected_profile"
    assert body["event"]["metadata"]["claim_type"] == "profile_overview"
    assert body["event"]["metadata"]["corrected_value"] == "I mainly need help understanding formulas and application scenarios."


def test_learner_profile_router_resets_learning_state(monkeypatch) -> None:
    service = _Service()
    evidence_service = _EvidenceService()

    class _MemoryService:
        def __init__(self) -> None:
            self.cleared = False

        def clear_memory(self):
            self.cleared = True
            return type("Snapshot", (), {"summary": "", "profile": ""})()

    class _GuideManager:
        def clear_learning_state(self):
            return {"cleared": True, "removed_sessions": 2, "learner_memory_cleared": True}

    class _SessionStore:
        def __init__(self) -> None:
            self.cleared_sessions = False
            self.cleared_notebook = False

        async def clear_all_sessions(self):
            self.cleared_sessions = True
            return {
                "cleared": True,
                "removed_sessions": 3,
                "removed_messages": 8,
                "removed_question_notebook_entries": 4,
            }

        async def clear_notebook_entries(self):
            self.cleared_notebook = True
            return {"cleared": True, "removed_entries": 4}

    class _NotebookManager:
        def __init__(self) -> None:
            self.cleared = False

        def clear_all_records(self):
            self.cleared = True
            return {"cleared": True, "removed_records": 5, "kept_notebooks": 2}

    memory_service = _MemoryService()
    session_store = _SessionStore()
    notebook_manager = _NotebookManager()
    app = FastAPI()
    app.include_router(learner_profile.router, prefix="/api/v1/learner-profile")
    monkeypatch.setattr(learner_profile, "get_learner_profile_service", lambda: service)
    monkeypatch.setattr(learner_profile, "get_learner_evidence_service", lambda: evidence_service)
    monkeypatch.setattr(learner_profile, "get_memory_service", lambda: memory_service)
    monkeypatch.setattr(learner_profile, "GuideV2Manager", _GuideManager)
    monkeypatch.setattr(learner_profile, "get_sqlite_session_store", lambda: session_store)
    monkeypatch.setattr(learner_profile, "get_notebook_manager", lambda: notebook_manager)

    with TestClient(app) as client:
        response = client.post("/api/v1/learner-profile/reset", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] is True
    assert body["scope"] == {
        "memory": True,
        "evidence": True,
        "guide_state": True,
        "chat_history": True,
        "question_notebook": True,
        "saved_notebook_records": True,
        "profile_cache": True,
    }
    assert memory_service.cleared is True
    assert evidence_service.cleared is True
    assert service.cleared is True
    assert session_store.cleared_sessions is True
    assert session_store.cleared_notebook is False
    assert notebook_manager.cleared is True
    assert body["guide_state"]["removed_sessions"] == 2
    assert body["chat_history"]["removed_sessions"] == 3
    assert body["chat_history"]["removed_question_notebook_entries"] == 4
    assert body["saved_notebook_records"]["removed_records"] == 5
