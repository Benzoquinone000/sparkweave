"""Data models for NG question generation agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuestionTemplate:
    """Standardized intermediate question template."""

    question_id: str
    concentration: str
    question_type: str
    difficulty: str
    source: str = "custom"
    reference_question: str | None = None
    reference_answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAPair:
    """Final generated question-answer payload."""

    question_id: str
    question: str
    correct_answer: str
    explanation: str
    question_type: str
    options: dict[str, str] | None = None
    concentration: str = ""
    difficulty: str = ""
    validation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["QAPair", "QuestionTemplate"]
