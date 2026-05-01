from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

FastAPI = pytest.importorskip("fastapi").FastAPI
TestClient = pytest.importorskip("fastapi.testclient").TestClient
system_module = importlib.import_module("sparkweave.api.routers.system")


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(system_module.router, prefix="/api/v1/system")
    return app


def _search_config(**overrides):
    defaults = {
        "requested_provider": "duckduckgo",
        "provider": "duckduckgo",
        "unsupported_provider": False,
        "deprecated_provider": False,
        "missing_credentials": False,
        "fallback_reason": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_system_status_uses_ng_service_facades(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        system_module,
        "get_llm_config",
        lambda: SimpleNamespace(model="ng-chat-model"),
    )
    monkeypatch.setattr(
        system_module,
        "get_embedding_config",
        lambda: SimpleNamespace(model="ng-embedding-model"),
    )
    monkeypatch.setattr(
        system_module,
        "resolve_search_runtime_config",
        lambda: _search_config(),
    )

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["llm"] == {
        "status": "configured",
        "model": "ng-chat-model",
        "testable": True,
    }
    assert body["embeddings"] == {
        "status": "configured",
        "model": "ng-embedding-model",
        "testable": True,
    }
    assert body["search"]["provider"] == "duckduckgo"
    assert body["search"]["status"] == "configured"


def test_system_search_probe_awaits_ng_search(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        system_module,
        "resolve_search_runtime_config",
        lambda: _search_config(provider="duckduckgo"),
    )

    async def _fake_web_search(**kwargs):
        calls.append(kwargs)
        return {"answer": "ok"}

    monkeypatch.setattr(system_module, "web_search", _fake_web_search)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/search")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "duckduckgo"
    assert calls == [{"query": "SparkWeave health check", "provider": "duckduckgo"}]


def test_system_ocr_probe_uses_iflytek_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(url="https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm")
    calls: list[dict] = []
    monkeypatch.setattr(system_module.XfyunOcrConfig, "from_env", classmethod(lambda cls: config))

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "OK"

    monkeypatch.setattr(system_module, "recognize_image_with_iflytek", _fake_recognize)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek"
    assert calls
    assert calls[0]["encoding"] == "png"
    assert calls[0]["config"] is config


def test_system_ocr_probe_reports_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunOcrConfig, "from_env", classmethod(lambda cls: None))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "OCR not configured"


