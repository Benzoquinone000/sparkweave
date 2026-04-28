"""NG-owned shared session-history helpers for API routers."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import Any
import uuid

from sparkweave.core.contracts import StreamEvent, StreamEventType
from sparkweave.services.session_store import SQLiteSessionStore


def session_matches_capability(
    session: dict[str, Any] | None,
    capability_names: set[str],
) -> bool:
    if session is None:
        return False
    preferences = session.get("preferences") if isinstance(session.get("preferences"), dict) else {}
    capability = str(
        session.get("capability")
        or preferences.get("capability")
        or ""
    ).strip()
    return capability in capability_names or (not capability and "" in capability_names)


def _session_sort_key(session: dict[str, Any]) -> float:
    raw = session.get("updated_at", session.get("created_at", 0)) or 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


async def list_merged_sessions(
    *,
    store: SQLiteSessionStore,
    capability_names: set[str],
    limit: int,
    map_shared_summary: Callable[[dict[str, Any]], dict[str, Any]],
    fallback_sessions: list[dict[str, Any]] | None = None,
    legacy_sessions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    batch_size = max(limit, 50)
    offset = 0
    merged: dict[str, dict[str, Any]] = {}

    while len(merged) < limit:
        sessions = await store.list_sessions(limit=batch_size, offset=offset)
        if not sessions:
            break
        for session in sessions:
            if not session_matches_capability(session, capability_names):
                continue
            summary = map_shared_summary(session)
            session_id = str(summary.get("session_id") or "").strip()
            if session_id:
                merged[session_id] = summary
            if len(merged) >= limit:
                break
        if len(sessions) < batch_size:
            break
        offset += batch_size

    external_sessions = fallback_sessions if fallback_sessions is not None else legacy_sessions or []
    for session in external_sessions:
        session_id = str(session.get("session_id") or "").strip()
        if session_id and session_id not in merged:
            merged[session_id] = session

    return sorted(merged.values(), key=_session_sort_key, reverse=True)[:limit]


async def get_shared_session(
    *,
    store: SQLiteSessionStore,
    session_id: str,
    capability_names: set[str],
) -> dict[str, Any] | None:
    session = await store.get_session_with_messages(session_id)
    if not session_matches_capability(session, capability_names):
        return None
    return session


async def delete_session_with_fallback(
    *,
    store: SQLiteSessionStore,
    session_id: str,
    capability_names: set[str],
    delete_fallback: Callable[[str], bool] | None = None,
    delete_legacy: Callable[[str], bool] | None = None,
) -> bool:
    session = await store.get_session(session_id)
    if session_matches_capability(session, capability_names):
        return await store.delete_session(session_id)
    fallback = delete_fallback or delete_legacy
    if fallback is None:
        return False
    return bool(fallback(session_id))


async def append_stream_event(
    *,
    store: SQLiteSessionStore,
    turn_id: str,
    session_id: str,
    event_type: StreamEventType,
    source: str,
    stage: str = "",
    content: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = StreamEvent(
        type=event_type,
        source=source,
        stage=stage,
        content=content,
        metadata=dict(metadata or {}),
        session_id=session_id,
        turn_id=turn_id,
    )
    if payload.type == StreamEventType.DONE and "status" not in payload.metadata:
        payload.metadata["status"] = "completed"
    return await store.append_turn_event(turn_id, payload.to_dict())


def build_session_id(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def build_legacy_style_session_id(prefix: str) -> str:
    """Backward-compatible alias for the old helper name."""
    return build_session_id(prefix)


__all__ = [
    "append_stream_event",
    "build_session_id",
    "build_legacy_style_session_id",
    "delete_session_with_fallback",
    "get_shared_session",
    "list_merged_sessions",
    "session_matches_capability",
]


