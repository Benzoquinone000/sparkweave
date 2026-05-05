"""
System Status API Router
Manages system status checks and model connection tests
"""

import asyncio
from datetime import datetime
import time

from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import Response

from sparkweave.services.config import clear_llm_config_cache, resolve_search_runtime_config
from sparkweave.services.diagnostics import explain_provider_error
from sparkweave.services.embedding import EmbeddingClient, get_embedding_config, reset_embedding_client
from sparkweave.services.llm import complete as llm_complete
from sparkweave.services.llm import get_llm_config, get_token_limit_kwargs
from sparkweave.services.ocr import OCR_SMOKE_TEST_PNG, XfyunOcrConfig, recognize_image_with_iflytek
from sparkweave.services.rag_support.factory import reset_pipeline_cache
from sparkweave.services.search import web_search
from sparkweave.services.tts import (
    TTS_SMOKE_TEST_TEXT,
    XfyunTtsConfig,
    synthesize_speech_with_iflytek,
)

router = APIRouter()


class TestResponse(BaseModel):
    success: bool
    message: str
    model: str | None = None
    response_time_ms: float | None = None
    error: str | None = None


class TtsPreviewRequest(BaseModel):
    text: str


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
        "ocr": {"status": "optional", "provider": None, "testable": True},
        "tts": {"status": "optional", "provider": None, "testable": True},
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
        ocr_config = XfyunOcrConfig.from_env()
        if ocr_config is None:
            result["ocr"]["status"] = "not_configured"
        else:
            result["ocr"]["status"] = "configured"
            result["ocr"]["provider"] = "iflytek"
    except Exception as e:
        result["ocr"]["status"] = "error"
        result["ocr"]["error"] = str(e)

    try:
        tts_config = XfyunTtsConfig.from_env()
        if tts_config is None:
            result["tts"]["status"] = "not_configured"
        else:
            result["tts"]["status"] = "configured"
            result["tts"]["provider"] = "iflytek"
    except Exception as e:
        result["tts"]["status"] = "error"
        result["tts"]["error"] = str(e)

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
        ocr_config = XfyunOcrConfig.from_env()
        if ocr_config is None:
            return TestResponse(
                success=False,
                message="OCR not configured",
                error="Set iFlytek OCR APPID, APIKey and APISecret in Settings.",
            )

        text = await asyncio.to_thread(
            recognize_image_with_iflytek,
            OCR_SMOKE_TEST_PNG,
            encoding="png",
            config=ocr_config,
        )
        response_time = (time.time() - start_time) * 1000
        return TestResponse(
            success=True,
            message="OCR connection successful" if text.strip() else "OCR connection successful; no text detected in smoke image",
            model="iflytek",
            response_time_ms=round(response_time, 2),
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
        if tts_config is None:
            return TestResponse(
                success=False,
                message="TTS not configured",
                error="Set iFlytek TTS APPID, APIKey and APISecret.",
            )

        result = await synthesize_speech_with_iflytek(TTS_SMOKE_TEST_TEXT, config=tts_config)
        response_time = (time.time() - start_time) * 1000
        return TestResponse(
            success=True,
            message="TTS connection successful" if result.audio else "TTS responded but returned empty audio",
            model=f"iflytek:{tts_config.voice}",
            response_time_ms=round(response_time, 2),
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


@router.post("/tts-preview")
async def create_tts_preview(payload: TtsPreviewRequest):
    tts_config = XfyunTtsConfig.from_env()
    if tts_config is None:
        return Response(
            content="TTS not configured",
            status_code=400,
            media_type="text/plain; charset=utf-8",
        )

    result = await synthesize_speech_with_iflytek(payload.text, config=tts_config)
    extension = "mp3" if result.content_type == "audio/mpeg" else "bin"
    headers = {
        "X-SparkWeave-TTS-Voice": result.voice,
        "X-SparkWeave-TTS-Encoding": result.encoding,
        "X-SparkWeave-TTS-Sample-Rate": str(result.sample_rate),
        "Content-Disposition": f'inline; filename="sparkweave-tts-preview.{extension}"',
    }
    if result.sid:
        headers["X-SparkWeave-TTS-SID"] = result.sid
    return Response(content=result.audio, media_type=result.content_type, headers=headers)


