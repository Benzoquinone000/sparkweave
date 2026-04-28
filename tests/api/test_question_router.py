from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient


@pytest.fixture(autouse=True)
def _cleanup_question_router_module():
    yield
    sys.modules.pop("sparkweave.api.routers.question", None)


def _load_question_router_module():
    sys.modules.pop("sparkweave.api.routers.question", None)
    return importlib.import_module("sparkweave.api.routers.question")


def _build_app(router_module) -> FastAPI:
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1/question")
    return app


def test_mimic_websocket_accepts_config_and_returns_messages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    question_router_module = _load_question_router_module()

    async def _fake_mimic_exam_questions(*_args, **_kwargs):
        return {"success": False, "error": "stub mimic failure"}

    monkeypatch.setattr(question_router_module, "mimic_exam_questions", _fake_mimic_exam_questions)
    monkeypatch.setattr(question_router_module, "MIMIC_OUTPUT_DIR", tmp_path / "mimic_papers")

    with TestClient(_build_app(question_router_module)) as client:
        with client.websocket_connect("/api/v1/question/mimic") as websocket:
            websocket.send_json(
                {
                    "mode": "parsed",
                    "paper_path": str(tmp_path / "paper"),
                    "kb_name": "demo-kb",
                    "max_questions": 3,
                }
            )
            messages = [websocket.receive_json() for _ in range(3)]

    assert [message["type"] for message in messages] == ["status", "status", "error"]
    assert messages[0]["stage"] == "init"
    assert messages[1]["stage"] == "processing"
    assert messages[2]["content"] == "stub mimic failure"


def test_question_router_uses_ng_generation_facade() -> None:
    question_router_module = _load_question_router_module()

    assert (
        question_router_module.AgentCoordinator.__module__
        == "sparkweave.services.question_generation"
    )
    assert (
        question_router_module.mimic_exam_questions.__module__
        == "sparkweave.services.question_generation"
    )


