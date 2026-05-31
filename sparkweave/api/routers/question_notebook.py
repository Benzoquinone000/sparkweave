"""
Question Notebook API — persists quiz questions, bookmarks, and categories.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationInfo, field_validator

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
    MAX_QUIZ_SESSION_ID_CHARS,
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
SessionIdQuery = Annotated[str, Query(min_length=1, max_length=MAX_QUIZ_SESSION_ID_CHARS)]
QuestionIdQuery = Annotated[str, Query(min_length=1, max_length=MAX_QUIZ_QUESTION_ID_CHARS)]
MANUAL_SESSION_PREFIX = "manual-"


# ── Models ────────────────────────────────────────────────────────

class NotebookEntryItem(BaseModel):
    id: int
    session_id: str
    session_title: str = ""
    question_id: str = ""
    question: str
    question_type: str = ""
    options: dict[str, str] = {}
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = ""
    user_answer: str = ""
    is_correct: bool = False
    bookmarked: bool = False
    followup_session_id: str = ""
    created_at: float
    updated_at: float
    categories: list[CategoryItem] | None = None


class NotebookEntryListResponse(BaseModel):
    items: list[NotebookEntryItem]
    total: int


class EntryUpdateRequest(BaseModel):
    bookmarked: bool | None = None
    followup_session_id: str | None = Field(default=None, max_length=MAX_QUIZ_SESSION_ID_CHARS)


class CategoryItem(BaseModel):
    id: int
    name: str
    created_at: float = 0
    entry_count: int = 0


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return strip_required_text(value, "name")


class CategoryRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return strip_required_text(value, "name")


class CategoryAddRequest(BaseModel):
    category_id: int


class UpsertEntryRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=MAX_QUIZ_SESSION_ID_CHARS)
    question_id: str = Field(..., min_length=1, max_length=MAX_QUIZ_QUESTION_ID_CHARS)
    question: str = Field(..., min_length=1, max_length=MAX_QUIZ_QUESTION_CHARS)
    question_type: str = Field(default="", max_length=MAX_QUIZ_QUESTION_TYPE_CHARS)
    options: dict[str, str] | None = Field(default=None, max_length=MAX_QUIZ_OPTION_ITEMS)
    correct_answer: str = Field(default="", max_length=MAX_QUIZ_ANSWER_CHARS)
    explanation: str = Field(default="", max_length=MAX_QUIZ_EXPLANATION_CHARS)
    difficulty: str = Field(default="", max_length=MAX_QUIZ_DIFFICULTY_CHARS)
    concepts: list[str] = Field(default_factory=list, max_length=MAX_QUIZ_LABEL_ITEMS)
    knowledge_points: list[str] = Field(default_factory=list, max_length=MAX_QUIZ_LABEL_ITEMS)
    duration_seconds: float | None = Field(default=None, ge=0, le=MAX_QUIZ_DURATION_SECONDS)
    attempt_count: int = Field(default=1, ge=1, le=MAX_QUIZ_ATTEMPT_COUNT)
    user_answer: str = Field(default="", max_length=MAX_QUIZ_ANSWER_CHARS)
    is_correct: bool = False
    record_evidence: bool = True

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, value):
        return coerce_limited_quiz_options(value)

    @field_validator("concepts", "knowledge_points", mode="before")
    @classmethod
    def _coerce_label_list(cls, value):
        return coerce_limited_quiz_labels(value)

    @field_validator("explanation", "difficulty", mode="before")
    @classmethod
    def _coerce_optional_text(cls, value):
        return coerce_quiz_optional_text(value)

    @field_validator("session_id", "question_id", "question")
    @classmethod
    def _strip_required_text(cls, value: str, info: ValidationInfo) -> str:
        return strip_required_text(value, info.field_name)


async def _ensure_manual_session(store, session_id: str) -> bool:
    if not session_id.startswith(MANUAL_SESSION_PREFIX):
        return False
    if await store.get_session(session_id) is not None:
        return False
    await store.create_session(title="题目快录", session_id=session_id)
    return True


# ── Entry endpoints ──────────────────────────────────────────────

@router.post("/entries/upsert")
async def upsert_single_entry(payload: UpsertEntryRequest):
    store = get_sqlite_session_store()
    entry_payload = payload.model_dump(exclude={"record_evidence"})
    try:
        await store.upsert_notebook_entries(payload.session_id, [entry_payload])
    except ValueError as e:
        if await _ensure_manual_session(store, payload.session_id):
            await store.upsert_notebook_entries(payload.session_id, [entry_payload])
        else:
            raise HTTPException(status_code=404, detail=str(e))
    entry = await store.find_notebook_entry(payload.session_id, payload.question_id)
    if entry is None:
        raise HTTPException(status_code=500, detail="Upsert failed")
    if payload.record_evidence:
        try:
            get_learner_evidence_service().append_events(
                build_quiz_answer_events(
                    [entry_payload],
                    source="question_notebook",
                    session_id=payload.session_id,
                    source_id_prefix=payload.session_id,
                ),
                dedupe=True,
            )
        except Exception:
            logger.warning("Failed to append question notebook learner evidence", exc_info=True)
    return entry

@router.get("/entries", response_model=NotebookEntryListResponse)
async def list_entries(
    category_id: int | None = Query(default=None),
    bookmarked: bool | None = Query(default=None),
    is_correct: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotebookEntryListResponse:
    store = get_sqlite_session_store()
    result = await store.list_notebook_entries(
        category_id=category_id,
        bookmarked=bookmarked,
        is_correct=is_correct,
        limit=limit,
        offset=offset,
    )
    return NotebookEntryListResponse(
        items=[NotebookEntryItem(**item) for item in result["items"]],
        total=result["total"],
    )


@router.get("/entries/lookup/by-question")
async def lookup_entry(session_id: SessionIdQuery, question_id: QuestionIdQuery):
    store = get_sqlite_session_store()
    entry = await store.find_notebook_entry(session_id, question_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("/entries/{entry_id}", response_model=NotebookEntryItem)
async def get_entry(entry_id: int) -> NotebookEntryItem:
    store = get_sqlite_session_store()
    entry = await store.get_notebook_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return NotebookEntryItem(**entry)


@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: int, payload: EntryUpdateRequest):
    store = get_sqlite_session_store()
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await store.update_notebook_entry(entry_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"updated": True, "id": entry_id}


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int):
    store = get_sqlite_session_store()
    deleted = await store.delete_notebook_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": True, "id": entry_id}


# ── Entry ↔ Category linking ────────────────────────────────────

@router.post("/entries/{entry_id}/categories")
async def add_entry_to_category(entry_id: int, payload: CategoryAddRequest):
    store = get_sqlite_session_store()
    entry = await store.get_notebook_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    ok = await store.add_entry_to_category(entry_id, payload.category_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add to category")
    return {"added": True, "entry_id": entry_id, "category_id": payload.category_id}


@router.delete("/entries/{entry_id}/categories/{category_id}")
async def remove_entry_from_category(entry_id: int, category_id: int):
    store = get_sqlite_session_store()
    removed = await store.remove_entry_from_category(entry_id, category_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"removed": True, "entry_id": entry_id, "category_id": category_id}


# ── Category CRUD ────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryItem])
async def list_categories():
    store = get_sqlite_session_store()
    return await store.list_categories()


@router.post("/categories", response_model=CategoryItem, status_code=201)
async def create_category(payload: CategoryCreateRequest):
    store = get_sqlite_session_store()
    try:
        return await store.create_category(payload.name)
    except Exception:
        raise HTTPException(status_code=409, detail="Category name already exists")


@router.patch("/categories/{category_id}")
async def rename_category(category_id: int, payload: CategoryRenameRequest):
    store = get_sqlite_session_store()
    updated = await store.rename_category(category_id, payload.name)
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"updated": True, "id": category_id, "name": payload.name}


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int):
    store = get_sqlite_session_store()
    deleted = await store.delete_category(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"deleted": True, "id": category_id}


