"""Speech input and oral-practice endpoints."""

from __future__ import annotations

import time
from typing import Any
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from sparkweave.services.iflytek_offline import (
    audio_descriptor,
    fallback_reason_text,
    offline_fallback_enabled,
    offline_speech_eval_result,
    offline_transcription_text,
)
from sparkweave.services.learner_evidence import get_learner_evidence_service
from sparkweave.services.speech import (
    SpeechEvaluationResult,
    SpeechTranscriptionResult,
    SpeechUnavailable,
    evaluate_speech_with_iflytek,
    guess_iflytek_audio_encoding,
    transcribe_audio_with_iflytek,
)

router = APIRouter()

MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_REFERENCE_TEXT_CHARS = 2_000
ALLOWED_AUDIO_CONTENT_TYPES = {
    "application/octet-stream",
    "audio/aac",
    "audio/amr",
    "audio/basic",
    "audio/m4a",
    "audio/mp3",
    "audio/mpeg",
    "audio/ogg",
    "audio/pcm",
    "audio/speex",
    "audio/wav",
    "audio/wave",
    "audio/x-m4a",
    "audio/x-pcm",
    "audio/x-wav",
}
ALLOWED_AUDIO_SUFFIXES = {
    ".aac",
    ".amr",
    ".m4a",
    ".mp3",
    ".mpeg",
    ".ogg",
    ".pcm",
    ".raw",
    ".speex",
    ".spx",
    ".wav",
}


class SpeechTranscribeResponse(BaseModel):
    success: bool
    text: str = ""
    provider: str = "iflytek"
    sid: str | None = None
    audio_encoding: str = ""
    fallback: bool = False
    fallback_reason: str | None = None
    error: str | None = None


class SpeechEvaluateResponse(BaseModel):
    success: bool
    provider: str = "iflytek"
    sid: str | None = None
    reference_text: str = ""
    overall_score: float | None = None
    normalized_score: float | None = None
    dimensions: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, Any] | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    error: str | None = None


@router.post("/transcribe", response_model=SpeechTranscribeResponse)
async def transcribe_speech(
    file: UploadFile = File(...),
    audio_encoding: str | None = Form(default=None),
):
    audio = await _read_audio_upload(file)
    encoding = (audio_encoding or "").strip() or guess_iflytek_audio_encoding(
        f"{file.filename or ''} {file.content_type or ''}"
    )
    try:
        result = await transcribe_audio_with_iflytek(audio, audio_encoding=encoding)
    except SpeechUnavailable as exc:
        if offline_fallback_enabled():
            descriptor = audio_descriptor(audio, audio_encoding=encoding)
            result = SpeechTranscriptionResult(
                text=offline_transcription_text(audio, audio_encoding=encoding, reason=exc),
                provider="offline_iflytek_fallback:asr",
                sid=f"offline-asr-{descriptor['digest']}",
                audio_encoding=descriptor["encoding"],
                audio_format="offline",
            )
            return SpeechTranscribeResponse(
                success=True,
                text=result.text,
                provider=result.provider,
                sid=result.sid,
                audio_encoding=result.audio_encoding,
                fallback=True,
                fallback_reason=fallback_reason_text(exc),
            )
        return SpeechTranscribeResponse(success=False, error=str(exc), audio_encoding=encoding)
    text = result.text.strip()
    if not text:
        return SpeechTranscribeResponse(
            success=False,
            provider=result.provider,
            sid=result.sid,
            audio_encoding=result.audio_encoding,
            error="No speech text recognized",
        )
    return SpeechTranscribeResponse(
        success=True,
        text=text,
        provider=result.provider,
        sid=result.sid,
        audio_encoding=result.audio_encoding,
    )


@router.post("/evaluate", response_model=SpeechEvaluateResponse)
async def evaluate_speech(
    file: UploadFile = File(...),
    reference_text: str = Form(...),
    course_id: str = Form(default=""),
    node_id: str = Form(default=""),
    task_id: str = Form(default=""),
    title: str = Form(default=""),
    persist_evidence: bool = Form(default=True),
):
    audio = await _read_audio_upload(file)
    reference = reference_text.strip()
    if not reference:
        raise HTTPException(status_code=400, detail="reference_text is required")
    if len(reference) > MAX_REFERENCE_TEXT_CHARS:
        raise HTTPException(status_code=413, detail="reference_text exceeds 2000 characters")
    started_at = time.time()
    try:
        result = await evaluate_speech_with_iflytek(audio, reference_text=reference)
    except SpeechUnavailable as exc:
        if offline_fallback_enabled():
            descriptor = audio_descriptor(audio, audio_encoding="raw")
            fallback = offline_speech_eval_result(audio, reference_text=reference)
            result = SpeechEvaluationResult(
                overall_score=fallback["overall_score"],
                normalized_score=fallback["normalized_score"],
                dimensions=fallback["dimensions"],
                provider="offline_iflytek_fallback:speech_eval",
                sid=f"offline-speech-eval-{descriptor['digest']}",
                raw_text=f"{fallback['raw_text']}\nreason={fallback_reason_text(exc)}",
            )
        else:
            return SpeechEvaluateResponse(success=False, reference_text=reference, error=str(exc))
    fallback = result.provider.startswith("offline_iflytek_fallback")
    if result.normalized_score is None and not result.dimensions:
        return SpeechEvaluateResponse(
            success=False,
            provider=result.provider,
            sid=result.sid,
            reference_text=reference,
            error="Speech evaluation did not return a score",
        )

    evidence = None
    if persist_evidence and not fallback:
        evidence = get_learner_evidence_service().append_event(
            {
                "id": f"ev_iflytek_speech_eval_{uuid.uuid4().hex}",
                "source": "iflytek_speech_eval",
                "source_id": result.sid or "",
                "verb": "evaluated",
                "object_type": "oral_practice",
                "object_id": task_id or node_id or "speech_eval",
                "title": title.strip() or "口语练习评测",
                "summary": reference[:300],
                "course_id": course_id,
                "node_id": node_id,
                "task_id": task_id,
                "resource_type": "audio",
                "score": result.normalized_score,
                "duration_seconds": round(time.time() - started_at, 3),
                "confidence": 0.82 if result.normalized_score is not None else 0.5,
                "metadata": {
                    "provider": result.provider,
                    "sid": result.sid,
                    "fallback": fallback,
                    "reference_text": reference,
                    "overall_score": result.overall_score,
                    "dimensions": result.dimensions,
                    "raw_result_chars": len(result.raw_text or ""),
                },
            }
        )
    return SpeechEvaluateResponse(
        success=True,
        provider=result.provider,
        sid=result.sid,
        reference_text=reference,
        overall_score=result.overall_score,
        normalized_score=result.normalized_score,
        dimensions=result.dimensions,
        evidence=evidence,
        fallback=fallback,
        fallback_reason=result.raw_text.split("reason=", 1)[-1] if fallback and "reason=" in result.raw_text else None,
    )


async def _read_audio_upload(file: UploadFile) -> bytes:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    filename = (file.filename or "").strip().lower()
    suffix = f".{filename.rsplit('.', 1)[-1]}" if "." in filename else ""
    if content_type and not content_type.startswith("audio/") and content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio content type")
    if suffix and suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported audio file type")
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds 20 MB")
    return audio
