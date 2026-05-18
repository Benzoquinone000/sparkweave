"""Helpers for bridging NG stream events to legacy-style trace payloads."""

from __future__ import annotations

from typing import Any

from sparkweave.core.contracts import StreamEvent, StreamEventType


def stream_event_to_trace_payload(event: StreamEvent) -> dict[str, Any]:
    """Convert an NG ``StreamEvent`` into the older callback payload shape."""
    event_type = event.type.value if isinstance(event.type, StreamEventType) else str(event.type)
    metadata = dict(event.metadata or {})
    trace_event = str(metadata.get("event") or event_type)
    state = str(metadata.get("call_state") or metadata.get("state") or "")

    if event.type == StreamEventType.PROGRESS and metadata.get("trace_kind") == "call_status":
        trace_event = "llm_call"
    elif event.type == StreamEventType.THINKING:
        trace_event = "llm_call"
        state = "streaming" if metadata.get("trace_kind") == "llm_chunk" else "complete"
    elif event.type == StreamEventType.TOOL_CALL:
        trace_event = "tool_call"
    elif event.type == StreamEventType.TOOL_RESULT:
        trace_event = "tool_result"

    payload: dict[str, Any] = {
        "event": trace_event,
        "type": event_type,
        "phase": event.stage,
        "stage": event.stage,
        "source": event.source,
        "message": event.content,
        "response": event.content,
        "state": state,
        "seq": event.seq,
        "timestamp": event.timestamp,
    }
    payload.update(metadata)
    if event.type == StreamEventType.TOOL_CALL:
        payload.setdefault("tool_name", event.content)
        payload.setdefault("tool_args", metadata.get("args", {}))
    if event.type == StreamEventType.TOOL_RESULT:
        payload.setdefault("tool_name", metadata.get("tool") or event.content)
        payload.setdefault("result", event.content)
    return payload


__all__ = ["stream_event_to_trace_payload"]

