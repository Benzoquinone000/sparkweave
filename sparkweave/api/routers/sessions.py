"""
Unified session history API.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from sparkweave.api.request_limits import (
    MAX_QUIZ_ANSWER_CHARS,
    MAX_QUIZ_ATTEMPT_COUNT,
    MAX_QUIZ_DIFFICULTY_CHARS,
    MAX_QUIZ_DURATION_SECONDS,
    MAX_QUIZ_EXPLANATION_CHARS,
    MAX_QUIZ_LABEL_ITEMS,
    MAX_QUIZ_OPTION_ITEMS,
    MAX_QUIZ_QUESTION_CHARS,
    MAX_QUIZ_QUESTION_ID_CHARS,
    MAX_QUIZ_QUESTION_TYPE_CHARS,
    MAX_QUIZ_RESULT_ITEMS,
    coerce_limited_quiz_labels,
    coerce_limited_quiz_options,
    coerce_quiz_optional_text,
    strip_required_text,
)
from sparkweave.services.learner_evidence import (
    build_quiz_answer_events,
    get_learner_evidence_service,
)
from sparkweave.services.session_store import get_sqlite_session_store

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class QuizResultItem(BaseModel):
    question_id: str = Field(default="", max_length=MAX_QUIZ_QUESTION_ID_CHARS)
    question: str = Field(..., min_length=1, max_length=MAX_QUIZ_QUESTION_CHARS)
    question_type: str = Field(default="", max_length=MAX_QUIZ_QUESTION_TYPE_CHARS)
    options: dict[str, str] | None = Field(default=None, max_length=MAX_QUIZ_OPTION_ITEMS)
    concepts: list[str] = Field(default_factory=list, max_length=MAX_QUIZ_LABEL_ITEMS)
    knowledge_points: list[str] = Field(default_factory=list, max_length=MAX_QUIZ_LABEL_ITEMS)
    user_answer: str = Field(default="", max_length=MAX_QUIZ_ANSWER_CHARS)
    correct_answer: str = Field(default="", max_length=MAX_QUIZ_ANSWER_CHARS)
    explanation: str | None = Field(default="", max_length=MAX_QUIZ_EXPLANATION_CHARS)
    difficulty: str | None = Field(default="", max_length=MAX_QUIZ_DIFFICULTY_CHARS)
    duration_seconds: float | None = Field(default=None, ge=0, le=MAX_QUIZ_DURATION_SECONDS)
    attempt_count: int = Field(default=1, ge=1, le=MAX_QUIZ_ATTEMPT_COUNT)
    is_correct: bool

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        return coerce_limited_quiz_options(v)

    @field_validator("concepts", "knowledge_points", mode="before")
    @classmethod
    def _coerce_string_list(cls, v):
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        if isinstance(v, str):
            return [item.strip() for item in v.replace("；", ",").replace(";", ",").split(",") if item.strip()]
        return []

    @field_validator("explanation", "difficulty", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return coerce_quiz_optional_text(v)

    @field_validator("concepts", "knowledge_points", mode="after")
    @classmethod
    def _limit_string_list(cls, v):
        return coerce_limited_quiz_labels(v)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        return strip_required_text(value, "question")


class QuizResultsRequest(BaseModel):
    answers: list[QuizResultItem] = Field(default_factory=list, max_length=MAX_QUIZ_RESULT_ITEMS)


def _format_quiz_results_message(answers: list[QuizResultItem]) -> str:
    total = len(answers)
    correct = sum(1 for item in answers if item.is_correct)
    score_pct = round((correct / total) * 100) if total else 0
    lines = ["[Quiz Performance]"]
    for idx, item in enumerate(answers, 1):
        question = item.question.strip().replace("\n", " ")
        user_answer = (item.user_answer or "").strip() or "(blank)"
        status = "Correct" if item.is_correct else "Incorrect"
        suffix = f" ({status})"
        if not item.is_correct and (item.correct_answer or "").strip():
            suffix = f" ({status}, correct: {(item.correct_answer or '').strip()})"
        qid = f"[{item.question_id}] " if item.question_id else ""
        lines.append(f"{idx}. {qid}Q: {question} -> Answered: {user_answer}{suffix}")
    lines.append(f"Score: {correct}/{total} ({score_pct}%)")
    return "\n".join(lines)


@router.get("")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    store = get_sqlite_session_store()
    sessions = await store.list_sessions(limit=limit, offset=offset)
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session(session_id: str):
    store = get_sqlite_session_store()
    session = await store.get_session_with_messages(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}")
async def rename_session(session_id: str, payload: SessionRenameRequest):
    store = get_sqlite_session_store()
    updated = await store.update_session_title(session_id, payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    session = await store.get_session(session_id)
    return {"session": session}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    store = get_sqlite_session_store()
    deleted = await store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@router.post("/{session_id}/quiz-results")
async def record_quiz_results(session_id: str, payload: QuizResultsRequest):
    if not payload.answers:
        raise HTTPException(status_code=400, detail="Quiz results are required")
    store = get_sqlite_session_store()
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    content = _format_quiz_results_message(payload.answers)
    await store.add_message(
        session_id=session_id,
        role="user",
        content=content,
        capability="deep_question",
    )
    notebook_count = 0
    try:
        notebook_count = await store.upsert_notebook_entries(
            session_id,
            [item.model_dump() for item in payload.answers],
        )
    except Exception:
        logger.warning("Failed to upsert notebook entries for session %s", session_id, exc_info=True)
    try:
        get_learner_evidence_service().append_events(
            build_quiz_answer_events(
                [item.model_dump() for item in payload.answers],
                source="question_notebook",
                session_id=session_id,
                source_id_prefix=session_id,
            ),
            dedupe=True,
        )
    except Exception:
        logger.warning("Failed to append quiz learner evidence for session %s", session_id, exc_info=True)
    return {
        "recorded": True,
        "session_id": session_id,
        "answer_count": len(payload.answers),
        "notebook_count": notebook_count,
        "content": content,
    }


