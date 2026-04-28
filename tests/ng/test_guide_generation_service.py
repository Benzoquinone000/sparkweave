from __future__ import annotations

import pytest

import sparkweave.services.guide_generation as guide_generation


@pytest.mark.asyncio
async def test_guide_manager_runs_session_lifecycle_without_legacy_agents(monkeypatch, tmp_path):
    async def fake_llm_complete(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(guide_generation, "llm_complete", fake_llm_complete)

    manager = guide_generation.GuideManager(output_dir=str(tmp_path), language="en")
    created = await manager.create_session("learn derivatives")
    session_id = created["session_id"]

    started = await manager.start_learning(session_id)
    chat = await manager.chat(session_id, "why does this matter?")
    completed = await manager.complete_learning(session_id)

    assert created["success"] is True
    assert len(created["knowledge_points"]) == 3
    assert started["html"].startswith("<main")
    assert chat["success"] is True
    assert "derivatives" in completed["summary"]
    assert manager.get_current_html(session_id) is not None
    assert manager.get_session_pages(session_id)["page_statuses"]["0"] == "ready"
    assert manager.delete_session(session_id)["success"] is True


def test_base_agent_stats_methods_are_compatible():
    assert guide_generation.BaseAgent.reset_stats("guide") is None
    assert guide_generation.BaseAgent.print_stats("guide") is None

