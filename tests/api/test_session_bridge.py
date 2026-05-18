from __future__ import annotations

import pytest

from sparkweave.api.session_bridge import (
    build_legacy_style_session_id,
    build_session_id,
    delete_session_with_fallback,
    list_merged_sessions,
)
from sparkweave.services.session import create_session_store


@pytest.mark.asyncio
async def test_session_bridge_accepts_ng_fallback_names(tmp_path) -> None:
    store = create_session_store(tmp_path / "sessions.db")
    session = await store.create_session(title="Shared", session_id="shared")
    await store.update_session_preferences(session["id"], {"capability": "chat"})

    merged = await list_merged_sessions(
        store=store,
        capability_names={"chat"},
        limit=10,
        fallback_sessions=[
            {
                "session_id": "json-fallback",
                "title": "JSON fallback",
                "updated_at": 1,
            }
        ],
        map_shared_summary=lambda item: {
            "session_id": item["id"],
            "title": item["title"],
            "updated_at": item["updated_at"],
        },
    )

    deleted_fallback: list[str] = []
    deleted = await delete_session_with_fallback(
        store=store,
        session_id="json-fallback",
        capability_names={"chat"},
        delete_fallback=lambda session_id: deleted_fallback.append(session_id) is None,
    )

    assert [item["session_id"] for item in merged] == ["shared", "json-fallback"]
    assert deleted is True
    assert deleted_fallback == ["json-fallback"]


@pytest.mark.asyncio
async def test_session_bridge_keeps_legacy_aliases_for_compatibility(tmp_path) -> None:
    store = create_session_store(tmp_path / "sessions.db")

    merged = await list_merged_sessions(
        store=store,
        capability_names={"chat"},
        limit=10,
        legacy_sessions=[{"session_id": "old-json", "updated_at": 1}],
        map_shared_summary=lambda item: item,
    )
    deleted = await delete_session_with_fallback(
        store=store,
        session_id="old-json",
        capability_names={"chat"},
        delete_legacy=lambda session_id: session_id == "old-json",
    )

    assert merged == [{"session_id": "old-json", "updated_at": 1}]
    assert deleted is True
    assert build_session_id("chat_").startswith("chat_")
    assert build_legacy_style_session_id("chat_").startswith("chat_")

