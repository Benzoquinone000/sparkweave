from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from sparkweave.core.contracts import StreamEvent, StreamEventType
from sparkweave.runtime.policy import MIGRATED_CAPABILITIES
from sparkweave.runtime.routing import RuntimeRoutingTurnManager
from sparkweave.services.session import (
    CompatibilityRuntimeUnavailable,
    create_runtime_router,
    create_session_store,
)


class FakeRuntime:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started: list[dict[str, Any]] = []
        self.subscribed: list[tuple[str, int]] = []
        self.cancelled: list[str] = []

    async def start_turn(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        self.started.append(payload)
        return {"id": f"{self.name}-session"}, {"id": f"{self.name}-turn"}

    async def subscribe_turn(
        self,
        turn_id: str,
        after_seq: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        self.subscribed.append((turn_id, after_seq))
        yield {"type": "content", "source": self.name, "turn_id": turn_id, "seq": after_seq + 1}

    async def cancel_turn(self, turn_id: str) -> bool:
        self.cancelled.append(turn_id)
        return True


@pytest.mark.asyncio
async def test_runtime_router_accepts_compatibility_runtime_alias(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    compatibility = FakeRuntime("compatibility")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(
        compatibility=compatibility,
        langgraph=langgraph,
        store=store,
    )

    _session, turn = await router.start_turn(
        {
            "content": "hello",
            "capability": "chat",
            "config": {"_runtime": "compatibility"},
        }
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert compatibility.started
    assert router.legacy is compatibility
    assert router._turn_runtimes[turn["id"]] == "compatibility"
    assert events[0]["source"] == "compatibility"


def test_runtime_router_rejects_conflicting_compatibility_aliases(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")

    with pytest.raises(ValueError, match="compatibility"):
        RuntimeRoutingTurnManager(
            compatibility=FakeRuntime("compatibility"),
            legacy=FakeRuntime("legacy"),
            store=store,
        )


def test_create_runtime_router_accepts_compatibility_runtime(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    compatibility = FakeRuntime("compatibility")

    router = create_runtime_router(compatibility=compatibility, store=store)

    assert router.compatibility is compatibility
    assert router.legacy is compatibility


@pytest.mark.asyncio
async def test_runtime_router_defaults_to_langgraph_for_migrated_capabilities(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn({"content": "hello", "config": {}})
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert not legacy.started
    assert langgraph.subscribed == [("langgraph-turn", 0)]
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_selects_langgraph_from_config(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {"content": "hello", "config": {"_runtime": "langgraph"}}
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=2)]
    cancelled = await router.cancel_turn(turn["id"])

    assert langgraph.started
    assert not legacy.started
    assert langgraph.subscribed == [("langgraph-turn", 2)]
    assert events[0]["source"] == "langgraph"
    assert cancelled is True
    assert langgraph.cancelled == ["langgraph-turn"]


@pytest.mark.asyncio
async def test_runtime_router_config_default_keeps_ng_default(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {"content": "hello", "capability": "chat", "config": {"_runtime": "default"}}
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert not legacy.started
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_detects_langgraph_from_persisted_events(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    session = await store.create_session("Persisted")
    turn = await store.create_turn(session["id"], capability="chat")
    await store.append_turn_event(
        turn["id"],
        StreamEvent(
            type=StreamEventType.SESSION,
            source="langgraph",
            metadata={"runtime": "langgraph"},
        ).to_dict(),
    )
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.subscribed == [(turn["id"], 0)]
    assert not legacy.subscribed
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_auto_selects_langgraph_from_allowlist(monkeypatch, tmp_path):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn({"content": "hello", "capability": "chat"})
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert not legacy.started
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_explicit_auto_uses_allowlist_without_runtime_env(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("SPARKWEAVE_RUNTIME", raising=False)
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {
            "content": "hello",
            "capability": "chat",
            "runtime": "auto",
        }
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert not legacy.started
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_auto_allowlist_supports_multiple_capabilities(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat,deep_solve")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {"content": "solve x^2 = 4", "capability": "deep_solve"}
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert not legacy.started
    assert langgraph.started[0]["capability"] == "deep_solve"
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_auto_all_routes_only_migrated_capabilities(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "all")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    for capability in sorted(MIGRATED_CAPABILITIES):
        await router.start_turn({"content": f"run {capability}", "capability": capability})

    await router.start_turn({"content": "run custom", "capability": "custom_plugin"})

    assert [payload["capability"] for payload in langgraph.started] == sorted(
        MIGRATED_CAPABILITIES
    )
    assert [payload["capability"] for payload in legacy.started] == ["custom_plugin"]


@pytest.mark.asyncio
async def test_runtime_router_auto_keeps_non_allowlisted_capability_on_legacy(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = FakeRuntime("legacy")
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {"content": "draw", "capability": "visualize"}
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert legacy.started
    assert not langgraph.started
    assert router._turn_runtimes[turn["id"]] == "compatibility"
    assert events[0]["source"] == "legacy"


@pytest.mark.asyncio
async def test_runtime_router_falls_back_to_langgraph_when_legacy_is_unavailable(tmp_path):
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = CompatibilityRuntimeUnavailable()
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {
            "content": "hello",
            "capability": "chat",
            "config": {"_runtime": "legacy"},
        }
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert router._turn_runtimes[turn["id"]] == "langgraph"
    assert events[0]["source"] == "langgraph"


@pytest.mark.asyncio
async def test_runtime_router_auto_uses_langgraph_for_non_allowlisted_when_legacy_unavailable(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
    monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")
    store = create_session_store(tmp_path / "chat_history.db")
    legacy = CompatibilityRuntimeUnavailable()
    langgraph = FakeRuntime("langgraph")
    router = RuntimeRoutingTurnManager(legacy=legacy, langgraph=langgraph, store=store)

    _session, turn = await router.start_turn(
        {"content": "draw", "capability": "visualize"}
    )
    events = [event async for event in router.subscribe_turn(turn["id"], after_seq=0)]

    assert langgraph.started
    assert router._turn_runtimes[turn["id"]] == "langgraph"
    assert events[0]["source"] == "langgraph"



