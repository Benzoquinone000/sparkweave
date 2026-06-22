"""Data models shared by the learning-effect service and callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LEARNING_EFFECT_DIMENSION_WEIGHTS: dict[str, float] = {
    "mastery": 0.27,
    "progress": 0.14,
    "stability": 0.16,
    "evidence_quality": 0.17,
    "engagement": 0.12,
    "remediation": 0.09,
    "resource_effectiveness": 0.05,
}


@dataclass
class ConceptMasteryState:
    concept_id: str
    title: str
    score: float = 0.0
    status: str = "unknown"
    confidence: float = 0.0
    trend: str = "flat"
    evidence_count: int = 0
    scored_event_count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    open_mistake_count: int = 0
    resource_count: int = 0
    last_practiced_at: float | None = None
    next_review_at: float | None = None
    evidence_refs: list[str] = field(default_factory=list)
    common_mistakes: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class NextBestAction:
    id: str
    type: str
    title: str
    reason: str
    target_concepts: list[str] = field(default_factory=list)
    estimated_minutes: int = 8
    priority: float = 0.5
    href: str = ""
    capability: str = "chat"
    prompt: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    knowledge_bases: list[str] = field(default_factory=list)
    writes_back: list[str] = field(default_factory=lambda: ["mastery", "profile"])


__all__ = [
    "LEARNING_EFFECT_DIMENSION_WEIGHTS",
    "ConceptMasteryState",
    "NextBestAction",
]
