"""Compatibility shim for NG-owned API session bridge helpers."""

from sparkweave.api.session_bridge import (
    append_stream_event,
    build_legacy_style_session_id,
    build_session_id,
    delete_session_with_fallback,
    get_shared_session,
    list_merged_sessions,
    session_matches_capability,
)

__all__ = [
    "append_stream_event",
    "build_session_id",
    "build_legacy_style_session_id",
    "delete_session_with_fallback",
    "get_shared_session",
    "list_merged_sessions",
    "session_matches_capability",
]


