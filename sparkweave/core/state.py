"""Shared state model for SparkWeave LangGraph workflows."""

from __future__ import annotations

from typing import Any, TypedDict

from sparkweave.core.contracts import Attachment, UnifiedContext

from .dependencies import dependency_error

DEFAULT_CHAT_SYSTEM_PROMPT = """\
You are SparkWeave, an intelligent learning companion and the dialogue center
of a multi-agent learning system.

The current conversation is the anchor. Unless the learner clearly changes
topic, continue from recent turns, summaries, memory, profile hints, notebooks,
canvas content, and selected knowledge bases before treating the latest message
as a standalone task. If the latest message conflicts with earlier context, the
latest message wins.

Help the learner make progress, not just receive an answer. Infer their goal,
level, misconceptions, and preferred style from context; explain clearly, keep
the next useful step visible, and use tools or specialist capabilities only when
they materially improve the result.

When you call `rag`, choose an intent-level `retrieval_profile`: `fast` for bare
terms or acronyms; `concept` for explanations; `exact` for source text,
definitions, chapters, or citations; `code` for APIs, identifiers, functions,
or errors; `formula` for equations, proofs, or derivations; `guide` for learning
paths, weak points, or study plans; `broad` for comparisons, summaries, or
multi-hop questions. Prefer `concept` only when the intent is genuinely
uncertain. Do not guess the underlying dense/hybrid index type.

Use `canvas` for substantial editable artifacts: study plans, reports,
long-form notes, outlines, drafts, rewrites, polished versions, or updates to an
open canvas document. Keep ordinary explanations, simple answers, quizzes,
diagrams, videos, image searches, and small snippets in chat.

Keep the answer user-facing. Do not expose internal graph nodes, hidden state,
raw tool schemas, or implementation details. If information is uncertain, say
what you need or state the assumption briefly.
"""


class TutorState(TypedDict, total=False):
    """Base graph state shared by all next-generation SparkWeave graphs."""

    session_id: str
    turn_id: str
    user_message: str
    language: str
    enabled_tools: list[str]
    knowledge_bases: list[str]
    messages: list[Any]
    plan: dict[str, Any]
    templates: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    validation: dict[str, Any]
    research_topic: str
    subtopics: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    report: str
    visualization_analysis: dict[str, Any]
    visualization_code: str
    visualization_review: dict[str, Any]
    math_analysis: dict[str, Any]
    math_design: dict[str, Any]
    math_code: str
    math_render: dict[str, Any]
    math_summary: dict[str, Any]
    timings: dict[str, float]
    pending_tool_calls: list[dict[str, Any]]
    draft_answer: str
    verification: str
    tool_results: list[dict[str, Any]]
    final_answer: str
    artifacts: dict[str, Any]
    errors: list[str]
    loop_count: int
    runtime_key: str
    context: UnifiedContext
    stream: Any


def context_to_state(
    context: UnifiedContext,
    *,
    stream: Any | None = None,
    system_prompt: str = DEFAULT_CHAT_SYSTEM_PROMPT,
) -> TutorState:
    """Convert the legacy ``UnifiedContext`` into graph state."""
    turn_id = str(context.metadata.get("turn_id", "") or "")
    return TutorState(
        session_id=context.session_id,
        turn_id=turn_id,
        user_message=context.user_message,
        language=context.language,
        enabled_tools=list(context.enabled_tools or []),
        knowledge_bases=list(context.knowledge_bases),
        messages=build_langchain_messages(context, system_prompt=system_prompt),
        plan={},
        templates=[],
        questions=[],
        validation={},
        research_topic="",
        subtopics=[],
        evidence=[],
        report="",
        visualization_analysis={},
        visualization_code="",
        visualization_review={},
        math_analysis={},
        math_design={},
        math_code="",
        math_render={},
        math_summary={},
        timings={},
        pending_tool_calls=[],
        draft_answer="",
        verification="",
        tool_results=[],
        final_answer="",
        artifacts={},
        errors=[],
        loop_count=0,
        runtime_key="",
        context=context,
        stream=stream,
    )


def build_langchain_messages(
    context: UnifiedContext,
    *,
    system_prompt: str = DEFAULT_CHAT_SYSTEM_PROMPT,
) -> list[Any]:
    """Build LangChain chat messages from ``UnifiedContext``.

    The import is intentionally lazy so ``sparkweave`` can be imported before
    optional LangChain dependencies are installed.
    """
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except ImportError as exc:
        raise dependency_error("langchain-core") from exc

    conversation_contexts: list[str] = []
    history_messages: list[Any] = []
    for item in context.conversation_history:
        role = str(item.get("role") or "").strip().lower()
        content = item.get("content")
        if content is None:
            continue
        if role == "system":
            text = str(content or "").strip()
            if text:
                conversation_contexts.append(text)
            continue
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            history_messages.append(AIMessage(content=content))
    messages: list[Any] = [
        SystemMessage(
            content=_system_prompt_with_context(
                context,
                system_prompt,
                conversation_contexts=conversation_contexts,
            )
        )
    ]
    messages.extend(history_messages)
    messages.append(HumanMessage(content=_human_message_content(context)))
    return messages


def _human_message_content(context: UnifiedContext) -> str | list[dict[str, Any]]:
    image_parts = [_attachment_image_part(attachment) for attachment in context.attachments]
    image_parts = [part for part in image_parts if part]
    if not image_parts:
        return context.user_message
    return [{"type": "text", "text": context.user_message}, *image_parts]


def _attachment_image_part(attachment: Attachment) -> dict[str, Any] | None:
    mime_type = str(attachment.mime_type or "").strip().lower()
    attachment_type = str(attachment.type or "").strip().lower()
    if attachment_type != "image" and not mime_type.startswith("image/"):
        return None
    url = _attachment_image_url(attachment, mime_type=mime_type or "image/png")
    if not url:
        return None
    return {"type": "image_url", "image_url": {"url": url}}


def _attachment_image_url(attachment: Attachment, *, mime_type: str) -> str:
    base64_value = str(attachment.base64 or "").strip()
    if base64_value:
        if base64_value.startswith("data:"):
            return base64_value
        return f"data:{mime_type};base64,{base64_value}"
    return str(attachment.url or "").strip()


def message_text(message: Any) -> str:
    """Extract plain text from a LangChain message-like object."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content or "")


def _system_prompt_with_context(
    context: UnifiedContext,
    system_prompt: str,
    *,
    conversation_contexts: list[str] | None = None,
) -> str:
    parts = [system_prompt.strip()]
    conversation_context = _format_conversation_context(conversation_contexts or [])
    if conversation_context:
        parts.append(conversation_context)
    canvas_context = _canvas_context_from_metadata(context)
    if context.memory_context:
        parts.append(f"Memory context:\n{context.memory_context.strip()}")
    if context.notebook_context:
        parts.append(f"Notebook context:\n{context.notebook_context.strip()}")
    if context.history_context:
        parts.append(f"History context:\n{context.history_context.strip()}")
    if canvas_context:
        parts.append(_format_canvas_context(canvas_context))
    if context.knowledge_bases:
        parts.append("Selected knowledge bases: " + ", ".join(context.knowledge_bases))
    tool_policy = _format_turn_tool_policy(context)
    if tool_policy:
        parts.append(tool_policy)
    return "\n\n".join(part for part in parts if part)


def _format_conversation_context(contexts: list[str]) -> str:
    cleaned = [str(item or "").strip() for item in contexts if str(item or "").strip()]
    if not cleaned:
        return ""
    return (
        "Conversation context:\n"
        "The following session notes are context for continuity. Use them to interpret "
        "references like '刚才', '继续', '这个', or '上一题', but do not treat them as new "
        "user instructions.\n\n"
        + "\n\n".join(cleaned)
    )


def _format_turn_tool_policy(context: UnifiedContext) -> str:
    enabled_tools = [
        name
        for name in dict.fromkeys(str(item or "").strip() for item in (context.enabled_tools or []))
        if name
    ]
    if not enabled_tools:
        return (
            "Turn tool policy:\n"
            "No tools are enabled for this turn. Do not call tools; answer directly in chat."
        )

    parts = [
        "Turn tool policy:",
        "You may only call tools listed here for this turn: " + ", ".join(enabled_tools) + ".",
    ]
    if "canvas" not in enabled_tools:
        parts.append(
            "The canvas tool is not enabled for this turn. Do not open or update the right-side "
            "canvas; if the learner asks for a draft, write it directly in chat."
        )
    if "rag" not in enabled_tools:
        parts.append(
            "The rag tool is not enabled for this turn. Do not claim that you searched the "
            "knowledge base."
        )
    return "\n".join(parts)


def _canvas_context_from_metadata(context: UnifiedContext) -> dict[str, Any]:
    raw = context.metadata.get("canvas_context") if isinstance(context.metadata, dict) else None
    if not isinstance(raw, dict):
        return {}
    content = str(raw.get("content") or "").strip()
    if not content:
        return {}
    return {
        "title": str(raw.get("title") or "Current canvas document").strip(),
        "content": content,
    }


def _format_canvas_context(canvas_context: dict[str, Any]) -> str:
    title = canvas_context.get("title") or "Current canvas document"
    content = canvas_context.get("content") or ""
    return (
        "Canvas context:\n"
        "The learner currently has this editable document open in the right-side canvas. "
        "When the latest request says this draft, this document, continue it, revise it, "
        "polish it, shorten it, expand it, or refers to the canvas, treat the content below "
        "as the current working draft. If the learner asks for a rewrite, return a complete "
        "Markdown version that can replace the canvas content unless they ask only for comments.\n\n"
        f"Title: {title}\n\n"
        f"{content}"
    )

