"""
System Status API Router
Manages system status checks and model connection tests
"""

import asyncio
import base64
import binascii
from datetime import datetime
import os
import time

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from sparkweave.services.config import (
    clear_llm_config_cache,
    get_env_store,
    resolve_search_runtime_config,
)
from sparkweave.services.diagnostics import explain_provider_error
from sparkweave.services.embedding import (
    EmbeddingClient,
    get_embedding_config,
    reset_embedding_client,
)
from sparkweave.services.iflytek_formula import (
    IflytekFormulaConfig,
)
from sparkweave.services.iflytek_formula import (
    recognize_formula_image_with_fallback as recognize_formula_image,
)
from sparkweave.services.iflytek_offline import offline_fallback_enabled
from sparkweave.services.iflytek_vision import IflytekVisionConfig
from sparkweave.services.iflytek_vision import understand_image_with_fallback as understand_image
from sparkweave.services.iflytek_workflow import (
    IflytekWorkflowConfig,
)
from sparkweave.services.iflytek_workflow import (
    call_iflytek_workflow_with_fallback as call_iflytek_workflow,
)
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.llm import get_llm_config, get_token_limit_kwargs
from sparkweave.services.ocr import (
    OCR_SMOKE_TEST_PNG,
    resolve_ocr_config,
)
from sparkweave.services.ocr import (
    recognize_image_with_fallback as recognize_image,
)
from sparkweave.services.rag_support.diagnostics import default_milvus_uri
from sparkweave.services.rag_support.factory import (
    DEFAULT_PROVIDER as DEFAULT_RAG_PROVIDER,
)
from sparkweave.services.rag_support.factory import (
    normalize_provider_name,
    reset_pipeline_cache,
)
from sparkweave.services.search import web_search
from sparkweave.services.speech import (
    XfyunAsrConfig,
    XfyunSpeechEvalConfig,
    evaluate_speech_with_iflytek,
    transcribe_audio_with_iflytek,
)
from sparkweave.services.tts import (
    TTS_SMOKE_TEST_TEXT,
    XfyunTtsConfig,
)
from sparkweave.services.tts import (
    synthesize_speech_with_fallback as synthesize_speech_with_iflytek,
)

router = APIRouter()


def _make_silence_wav(*, sample_rate: int = 16_000, duration_ms: int = 240) -> bytes:
    frames = max(int(sample_rate * duration_ms / 1000), 1)
    payload = b"\x00\x00" * frames
    byte_rate = sample_rate * 2
    riff_size = 36 + len(payload)
    return (
        b"RIFF"
        + riff_size.to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + byte_rate.to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + len(payload).to_bytes(4, "little")
        + payload
    )


MAX_TTS_PREVIEW_CHARS = 2_000
MAX_OCR_PREVIEW_IMAGE_BYTES = 10 * 1024 * 1024
ASR_SMOKE_TEST_AUDIO = _make_silence_wav()
SPEECH_EVAL_SMOKE_TEST_AUDIO = ASR_SMOKE_TEST_AUDIO
SPEECH_EVAL_SMOKE_REFERENCE = "你好，欢迎使用 SparkWeave。"
OCR_PREVIEW_MIME_TO_ENCODING = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
OCR_PREVIEW_ALLOWED_ENCODINGS = {"png", "jpg", "jpeg", "gif", "webp"}


def _env_value(name: str, default: str = "") -> str:
    try:
        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _offline_status(provider: str, message: str) -> dict[str, object]:
    return {
        "status": "fallback",
        "provider": provider,
        "model": provider,
        "testable": True,
        "fallback": True,
        "fallback_reason": message,
        "error": message,
    }


class TestResponse(BaseModel):
    success: bool
    message: str
    model: str | None = None
    response_time_ms: float | None = None
    error: str | None = None


class TtsPreviewRequest(BaseModel):
    text: str


class OcrPreviewRequest(BaseModel):
    image_base64: str
    encoding: str | None = None


class OcrPreviewResponse(BaseModel):
    success: bool
    text: str = ""
    provider: str | None = None
    model: str | None = None
    error: str | None = None


@router.get("/runtime-topology")
async def get_runtime_topology():
    """
    Describe the current execution topology.

    This makes the unified runtime explicit for operators and frontend code:
    interactive chat turns should prefer `/api/v1/ws`, while a few routers still
    exist as compatibility or isolated subsystem endpoints.
    """
    return {
        "primary_runtime": {
            "transport": "/api/v1/ws",
            "manager": "LangGraphTurnRuntimeManager",
            "orchestrator": "LangGraphRunner",
            "session_store": "SQLiteSessionStore",
            "capability_entry": "CapabilityRegistry",
            "tool_entry": "ToolRegistry",
        },
        "compatibility_routes": [
            {"router": "chat", "mode": "ng_router"},
            {"router": "solve", "mode": "ng_router"},
            {"router": "question", "mode": "ng_router"},
            {"router": "research", "mode": "ng_router"},
        ],
        "isolated_subsystems": [
            {"router": "guide", "mode": "independent_subsystem"},
            {"router": "co_writer", "mode": "independent_subsystem"},
            {"router": "plugins_api", "mode": "playground_transport"},
        ],
    }


@router.get("/status")
async def get_system_status():
    """
    Get overall system status including backend and model configurations

    Returns:
        Dictionary containing status of backend, LLM, embeddings, and search
    """
    result = {
        "backend": {"status": "online", "timestamp": datetime.now().isoformat()},
        "llm": {"status": "unknown", "model": None, "testable": True},
        "embeddings": {"status": "unknown", "model": None, "testable": True},
        "search": {"status": "optional", "provider": None, "testable": True},
        "rag": {"status": "unknown", "provider": None, "uri": None, "testable": False},
        "ocr": {"status": "optional", "provider": None, "testable": True},
        "tts": {"status": "optional", "provider": None, "testable": True},
        "asr": {"status": "optional", "provider": None, "testable": True},
        "speech_eval": {"status": "optional", "provider": None, "testable": True},
        "iflytek_workflow": {"status": "optional", "provider": None, "testable": True},
        "formula_ocr": {"status": "optional", "provider": None, "testable": True},
        "image_understanding": {"status": "optional", "provider": None, "testable": True},
    }

    # Check backend status (this endpoint itself proves backend is online)
    result["backend"]["status"] = "online"

    # Check LLM configuration
    try:
        llm_config = get_llm_config()
        result["llm"]["model"] = llm_config.model
        result["llm"]["status"] = "configured"
    except ValueError as e:
        result["llm"]["status"] = "not_configured"
        result["llm"]["error"] = str(e)
    except Exception as e:
        result["llm"]["status"] = "error"
        result["llm"]["error"] = str(e)

    # Check Embeddings configuration
    try:
        embedding_config = get_embedding_config()
        result["embeddings"]["model"] = embedding_config.model
        result["embeddings"]["status"] = "configured"
    except ValueError as e:
        result["embeddings"]["status"] = "not_configured"
        result["embeddings"]["error"] = str(e)
    except Exception as e:
        result["embeddings"]["status"] = "error"
        result["embeddings"]["error"] = str(e)

    try:
        search_config = resolve_search_runtime_config()
        if search_config.requested_provider:
            result["search"]["provider"] = search_config.provider
            if search_config.unsupported_provider:
                result["search"]["status"] = "unsupported"
                result["search"]["error"] = (
                    f"{search_config.requested_provider} is deprecated/unsupported. "
                    "Switch to brave/tavily/jina/searxng/duckduckgo/perplexity/serper/iflytek_spark."
                )
            elif search_config.deprecated_provider:
                result["search"]["status"] = "deprecated"
                result["search"]["error"] = (
                    f"{search_config.requested_provider} is deprecated. "
                    "Switch to brave/tavily/jina/searxng/duckduckgo/perplexity/serper/iflytek_spark."
                )
            elif search_config.missing_credentials:
                result["search"]["status"] = "not_configured"
                result["search"]["error"] = (
                    f"{search_config.requested_provider} requires api_key. "
                    "Set profile.api_key or the provider-specific API key env var."
                )
            else:
                result["search"]["status"] = "configured"
                if search_config.fallback_reason:
                    result["search"]["status"] = "fallback"
                    result["search"]["error"] = search_config.fallback_reason
    except Exception as e:
        result["search"]["status"] = "error"
        result["search"]["error"] = str(e)

    try:
        rag_provider = normalize_provider_name(_env_value("RAG_PROVIDER", DEFAULT_RAG_PROVIDER))
        result["rag"]["provider"] = rag_provider
        result["rag"]["status"] = "configured"
        if rag_provider == "milvus":
            result["rag"]["uri"] = _env_value("MILVUS_URI", default_milvus_uri())
        else:
            result["rag"]["uri"] = "local"
    except Exception as e:
        result["rag"]["status"] = "error"
        result["rag"]["error"] = str(e)

    try:
        ocr_config = resolve_ocr_config()
        if ocr_config is None:
            if offline_fallback_enabled():
                result["ocr"].update(
                    _offline_status(
                        "offline_iflytek_fallback:ocr",
                        "OCR provider is not configured; offline fallback will ask for text confirmation.",
                    )
                )
            else:
                result["ocr"]["status"] = "not_configured"
        else:
            result["ocr"]["status"] = "configured"
            result["ocr"]["provider"] = getattr(ocr_config, "provider", "ocr")
    except Exception as e:
        result["ocr"]["status"] = "error"
        result["ocr"]["error"] = str(e)

    try:
        tts_config = XfyunTtsConfig.from_env()
        if tts_config is None:
            if offline_fallback_enabled():
                result["tts"].update(
                    _offline_status(
                        "offline_iflytek_fallback:tts",
                        "iFlytek TTS is not configured; offline fallback can keep audio previews available.",
                    )
                )
            else:
                result["tts"]["status"] = "not_configured"
        else:
            result["tts"]["status"] = "configured"
            result["tts"]["provider"] = "iflytek"
    except Exception as e:
        result["tts"]["status"] = "error"
        result["tts"]["error"] = str(e)

    try:
        asr_config = XfyunAsrConfig.from_env()
        if asr_config is None:
            if offline_fallback_enabled():
                result["asr"].update(
                    _offline_status(
                        "offline_iflytek_fallback:asr",
                        "iFlytek ASR is not configured; offline fallback will ask for text confirmation.",
                    )
                )
            else:
                result["asr"]["status"] = "not_configured"
        else:
            result["asr"]["status"] = "configured"
            result["asr"]["provider"] = "iflytek"
    except Exception as e:
        result["asr"]["status"] = "error"
        result["asr"]["error"] = str(e)

    try:
        speech_eval_config = XfyunSpeechEvalConfig.from_env()
        if speech_eval_config is None:
            if offline_fallback_enabled():
                result["speech_eval"].update(
                    _offline_status(
                        "offline_iflytek_fallback:speech_eval",
                        "iFlytek speech evaluation is not configured; offline fallback returns heuristic scores.",
                    )
                )
            else:
                result["speech_eval"]["status"] = "not_configured"
        else:
            result["speech_eval"]["status"] = "configured"
            result["speech_eval"]["provider"] = "iflytek"
    except Exception as e:
        result["speech_eval"]["status"] = "error"
        result["speech_eval"]["error"] = str(e)

    try:
        workflow_config = IflytekWorkflowConfig.from_env()
        if workflow_config is None:
            if offline_fallback_enabled():
                result["iflytek_workflow"].update(
                    _offline_status(
                        "offline_iflytek_fallback:workflow",
                        "iFlytek workflow is not configured; offline fallback will generate a structured rehearsal plan.",
                    )
                )
            else:
                result["iflytek_workflow"]["status"] = "not_configured"
        else:
            result["iflytek_workflow"]["status"] = "configured"
            result["iflytek_workflow"]["provider"] = "iflytek_workflow"
            result["iflytek_workflow"]["model"] = workflow_config.flow_id
    except Exception as e:
        result["iflytek_workflow"]["status"] = "error"
        result["iflytek_workflow"]["error"] = str(e)

    try:
        formula_config = IflytekFormulaConfig.from_env()
        if formula_config is None:
            if offline_fallback_enabled():
                result["formula_ocr"].update(
                    _offline_status(
                        "offline_iflytek_fallback:formula_ocr",
                        "iFlytek formula recognition is not configured; offline fallback will ask for formula confirmation.",
                    )
                )
            else:
                result["formula_ocr"]["status"] = "not_configured"
        else:
            result["formula_ocr"]["status"] = "configured"
            result["formula_ocr"]["provider"] = formula_config.provider
            result["formula_ocr"]["model"] = formula_config.ent
    except Exception as e:
        result["formula_ocr"]["status"] = "error"
        result["formula_ocr"]["error"] = str(e)

    try:
        vision_config = IflytekVisionConfig.from_env()
        if vision_config is None:
            if offline_fallback_enabled():
                result["image_understanding"].update(
                    _offline_status(
                        "offline_iflytek_fallback:image_understanding",
                        "iFlytek image understanding is not configured; offline fallback will describe image metadata.",
                    )
                )
            else:
                result["image_understanding"]["status"] = "not_configured"
        else:
            result["image_understanding"]["status"] = "configured"
            result["image_understanding"]["provider"] = vision_config.provider
            result["image_understanding"]["model"] = vision_config.domain
    except Exception as e:
        result["image_understanding"]["status"] = "error"
        result["image_understanding"]["error"] = str(e)

    return result


@router.post("/test/llm", response_model=TestResponse)
async def test_llm_connection():
    """
    Test LLM model connection by sending a simple completion request

    Returns:
        Test result with success status and response time
    """
    start_time = time.time()

    try:
        clear_llm_config_cache()
        llm_config = get_llm_config()
        model = llm_config.model
        base_url = llm_config.base_url.rstrip("/")

        # Sanitize Base URL (remove /chat/completions suffix if present)
        for suffix in ["/chat/completions", "/completions"]:
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]

        # Handle API Key (inject dummy if missing for local LLMs)
        api_key = llm_config.api_key
        if not api_key:
            api_key = "sk-no-key-required"

        # Send a minimal test request with a prompt that guarantees output
        test_prompt = "Say 'OK' to confirm you are working. Do not produce long output."
        token_kwargs = get_token_limit_kwargs(model, max_tokens=200)

        response = await llm_complete(
            model=model,
            prompt=test_prompt,
            system_prompt="You are a helpful assistant. Respond briefly.",
            binding=llm_config.binding,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1,
            **token_kwargs,
        )

        response_time = (time.time() - start_time) * 1000

        if response and len(response.strip()) > 0:
            return TestResponse(
                success=True,
                message="LLM connection successful",
                model=model,
                response_time_ms=round(response_time, 2),
            )
        return TestResponse(
            success=False,
            message="LLM connection failed: Empty response",
            model=model,
            error="Empty response from API",
        )

    except ValueError as e:
        detail = explain_provider_error("llm", e)
        return TestResponse(success=False, message=f"LLM configuration error: {detail}", error=detail)
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("llm", e)
        return TestResponse(
            success=False,
            message=f"LLM connection failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/embeddings", response_model=TestResponse)
async def test_embeddings_connection():
    """
    Test Embeddings model connection by sending a simple embedding request

    Returns:
        Test result with success status and response time
    """
    start_time = time.time()

    try:
        reset_embedding_client()
        reset_pipeline_cache()
        embedding_config = get_embedding_config()
        embedding_client = EmbeddingClient(embedding_config)

        model = embedding_config.model
        binding = embedding_config.binding

        # Send a minimal test request using unified client
        test_texts = ["test"]
        embeddings = await embedding_client.embed(test_texts)

        response_time = (time.time() - start_time) * 1000

        if embeddings is not None and len(embeddings) > 0 and len(embeddings[0]) > 0:
            return TestResponse(
                success=True,
                message=f"Embeddings connection successful ({binding} provider)",
                model=model,
                response_time_ms=round(response_time, 2),
            )
        return TestResponse(
            success=False,
            message="Embeddings connection failed: Empty response",
            model=model,
            error="Empty embedding vector",
        )

    except ValueError as e:
        detail = explain_provider_error("embedding", e)
        return TestResponse(
            success=False, message=f"Embeddings configuration error: {detail}", error=detail
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("embedding", e)
        return TestResponse(
            success=False,
            message=f"Embeddings connection failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/search", response_model=TestResponse)
async def test_search_connection():
    start_time = time.time()

    try:
        search_config = resolve_search_runtime_config()
        if not search_config.requested_provider:
            return TestResponse(
                success=False,
                message="Search not configured",
                error="Missing SEARCH_PROVIDER",
            )
        if search_config.unsupported_provider:
            return TestResponse(
                success=False,
                message=(
                    f"Search provider `{search_config.requested_provider}` is deprecated/unsupported."
                ),
                error="Switch to brave/tavily/jina/searxng/duckduckgo/perplexity/serper/iflytek_spark",
            )
        if search_config.missing_credentials:
            return TestResponse(
                success=False,
                message=f"Search provider `{search_config.requested_provider}` missing credentials.",
                error="Set profile.api_key or the provider-specific API key env var.",
            )
        result = await web_search(query="SparkWeave health check", provider=search_config.provider)
        response_time = (time.time() - start_time) * 1000
        answer = result.get("answer") or result.get("search_results")
        if not answer:
            raise ValueError("Search provider returned no content")
        return TestResponse(
            success=True,
            message="Search connection successful",
            model=search_config.provider,
            response_time_ms=round(response_time, 2),
        )

    except ValueError as e:
        return TestResponse(success=False, message=f"Search configuration error: {e!s}", error=str(e))
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("search", e)
        return TestResponse(
            success=False,
            message=f"Search connection check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/ocr", response_model=TestResponse)
async def test_ocr_connection():
    start_time = time.time()

    try:
        ocr_config = resolve_ocr_config()
        if ocr_config is None and offline_fallback_enabled():
            response_time = (time.time() - start_time) * 1000
            return TestResponse(
                success=True,
                message="OCR offline fallback is ready",
                model="offline_iflytek_fallback:ocr",
                response_time_ms=round(response_time, 2),
                error="OCR provider is not configured; offline fallback will ask for text confirmation.",
            )
        text = await asyncio.to_thread(
            recognize_image,
            OCR_SMOKE_TEST_PNG,
            encoding="png",
            config=ocr_config,
        )
        response_time = (time.time() - start_time) * 1000
        fallback = ocr_config is None and "离线 OCR 替补" in text
        provider = "offline_iflytek_fallback:ocr" if fallback else getattr(ocr_config, "provider", "ocr")
        model = f"{provider}:{getattr(ocr_config, 'model', '')}".rstrip(":")
        return TestResponse(
            success=True,
            message=(
                "OCR offline fallback is ready"
                if fallback
                else "OCR connection successful"
                if text.strip()
                else "OCR connection successful; no text detected in smoke image"
            ),
            model=model,
            response_time_ms=round(response_time, 2),
            error="OCR provider is not configured; offline fallback will ask for text confirmation." if fallback else None,
        )

    except ValueError as e:
        detail = explain_provider_error("ocr", e)
        return TestResponse(success=False, message=f"OCR configuration error: {detail}", error=detail)
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("ocr", e)
        return TestResponse(
            success=False,
            message=f"OCR connection check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/tts", response_model=TestResponse)
async def test_tts_connection():
    start_time = time.time()

    try:
        tts_config = XfyunTtsConfig.from_env()
        result = await synthesize_speech_with_iflytek(TTS_SMOKE_TEST_TEXT, config=tts_config)
        response_time = (time.time() - start_time) * 1000
        voice = getattr(result, "voice", tts_config.voice if tts_config else "unknown")
        fallback = voice == "offline-iflytek-fallback"
        return TestResponse(
            success=True,
            message=(
                "TTS offline fallback is ready"
                if fallback
                else "TTS connection successful"
                if result.audio
                else "TTS responded but returned empty audio"
            ),
            model=f"offline_iflytek_fallback:{voice}" if fallback else f"iflytek:{tts_config.voice if tts_config else voice}",
            response_time_ms=round(response_time, 2),
            error=getattr(result, "phonetic_text", None) if fallback else None,
        )

    except ValueError as e:
        detail = explain_provider_error("tts", e)
        return TestResponse(success=False, message=f"TTS configuration error: {detail}", error=detail)
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("tts", e)
        return TestResponse(
            success=False,
            message=f"TTS connection check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/asr", response_model=TestResponse)
async def test_asr_connection():
    start_time = time.time()

    try:
        asr_config = XfyunAsrConfig.from_env()
        if asr_config is None:
            if offline_fallback_enabled():
                response_time = (time.time() - start_time) * 1000
                return TestResponse(
                    success=True,
                    message="ASR offline fallback is ready",
                    model="offline_iflytek_fallback:asr",
                    response_time_ms=round(response_time, 2),
                    error="iFlytek ASR is not configured; offline fallback will ask for text confirmation.",
                )
            return TestResponse(
                success=False,
                message="ASR not configured",
                error="Set iFlytek ASR APPID, APIKey and APISecret.",
            )

        result = await transcribe_audio_with_iflytek(
            ASR_SMOKE_TEST_AUDIO,
            config=asr_config,
            audio_encoding="raw",
        )
        response_time = (time.time() - start_time) * 1000
        recognized = (result.text or "").strip()
        return TestResponse(
            success=True,
            message=(
                "ASR connection successful"
                if recognized
                else "ASR connection successful; no speech text recognized in smoke audio"
            ),
            model=f"iflytek:{asr_config.language}/{asr_config.domain}",
            response_time_ms=round(response_time, 2),
        )

    except ValueError as e:
        detail = explain_provider_error("asr", e)
        return TestResponse(success=False, message=f"ASR configuration error: {detail}", error=detail)
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("asr", e)
        return TestResponse(
            success=False,
            message=f"ASR connection check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/speech_eval", response_model=TestResponse)
async def test_speech_eval_connection():
    start_time = time.time()

    try:
        eval_config = XfyunSpeechEvalConfig.from_env()
        if eval_config is None:
            if offline_fallback_enabled():
                response_time = (time.time() - start_time) * 1000
                return TestResponse(
                    success=True,
                    message="Speech evaluation offline fallback is ready",
                    model="offline_iflytek_fallback:speech_eval",
                    response_time_ms=round(response_time, 2),
                    error="iFlytek speech evaluation is not configured; offline fallback returns heuristic scores.",
                )
            return TestResponse(
                success=False,
                message="Speech evaluation not configured",
                error="Set iFlytek speech evaluation APPID, APIKey and APISecret.",
            )

        result = await evaluate_speech_with_iflytek(
            SPEECH_EVAL_SMOKE_TEST_AUDIO,
            reference_text=SPEECH_EVAL_SMOKE_REFERENCE,
            config=eval_config,
        )
        response_time = (time.time() - start_time) * 1000
        has_score = result.normalized_score is not None or bool(result.dimensions)
        return TestResponse(
            success=True,
            message=(
                "Speech evaluation connection successful"
                if has_score
                else "Speech evaluation responded; no score returned for smoke audio"
            ),
            model=f"iflytek:{eval_config.category}/{eval_config.language}",
            response_time_ms=round(response_time, 2),
            error=None if has_score else "No score returned for smoke audio.",
        )

    except ValueError as e:
        detail = explain_provider_error("speech_eval", e)
        return TestResponse(
            success=False,
            message=f"Speech evaluation configuration error: {detail}",
            error=detail,
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("speech_eval", e)
        return TestResponse(
            success=False,
            message=f"Speech evaluation check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/iflytek_workflow", response_model=TestResponse)
async def test_iflytek_workflow_connection():
    start_time = time.time()

    try:
        workflow_config = IflytekWorkflowConfig.from_env()
        result = await call_iflytek_workflow(
            "请用一句话回复：SparkWeave 讯飞工作流连接测试成功。",
            config=workflow_config,
        )
        response_time = (time.time() - start_time) * 1000
        fallback = bool(result.get("fallback"))
        return TestResponse(
            success=bool(result.get("content")),
            message=(
                "iFlytek workflow offline fallback is ready"
                if fallback
                else "iFlytek workflow connection successful"
                if result.get("content")
                else "iFlytek workflow responded but returned empty content"
            ),
            model=(
                f"offline_iflytek_fallback:{result.get('flow_id') or 'workflow'}"
                if fallback
                else f"iflytek_workflow:{workflow_config.flow_id if workflow_config else ''}"
            ),
            response_time_ms=round(response_time, 2),
            error=str(result.get("fallback_reason") or "") or None,
        )

    except ValueError as e:
        detail = explain_provider_error("iflytek_workflow", e)
        return TestResponse(success=False, message=f"iFlytek workflow configuration error: {detail}", error=detail)
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("iflytek_workflow", e)
        return TestResponse(
            success=False,
            message=f"iFlytek workflow check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/formula_ocr", response_model=TestResponse)
async def test_formula_ocr_connection():
    start_time = time.time()

    try:
        formula_config = IflytekFormulaConfig.from_env()
        result = await recognize_formula_image(OCR_SMOKE_TEST_PNG, config=formula_config)
        response_time = (time.time() - start_time) * 1000
        fallback = bool(result.get("fallback"))
        return TestResponse(
            success=True,
            message=(
                "iFlytek formula recognition offline fallback is ready"
                if fallback
                else (
                "iFlytek formula recognition connection successful"
                if result.get("text")
                else "iFlytek formula recognition responded; no formula detected in smoke image"
                )
            ),
            model=(
                "offline_iflytek_fallback:formula_ocr"
                if fallback
                else f"iflytek_formula:{formula_config.ent if formula_config else ''}"
            ),
            response_time_ms=round(response_time, 2),
            error=str(result.get("fallback_reason") or "") or None,
        )

    except ValueError as e:
        detail = explain_provider_error("formula_ocr", e)
        return TestResponse(
            success=False,
            message=f"iFlytek formula recognition configuration error: {detail}",
            error=detail,
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("formula_ocr", e)
        return TestResponse(
            success=False,
            message=f"iFlytek formula recognition check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/test/image_understanding", response_model=TestResponse)
async def test_image_understanding_connection():
    start_time = time.time()

    try:
        vision_config = IflytekVisionConfig.from_env()
        result = await understand_image(
            OCR_SMOKE_TEST_PNG,
            prompt="请用一句话描述图片里能看到的内容。",
            mime_type="image/png",
            config=vision_config,
        )
        response_time = (time.time() - start_time) * 1000
        fallback = bool(result.get("fallback"))
        return TestResponse(
            success=bool(result.get("content")) or bool(result.get("events")),
            message=(
                "iFlytek image understanding offline fallback is ready"
                if fallback
                else (
                "iFlytek image understanding connection successful"
                if result.get("content")
                else "iFlytek image understanding responded; no text returned"
                )
            ),
            model=(
                "offline_iflytek_fallback:image_understanding"
                if fallback
                else f"iflytek_image:{vision_config.domain if vision_config else ''}"
            ),
            response_time_ms=round(response_time, 2),
            error=str(result.get("fallback_reason") or "") or None,
        )

    except ValueError as e:
        detail = explain_provider_error("image_understanding", e)
        return TestResponse(
            success=False,
            message=f"iFlytek image understanding configuration error: {detail}",
            error=detail,
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        detail = explain_provider_error("image_understanding", e)
        return TestResponse(
            success=False,
            message=f"iFlytek image understanding check failed: {detail}",
            response_time_ms=round(response_time, 2),
            error=detail,
        )


@router.post("/tts-preview")
async def create_tts_preview(payload: TtsPreviewRequest):
    text = payload.text.strip()
    if not text:
        return Response(
            content="TTS preview text is empty",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )
    if len(text) > MAX_TTS_PREVIEW_CHARS:
        return Response(
            content=f"TTS preview text exceeds {MAX_TTS_PREVIEW_CHARS} characters",
            status_code=413,
            media_type="text/plain; charset=utf-8",
        )

    tts_config = XfyunTtsConfig.from_env()
    result = await synthesize_speech_with_iflytek(text, config=tts_config)
    extension = "mp3" if result.content_type == "audio/mpeg" else "wav" if result.content_type == "audio/wav" else "bin"
    headers = {
        "X-SparkWeave-TTS-Voice": result.voice,
        "X-SparkWeave-TTS-Encoding": result.encoding,
        "X-SparkWeave-TTS-Sample-Rate": str(result.sample_rate),
        "Content-Disposition": f'inline; filename="sparkweave-tts-preview.{extension}"',
    }
    if result.voice == "offline-iflytek-fallback":
        headers["X-SparkWeave-TTS-Fallback"] = "true"
        if result.phonetic_text:
            headers["X-SparkWeave-TTS-Fallback-Reason"] = result.phonetic_text
    if result.sid:
        headers["X-SparkWeave-TTS-SID"] = result.sid
    return Response(content=result.audio, media_type=result.content_type, headers=headers)


@router.post("/ocr-preview", response_model=OcrPreviewResponse)
async def create_ocr_preview(payload: OcrPreviewRequest):
    ocr_config = resolve_ocr_config()

    requested_encoding = (payload.encoding or "").strip().lower().lstrip(".")
    if requested_encoding == "jpeg":
        requested_encoding = "jpg"
    if requested_encoding and requested_encoding not in OCR_PREVIEW_ALLOWED_ENCODINGS:
        return OcrPreviewResponse(
            success=False,
            error="Unsupported image type",
        )

    raw = payload.image_base64.strip()
    if raw.startswith("data:"):
        header, separator, data = raw.partition(",")
        if not separator:
            return OcrPreviewResponse(
                success=False,
                error="Invalid image data URI",
            )
        if ";base64" not in header.lower():
            return OcrPreviewResponse(
                success=False,
                error="Image data URI must be base64 encoded",
            )
        mime_type = header[5:].split(";", 1)[0].strip().lower()
        if mime_type:
            data_uri_encoding = OCR_PREVIEW_MIME_TO_ENCODING.get(mime_type)
            if data_uri_encoding is None:
                return OcrPreviewResponse(
                    success=False,
                    error="Unsupported image type",
                )
            if requested_encoding and requested_encoding != data_uri_encoding:
                return OcrPreviewResponse(
                    success=False,
                    error="Image MIME type does not match encoding",
                )
            requested_encoding = data_uri_encoding
        raw = data

    requested_encoding = requested_encoding or "png"

    try:
        image = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return OcrPreviewResponse(
            success=False,
            error="Invalid base64 image",
        )
    if not image:
        return OcrPreviewResponse(
            success=False,
            error="Empty image",
        )
    if len(image) > MAX_OCR_PREVIEW_IMAGE_BYTES:
        return OcrPreviewResponse(
            success=False,
            error="Image exceeds 10 MB",
        )

    try:
        text = await asyncio.to_thread(
            recognize_image,
            image,
            encoding=requested_encoding,
            config=ocr_config,
        )
        provider = getattr(ocr_config, "provider", "offline_iflytek_fallback:ocr")
        model = f"{provider}:{getattr(ocr_config, 'model', '')}".rstrip(":")
        return OcrPreviewResponse(
            success=True,
            text=text,
            provider=provider,
            model=model,
        )
    except Exception as exc:
        detail = explain_provider_error("ocr", exc)
        return OcrPreviewResponse(
            success=False,
            provider=getattr(ocr_config, "provider", "ocr"),
            error=detail,
        )


