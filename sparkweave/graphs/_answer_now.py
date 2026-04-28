"""Answer-now helpers for LangGraph-backed capabilities."""

from __future__ import annotations

import re
from typing import Any

from sparkweave.core.contracts import UnifiedContext
from sparkweave.core.json import parse_json_response
from sparkweave.core.state import TutorState

_MAX_EVENT_SNIPPET = 800
_MAX_TRACE_TOTAL = 6000


def extract_answer_now_payload(context: UnifiedContext) -> dict[str, Any] | None:
    raw = getattr(context, "config_overrides", {}).get("answer_now_context")
    if not isinstance(raw, dict):
        return None
    if not str(raw.get("original_user_message") or "").strip():
        return None
    return raw


def extract_answer_now_context(context: UnifiedContext) -> dict[str, Any] | None:
    """Compatibility alias for the legacy helper name."""
    return extract_answer_now_payload(context)


def answer_now_parts(
    state: TutorState,
    payload: dict[str, Any],
) -> tuple[str, str, str]:
    original = str(payload.get("original_user_message") or state.get("user_message") or "").strip()
    partial = str(payload.get("partial_response") or "").strip()
    trace = format_trace_summary(payload.get("events"), language=str(state.get("language") or "en"))
    return original, partial, trace


def answer_now_user_prompt(
    *,
    original: str,
    partial: str,
    trace_summary: str,
    original_label: str = "Original user request",
    trace_label: str = "Execution Trace",
    extra_context: str = "",
    final_instruction: str = "",
) -> str:
    """Build the shared user prompt block for answer-now synthesis."""
    parts = [f"{original_label}:\n{original}"]
    if extra_context.strip():
        parts.append(extra_context.strip())
    parts.append(labeled_block("Current Draft", partial))
    parts.append(labeled_block(trace_label, trace_summary))
    if final_instruction.strip():
        parts.append(final_instruction.strip())
    return "\n\n".join(parts)


def answer_now_progress_metadata(call_state: str, **extra: Any) -> dict[str, Any]:
    metadata = {
        "trace_kind": "call_status",
        "call_state": call_state,
        "answer_now": True,
    }
    metadata.update(extra)
    return metadata


def answer_now_metadata(**extra: Any) -> dict[str, Any]:
    metadata = {"answer_now": True}
    metadata.update(extra)
    return metadata


def answer_now_body(content: str, *, notice: str = "") -> str:
    body = str(content or "").strip()
    prefix = str(notice or "").strip()
    return (prefix + "\n\n" + body).strip() if prefix else body


def format_trace_summary(events: Any, *, language: str = "en") -> str:
    fallback = "No intermediate execution trace was provided."
    if not isinstance(events, list) or not events:
        return fallback

    lines: list[str] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "event").strip()
        stage = str(event.get("stage") or "").strip()
        content = str(event.get("content") or "").strip()
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}

        label = event_type if not stage else f"{event_type} / {stage}"
        line = f"{index}. {label}"
        if content:
            snippet = (
                content
                if len(content) <= _MAX_EVENT_SNIPPET
                else content[: _MAX_EVENT_SNIPPET - 3].rstrip() + "..."
            )
            line += f": {snippet}"
        tool_name = str(metadata.get("tool_name") or metadata.get("tool") or "").strip()
        if tool_name:
            line += f" [tool={tool_name}]"
        lines.append(line)

    if not lines:
        return fallback
    text = "\n".join(lines)
    if len(text) > _MAX_TRACE_TOTAL:
        text = text[: _MAX_TRACE_TOTAL - 3].rstrip() + "..."
    return text


def labeled_block(label: str, content: str) -> str:
    body = content.strip() if isinstance(content, str) and content.strip() else "(empty)"
    return f"[{label}]\n{body}"


def skip_notice(*, capability: str, stages_skipped: list[str]) -> str:
    if not stages_skipped:
        return ""
    joined = ", ".join(stages_skipped)
    return (
        f"> Skipped {joined} stage(s) of `{capability}`; the result below is "
        "a best-effort synthesis from the partial trace."
    )


def make_skip_notice(
    *,
    capability: str,
    language: str = "en",
    stages_skipped: list[str],
) -> str:
    """Compatibility wrapper for callers that still pass a language."""
    _ = language
    return skip_notice(capability=capability, stages_skipped=stages_skipped)


def parse_answer_now_json(raw: str) -> Any:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        if text.endswith("```"):
            text = text[: -3].rstrip()
    return parse_json_response(text, fallback={})


def join_chunks(chunks: list[str]) -> str:
    """Join streamed chunks and strip private thinking blocks when present."""
    return re.sub(r"<think>.*?</think>", "", "".join(chunks), flags=re.DOTALL).strip()


__all__ = [
    "answer_now_body",
    "answer_now_metadata",
    "answer_now_parts",
    "answer_now_progress_metadata",
    "answer_now_user_prompt",
    "extract_answer_now_context",
    "extract_answer_now_payload",
    "format_trace_summary",
    "join_chunks",
    "labeled_block",
    "make_skip_notice",
    "parse_answer_now_json",
    "skip_notice",
]

