"""RAG pipeline factory.

The project ships with a single LlamaIndex-backed pipeline. The helpers
below remain because several call-sites import them; they have all been
collapsed to operate on the single supported pipeline.
"""

from __future__ import annotations

from functools import lru_cache
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

DEFAULT_PROVIDER = "llamaindex"

# Cached pipeline instances keyed by kb_base_dir.
_PIPELINE_CACHE: Dict[Optional[str], Any] = {}


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


def normalize_provider_name(_name: Optional[str] = None) -> str:
    """Always return the canonical provider name.

    Older configs/migrations may carry legacy provider strings (e.g.
    ``lightrag``); they are all treated as the only supported pipeline.
    """
    return DEFAULT_PROVIDER


def get_pipeline(
    name: str = DEFAULT_PROVIDER,
    kb_base_dir: Optional[str] = None,
    **kwargs: Any,
):
    """Return the (cached) LlamaIndex pipeline instance.

    The ``name`` argument is accepted for backward compatibility but is
    ignored; only the LlamaIndex pipeline is supported.
    """
    _assert_llamaindex_runtime_available()

    from .pipelines.llamaindex import LlamaIndexPipeline

    if kwargs:
        # When custom kwargs are provided, build a fresh instance and skip
        # the cache to honour overrides.
        if kb_base_dir is not None:
            kwargs.setdefault("kb_base_dir", kb_base_dir)
        return LlamaIndexPipeline(**kwargs)

    if kb_base_dir not in _PIPELINE_CACHE:
        _PIPELINE_CACHE[kb_base_dir] = LlamaIndexPipeline(kb_base_dir=kb_base_dir)
    return _PIPELINE_CACHE[kb_base_dir]


def reset_pipeline_cache() -> None:
    """Drop cached RAG pipelines so runtime config changes take effect."""
    _PIPELINE_CACHE.clear()


def list_pipelines() -> List[Dict[str, str]]:
    """Return the single available pipeline (kept for callers that still ask)."""
    return [
        {
            "id": DEFAULT_PROVIDER,
            "name": "LlamaIndex",
            "description": "Pure vector retrieval, fastest processing speed.",
        }
    ]


__all__ = [
    "DEFAULT_PROVIDER",
    "get_pipeline",
    "list_pipelines",
    "normalize_provider_name",
    "reset_pipeline_cache",
]

