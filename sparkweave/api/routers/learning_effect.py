"""Learning effect closed-loop API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from sparkweave.services.learning_effect import get_learning_effect_service

router = APIRouter()


class LearningEffectEventRequest(BaseModel):
    source: str = "learning_effect"
    source_id: str = ""
    actor: str = "learner"
    verb: str = "observed"
    object_type: str = "learning_activity"
    object_id: str = ""
    title: str = ""
    summary: str = ""
    course_id: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    node_id: str = ""
    task_id: str = ""
    resource_type: str = ""
    score: float | None = None
    is_correct: bool | None = None
    duration_seconds: float | None = None
    confidence: float = 0.68
    reflection: str = ""
    mistake_types: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float | str | None = None
    weight: float = 1.0


class CompleteLearningActionRequest(BaseModel):
    note: str = ""
    score: float | None = None
    course_id: str = ""
    concept_ids: list[str] = Field(default_factory=list)


@router.get("/health")
async def health() -> dict[str, Any]:
    return get_learning_effect_service().health()


@router.get("/report")
async def get_report(
    course_id: str = Query(default=""),
    window: str = Query(default="14d"),
) -> dict[str, Any]:
    return get_learning_effect_service().build_report(course_id=course_id, window=window)


@router.get("/demo-summary")
async def get_demo_summary(
    course_id: str = Query(default=""),
    window: str = Query(default="14d"),
) -> dict[str, Any]:
    return get_learning_effect_service().demo_summary(course_id=course_id, window=window)


@router.get("/concepts")
async def list_concepts(
    course_id: str = Query(default=""),
    window: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    return get_learning_effect_service().list_concepts(course_id=course_id, window=window, limit=limit)


@router.get("/next-actions")
async def list_next_actions(
    course_id: str = Query(default=""),
    window: str = Query(default="14d"),
    limit: int = Query(default=6, ge=1, le=20),
) -> dict[str, Any]:
    return get_learning_effect_service().next_actions(course_id=course_id, window=window, limit=limit)


@router.post("/events")
async def append_event(request: LearningEffectEventRequest) -> dict[str, Any]:
    return get_learning_effect_service().append_event(request.model_dump(exclude_none=True))


@router.post("/actions/{action_id}/complete")
async def complete_action(action_id: str, request: CompleteLearningActionRequest) -> dict[str, Any]:
    return get_learning_effect_service().complete_action(
        action_id,
        note=request.note,
        score=request.score,
        course_id=request.course_id,
        concept_ids=request.concept_ids,
    )
