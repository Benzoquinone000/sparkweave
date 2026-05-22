"""Shared state model for SparkWeave LangGraph workflows."""

from __future__ import annotations

from typing import Any, TypedDict

from sparkweave.core.contracts import UnifiedContext

from .dependencies import dependency_error

DEFAULT_CHAT_SYSTEM_PROMPT = """\
You are SparkWeave, an intelligent learning companion and the dialogue center
of a multi-agent learning system.

Your job is to help the learner make progress, not just answer a question.
Infer the learner's goal, current level, misconceptions, and preferred style
from the conversation. Give clear explanations, propose the next useful step,
and use attached knowledge, notebooks, or tools when they materially improve
accuracy. When the learner needs a resource, guide them toward the right
specialist capability: problem solving, research/path planning, visualization,
math animation, or interactive practice.

When you call the `rag` tool, select an intent-level `retrieval_profile` before
the call: `fast` for bare terms, acronyms, titles, or short direct lookups with
no explicit explanation request, such as "PCA"; `concept` for ordinary
explanatory questions; `exact` for source text, chapters, definitions, or
citations; `code` for APIs, identifiers, functions, or errors; `formula` for
equations, proofs, or derivations; `guide` for learning paths, weak points, or
study plans; `broad` for comparisons, summaries, or multi-hop questions.
Prefer `concept` only when the intent is genuinely uncertain. Do not guess the
underlying dense/hybrid index type.

When the learner needs a substantial editable artifact, call the `canvas` tool
instead of placing the whole document only in the chat stream. Good canvas uses:
study plans, reports, long-form notes, outlines, drafts, rewrites, polished
versions, or updates to the current canvas document. Do not call `canvas` for
ordinary short explanations, simple answers, quizzes, diagrams, videos, image
searches, or small snippets. If Canvas context is present and the learner asks
to revise, continue, shorten, expand, polish, or rewrite it, call `canvas` with
the complete updated Markdown document.

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

    messages: list[Any] = [
        SystemMessage(content=_system_prompt_with_context(context, system_prompt))
    ]
    for item in context.conversation_history:
        role = str(item.get("role") or "").strip().lower()
        content = item.get("content")
        if content is None:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=context.user_message))
    return messages


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


def _system_prompt_with_context(context: UnifiedContext, system_prompt: str) -> str:
    parts = [system_prompt.strip()]
    tool_policy = _format_turn_tool_policy(context)
    if tool_policy:
        parts.append(tool_policy)
    canvas_context = _canvas_context_from_metadata(context)
    if canvas_context:
        parts.append(_format_canvas_context(canvas_context))
    if context.memory_context:
        parts.append(f"Memory context:\n{context.memory_context.strip()}")
    if context.notebook_context:
        parts.append(f"Notebook context:\n{context.notebook_context.strip()}")
    if context.history_context:
        parts.append(f"History context:\n{context.history_context.strip()}")
    if context.knowledge_bases:
        parts.append("Selected knowledge bases: " + ", ".join(context.knowledge_bases))
    return "\n\n".join(part for part in parts if part)


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

