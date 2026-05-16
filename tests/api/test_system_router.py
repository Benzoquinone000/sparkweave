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
    assert body["rag"]["provider"] == "milvus"
    assert body["rag"]["status"] == "configured"


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


def test_system_ocr_probe_uses_configured_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(url="https://api.siliconflow.cn/v1/chat/completions", provider="siliconflow", model="deepseek-ai/DeepSeek-OCR")
    calls: list[dict] = []
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: config)

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "OK"

    monkeypatch.setattr(system_module, "recognize_image", _fake_recognize)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "siliconflow:deepseek-ai/DeepSeek-OCR"
    assert calls
    assert calls[0]["encoding"] == "png"
    assert calls[0]["config"] is config


def test_system_ocr_probe_reports_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: None)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "OCR not configured"


def test_system_ocr_preview_recognizes_uploaded_image(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(url="https://ocr.example", provider="iflytek")
    calls: list[dict] = []
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: config)

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "导数讲义截图"

    monkeypatch.setattr(system_module, "recognize_image", _fake_recognize)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/system/ocr-preview",
            json={"image_base64": "data:image/png;base64,aW1hZ2U=", "encoding": "png"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["text"] == "导数讲义截图"
    assert body["provider"] == "iflytek"
    assert calls == [{"image": b"image", "encoding": "png", "config": config}]


def test_system_ocr_preview_reports_invalid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: SimpleNamespace(provider="iflytek"))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/ocr-preview", json={"image_base64": "not-base64"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "Invalid base64 image"


def test_system_tts_probe_uses_iflytek_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(voice="x5_lingxiaoxuan_flow")
    calls: list[dict] = []
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: config))

    async def _fake_tts(text: str, **kwargs):
        calls.append({"text": text, **kwargs})
        return SimpleNamespace(audio=b"mp3")

    monkeypatch.setattr(system_module, "synthesize_speech_with_iflytek", _fake_tts)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/tts")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek:x5_lingxiaoxuan_flow"
    assert calls == [{"text": system_module.TTS_SMOKE_TEST_TEXT, "config": config}]


def test_system_tts_probe_reports_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: None))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/tts")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "TTS not configured"


def test_system_tts_preview_returns_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(voice="x5_lingxiaoxuan_flow")
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: config))

    async def _fake_tts(text: str, **kwargs):
        assert text == "hello"
        assert kwargs["config"] is config
        return SimpleNamespace(
            audio=b"mp3bytes",
            content_type="audio/mpeg",
            encoding="lame",
            sample_rate=24000,
            voice="x5_lingxiaoxuan_flow",
            sid="sid-123",
        )

    monkeypatch.setattr(system_module, "synthesize_speech_with_iflytek", _fake_tts)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/tts-preview", json={"text": "hello"})

    assert response.status_code == 200
    assert response.content == b"mp3bytes"
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.headers["x-sparkweave-tts-voice"] == "x5_lingxiaoxuan_flow"


