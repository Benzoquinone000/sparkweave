"""Learner profile API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from sparkweave.services.learner_evidence import (
    build_profile_calibration_event,
    get_learner_evidence_service,
)
from sparkweave.services.guide_v2 import GuideV2Manager
from sparkweave.services.learner_profile import get_learner_profile_service
from sparkweave.services.memory import get_memory_service
from sparkweave.services.notebook import get_notebook_manager
from sparkweave.services.session_store import get_sqlite_session_store

router = APIRouter()


class LearnerProfileRefreshRequest(BaseModel):
    include_sources: list[str] | None = Field(
        default=None,
        description="Optional source filter: memory, guide, question_notebook, notebook.",
    )
    force: bool = True


class LearnerEvidenceAppendRequest(BaseModel):
    source: str = Field(default="manual")
    source_id: str = ""
    actor: str = "learner"
    verb: str = "observed"
    object_type: str = "learning_activity"
    object_id: str = ""
    title: str = ""
    summary: str = ""
    course_id: str = ""
    node_id: str = ""
    task_id: str = ""
    resource_type: str = ""
    score: float | None = None
    is_correct: bool | None = None
    duration_seconds: float | None = None
    confidence: float = 0.5
    reflection: str = ""
    mistake_types: list[str] = Field(default_factory=list)
    created_at: float | str | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearnerEvidenceBatchRequest(BaseModel):
    events: list[LearnerEvidenceAppendRequest] = Field(default_factory=list)
    dedupe: bool = True


class LearnerEvidenceRebuildRequest(BaseModel):
    clear: bool = False


class LearnerProfileCalibrationRequest(BaseModel):
    action: str = Field(default="confirm", description="confirm, reject, or correct")
    claim_type: str = Field(default="profile_claim")
    value: str = Field(default="")
    corrected_value: str = Field(default="")
    note: str = Field(default="")
    source_id: str = Field(default="")


class LearnerProfileResetRequest(BaseModel):
    clear_memory: bool = True
    clear_evidence: bool = True
    clear_guide_state: bool = True
    clear_chat_history: bool = True
    clear_question_notebook: bool = True
    clear_saved_notebook_records: bool = True
    clear_profile_cache: bool = True


@router.get("")
async def get_learner_profile() -> dict[str, Any]:
    """Return the current unified learner profile snapshot."""

    return await get_learner_profile_service().read_profile(auto_refresh=True)


@router.post("/refresh")
async def refresh_learner_profile(request: LearnerProfileRefreshRequest) -> dict[str, Any]:
    """Rebuild the profile snapshot from existing read-only sources."""

    return await get_learner_profile_service().refresh(
        include_sources=request.include_sources,
        force=request.force,
    )


@router.post("/reset")
async def reset_learner_profile(request: LearnerProfileResetRequest | None = None) -> dict[str, Any]:
    """Clear learner-state data without touching course files or knowledge bases."""

    options = request or LearnerProfileResetRequest()
    result: dict[str, Any] = {
        "cleared": True,
        "scope": {
            "memory": options.clear_memory,
            "evidence": options.clear_evidence,
            "guide_state": options.clear_guide_state,
            "chat_history": options.clear_chat_history,
            "question_notebook": options.clear_question_notebook,
            "saved_notebook_records": options.clear_saved_notebook_records,
            "profile_cache": options.clear_profile_cache,
        },
    }
    if options.clear_memory:
        snap = get_memory_service().clear_memory()
        result["memory"] = {
            "summary": bool(snap.summary),
            "profile": bool(snap.profile),
        }
    if options.clear_evidence:
        result["evidence"] = get_learner_evidence_service().clear()
    if options.clear_guide_state:
        result["guide_state"] = GuideV2Manager().clear_learning_state()
    if options.clear_chat_history:
        result["chat_history"] = await get_sqlite_session_store().clear_all_sessions()
    elif options.clear_question_notebook:
        result["question_notebook"] = await get_sqlite_session_store().clear_notebook_entries()
    if options.clear_saved_notebook_records:
        result["saved_notebook_records"] = get_notebook_manager().clear_all_records()
    if options.clear_profile_cache:
        result["profile_cache"] = get_learner_profile_service().clear_snapshot()
    return result


@router.get("/evidence-preview")
async def get_learner_profile_evidence_preview(
    source: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    """Return a compact evidence list used by the profile UI."""

    return await get_learner_profile_service().list_evidence_preview(source=source, limit=limit)


@router.get("/evidence")
async def list_learner_evidence(
    source: str | None = Query(default=None),
    verb: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return normalized learner evidence events from the append-only ledger."""

    return get_learner_evidence_service().list_events(
        source=source,
        verb=verb,
        object_type=object_type,
        limit=limit,
        offset=offset,
    )


@router.post("/evidence")
async def append_learner_evidence(request: LearnerEvidenceAppendRequest) -> dict[str, Any]:
    """Append one normalized learner evidence event."""

    event = get_learner_evidence_service().append_event(request.model_dump(exclude_none=True))
    return {"event": event}


@router.post("/evidence/batch")
async def append_learner_evidence_batch(request: LearnerEvidenceBatchRequest) -> dict[str, Any]:
    """Append multiple learner evidence events."""

    payloads = [event.model_dump(exclude_none=True) for event in request.events]
    return get_learner_evidence_service().append_events(payloads, dedupe=request.dedupe)


@router.post("/evidence/rebuild")
async def rebuild_learner_evidence(request: LearnerEvidenceRebuildRequest) -> dict[str, Any]:
    """Seed the formal ledger from the current read-only profile preview."""

    profile = await get_learner_profile_service().read_profile(auto_refresh=True)
    return get_learner_evidence_service().rebuild_from_profile(profile, clear=request.clear)


@router.post("/calibrations")
async def calibrate_learner_profile(request: LearnerProfileCalibrationRequest) -> dict[str, Any]:
    """Let the learner confirm, reject, or correct a profile claim."""

    event = get_learner_evidence_service().append_event(
        build_profile_calibration_event(
            action=request.action,
            claim_type=request.claim_type,
            value=request.value,
            corrected_value=request.corrected_value,
            note=request.note,
            source_id=request.source_id,
        )
    )
    profile = await get_learner_profile_service().refresh(force=True)
    return {"event": event, "profile": profile}
