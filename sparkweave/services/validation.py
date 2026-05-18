"""Capability request validation owned by the NG runtime."""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_RUNTIME_ONLY_KEYS = {
    "_persist_user_message",
    "_runtime",
    "answer_now_context",
    "followup_question_context",
}


class ChatRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str | None = None
    topic: str | None = None
    auto_delegate: bool | None = None
    delegate_capability: str | None = None
    coordinator_capability: str | None = None
    coordinator_llm: bool | str | None = None
    intent_classifier: bool | str | None = None
    prefetch_rag: bool | str | None = None
    retrieval_profile: str | None = None
    retrieval_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    candidate_top_k: int | None = Field(default=None, ge=1, le=100)
    reranker: str | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)
    max_context_chars: int | None = Field(default=None, ge=500, le=30000)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    agentic_rag: bool | str | None = None
    agentic_mode: str | None = None
    query_planning: str | bool | None = None
    agentic_max_subqueries: int | None = Field(default=None, ge=1, le=8)
    agentic_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    agentic_max_concurrency: int | None = Field(default=None, ge=1, le=8)
    agentic_fallback_to_single: bool | str | None = None
    agentic_max_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_max_sources: int | None = Field(default=None, ge=0, le=80)
    agentic_min_sources: int | None = Field(default=None, ge=0, le=20)
    agentic_min_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_relevant_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_min_score: float | None = Field(default=None, ge=0, le=1)
    query_transform: str | None = None
    hyde_max_chars: int | None = Field(default=None, ge=100, le=8000)
    hyde_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    hybrid_ranker: str | None = None
    dense_weight: float | None = Field(default=None, ge=0, le=5)
    sparse_weight: float | None = Field(default=None, ge=0, le=5)
    rrf_k: int | None = Field(default=None, ge=1, le=200)


class DeepSolveRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detailed_answer: bool = True
    prefetch_rag: bool | str | None = None
    retrieval_profile: str | None = None
    retrieval_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    candidate_top_k: int | None = Field(default=None, ge=1, le=100)
    reranker: str | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)
    max_context_chars: int | None = Field(default=None, ge=500, le=30000)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    agentic_rag: bool | str | None = None
    agentic_mode: str | None = None
    query_planning: str | bool | None = None
    agentic_max_subqueries: int | None = Field(default=None, ge=1, le=8)
    agentic_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    agentic_max_concurrency: int | None = Field(default=None, ge=1, le=8)
    agentic_fallback_to_single: bool | str | None = None
    agentic_max_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_max_sources: int | None = Field(default=None, ge=0, le=80)
    agentic_min_sources: int | None = Field(default=None, ge=0, le=20)
    agentic_min_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_relevant_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_min_score: float | None = Field(default=None, ge=0, le=1)
    query_transform: str | None = None
    hyde_max_chars: int | None = Field(default=None, ge=100, le=8000)
    hyde_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    hybrid_ranker: str | None = None
    dense_weight: float | None = Field(default=None, ge=0, le=5)
    sparse_weight: float | None = Field(default=None, ge=0, le=5)
    rrf_k: int | None = Field(default=None, ge=1, le=200)


class DeepQuestionRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["custom", "mimic"] = "custom"
    purpose: str | None = None
    topic: str = ""
    num_questions: int = Field(default=1, ge=1, le=50)
    difficulty: str = ""
    question_type: str = ""
    preference: str = ""
    paper_path: str = ""
    max_questions: int = Field(default=10, ge=1, le=100)
    retrieval_profile: str | None = None
    retrieval_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    candidate_top_k: int | None = Field(default=None, ge=1, le=100)
    reranker: str | None = None
    max_context_chars: int | None = Field(default=None, ge=500, le=30000)
    agentic_rag: bool | str | None = None
    query_transform: str | None = None
    agentic_max_subqueries: int | None = Field(default=None, ge=1, le=8)
    agentic_max_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_max_sources: int | None = Field(default=None, ge=0, le=80)
    agentic_min_sources: int | None = Field(default=None, ge=0, le=20)
    agentic_min_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_relevant_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_min_score: float | None = Field(default=None, ge=0, le=1)


class DeepResearchOutlineItem(BaseModel):
    title: str
    overview: str = ""


class DeepResearchRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["notes", "report", "comparison", "learning_path"]
    depth: Literal["quick", "standard", "deep", "manual"]
    sources: list[Literal["kb", "web", "papers"]]
    manual_subtopics: int | None = None
    manual_max_iterations: int | None = None
    confirmed_outline: list[DeepResearchOutlineItem] | None = None
    outline_preview: bool | None = None
    checkpoint_id: str | None = None
    checkpoint_thread_id: str | None = None
    use_code: bool | None = None
    retrieval_profile: str | None = None
    retrieval_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    candidate_top_k: int | None = Field(default=None, ge=1, le=100)
    reranker: str | None = None
    max_context_chars: int | None = Field(default=None, ge=500, le=30000)
    agentic_rag: bool | str | None = None
    query_transform: str | None = None
    agentic_max_subqueries: int | None = Field(default=None, ge=1, le=8)
    agentic_max_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_max_sources: int | None = Field(default=None, ge=0, le=80)
    agentic_min_sources: int | None = Field(default=None, ge=0, le=20)
    agentic_min_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_relevant_coverage_ratio: float | None = Field(default=None, ge=0, le=1)
    agentic_min_context_chars: int | None = Field(default=None, ge=0, le=30000)
    agentic_min_score: float | None = Field(default=None, ge=0, le=1)

    @field_validator("sources")
    @classmethod
    def validate_sources(
        cls, value: list[Literal["kb", "web", "papers"]]
    ) -> list[Literal["kb", "web", "papers"]]:
        return list(dict.fromkeys(value))

    @field_validator("manual_subtopics")
    @classmethod
    def validate_manual_subtopics(cls, value: int | None) -> int | None:
        if value is not None:
            return max(1, min(value, 10))
        return value

    @field_validator("manual_max_iterations")
    @classmethod
    def validate_manual_max_iterations(cls, value: int | None) -> int | None:
        if value is not None:
            return max(1, min(value, 10))
        return value


class VisualizeRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_mode: Literal["auto", "svg", "chartjs", "mermaid"] = "auto"
    topic: str | None = None
    purpose: str | None = None


class MathAnimatorRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_mode: Literal["video", "image"] = "video"
    quality: Literal["low", "medium", "high"] = "medium"
    style_hint: str = Field(default="", max_length=500)
    max_retries: int = Field(default=4, ge=0, le=10)
    enable_narration_audio: bool | None = None
    enable_visual_review: bool | None = None
    visual_review: bool | None = None


def validate_capability_config(
    capability: str,
    raw_config: dict[str, Any] | None,
) -> dict[str, Any]:
    validator = _CONFIG_VALIDATORS.get(capability)
    if validator is None:
        return _clean_public_config(raw_config)
    model = validator(raw_config)
    return model.model_dump(exclude_none=True)


def _clean_public_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    if raw_config is None:
        return {}
    if not isinstance(raw_config, dict):
        raise ValueError("Capability config must be an object.")
    cleaned = dict(raw_config)
    for key in _RUNTIME_ONLY_KEYS:
        cleaned.pop(key, None)
    return cleaned


def _validate_model(
    model_type: type[BaseModel],
    raw_config: dict[str, Any] | None,
    *,
    label: str,
) -> BaseModel:
    cleaned = _clean_public_config(raw_config)
    try:
        return model_type.model_validate(cleaned)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid {label} config: {details}") from exc


def _validate_chat(raw_config: dict[str, Any] | None) -> ChatRequestConfig:
    return _validate_model(ChatRequestConfig, raw_config, label="chat")


def _validate_deep_solve(raw_config: dict[str, Any] | None) -> DeepSolveRequestConfig:
    return _validate_model(DeepSolveRequestConfig, raw_config, label="deep solve")


def _validate_deep_question(
    raw_config: dict[str, Any] | None,
) -> DeepQuestionRequestConfig:
    return _validate_model(DeepQuestionRequestConfig, raw_config, label="deep question")


def _validate_deep_research(
    raw_config: dict[str, Any] | None,
) -> DeepResearchRequestConfig:
    if raw_config is None:
        raise ValueError("Deep research requires an explicit config object.")
    return _validate_model(DeepResearchRequestConfig, raw_config, label="deep research")


def _validate_visualize(raw_config: dict[str, Any] | None) -> VisualizeRequestConfig:
    return _validate_model(VisualizeRequestConfig, raw_config, label="visualize")


def _validate_math_animator(
    raw_config: dict[str, Any] | None,
) -> MathAnimatorRequestConfig:
    return _validate_model(MathAnimatorRequestConfig, raw_config, label="math animator")


def validate_math_animator_request_config(
    raw_config: dict[str, Any] | None,
) -> MathAnimatorRequestConfig:
    """Validate public math animator request configuration."""
    return _validate_math_animator(raw_config)


_CONFIG_VALIDATORS: dict[str, Callable[[dict[str, Any] | None], BaseModel]] = {
    "chat": _validate_chat,
    "deep_solve": _validate_deep_solve,
    "deep_question": _validate_deep_question,
    "deep_research": _validate_deep_research,
    "math_animator": _validate_math_animator,
    "visualize": _validate_visualize,
}

__all__ = [
    "ChatRequestConfig",
    "DeepQuestionRequestConfig",
    "DeepResearchRequestConfig",
    "DeepSolveRequestConfig",
    "MathAnimatorRequestConfig",
    "VisualizeRequestConfig",
    "validate_capability_config",
    "validate_math_animator_request_config",
]
