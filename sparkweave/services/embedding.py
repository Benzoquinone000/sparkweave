"""Embedding service facade owned by ``sparkweave``."""

from sparkweave.services.embedding_support import (
    BaseEmbeddingAdapter,
    CohereEmbeddingAdapter,
    EmbeddingClient,
    EmbeddingConfig,
    EmbeddingRequest,
    EmbeddingResponse,
    JinaEmbeddingAdapter,
    OllamaEmbeddingAdapter,
    OpenAICompatibleEmbeddingAdapter,
    get_embedding_client,
    get_embedding_config,
    reset_embedding_client,
)

__all__ = [
    "BaseEmbeddingAdapter",
    "CohereEmbeddingAdapter",
    "EmbeddingClient",
    "EmbeddingConfig",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "JinaEmbeddingAdapter",
    "OllamaEmbeddingAdapter",
    "OpenAICompatibleEmbeddingAdapter",
    "get_embedding_client",
    "get_embedding_config",
    "reset_embedding_client",
]

