"""Pre-configured RAG pipelines.

SparkWeave ships with Milvus as the production vector database and keeps the
local LlamaIndex store as a compatibility fallback.
"""

from typing import Any

__all__ = [
    "LlamaIndexPipeline",
    "MilvusPipeline",
]


def __getattr__(name: str) -> Any:
    if name == "LlamaIndexPipeline":
        from .llamaindex import LlamaIndexPipeline

        return LlamaIndexPipeline
    if name == "MilvusPipeline":
        from .milvus import MilvusPipeline

        return MilvusPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

