from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkweave.api.routers import speech
from sparkweave.services.speech import (
    SpeechEvaluationResult,
    SpeechTranscriptionResult,
    SpeechUnavailable,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(speech.router, prefix="/speech")
    return TestClient(app)


def test_transcribe_speech_upload(monkeypatch) -> None:
    async def fake_transcribe(audio: bytes, *, audio_encoding: str):
        assert audio == b"mp3"
        assert audio_encoding == "lame"
        return SpeechTranscriptionResult(text="讲一下导数", sid="sid-1", audio_encoding=audio_encoding)

    monkeypatch.setattr(speech, "transcribe_audio_with_iflytek", fake_transcribe)

    response = _client().post(
        "/speech/transcribe",
        files={"file": ("ask.mp3", b"mp3", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["text"] == "讲一下导数"
    assert response.json()["audio_encoding"] == "lame"


def test_transcribe_speech_returns_provider_error(monkeypatch) -> None:
    async def fake_transcribe(audio: bytes, *, audio_encoding: str):
        raise SpeechUnavailable("not configured")

    monkeypatch.setattr(speech, "transcribe_audio_with_iflytek", fake_transcribe)

    response = _client().post(
        "/speech/transcribe",
        files={"file": ("ask.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["fallback"] is True
    assert body["provider"] == "offline_iflytek_fallback:asr"
    assert body["fallback_reason"] == "not configured"


def test_transcribe_speech_treats_empty_transcript_as_failure(monkeypatch) -> None:
    async def fake_transcribe(audio: bytes, *, audio_encoding: str):
        return SpeechTranscriptionResult(text="   ", sid="sid-empty", audio_encoding=audio_encoding)

    monkeypatch.setattr(speech, "transcribe_audio_with_iflytek", fake_transcribe)

    response = _client().post(
        "/speech/transcribe",
        files={"file": ("ask.wav", b"wav", "audio/wav")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["sid"] == "sid-empty"
    assert data["error"] == "No speech text recognized"


def test_transcribe_speech_rejects_non_audio_upload(monkeypatch) -> None:
    async def fake_transcribe(audio: bytes, *, audio_encoding: str):
        raise AssertionError("non-audio upload should be rejected before provider call")

    monkeypatch.setattr(speech, "transcribe_audio_with_iflytek", fake_transcribe)

    response = _client().post(
        "/speech/transcribe",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Unsupported audio content type"


def test_transcribe_speech_rejects_spoofed_audio_suffix(monkeypatch) -> None:
    async def fake_transcribe(audio: bytes, *, audio_encoding: str):
        raise AssertionError("spoofed audio upload should be rejected before provider call")

    monkeypatch.setattr(speech, "transcribe_audio_with_iflytek", fake_transcribe)

    response = _client().post(
        "/speech/transcribe",
        files={"file": ("notes.txt", b"fake mp3", "audio/mpeg")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "Unsupported audio file type"


def test_evaluate_speech_writes_learner_evidence(monkeypatch) -> None:
    async def fake_evaluate(audio: bytes, *, reference_text: str):
        assert audio == b"pcm"
        assert reference_text == "函数在一点可导"
        return SpeechEvaluationResult(
            overall_score=86.0,
            normalized_score=0.86,
            dimensions={"accuracy": 88.0, "fluency": 84.0},
            sid="ise-1",
            raw_text="<xml />",
        )

    class FakeEvidenceService:
        def append_event(self, payload):
            assert payload["source"] == "iflytek_speech_eval"
            assert payload["resource_type"] == "audio"
            assert payload["score"] == 0.86
            assert payload["metadata"]["overall_score"] == 86.0
            return {**payload, "saved": True}

    monkeypatch.setattr(speech, "evaluate_speech_with_iflytek", fake_evaluate)
    monkeypatch.setattr(speech, "get_learner_evidence_service", lambda: FakeEvidenceService())

    response = _client().post(
        "/speech/evaluate",
        data={"reference_text": "函数在一点可导", "task_id": "task-1"},
        files={"file": ("answer.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["overall_score"] == 86.0
    assert data["normalized_score"] == 0.86
    assert data["evidence"]["saved"] is True


def test_evaluate_speech_can_skip_learner_evidence(monkeypatch) -> None:
    async def fake_evaluate(audio: bytes, *, reference_text: str):
        assert audio == b"pcm"
        assert reference_text == "设置页试录"
        return SpeechEvaluationResult(
            overall_score=91.0,
            normalized_score=0.91,
            dimensions={"accuracy": 90.0},
            sid="ise-preview",
        )

    class FakeEvidenceService:
        def append_event(self, payload):
            raise AssertionError("settings preview should not write learner evidence")

    monkeypatch.setattr(speech, "evaluate_speech_with_iflytek", fake_evaluate)
    monkeypatch.setattr(speech, "get_learner_evidence_service", lambda: FakeEvidenceService())

    response = _client().post(
        "/speech/evaluate",
        data={"reference_text": "设置页试录", "persist_evidence": "false"},
        files={"file": ("answer.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["overall_score"] == 91.0
    assert data["evidence"] is None


def test_evaluate_speech_fallback_does_not_write_formal_evidence(monkeypatch) -> None:
    async def fake_evaluate(audio: bytes, *, reference_text: str):
        raise SpeechUnavailable('not configured api_key="leaky-key" api_secret=leaky-secret')

    class FakeEvidenceService:
        def append_event(self, payload):
            raise AssertionError("offline fallback scores should not write formal learner evidence")

    monkeypatch.setattr(speech, "evaluate_speech_with_iflytek", fake_evaluate)
    monkeypatch.setattr(speech, "get_learner_evidence_service", lambda: FakeEvidenceService())

    response = _client().post(
        "/speech/evaluate",
        data={"reference_text": "函数在一点可导", "task_id": "task-1"},
        files={"file": ("answer.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["fallback"] is True
    assert "leaky-key" not in data["fallback_reason"]
    assert "leaky-secret" not in data["fallback_reason"]
    assert "[REDACTED]" in data["fallback_reason"]
    assert data["evidence"] is None


def test_evaluate_speech_rejects_long_reference(monkeypatch) -> None:
    async def fake_evaluate(audio: bytes, *, reference_text: str):
        raise AssertionError("long reference should be rejected before provider call")

    monkeypatch.setattr(speech, "evaluate_speech_with_iflytek", fake_evaluate)

    response = _client().post(
        "/speech/evaluate",
        data={"reference_text": "x" * (speech.MAX_REFERENCE_TEXT_CHARS + 1)},
        files={"file": ("answer.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "reference_text exceeds 2000 characters"


def test_evaluate_speech_treats_missing_score_as_failure(monkeypatch) -> None:
    async def fake_evaluate(audio: bytes, *, reference_text: str):
        return SpeechEvaluationResult(
            overall_score=None,
            normalized_score=None,
            dimensions={},
            sid="ise-empty",
            raw_text="<xml />",
        )

    class FakeEvidenceService:
        def append_event(self, payload):
            raise AssertionError("missing-score result should not write learner evidence")

    monkeypatch.setattr(speech, "evaluate_speech_with_iflytek", fake_evaluate)
    monkeypatch.setattr(speech, "get_learner_evidence_service", lambda: FakeEvidenceService())

    response = _client().post(
        "/speech/evaluate",
        data={"reference_text": "设置页试录"},
        files={"file": ("answer.pcm", b"pcm", "application/octet-stream")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["sid"] == "ise-empty"
    assert data["error"] == "Speech evaluation did not return a score"
    assert data["evidence"] is None
