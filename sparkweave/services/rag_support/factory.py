"""RAG pipeline factory."""

from __future__ import annotations

from functools import lru_cache
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

DEFAULT_PROVIDER = "milvus"
LOCAL_PROVIDER = "llamaindex"
SUPPORTED_PROVIDERS = {DEFAULT_PROVIDER, LOCAL_PROVIDER}

# Cached pipeline instances keyed by (provider, kb_base_dir).
_PIPELINE_CACHE: Dict[tuple[str, Optional[str]], Any] = {}


@lru_cache(maxsize=1)
def _llamaindex_runtime_error() -> str:
    """Return an import error message when LlamaIndex would crash this process."""
    if os.getenv("SPARKWEAVE_RAG_SKIP_IMPORT_PREFLIGHT") == "1":
        return ""

    probe = "import numpy\nimport llama_index.core\n"
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"LlamaIndex import preflight failed: {exc}"

    if completed.returncode == 0:
        return ""

    output = "\n".join(
        part.strip()
        for part in (completed.stderr, completed.stdout)
        if part and part.strip()
    )
    tail = "\n".join(output.splitlines()[-8:])
    return tail or f"LlamaIndex import preflight exited with {completed.returncode}."


def _assert_llamaindex_runtime_available() -> None:
    error = _llamaindex_runtime_error()
    if error:
        raise ImportError(
            "LlamaIndex runtime is unavailable in this Python environment.\n"
            f"{error}"
        )


def normalize_provider_name(name: Optional[str] = None) -> str:
    """Return a supported provider name.

    Milvus is the production default. The old local LlamaIndex store remains
    available as an explicit compatibility provider; removed legacy providers
    are treated as Milvus so newly rebuilt knowledge bases land in the vector DB.
    """
    normalized = (name or "").strip().lower()
    if normalized in {"llamaindex", "llama_index", "local", "local_llamaindex"}:
        return LOCAL_PROVIDER
    if normalized in {"milvus", "zilliz", "zilliz_cloud"}:
        return DEFAULT_PROVIDER
    return DEFAULT_PROVIDER


def get_pipeline(
    name: str = DEFAULT_PROVIDER,
    kb_base_dir: Optional[str] = None,
    **kwargs: Any,
):
    """Return the configured RAG pipeline instance."""
    provider = normalize_provider_name(name)
    if provider == LOCAL_PROVIDER:
        _assert_llamaindex_runtime_available()

    if kwargs:
        # When custom kwargs are provided, build a fresh instance and skip
        # the cache to honour overrides.
        if kb_base_dir is not None:
            kwargs.setdefault("kb_base_dir", kb_base_dir)
        return _build_pipeline(provider, **kwargs)

    cache_key = (provider, kb_base_dir)
    if cache_key not in _PIPELINE_CACHE:
        _PIPELINE_CACHE[cache_key] = _build_pipeline(provider, kb_base_dir=kb_base_dir)
    return _PIPELINE_CACHE[cache_key]


def _build_pipeline(provider: str, **kwargs: Any):
    if provider == DEFAULT_PROVIDER:
        from .pipelines.milvus import MilvusPipeline

        return MilvusPipeline(**kwargs)
    if provider == LOCAL_PROVIDER:
        from .pipelines.llamaindex import LlamaIndexPipeline

        return LlamaIndexPipeline(**kwargs)
    raise ValueError(f"Unsupported RAG provider: {provider}")


def reset_pipeline_cache() -> None:
    """Drop cached RAG pipelines so runtime config changes take effect."""
    _PIPELINE_CACHE.clear()


def list_pipelines() -> List[Dict[str, str]]:
    """Return available built-in RAG pipelines."""
    return [
        {
            "id": DEFAULT_PROVIDER,
            "name": "Milvus",
            "description": "Production vector database for scalable course-material retrieval.",
        },
        {
            "id": LOCAL_PROVIDER,
            "name": "LlamaIndex Local",
            "description": "Compatibility fallback using local LlamaIndex JSON storage.",
        },
    ]


__all__ = [
    "DEFAULT_PROVIDER",
    "LOCAL_PROVIDER",
    "SUPPORTED_PROVIDERS",
    "get_pipeline",
    "list_pipelines",
    "normalize_provider_name",
    "reset_pipeline_cache",
]

