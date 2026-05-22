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
    assert body["success"] is True
    assert body["message"] == "OCR offline fallback is ready"
    assert body["model"] == "offline_iflytek_fallback:ocr"


def test_system_status_marks_iflytek_fallback_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "get_llm_config", lambda: SimpleNamespace(model="chat"))
    monkeypatch.setattr(system_module, "get_embedding_config", lambda: SimpleNamespace(model="embedding"))
    monkeypatch.setattr(system_module, "resolve_search_runtime_config", lambda: _search_config())
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: None)
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr(system_module.XfyunAsrConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr(system_module.XfyunSpeechEvalConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr(system_module.IflytekWorkflowConfig, "from_env", lambda: None)
    monkeypatch.setattr(system_module.IflytekFormulaConfig, "from_env", lambda: None)
    monkeypatch.setattr(system_module.IflytekVisionConfig, "from_env", lambda: None)
    monkeypatch.setattr(system_module, "offline_fallback_enabled", lambda: True)

    with TestClient(_build_app()) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    for key in ("ocr", "tts", "asr", "speech_eval", "iflytek_workflow", "formula_ocr", "image_understanding"):
        assert body[key]["status"] == "fallback"
        assert body[key]["fallback"] is True
        assert body[key]["provider"].startswith("offline_iflytek_fallback")


def test_system_iflytek_workflow_probe_uses_configured_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(flow_id="flow-demo")
    calls: list[dict] = []
    monkeypatch.setattr(system_module.IflytekWorkflowConfig, "from_env", lambda: config)

    async def _fake_call(prompt: str, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return {"content": "ok"}

    monkeypatch.setattr(system_module, "call_iflytek_workflow", _fake_call)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/iflytek_workflow")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek_workflow:flow-demo"
    assert calls[0]["config"] is config


def test_system_formula_ocr_probe_uses_configured_service(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(ent="teach-photo-print", provider="iflytek_formula")
    calls: list[dict] = []
    monkeypatch.setattr(system_module.IflytekFormulaConfig, "from_env", lambda: config)

    async def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return {"text": "$x+1=2$"}

    monkeypatch.setattr(system_module, "recognize_formula_image", _fake_recognize)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/formula_ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek_formula:teach-photo-print"
    assert calls[0]["config"] is config


def test_system_image_understanding_probe_uses_configured_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(domain="imagev3", provider="iflytek_image_understanding")
    calls: list[dict] = []
    monkeypatch.setattr(system_module.IflytekVisionConfig, "from_env", lambda: config)

    async def _fake_understand(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return {"content": "ok"}

    monkeypatch.setattr(system_module, "understand_image", _fake_understand)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/image_understanding")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek_image:imagev3"
    assert calls[0]["config"] is config
    assert calls[0]["mime_type"] == "image/png"


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


def test_system_ocr_preview_uses_data_uri_mime_when_encoding_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(url="https://ocr.example", provider="iflytek")
    calls: list[dict] = []
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: config)

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "OK"

    monkeypatch.setattr(system_module, "recognize_image", _fake_recognize)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/system/ocr-preview",
            json={"image_base64": "data:image/jpeg;base64,aW1hZ2U="},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert calls == [{"image": b"image", "encoding": "jpg", "config": config}]


def test_system_ocr_preview_reports_invalid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: SimpleNamespace(provider="iflytek"))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/ocr-preview", json={"image_base64": "not-base64"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "Invalid base64 image"


def test_system_ocr_preview_rejects_unsupported_image_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: SimpleNamespace(provider="iflytek"))

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/system/ocr-preview",
            json={"image_base64": "data:image/svg+xml;base64,PHN2Zy8+", "encoding": "svg"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "Unsupported image type"


def test_system_ocr_preview_rejects_oversized_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module, "resolve_ocr_config", lambda: SimpleNamespace(provider="iflytek"))
    monkeypatch.setattr(system_module, "MAX_OCR_PREVIEW_IMAGE_BYTES", 4)

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/system/ocr-preview",
            json={"image_base64": "data:image/png;base64,aW1hZ2U=", "encoding": "png"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "Image exceeds 10 MB"


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
    assert body["success"] is True
    assert body["message"] == "TTS offline fallback is ready"
    assert body["model"] == "offline_iflytek_fallback:offline-iflytek-fallback"


def test_system_asr_probe_checks_iflytek_config(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(language="zh_cn", domain="iat")
    monkeypatch.setattr(system_module.XfyunAsrConfig, "from_env", classmethod(lambda cls: config))
    calls: list[dict] = []

    async def _fake_transcribe(audio: bytes, **kwargs):
        calls.append({"audio": audio, **kwargs})
        return SimpleNamespace(text="", sid="asr-smoke")

    monkeypatch.setattr(system_module, "transcribe_audio_with_iflytek", _fake_transcribe)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/asr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek:zh_cn/iat"
    assert "connection successful" in body["message"]
    assert calls
    assert calls[0]["audio"].startswith(b"RIFF")
    assert calls[0]["config"] is config
    assert calls[0]["audio_encoding"] == "raw"


def test_system_asr_probe_reports_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunAsrConfig, "from_env", classmethod(lambda cls: None))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/asr")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ASR offline fallback is ready"
    assert body["model"] == "offline_iflytek_fallback:asr"


def test_system_speech_eval_probe_checks_iflytek_config(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(category="read_sentence", language="zh_cn")
    monkeypatch.setattr(system_module.XfyunSpeechEvalConfig, "from_env", classmethod(lambda cls: config))
    calls: list[dict] = []

    async def _fake_evaluate(audio: bytes, **kwargs):
        calls.append({"audio": audio, **kwargs})
        return SimpleNamespace(normalized_score=0.92, dimensions={"total": 92.0}, sid="ise-smoke")

    monkeypatch.setattr(system_module, "evaluate_speech_with_iflytek", _fake_evaluate)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/speech_eval")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["model"] == "iflytek:read_sentence/zh_cn"
    assert body["message"] == "Speech evaluation connection successful"
    assert calls
    assert calls[0]["audio"].startswith(b"RIFF")
    assert calls[0]["config"] is config
    assert calls[0]["reference_text"] == system_module.SPEECH_EVAL_SMOKE_REFERENCE


def test_system_speech_eval_probe_reports_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunSpeechEvalConfig, "from_env", classmethod(lambda cls: None))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/test/speech_eval")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Speech evaluation offline fallback is ready"
    assert body["model"] == "offline_iflytek_fallback:speech_eval"


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


def test_system_tts_preview_marks_offline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: None))

    async def _fake_tts(text: str, **kwargs):
        return SimpleNamespace(
            audio=b"wavbytes",
            content_type="audio/wav",
            encoding="raw",
            sample_rate=16000,
            voice="offline-iflytek-fallback",
            sid=None,
            phonetic_text="offline fallback: not configured",
        )

    monkeypatch.setattr(system_module, "synthesize_speech_with_iflytek", _fake_tts)

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/tts-preview", json={"text": "hello"})

    assert response.status_code == 200
    assert response.headers["x-sparkweave-tts-fallback"] == "true"
    assert response.headers["x-sparkweave-tts-fallback-reason"] == "offline fallback: not configured"


def test_system_tts_preview_rejects_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: SimpleNamespace()))

    with TestClient(_build_app()) as client:
        response = client.post("/api/v1/system/tts-preview", json={"text": "   "})

    assert response.status_code == 400
    assert response.text == "TTS preview text is empty"


def test_system_tts_preview_rejects_long_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: SimpleNamespace()))

    with TestClient(_build_app()) as client:
        response = client.post(
            "/api/v1/system/tts-preview",
            json={"text": "x" * (system_module.MAX_TTS_PREVIEW_CHARS + 1)},
        )

    assert response.status_code == 413
    assert str(system_module.MAX_TTS_PREVIEW_CHARS) in response.text
