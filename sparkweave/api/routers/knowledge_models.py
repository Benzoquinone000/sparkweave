"""Request and response models for the knowledge-base API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

MAX_RAG_QUERY_CHARS = 2_000
MAX_RAG_EVAL_CASES = 30
MAX_RAG_EVAL_STRATEGIES = 8
MAX_RAG_EXPECTED_ITEMS = 50
MAX_RAG_LABEL_CHARS = 120


class KnowledgeBaseInfo(BaseModel):
    name: str
    is_default: bool
    statistics: dict
    status: str | None = None
    progress: dict | None = None


class LinkFolderRequest(BaseModel):
    """Request model for linking a local folder to a KB."""

    folder_path: str = Field(..., min_length=1, max_length=1024)


class LinkedFolderInfo(BaseModel):
    """Response model for linked folder information."""

    id: str
    path: str
    added_at: str
    file_count: int


class ReindexKnowledgeBaseRequest(BaseModel):
    """Request model for rebuilding a knowledge-base index."""

    rag_provider: str | None = None
    backup: bool = True


class RagEvaluationCase(BaseModel):
    """One user-facing RAG evaluation case."""

    id: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    question: str = Field(..., min_length=1, max_length=MAX_RAG_QUERY_CHARS)
    kb_name: str | None = Field(default=None, max_length=180)
    query_type: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    topic: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    expected_keywords: list[str] = Field(default_factory=list, max_length=MAX_RAG_EXPECTED_ITEMS)
    expected_sources: list[str] = Field(default_factory=list, max_length=MAX_RAG_EXPECTED_ITEMS)


class RagEvaluationStrategyRequest(BaseModel):
    """One retrieval strategy supplied by API clients."""

    name: str = Field(..., min_length=1, max_length=MAX_RAG_LABEL_CHARS)
    params: dict[str, Any] = Field(default_factory=dict)


class RagEvaluationRequest(BaseModel):
    """Request model for quick RAG quality evaluation."""

    cases: list[RagEvaluationCase] = Field(..., min_length=1, max_length=MAX_RAG_EVAL_CASES)
    strategies: list[RagEvaluationStrategyRequest] | None = Field(default=None, max_length=MAX_RAG_EVAL_STRATEGIES)
    provider: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    baseline_strategy: str = Field(default="baseline", max_length=MAX_RAG_LABEL_CHARS)
    preset: str = Field(default="default", max_length=MAX_RAG_LABEL_CHARS)


class RagSearchTestRequest(BaseModel):
    """Request model for one interactive RAG retrieval test."""

    query: str = Field(..., min_length=1, max_length=MAX_RAG_QUERY_CHARS)
    provider: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    retrieval_profile: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    retrieval_mode: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_top_k: int | None = Field(default=None, ge=1, le=80)
    reranker: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    query_transform: str | None = Field(default=None, max_length=MAX_RAG_LABEL_CHARS)
    agentic_rag: str | bool | None = None
    agentic_max_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_max_sources: int | None = Field(default=None, ge=0, le=80)
    agentic_min_sources: int | None = Field(default=None, ge=0, le=20)
    agentic_min_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_relevant_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_min_score: float | None = Field(default=None, ge=0, le=1)
    max_context_chars: int = Field(default=5000, ge=500, le=20000)


class KnowledgeDocumentDeleteRequest(BaseModel):
    """Document deletion options for user-facing KB management."""

    remove_raw: bool = True
    remove_vectors: bool = True
