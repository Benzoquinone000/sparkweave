from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkweave.api.routers import learning_effect


class _Service:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.completed: list[str] = []

    def health(self):
        return {"status": "healthy", "service": "learning_effect", "event_count": len(self.events)}

    def build_report(self, *, course_id="", window="14d"):
        return {
            "success": True,
            "course_id": course_id,
            "window": window,
            "overall": {"score": 62, "label": "正在进步", "summary": "先做一次复测。"},
            "dimensions": [],
            "concepts": [],
            "visualization": {
                "summary": "证据进入评估链路。",
                "nodes": [{"id": "evidence", "label": "证据流", "value": "1 条"}],
                "evidence_timeline": [{"id": "ev_1", "label": "梯度下降练习", "kind": "quiz"}],
            },
            "learner_receipt": {
                "headline": "先复测梯度下降",
                "state_label": "正在进步",
                "score": 62,
                "score_label": "62 分",
                "confidence_label": "初步可靠",
                "evidence_summary": "基于 1 条学习证据。",
                "profile_update": "画像已同步最近证据。",
                "next_step": "复测",
                "reason": "确认是否真正掌握。",
                "action_id": "nba_1",
                "action_label": "去复测",
                "action_href": "/chat?new=1&capability=deep_question",
                "writes_back": ["mastery", "profile"],
                "focus_concepts": [],
                "loop": {"pending": 0, "ready_for_retest": 1, "closed": 0},
            },
            "next_actions": [{"id": "nba_1", "type": "retest", "title": "复测"}],
        }

    def demo_summary(self, *, course_id="", window="14d"):
        return {
            "success": True,
            "course_id": course_id,
            "window": window,
            "headline": "先复测梯度下降",
            "primary_action": {"id": "nba_1", "title": "复测", "href": "/guide?new=1&effect_action=retest"},
            "proof_points": [{"label": "证据", "value": "1 条"}],
            "requirement_alignment": [{"requirement": "学习效果评估", "status": "正在进步"}],
            "markdown": "# 学习效果评估闭环摘要\n",
        }

    def list_concepts(self, *, course_id="", window="all", limit=100):
        return {"success": True, "items": [{"concept_id": "gradient_descent", "status": "needs_support"}], "total": 1}

    def next_actions(self, *, course_id="", window="14d", limit=6):
        return {"success": True, "items": [{"id": "nba_1", "type": "retest"}], "total": 1}

    def append_event(self, payload):
        event = {"id": "ev_1", **payload}
        self.events.append(event)
        return {"event": event}

    def complete_action(self, action_id, *, note="", score=None, course_id="", concept_ids=None):
        self.completed.append(action_id)
        return {"event": {"id": "ev_done", "object_id": action_id, "score": score}, "report": self.build_report(course_id=course_id)}


def test_learning_effect_router(monkeypatch) -> None:
    service = _Service()
    app = FastAPI()
    app.include_router(learning_effect.router, prefix="/api/v1/learning-effect")
    monkeypatch.setattr(learning_effect, "get_learning_effect_service", lambda: service)

    with TestClient(app) as client:
        health = client.get("/api/v1/learning-effect/health")
        assert health.status_code == 200
        assert health.json()["service"] == "learning_effect"

        report = client.get("/api/v1/learning-effect/report?course_id=ml&window=7d")
        assert report.status_code == 200
        assert report.json()["course_id"] == "ml"
        assert report.json()["overall"]["label"] == "正在进步"
        assert report.json()["visualization"]["nodes"][0]["id"] == "evidence"
        assert report.json()["learner_receipt"]["action_id"] == "nba_1"

        demo = client.get("/api/v1/learning-effect/demo-summary?course_id=ml&window=7d")
        assert demo.status_code == 200
        assert demo.json()["course_id"] == "ml"
        assert demo.json()["primary_action"]["id"] == "nba_1"
        assert "学习效果评估闭环摘要" in demo.json()["markdown"]

        concepts = client.get("/api/v1/learning-effect/concepts")
        assert concepts.status_code == 200
        assert concepts.json()["items"][0]["concept_id"] == "gradient_descent"

        actions = client.get("/api/v1/learning-effect/next-actions")
        assert actions.status_code == 200
        assert actions.json()["items"][0]["type"] == "retest"

        appended = client.post(
            "/api/v1/learning-effect/events",
            json={
                "source": "guide_v2",
                "verb": "answered",
                "object_type": "quiz",
                "title": "梯度下降练习",
                "concept_ids": ["梯度下降"],
                "result": {"score": 0.8, "is_correct": True},
            },
        )
        assert appended.status_code == 200
        assert service.events[0]["concept_ids"] == ["梯度下降"]

        completed = client.post(
            "/api/v1/learning-effect/actions/nba_1/complete",
            json={"note": "done", "score": 0.9, "course_id": "ml", "concept_ids": ["梯度下降"]},
        )
        assert completed.status_code == 200
        assert service.completed == ["nba_1"]
