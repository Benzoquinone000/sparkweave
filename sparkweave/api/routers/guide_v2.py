"""Guide v2 API: structured learning path cockpit."""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from sparkweave.api.utils.task_log_stream import get_task_stream_manager
from sparkweave.services.context import NotebookAnalysisAgent
from sparkweave.services.guide_v2 import GuideV2CreateInput, GuideV2Manager
from sparkweave.services.learner_evidence import (
    build_guide_resource_event,
    build_guide_session_event,
    build_guide_task_event,
    build_notebook_record_event,
    build_quiz_answer_events,
    get_learner_evidence_service,
)
from sparkweave.services.learner_profile import get_learner_profile_service
from sparkweave.services.llm import get_llm_config
from sparkweave.services.notebook import notebook_manager
from sparkweave.services.session_store import get_sqlite_session_store
from sparkweave.services.settings import get_ui_language

router = APIRouter()
_manager: GuideV2Manager | None = None
logger = logging.getLogger(__name__)


class CreateGuideV2SessionRequest(BaseModel):
    goal: str = ""
    level: str = ""
    time_budget_minutes: int | None = Field(default=None, ge=5, le=240)
    horizon: str = ""
    preferences: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    notebook_context: str = ""
    course_template_id: str = ""
    notebook_references: list[dict] = Field(default_factory=list)
    use_memory: bool = True
    source_action: dict = Field(default_factory=dict)


class CompleteGuideV2TaskRequest(BaseModel):
    score: float | None = Field(default=None, ge=0, le=1)
    reflection: str = ""
    mistake_types: list[str] = Field(default_factory=list)


class GuideV2DiagnosticAnswer(BaseModel):
    question_id: str = Field(..., min_length=1)
    value: str | int | float | bool | list[str] = ""


class SubmitGuideV2DiagnosticRequest(BaseModel):
    answers: list[GuideV2DiagnosticAnswer] = Field(default_factory=list)


class SubmitGuideV2ProfileDialogueRequest(BaseModel):
    message: str = Field(..., min_length=1)


class GenerateGuideV2ResourceRequest(BaseModel):
    resource_type: str = Field(default="visual", min_length=1)
    prompt: str = ""
    quality: str = "low"


class SaveGuideV2ArtifactRequest(BaseModel):
    notebook_ids: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""
    save_questions: bool = True


class SaveGuideV2ReportRequest(BaseModel):
    notebook_ids: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""


class SaveGuideV2PackageRequest(BaseModel):
    notebook_ids: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""


class GuideV2QuizResultItem(BaseModel):
    question_id: str = ""
    question: str = Field(..., min_length=1)
    question_type: str = ""
    options: dict[str, str] | None = None
    concepts: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    user_answer: str = ""
    correct_answer: str = ""
    explanation: str | None = ""
    difficulty: str | None = ""
    is_correct: bool

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, value):
        return value if isinstance(value, dict) else {}

    @field_validator("concepts", "knowledge_points", mode="before")
    @classmethod
    def _coerce_string_list(cls, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"\s*(?:,|，|、|;|；|\|)\s*", value) if item.strip()]
        return []

    @field_validator("explanation", "difficulty", mode="before")
    @classmethod
    def _coerce_string(cls, value):
        return value if isinstance(value, str) else ""


class SubmitGuideV2QuizResultsRequest(BaseModel):
    answers: list[GuideV2QuizResultItem] = Field(default_factory=list)
    save_questions: bool = True


def get_guide_v2_manager() -> GuideV2Manager:
    global _manager
    if _manager is not None:
        return _manager

    llm_config = get_llm_config()
    _manager = GuideV2Manager(
        learner_profile_service=get_learner_profile_service(),
        llm_options={
            "api_key": llm_config.api_key,
            "base_url": llm_config.base_url,
            "api_version": getattr(llm_config, "api_version", None),
            "binding": llm_config.binding,
        }
    )
    return _manager


async def _build_notebook_context(goal: str, references: list[dict]) -> str:
    if not references:
        return ""
    selected_records = notebook_manager.get_records_by_references(references)
    if not selected_records:
        return ""
    agent = NotebookAnalysisAgent(language=get_ui_language(default="zh"))
    return await agent.analyze(user_question=goal, records=selected_records)


def _append_evidence_event(event: dict) -> dict:
    try:
        recorded = get_learner_evidence_service().append_events([event], dedupe=True)
        return {"recorded": bool(recorded.get("added")), "count": int(recorded.get("added") or 0)}
    except Exception:
        logger.warning("Failed to append learner evidence event", exc_info=True)
        return {"recorded": False, "count": 0}


def _append_evidence_events(events: list[dict]) -> dict:
    if not events:
        return {"recorded": False, "count": 0}
    try:
        recorded = get_learner_evidence_service().append_events(events, dedupe=True)
        return {"recorded": bool(recorded.get("added")), "count": int(recorded.get("added") or 0)}
    except Exception:
        logger.warning("Failed to append learner evidence events", exc_info=True)
        return {"recorded": False, "count": 0}


def _append_resource_generation_evidence(session_id: str, task_id: str, result: dict) -> dict:
    artifact = result.get("artifact") if isinstance(result.get("artifact"), dict) else {}
    if not artifact:
        return {"recorded": False, "count": 0}
    session_payload = result.get("session") if isinstance(result.get("session"), dict) else {}
    task_payload = result.get("task") if isinstance(result.get("task"), dict) else {}
    if not task_payload and session_payload:
        task_payload = _find_task(session_payload, task_id) or {}
    return _append_evidence_event(
        build_guide_resource_event(
            session_id=session_id,
            task=task_payload,
            artifact=artifact,
            session_goal=str(session_payload.get("goal") or ""),
        )
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "guide_v2"}


@router.get("/templates")
async def list_course_templates():
    try:
        return {"templates": get_guide_v2_manager().list_course_templates()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions")
async def create_session(request: CreateGuideV2SessionRequest):
    goal = request.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="Learning goal cannot be empty")
    try:
        notebook_context = request.notebook_context.strip()
        referenced_context = await _build_notebook_context(goal, request.notebook_references)
        if referenced_context:
            notebook_context = (
                f"{notebook_context}\n\n[Notebook Analysis]\n{referenced_context}"
                if notebook_context
                else referenced_context
            )
        manager = get_guide_v2_manager()
        result = await manager.create_session(
            GuideV2CreateInput(
                goal=goal,
                level=request.level,
                time_budget_minutes=request.time_budget_minutes,
                horizon=request.horizon,
                preferences=request.preferences,
                weak_points=request.weak_points,
                notebook_context=notebook_context,
                course_template_id=request.course_template_id,
                use_memory=request.use_memory,
                source_action=request.source_action,
            )
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=str(result.get("error") or "Create session failed"))
        result["evidence"] = _append_evidence_event(build_guide_session_event(session=result.get("session") or {}))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions")
async def list_sessions():
    try:
        return {"sessions": get_guide_v2_manager().list_sessions()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/learner-memory")
async def get_learner_memory():
    try:
        return get_guide_v2_manager().build_learner_memory(refresh=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session = get_guide_v2_manager().get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/evaluation")
async def get_session_evaluation(session_id: str):
    try:
        result = get_guide_v2_manager().evaluate_session(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/learning-timeline")
async def get_session_learning_timeline(session_id: str):
    try:
        result = get_guide_v2_manager().build_learning_timeline(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/mistake-review")
async def get_session_mistake_review(session_id: str):
    try:
        result = get_guide_v2_manager().build_mistake_review(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/coach-briefing")
async def get_session_coach_briefing(session_id: str):
    try:
        result = get_guide_v2_manager().build_coach_briefing(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/study-plan")
async def get_session_study_plan(session_id: str):
    try:
        result = get_guide_v2_manager().build_study_plan(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/diagnostic")
async def get_session_diagnostic(session_id: str):
    try:
        result = get_guide_v2_manager().build_diagnostic(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/diagnostic")
async def submit_session_diagnostic(session_id: str, request: SubmitGuideV2DiagnosticRequest):
    if not request.answers:
        raise HTTPException(status_code=400, detail="Diagnostic answers are required")
    try:
        answers = [item.model_dump() for item in request.answers]
        result = get_guide_v2_manager().submit_diagnostic(session_id, answers)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/profile-dialogue")
async def get_session_profile_dialogue(session_id: str):
    try:
        result = get_guide_v2_manager().build_profile_dialogue(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/profile-dialogue")
async def submit_session_profile_dialogue(
    session_id: str,
    request: SubmitGuideV2ProfileDialogueRequest,
):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Dialogue message is required")
    try:
        result = get_guide_v2_manager().submit_profile_dialogue(session_id, message)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/report")
async def get_session_report(session_id: str):
    try:
        result = get_guide_v2_manager().build_learning_report(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/course-package")
async def get_session_course_package(session_id: str):
    try:
        result = get_guide_v2_manager().build_course_package(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/resource-recommendations")
async def get_session_resource_recommendations(session_id: str):
    try:
        result = get_guide_v2_manager().recommend_resources(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/tasks/{task_id}/complete")
async def complete_task(session_id: str, task_id: str, request: CompleteGuideV2TaskRequest):
    try:
        result = get_guide_v2_manager().complete_task(
            session_id,
            task_id,
            score=request.score,
            reflection=request.reflection,
            mistake_types=request.mistake_types,
        )
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Task not found"))
        result["learner_evidence"] = _append_evidence_event(
            build_guide_task_event(
                session_id=session_id,
                task=result.get("completed_task") or {},
                evidence=result.get("evidence") or {},
                session_goal=str((result.get("session") or {}).get("goal") or ""),
            )
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/recommendations/refresh")
async def refresh_recommendations(session_id: str):
    try:
        result = get_guide_v2_manager().refresh_recommendations(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/tasks/{task_id}/resources")
async def generate_task_resource(
    session_id: str,
    task_id: str,
    request: GenerateGuideV2ResourceRequest,
):
    try:
        result = await get_guide_v2_manager().generate_resource(
            session_id,
            task_id,
            resource_type=request.resource_type,
            prompt=request.prompt,
            quality=request.quality,
        )
        if not result.get("success"):
            error = str(result.get("error") or "Resource generation failed")
            status_code = 404 if "not found" in error.lower() else 400
            raise HTTPException(status_code=status_code, detail=error)
        result["learner_evidence"] = _append_resource_generation_evidence(session_id, task_id, result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/tasks/{task_id}/resources/jobs")
async def start_task_resource_job(
    session_id: str,
    task_id: str,
    request: GenerateGuideV2ResourceRequest,
    background_tasks: BackgroundTasks,
):
    manager = get_guide_v2_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not any(str(item.get("task_id")) == task_id for item in session.get("tasks", [])):
        raise HTTPException(status_code=404, detail="Task not found")

    job_id = f"guide_resource_{uuid.uuid4().hex[:12]}"
    stream_manager = get_task_stream_manager()
    stream_manager.ensure_task(job_id)
    stream_manager.emit(
        job_id,
        "status",
        {
            "task_id": job_id,
            "session_id": session_id,
            "learning_task_id": task_id,
            "resource_type": request.resource_type,
            "stage": "queued",
            "message": "Resource generation queued.",
        },
    )
    background_tasks.add_task(
        _run_resource_generation_job,
        job_id,
        session_id,
        task_id,
        request.resource_type,
        request.prompt,
        request.quality,
    )
    return {
        "task_id": job_id,
        "session_id": session_id,
        "learning_task_id": task_id,
        "resource_type": request.resource_type,
    }


@router.get("/resource-jobs/{job_id}/events")
async def stream_resource_job(job_id: str):
    stream_manager = get_task_stream_manager()
    stream_manager.ensure_task(job_id)
    return StreamingResponse(
        stream_manager.stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/tasks/{task_id}/artifacts/{artifact_id}/save")
async def save_artifact(
    session_id: str,
    task_id: str,
    artifact_id: str,
    request: SaveGuideV2ArtifactRequest,
):
    session = get_guide_v2_manager().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    task = _find_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    artifact = _find_artifact(task, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    saved_record = None
    added_to_notebooks: list[str] = []
    if request.notebook_ids:
        record_title = request.title.strip() or str(artifact.get("title") or task.get("title") or "导学资源")
        result = notebook_manager.add_record(
            notebook_ids=request.notebook_ids,
            record_type="guided_learning",
            title=record_title,
            summary=request.summary.strip() or _artifact_summary(artifact),
            user_query=str(task.get("instruction") or session.get("goal") or ""),
            output=_artifact_to_markdown(session, task, artifact),
            metadata={
                "source": "guide_v2",
                "guide_session_id": session_id,
                "guide_task_id": task_id,
                "artifact_id": artifact_id,
                "artifact_type": artifact.get("type"),
                "capability": artifact.get("capability"),
            },
            kb_name=None,
        )
        saved_record = result.get("record")
        added_to_notebooks = list(result.get("added_to_notebooks") or [])
        if saved_record:
            _append_evidence_event(
                build_notebook_record_event(
                    record=saved_record,
                    notebook_ids=added_to_notebooks,
                    source="guide_v2",
                )
            )

    question_result = {"saved": False, "count": 0, "session_id": ""}
    if request.save_questions and str(artifact.get("type") or "") == "quiz":
        questions = _extract_questions(artifact)
        if questions:
            question_session_id = f"guide_v2_{session_id}"
            store = get_sqlite_session_store()
            if await store.get_session(question_session_id) is None:
                await store.create_session(
                    title=f"导学：{str(session.get('goal') or '')[:80]}",
                    session_id=question_session_id,
                )
            count = await store.upsert_notebook_entries(question_session_id, questions)
            question_result = {
                "saved": True,
                "count": count,
                "session_id": question_session_id,
            }
            _append_evidence_events(
                build_quiz_answer_events(
                    questions,
                    source="question_notebook",
                    session_id=question_session_id,
                    task_id=task_id,
                    artifact_id=artifact_id,
                    node_id=str(task.get("node_id") or ""),
                    source_id_prefix=question_session_id,
                )
            )

    if not request.notebook_ids and not question_result["saved"]:
        raise HTTPException(status_code=400, detail="No save target selected")

    return {
        "success": True,
        "artifact_id": artifact_id,
        "notebook": {
            "record": saved_record,
            "added_to_notebooks": added_to_notebooks,
        },
        "question_notebook": question_result,
    }


@router.post("/sessions/{session_id}/tasks/{task_id}/artifacts/{artifact_id}/quiz-results")
async def submit_quiz_results(
    session_id: str,
    task_id: str,
    artifact_id: str,
    request: SubmitGuideV2QuizResultsRequest,
):
    if not request.answers:
        raise HTTPException(status_code=400, detail="Quiz answers are required")

    answers = [item.model_dump() for item in request.answers]
    result = get_guide_v2_manager().submit_quiz_attempt(
        session_id,
        task_id,
        artifact_id,
        answers=answers,
    )
    if not result.get("success"):
        error = str(result.get("error") or "Quiz submission failed")
        status_code = 404 if "not found" in error.lower() else 400
        raise HTTPException(status_code=status_code, detail=error)

    question_result = {"saved": False, "count": 0, "session_id": ""}
    if request.save_questions:
        question_session_id = f"guide_v2_{session_id}"
        store = get_sqlite_session_store()
        if await store.get_session(question_session_id) is None:
            await store.create_session(
                title=f"导学练习：{session_id}",
                session_id=question_session_id,
            )
        count = await store.upsert_notebook_entries(question_session_id, answers)
        question_result = {
            "saved": True,
            "count": count,
            "session_id": question_session_id,
        }

    session_payload = result.get("session") or {}
    task_payload = _find_task(session_payload, task_id) or {}
    evidence_events = [
        build_guide_task_event(
            session_id=session_id,
            task=task_payload,
            evidence=result.get("evidence") or {},
            session_goal=str(session_payload.get("goal") or ""),
        )
    ]
    evidence_events.extend(
        build_quiz_answer_events(
            answers,
            source="guide_v2",
            session_id=session_id,
            task_id=task_id,
            artifact_id=artifact_id,
            node_id=str(task_payload.get("node_id") or ""),
            source_id_prefix=f"guide_v2:{session_id}",
        )
    )
    evidence_result = _append_evidence_events(evidence_events)

    return {
        **result,
        "question_notebook": question_result,
        "learner_evidence": evidence_result,
    }


@router.post("/sessions/{session_id}/report/save")
async def save_session_report(session_id: str, request: SaveGuideV2ReportRequest):
    if not request.notebook_ids:
        raise HTTPException(status_code=400, detail="No notebook selected")
    report = get_guide_v2_manager().build_learning_report(session_id)
    if not report.get("success"):
        raise HTTPException(status_code=404, detail=str(report.get("error") or "Session not found"))

    title = request.title.strip() or str(report.get("title") or "学习效果报告")
    summary = request.summary.strip() or str(report.get("summary") or "")
    result = notebook_manager.add_record(
        notebook_ids=request.notebook_ids,
        record_type="guided_learning",
        title=title,
        summary=summary,
        user_query=str(report.get("title") or session_id),
        output=str(report.get("markdown") or ""),
        metadata={
            "source": "guide_v2_report",
            "guide_session_id": session_id,
            "overall_score": (report.get("overview") or {}).get("overall_score"),
            "progress": (report.get("overview") or {}).get("progress"),
        },
        kb_name=None,
    )
    saved_record = result.get("record")
    if saved_record:
        _append_evidence_event(
            build_notebook_record_event(
                record=saved_record,
                notebook_ids=list(result.get("added_to_notebooks") or []),
                source="guide_v2_report",
            )
        )
    return {
        "success": True,
        "session_id": session_id,
        "notebook": {
            "record": saved_record,
            "added_to_notebooks": list(result.get("added_to_notebooks") or []),
        },
    }


@router.post("/sessions/{session_id}/course-package/save")
async def save_session_course_package(session_id: str, request: SaveGuideV2PackageRequest):
    if not request.notebook_ids:
        raise HTTPException(status_code=400, detail="No notebook selected")
    package = get_guide_v2_manager().build_course_package(session_id)
    if not package.get("success"):
        raise HTTPException(status_code=404, detail=str(package.get("error") or "Session not found"))

    title = request.title.strip() or str(package.get("title") or "课程产出包")
    summary = request.summary.strip() or str(package.get("summary") or "")
    result = notebook_manager.add_record(
        notebook_ids=request.notebook_ids,
        record_type="guided_learning",
        title=title,
        summary=summary,
        user_query=str(package.get("title") or session_id),
        output=str(package.get("markdown") or ""),
        metadata={
            "source": "guide_v2_course_package",
            "guide_session_id": session_id,
            "overall_score": ((package.get("learning_report") or {}).get("overall_score")),
            "progress": ((package.get("learning_report") or {}).get("progress")),
        },
        kb_name=None,
    )
    saved_record = result.get("record")
    if saved_record:
        _append_evidence_event(
            build_notebook_record_event(
                record=saved_record,
                notebook_ids=list(result.get("added_to_notebooks") or []),
                source="guide_v2_course_package",
            )
        )
    return {
        "success": True,
        "session_id": session_id,
        "notebook": {
            "record": saved_record,
            "added_to_notebooks": list(result.get("added_to_notebooks") or []),
        },
    }


async def _run_resource_generation_job(
    job_id: str,
    session_id: str,
    task_id: str,
    resource_type: str,
    prompt: str,
    quality: str,
) -> None:
    stream_manager = get_task_stream_manager()

    def emit(event: str, payload: dict) -> None:
        stream_manager.emit(
            job_id,
            event,
            {
                "task_id": job_id,
                "session_id": session_id,
                "learning_task_id": task_id,
                **payload,
            },
        )

    emit(
        "status",
        {
            "stage": "running",
            "resource_type": resource_type,
            "message": "Resource generation started.",
        },
    )
    try:
        result = await get_guide_v2_manager().generate_resource(
            session_id,
            task_id,
            resource_type=resource_type,
            prompt=prompt,
            quality=quality,
            event_sink=emit,
        )
        if not result.get("success"):
            stream_manager.emit_failed(job_id, str(result.get("error") or "Resource generation failed"))
            return
        artifact = result.get("artifact") or {}
        result["learner_evidence"] = _append_resource_generation_evidence(session_id, task_id, result)
        stream_manager.emit(job_id, "result", result)
        stream_manager.emit_complete(
            job_id,
            f"Generated {artifact.get('type') or resource_type} resource.",
        )
    except Exception as exc:
        stream_manager.emit_failed(job_id, str(exc))


def _find_task(session: dict, task_id: str) -> dict | None:
    return next((item for item in session.get("tasks", []) if str(item.get("task_id")) == task_id), None)


def _find_artifact(task: dict, artifact_id: str) -> dict | None:
    return next(
        (item for item in task.get("artifact_refs", []) if str(item.get("id")) == artifact_id),
        None,
    )


def _artifact_summary(artifact: dict) -> str:
    result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
    response = str(result.get("response") or "").strip()
    if response:
        return response[:280]
    artifact_type = str(artifact.get("type") or "resource")
    capability = str(artifact.get("capability") or "")
    return f"导学资源：{artifact_type} {capability}".strip()


def _artifact_to_markdown(session: dict, task: dict, artifact: dict) -> str:
    result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
    lines = [
        f"# {artifact.get('title') or task.get('title') or '导学资源'}",
        "",
        f"- 学习目标：{session.get('goal') or ''}",
        f"- 当前任务：{task.get('title') or ''}",
        f"- 资源类型：{artifact.get('type') or ''}",
        f"- 调用智能体：{artifact.get('capability') or ''}",
        "",
    ]
    response = str(result.get("response") or "").strip()
    if response:
        lines.extend(["## 说明", response, ""])
    if isinstance(result.get("artifacts"), list) and result["artifacts"]:
        lines.append("## 生成产物")
        for item in result["artifacts"]:
            if isinstance(item, dict):
                label = item.get("label") or item.get("filename") or item.get("type") or "artifact"
                url = item.get("url") or ""
                lines.append(f"- {label}: {url}")
        lines.append("")
    if str(artifact.get("type") or "") == "external_video" and isinstance(result.get("videos"), list):
        lines.append("## 精选视频")
        for index, item in enumerate(result["videos"], start=1):
            if not isinstance(item, dict):
                continue
            title = item.get("title") or f"视频 {index}"
            url = item.get("url") or ""
            platform = item.get("platform") or "公开视频"
            reason = item.get("why_recommended") or item.get("summary") or ""
            lines.append(f"{index}. [{title}]({url})")
            lines.append(f"   - 平台：{platform}")
            if reason:
                lines.append(f"   - 推荐原因：{reason}")
        lines.append("")
    code = result.get("code") if isinstance(result.get("code"), dict) else {}
    code_content = str(code.get("content") or "").strip()
    if code_content:
        language = str(code.get("language") or "").strip() or "text"
        lines.extend(["## 代码", f"```{language}", code_content, "```", ""])
    if str(artifact.get("type") or "") == "quiz":
        questions = _extract_questions(artifact)
        if questions:
            lines.append("## 练习题")
            for index, question in enumerate(questions, start=1):
                lines.append(f"{index}. {question['question']}")
                if question.get("options"):
                    for key, value in question["options"].items():
                        lines.append(f"   - {key}. {value}")
                if question.get("correct_answer"):
                    lines.append(f"   - 参考答案：{question['correct_answer']}")
                if question.get("explanation"):
                    lines.append(f"   - 解析：{question['explanation']}")
            lines.append("")
    return "\n".join(lines).strip()


def _extract_questions(artifact: dict) -> list[dict]:
    result = artifact.get("result") if isinstance(artifact.get("result"), dict) else {}
    raw_items = result.get("results") if isinstance(result.get("results"), list) else []
    questions: list[dict] = []
    for index, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            continue
        qa = raw.get("qa_pair") if isinstance(raw.get("qa_pair"), dict) else raw
        question = str(qa.get("question") or "").strip()
        if not question:
            continue
        raw_options = qa.get("options") if isinstance(qa.get("options"), dict) else {}
        questions.append(
            {
                "question_id": str(qa.get("question_id") or raw.get("question_id") or f"{artifact.get('id')}_{index}"),
                "question": question,
                "question_type": str(qa.get("question_type") or raw.get("question_type") or ""),
                "options": {str(key): str(value) for key, value in raw_options.items()},
                "correct_answer": str(qa.get("correct_answer") or raw.get("correct_answer") or ""),
                "explanation": str(qa.get("explanation") or raw.get("explanation") or ""),
                "difficulty": str(qa.get("difficulty") or raw.get("difficulty") or ""),
                "user_answer": "",
                "is_correct": False,
            }
        )
    return questions


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        result = get_guide_v2_manager().delete_session(session_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=str(result.get("error") or "Session not found"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
