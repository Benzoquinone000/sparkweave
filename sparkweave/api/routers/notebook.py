"""
Notebook API Router
Provides notebook creation, querying, updating, deletion, and record management functions
"""

import json
import logging
from typing import Annotated, Any, AsyncGenerator, Literal

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from sparkweave.api.request_limits import (
    MAX_NOTEBOOK_COLOR_CHARS,
    MAX_NOTEBOOK_DESCRIPTION_CHARS,
    MAX_NOTEBOOK_ICON_CHARS,
    MAX_NOTEBOOK_ID_CHARS,
    MAX_NOTEBOOK_IDS,
    MAX_NOTEBOOK_KB_NAME_CHARS,
    MAX_NOTEBOOK_NAME_CHARS,
    MAX_NOTEBOOK_RECORD_METADATA_KEYS,
    MAX_NOTEBOOK_RECORD_METADATA_JSON_CHARS,
    MAX_NOTEBOOK_RECORD_OUTPUT_CHARS,
    MAX_NOTEBOOK_RECORD_QUERY_CHARS,
    MAX_NOTEBOOK_RECORD_SUMMARY_CHARS,
    MAX_NOTEBOOK_RECORD_TITLE_CHARS,
    NOTEBOOK_ID_PATTERN,
    strip_required_text,
    validate_notebook_metadata,
)
from sparkweave.services.learner_evidence import build_notebook_record_event, get_learner_evidence_service
from sparkweave.services.notebook import notebook_manager
from sparkweave.services.notebook_summary import NotebookSummarizeAgent

router = APIRouter()
logger = logging.getLogger(__name__)
NotebookIdField = Annotated[
    str,
    Field(min_length=1, max_length=MAX_NOTEBOOK_ID_CHARS, pattern=NOTEBOOK_ID_PATTERN),
]
NotebookPathId = Annotated[
    str,
    Path(min_length=1, max_length=MAX_NOTEBOOK_ID_CHARS, pattern=NOTEBOOK_ID_PATTERN),
]


# === Request/Response Models ===


class CreateNotebookRequest(BaseModel):
    """Create notebook request"""

    name: str = Field(..., min_length=1, max_length=MAX_NOTEBOOK_NAME_CHARS)
    description: str = Field(default="", max_length=MAX_NOTEBOOK_DESCRIPTION_CHARS)
    color: str = Field(default="#3B82F6", max_length=MAX_NOTEBOOK_COLOR_CHARS)
    icon: str = Field(default="book", max_length=MAX_NOTEBOOK_ICON_CHARS)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return strip_required_text(value, "name")


class UpdateNotebookRequest(BaseModel):
    """Update notebook request"""

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NOTEBOOK_NAME_CHARS)
    description: str | None = Field(default=None, max_length=MAX_NOTEBOOK_DESCRIPTION_CHARS)
    color: str | None = Field(default=None, max_length=MAX_NOTEBOOK_COLOR_CHARS)
    icon: str | None = Field(default=None, max_length=MAX_NOTEBOOK_ICON_CHARS)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return strip_required_text(value, "name")


class AddRecordRequest(BaseModel):
    """Add record request"""

    notebook_ids: list[NotebookIdField] = Field(..., min_length=1, max_length=MAX_NOTEBOOK_IDS)
    record_type: Literal["solve", "question", "research", "co_writer", "chat", "guided_learning"]
    title: str = Field(..., min_length=1, max_length=MAX_NOTEBOOK_RECORD_TITLE_CHARS)
    summary: str = Field(default="", max_length=MAX_NOTEBOOK_RECORD_SUMMARY_CHARS)
    user_query: str = Field(..., max_length=MAX_NOTEBOOK_RECORD_QUERY_CHARS)
    output: str = Field(..., max_length=MAX_NOTEBOOK_RECORD_OUTPUT_CHARS)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=MAX_NOTEBOOK_RECORD_METADATA_KEYS)
    kb_name: str | None = Field(default=None, max_length=MAX_NOTEBOOK_KB_NAME_CHARS)

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_notebook_metadata(value) or {}

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        return strip_required_text(value, "title")


class RemoveRecordRequest(BaseModel):
    """Remove record request"""

    record_id: NotebookIdField


class UpdateRecordRequest(BaseModel):
    """Update an existing notebook record."""

    title: str | None = Field(default=None, min_length=1, max_length=MAX_NOTEBOOK_RECORD_TITLE_CHARS)
    summary: str | None = Field(default=None, max_length=MAX_NOTEBOOK_RECORD_SUMMARY_CHARS)
    user_query: str | None = Field(default=None, max_length=MAX_NOTEBOOK_RECORD_QUERY_CHARS)
    output: str | None = Field(default=None, max_length=MAX_NOTEBOOK_RECORD_OUTPUT_CHARS)
    metadata: dict[str, Any] | None = Field(default=None, max_length=MAX_NOTEBOOK_RECORD_METADATA_KEYS)
    kb_name: str | None = Field(default=None, max_length=MAX_NOTEBOOK_KB_NAME_CHARS)

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_notebook_metadata(value)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return strip_required_text(value, "title")


# === API Endpoints ===


async def _build_record_summary(request: AddRecordRequest) -> str:
    if request.summary.strip():
        return request.summary.strip()
    agent = NotebookSummarizeAgent(language=str(request.metadata.get("ui_language", "en")))
    return await agent.summarize(
        title=request.title,
        record_type=request.record_type,
        user_query=request.user_query,
        output=request.output,
        metadata=request.metadata,
    )


async def _stream_add_record_with_summary(
    request: AddRecordRequest,
) -> AsyncGenerator[str, None]:
    try:
        agent = NotebookSummarizeAgent(language=str(request.metadata.get("ui_language", "en")))
        summary_parts: list[str] = []
        if request.summary.strip():
            summary_parts.append(request.summary.strip())
            yield f"data: {json.dumps({'type': 'summary_chunk', 'content': request.summary.strip()}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in agent.stream_summary(
                title=request.title,
                record_type=request.record_type,
                user_query=request.user_query,
                output=request.output,
                metadata=request.metadata,
            ):
                if not chunk:
                    continue
                summary_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'summary_chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

        summary = "".join(summary_parts).strip()
        result = notebook_manager.add_record(
            notebook_ids=request.notebook_ids,
            record_type=request.record_type,
            title=request.title,
            summary=summary,
            user_query=request.user_query,
            output=request.output,
            metadata=request.metadata,
            kb_name=request.kb_name,
        )
        _append_notebook_evidence(result)
        payload = {
            "type": "result",
            "success": True,
            "summary": summary,
            "record": result["record"],
            "added_to_notebooks": result["added_to_notebooks"],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    except Exception as exc:
        payload = {"type": "error", "detail": str(exc)}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/list")
async def list_notebooks():
    """
    Get all notebook list

    Returns:
        Notebook list (includes summary information)
    """
    try:
        notebooks = notebook_manager.list_notebooks()
        return {"notebooks": notebooks, "total": len(notebooks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics():
    """
    Get notebook statistics

    Returns:
        Statistics information
    """
    try:
        stats = notebook_manager.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "service": "notebook"}


@router.post("/create")
async def create_notebook(request: CreateNotebookRequest):
    """
    Create new notebook

    Args:
        request: Create request

    Returns:
        Created notebook information
    """
    try:
        notebook = notebook_manager.create_notebook(
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon,
        )
        return {"success": True, "notebook": notebook}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{notebook_id}")
async def get_notebook(notebook_id: NotebookPathId):
    """
    Get notebook details

    Args:
        notebook_id: Notebook ID

    Returns:
        Notebook details (includes all records)
    """
    try:
        notebook = notebook_manager.get_notebook(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        return notebook
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.put("/{notebook_id}")
async def update_notebook(notebook_id: NotebookPathId, request: UpdateNotebookRequest):
    """
    Update notebook information

    Args:
        notebook_id: Notebook ID
        request: Update request

    Returns:
        Updated notebook information
    """
    try:
        notebook = notebook_manager.update_notebook(
            notebook_id=notebook_id,
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon,
        )
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        return {"success": True, "notebook": notebook}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notebook_id}")
async def delete_notebook(notebook_id: NotebookPathId):
    """
    Delete notebook

    Args:
        notebook_id: Notebook ID

    Returns:
        Deletion result
    """
    try:
        success = notebook_manager.delete_notebook(notebook_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notebook not found")
        return {"success": True, "message": "Notebook deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add_record")
async def add_record(request: AddRecordRequest):
    """
    Add record to notebook

    Args:
        request: Add record request

    Returns:
        Addition result
    """
    try:
        summary = await _build_record_summary(request)
        result = notebook_manager.add_record(
            notebook_ids=request.notebook_ids,
            record_type=request.record_type,
            title=request.title,
            summary=summary,
            user_query=request.user_query,
            output=request.output,
            metadata=request.metadata,
            kb_name=request.kb_name,
        )
        _append_notebook_evidence(result)
        return {
            "success": True,
            "summary": summary,
            "record": result["record"],
            "added_to_notebooks": result["added_to_notebooks"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _append_notebook_evidence(result: dict) -> None:
    record = result.get("record") if isinstance(result, dict) else None
    if not isinstance(record, dict):
        return
    try:
        get_learner_evidence_service().append_events(
            [
                build_notebook_record_event(
                    record=record,
                    notebook_ids=list(result.get("added_to_notebooks") or []),
                    source="notebook",
                )
            ],
            dedupe=True,
        )
    except Exception:
        logger.warning("Failed to append notebook learner evidence", exc_info=True)


@router.post("/add_record_with_summary")
async def add_record_with_summary(request: AddRecordRequest):
    """Add record to notebook and stream generated summary."""
    return StreamingResponse(
        _stream_add_record_with_summary(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/{notebook_id}/records/{record_id}")
async def remove_record(notebook_id: NotebookPathId, record_id: NotebookPathId):
    """
    Remove record from notebook

    Args:
        notebook_id: Notebook ID
        record_id: Record ID

    Returns:
        Deletion result
    """
    try:
        success = notebook_manager.remove_record(notebook_id, record_id)
        if not success:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"success": True, "message": "Record removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{notebook_id}/records/{record_id}")
async def update_record(notebook_id: NotebookPathId, record_id: NotebookPathId, request: UpdateRecordRequest):
    """Update an existing notebook record in place."""
    try:
        updated = notebook_manager.update_record(
            notebook_id=notebook_id,
            record_id=record_id,
            title=request.title,
            summary=request.summary,
            user_query=request.user_query,
            output=request.output,
            metadata=request.metadata,
            kb_name=request.kb_name,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"success": True, "record": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
