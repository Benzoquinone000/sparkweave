"""Build Web/API context enrichments for NG turn execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import inspect
from typing import Any

from sparkweave.core.contracts import Attachment, StreamEvent, UnifiedContext
from sparkweave.services.config import get_llm_config
from sparkweave.services.context import ContextBuilder, NotebookAnalysisAgent
from sparkweave.services.learner_evidence import build_chat_statement_events
from sparkweave.services.memory import get_memory
from sparkweave.services.notebook import get_notebooks
from sparkweave.services.session import SQLiteSessionStore

EventSink = Callable[[StreamEvent], Awaitable[None]]


def clip_text(value: str, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def extract_followup_question_context(
    config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(config, dict):
        return None
    raw = config.pop("followup_question_context", None)
    if not isinstance(raw, dict):
        return None

    question = str(raw.get("question", "") or "").strip()
    question_id = str(raw.get("question_id", "") or "").strip()
    if not question:
        return None

    options = raw.get("options")
    normalized_options: dict[str, str] | None = None
    if isinstance(options, dict):
        normalized_options = {
            str(key).strip().upper()[:1]: str(value or "").strip()
            for key, value in options.items()
            if str(value or "").strip()
        }

    return {
        "parent_quiz_session_id": str(raw.get("parent_quiz_session_id", "") or "").strip(),
        "question_id": question_id,
        "question": question,
        "question_type": str(raw.get("question_type", "") or "").strip(),
        "options": normalized_options,
        "correct_answer": str(raw.get("correct_answer", "") or "").strip(),
        "explanation": str(raw.get("explanation", "") or "").strip(),
        "difficulty": str(raw.get("difficulty", "") or "").strip(),
        "concentration": str(raw.get("concentration", "") or "").strip(),
        "knowledge_context": clip_text(str(raw.get("knowledge_context", "") or "").strip()),
        "user_answer": str(raw.get("user_answer", "") or "").strip(),
        "is_correct": raw.get("is_correct"),
    }


def extract_persist_user_message(config: dict[str, Any] | None) -> bool:
    if not isinstance(config, dict):
        return True
    raw = config.pop("_persist_user_message", True)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() not in {"false", "0", "no"}
    return bool(raw)


def format_followup_question_context(context: dict[str, Any], language: str = "en") -> str:
    options = context.get("options") or {}
    option_lines = []
    if isinstance(options, dict) and options:
        for key, value in options.items():
            if value:
                option_lines.append(f"{key}. {value}")
    correctness = context.get("is_correct")
    correctness_text = (
        "correct" if correctness is True else "incorrect" if correctness is False else "unknown"
    )

    if str(language or "en").lower().startswith("zh"):
        lines = [
            "You are handling follow-up questions about a single quiz item.",
            "Use the question context below as the primary grounding for future turns.",
            "",
            "[Question Follow-up Context]",
            f"Question ID: {context.get('question_id') or '(none)'}",
            f"Parent quiz session: {context.get('parent_quiz_session_id') or '(none)'}",
            f"Question type: {context.get('question_type') or '(none)'}",
            f"Difficulty: {context.get('difficulty') or '(none)'}",
            f"Concentration: {context.get('concentration') or '(none)'}",
            "",
            "Question:",
            context.get("question") or "(none)",
        ]
    else:
        lines = [
            "You are handling follow-up questions about a single quiz item.",
            "Use the question context below as the primary grounding for future turns in this session.",
            "If the user asks something broader, you may answer normally, but maintain continuity with this quiz item.",
            "",
            "[Question Follow-up Context]",
            f"Question ID: {context.get('question_id') or '(none)'}",
            f"Parent quiz session: {context.get('parent_quiz_session_id') or '(none)'}",
            f"Question type: {context.get('question_type') or '(none)'}",
            f"Difficulty: {context.get('difficulty') or '(none)'}",
            f"Concentration: {context.get('concentration') or '(none)'}",
            "",
            "Question:",
            context.get("question") or "(none)",
        ]
    if option_lines:
        lines.extend(["", "Options:", *option_lines])
    lines.extend(
        [
            "",
            f"User answer: {context.get('user_answer') or '(not provided)'}",
            f"User result: {correctness_text}",
            f"Reference answer: {context.get('correct_answer') or '(none)'}",
            "",
            "Explanation:",
            context.get("explanation") or "(none)",
        ]
    )
    if context.get("knowledge_context"):
        lines.extend(["", "Knowledge context:", context["knowledge_context"]])
    return "\n".join(lines).strip()


async def build_turn_context(
    *,
    payload: dict[str, Any],
    store: SQLiteSessionStore,
    session_id: str,
    turn_id: str,
    capability: str,
    memory_service: Any | None = None,
    notebook_manager: Any | None = None,
    evidence_service: Any | None = None,
    profile_context_injector: Any | None = None,
    emit: EventSink | None = None,
) -> UnifiedContext:
    request_config = dict(payload.get("config", {}) or {})
    followup_question_context = extract_followup_question_context(request_config)
    persist_user_message = extract_persist_user_message(request_config)
    raw_user_content = str(payload.get("content", "") or "")
    language = str(payload.get("language", "en") or "en")
    notebook_references = payload.get("notebook_references", []) or []
    history_references = payload.get("history_references", []) or []
    attachment_records = _attachment_records(payload)
    attachments = [Attachment(**record) for record in attachment_records]

    if followup_question_context:
        existing_messages = await store.get_messages_for_context(session_id)
        if not existing_messages:
            await store.add_message(
                session_id=session_id,
                role="system",
                content=format_followup_question_context(
                    followup_question_context,
                    language=language,
                ),
                capability=capability or "chat",
            )

    history_result = await ContextBuilder(store).build(
        session_id=session_id,
        llm_config=get_llm_config(),
        language=language,
        on_event=emit,
    )
    memory = memory_service or get_memory()
    memory_context = _build_memory_context(memory)
    learner_profile_context = await _build_learner_profile_context(profile_context_injector)
    memory_context = _merge_memory_and_profile_context(
        memory_context=memory_context,
        learner_profile_text=str(learner_profile_context.get("text") or ""),
    )

    notebook_context = await _build_notebook_context(
        user_question=raw_user_content,
        notebook_references=notebook_references,
        notebook_manager=notebook_manager,
        language=language,
        emit=emit,
    )
    history_context = await _build_history_context(
        store=store,
        user_question=raw_user_content,
        history_references=history_references,
        language=language,
        emit=emit,
    )

    effective_user_message = _effective_user_message(
        raw_user_content=raw_user_content,
        notebook_context=notebook_context,
        history_context=history_context,
    )
    if persist_user_message:
        await store.add_message(
            session_id=session_id,
            role="user",
            content=raw_user_content,
            capability=capability,
            attachments=attachment_records,
        )
        _append_chat_statement_evidence(
            evidence_service=evidence_service,
            message=raw_user_content,
            session_id=session_id,
            turn_id=turn_id,
            capability=capability,
            language=language,
        )

    return UnifiedContext(
        session_id=session_id,
        user_message=effective_user_message,
        conversation_history=list(history_result.conversation_history),
        enabled_tools=list(payload.get("tools") or []),
        active_capability=capability,
        knowledge_bases=list(payload.get("knowledge_bases") or []),
        attachments=attachments,
        config_overrides=request_config,
        language=language,
        notebook_context=notebook_context,
        history_context=history_context,
        memory_context=memory_context,
        metadata={
            "turn_id": turn_id,
            "runtime": "langgraph",
            "conversation_summary": history_result.conversation_summary,
            "conversation_context_text": history_result.context_text,
            "history_token_count": history_result.token_count,
            "history_budget": history_result.budget,
            "question_followup_context": followup_question_context or {},
            "notebook_references": notebook_references,
            "history_references": history_references,
            "memory_context": memory_context,
            "learner_profile_context": learner_profile_context,
        },
    )


def _attachment_records(payload: dict[str, Any]) -> list[dict[str, str]]:
    records = []
    for item in payload.get("attachments", []) or []:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "type": str(item.get("type") or "file"),
                "url": str(item.get("url") or ""),
                "base64": str(item.get("base64") or ""),
                "filename": str(item.get("filename") or ""),
                "mime_type": str(item.get("mime_type") or ""),
            }
        )
    return records


def _append_chat_statement_evidence(
    *,
    evidence_service: Any | None,
    message: str,
    session_id: str,
    turn_id: str,
    capability: str,
    language: str,
) -> None:
    if evidence_service is None:
        return
    events = build_chat_statement_events(
        message,
        session_id=session_id,
        turn_id=turn_id,
        capability=capability or "chat",
        language=language,
    )
    if not events:
        return
    try:
        evidence_service.append_events(events, dedupe=True)
    except Exception:
        return


def _build_memory_context(memory: Any) -> str:
    build = getattr(memory, "build_memory_context", None)
    if not callable(build):
        return ""
    try:
        return str(build() or "")
    except Exception:
        return ""


async def _build_learner_profile_context(profile_context_injector: Any | None) -> dict[str, Any]:
    if profile_context_injector is None:
        return {
            "available": False,
            "source": "learner_profile",
            "text": "",
            "hints": {},
        }
    build = getattr(profile_context_injector, "build_context", None)
    if not callable(build):
        return {
            "available": False,
            "source": "learner_profile",
            "text": "",
            "hints": {},
        }
    try:
        result = build()
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        return {
            "available": False,
            "source": "learner_profile",
            "text": "",
            "hints": {},
            "error": str(exc),
        }
    if not isinstance(result, dict):
        return {
            "available": False,
            "source": "learner_profile",
            "text": "",
            "hints": {},
        }
    return result


def _merge_memory_and_profile_context(
    *,
    memory_context: str,
    learner_profile_text: str,
) -> str:
    parts = [str(memory_context or "").strip(), str(learner_profile_text or "").strip()]
    return "\n\n".join(part for part in parts if part)


async def _build_notebook_context(
    *,
    user_question: str,
    notebook_references: list[Any],
    notebook_manager: Any | None,
    language: str,
    emit: EventSink | None,
) -> str:
    if not notebook_references:
        return ""
    manager = notebook_manager or get_notebooks()
    records = manager.get_records_by_references(notebook_references)
    if not records:
        return ""
    return await NotebookAnalysisAgent(language=language).analyze(
        user_question=user_question,
        records=records,
        emit=emit,
    )


async def _build_history_context(
    *,
    store: SQLiteSessionStore,
    user_question: str,
    history_references: list[Any],
    language: str,
    emit: EventSink | None,
) -> str:
    if not history_references:
        return ""
    records = []
    for session_ref in history_references:
        session_id = str(session_ref or "").strip()
        if not session_id:
            continue
        session = await store.get_session(session_id)
        if not session:
            continue
        messages = await store.get_messages_for_context(session_id)
        transcript_lines = [
            f"## {str(message.get('role', '')).title()}\n{message.get('content', '')}"
            for message in messages
            if str(message.get("content", "") or "").strip()
        ]
        if not transcript_lines:
            continue
        summary = str(session.get("compressed_summary", "") or "").strip()
        if not summary:
            summary = clip_text(
                " ".join(
                    str(message.get("content", "") or "").strip()
                    for message in messages[-4:]
                    if str(message.get("content", "") or "").strip()
                ),
                limit=400,
            )
        records.append(
            {
                "id": session_id,
                "notebook_id": "__history__",
                "notebook_name": "History",
                "title": str(session.get("title", "") or "Untitled session"),
                "summary": summary or f"{len(messages)} messages",
                "output": "\n\n".join(transcript_lines),
                "metadata": {"session_id": session_id, "source": "history"},
            }
        )
    if not records:
        return ""
    context = await NotebookAnalysisAgent(language=language).analyze(
        user_question=user_question,
        records=records,
        emit=emit,
    )
    if context.strip():
        return context
    return _history_fallback(records)


def _history_fallback(records: list[dict[str, Any]]) -> str:
    max_chars = 8000
    parts: list[str] = []
    total = 0
    for record in records:
        output = record.get("output")
        if not output:
            continue
        part = f"## Session: {record.get('title', 'Untitled')}\n{output}"
        if total + len(part) > max_chars:
            remaining = max_chars - total
            if remaining > 100:
                parts.append(part[:remaining] + "\n...(truncated)")
            break
        parts.append(part)
        total += len(part)
    return "\n\n".join(parts)


def _effective_user_message(
    *,
    raw_user_content: str,
    notebook_context: str,
    history_context: str,
) -> str:
    context_parts = []
    if notebook_context:
        context_parts.append(f"[Notebook Context]\n{notebook_context}")
    if history_context:
        context_parts.append(f"[History Context]\n{history_context}")
    if not context_parts:
        return raw_user_content
    context_parts.append(f"[User Question]\n{raw_user_content}")
    return "\n\n".join(context_parts)


__all__ = [
    "build_turn_context",
    "clip_text",
    "extract_followup_question_context",
    "extract_persist_user_message",
    "format_followup_question_context",
]

