"""Tests for ChatOrchestrator routing and lifecycle."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkweave.core.capability_protocol import BaseCapability, CapabilityManifest
from sparkweave.core.contracts import StreamBus, StreamEvent, StreamEventType, UnifiedContext
from sparkweave.events.event_bus import EventType
from sparkweave.runtime.orchestrator import ChatOrchestrator


@pytest.fixture(autouse=True)
def _patch_event_bus():
    """Prevent EventBus background processor from running during tests."""
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    with patch("sparkweave.runtime.orchestrator.get_event_bus", return_value=mock_bus):
        yield mock_bus
    from sparkweave.events.event_bus import EventBus

    EventBus.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _EchoCapability(BaseCapability):
    """Minimal capability that echoes the user message."""

    manifest = CapabilityManifest(
        name="echo",
        description="Echoes back user message.",
        stages=["responding"],
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        await stream.content(context.user_message, source=self.name)


class _FailingCapability(BaseCapability):
    """Capability that raises."""

    manifest = CapabilityManifest(name="fail", description="Always fails.")

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        raise RuntimeError("intentional failure")


class _FakeLangGraphRunner:
    contexts: list[UnifiedContext] = []

    async def handle(self, context: UnifiedContext):
        self.contexts.append(context)
        yield StreamEvent(
            type=StreamEventType.SESSION,
            source="langgraph",
            metadata={"session_id": context.session_id, "runtime": "langgraph"},
        )
        yield StreamEvent(
            type=StreamEventType.RESULT,
            source="langgraph",
            metadata={"response": "ng response", "runtime": "langgraph"},
        )
        yield StreamEvent(type=StreamEventType.DONE, source="langgraph")


def _make_orchestrator(
    capabilities: dict[str, BaseCapability] | None = None,
) -> ChatOrchestrator:
    """Build an orchestrator with fake registries."""
    cap_reg = MagicMock()
    cap_map = capabilities or {}
    cap_reg.get = lambda name: cap_map.get(name)
    cap_reg.list_capabilities = lambda: list(cap_map.keys())

    tool_reg = MagicMock()
    tool_reg.list_tools = MagicMock(return_value=[])
    tool_reg.build_openai_schemas = MagicMock(return_value=[])

    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    orch._cap_registry = cap_reg
    orch._tool_registry = tool_reg
    return orch


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestOrchestratorRouting:
    @pytest.fixture(autouse=True)
    def _reset_fake_langgraph_runner(self):
        _FakeLangGraphRunner.contexts = []

    @pytest.mark.asyncio
    async def test_routes_to_active_capability(self) -> None:
        echo = _EchoCapability()
        orch = _make_orchestrator({"echo": echo})

        ctx = UnifiedContext(
            user_message="ping",
            active_capability="echo",
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        types = [e.type for e in events]
        assert StreamEventType.SESSION in types
        assert StreamEventType.CONTENT in types
        assert StreamEventType.DONE in types

        content_events = [e for e in events if e.type == StreamEventType.CONTENT]
        assert content_events[0].content == "ping"

    @pytest.mark.asyncio
    async def test_defaults_to_chat_capability(self) -> None:
        chat_cap = _EchoCapability()
        chat_cap.manifest = CapabilityManifest(
            name="chat", description="Default chat.", stages=["responding"]
        )
        orch = _make_orchestrator({"chat": chat_cap})

        ctx = UnifiedContext(
            user_message="hello",
            config_overrides={"_runtime": "legacy"},
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        content_events = [e for e in events if e.type == StreamEventType.CONTENT]
        assert len(content_events) == 1
        assert content_events[0].content == "hello"

    @pytest.mark.asyncio
    async def test_answer_now_context_preserves_active_capability(self) -> None:
        """``answer_now_context`` must be handled by the originally
        selected capability ¡ª each capability owns its own fast-path now.

        Regression test for the previous behavior where the orchestrator
        force-routed every answer-now turn into the ``chat`` capability.
        """
        chat_cap = _EchoCapability()
        chat_cap.manifest = CapabilityManifest(
            name="chat", description="Chat capability.", stages=["responding"]
        )
        chat_cap.run = AsyncMock(
            side_effect=AssertionError("chat must not steal answer_now from deep_solve")
        )
        deep_cap = _EchoCapability()
        deep_cap.manifest = CapabilityManifest(
            name="deep_solve", description="Deep solve.", stages=["responding"]
        )
        orch = _make_orchestrator({"chat": chat_cap, "deep_solve": deep_cap})

        ctx = UnifiedContext(
            user_message="ping",
            active_capability="deep_solve",
            config_overrides={
                "_runtime": "legacy",
                "answer_now_context": {
                    "original_user_message": "ping",
                    "partial_response": "",
                    "events": [],
                }
            },
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        content_events = [e for e in events if e.type == StreamEventType.CONTENT]
        assert len(content_events) == 1
        assert content_events[0].content == "ping"
        chat_cap.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_answer_now_falls_back_to_chat_when_capability_missing(self) -> None:
        """If the originally selected capability is no longer registered
        but the user is mid-``answer_now``, the orchestrator should
        gracefully degrade to ``chat`` instead of erroring out."""
        chat_cap = _EchoCapability()
        chat_cap.manifest = CapabilityManifest(
            name="chat", description="Chat capability.", stages=["responding"]
        )
        orch = _make_orchestrator({"chat": chat_cap})

        ctx = UnifiedContext(
            user_message="ping",
            active_capability="removed_capability",
            config_overrides={
                "answer_now_context": {
                    "original_user_message": "ping",
                    "partial_response": "",
                    "events": [],
                }
            },
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        content_events = [e for e in events if e.type == StreamEventType.CONTENT]
        assert error_events == []
        assert len(content_events) == 1
        assert content_events[0].content == "ping"

    @pytest.mark.asyncio
    async def test_answer_now_without_chat_fallback_still_errors(self) -> None:
        """If neither the requested capability nor ``chat`` is present,
        the orchestrator must still emit a clear error rather than hang."""
        orch = _make_orchestrator({})

        ctx = UnifiedContext(
            user_message="ping",
            active_capability="missing",
            config_overrides={
                "answer_now_context": {
                    "original_user_message": "ping",
                    "partial_response": "",
                    "events": [],
                }
            },
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "Unknown capability" in error_events[0].content

    @pytest.mark.asyncio
    async def test_runtime_override_routes_to_langgraph_runner(self, monkeypatch) -> None:
        legacy_cap = _EchoCapability()
        legacy_cap.run = AsyncMock(side_effect=AssertionError("legacy capability should not run"))
        orch = _make_orchestrator({"chat": legacy_cap})
        monkeypatch.setattr("sparkweave.runtime.LangGraphRunner", _FakeLangGraphRunner)

        ctx = UnifiedContext(
            user_message="hello",
            active_capability="chat",
            config_overrides={"_runtime": "langgraph"},
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        assert [event.source for event in events] == ["langgraph", "langgraph", "langgraph"]
        assert events[0].metadata["runtime"] == "langgraph"
        assert events[-1].type == StreamEventType.DONE
        assert _FakeLangGraphRunner.contexts == [ctx]
        legacy_cap.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_env_routes_to_langgraph_runner(self, monkeypatch) -> None:
        orch = _make_orchestrator({})
        monkeypatch.setattr("sparkweave.runtime.LangGraphRunner", _FakeLangGraphRunner)
        monkeypatch.setenv("SPARKWEAVE_RUNTIME", "ng")

        ctx = UnifiedContext(user_message="hello", active_capability="chat")
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        assert events[0].source == "langgraph"
        assert events[0].metadata["runtime"] == "langgraph"
        assert events[-1].type == StreamEventType.DONE
        assert _FakeLangGraphRunner.contexts == [ctx]

    @pytest.mark.asyncio
    async def test_runtime_auto_routes_allowlisted_capability_to_langgraph(
        self,
        monkeypatch,
    ) -> None:
        legacy_cap = _EchoCapability()
        legacy_cap.run = AsyncMock(side_effect=AssertionError("legacy should not run"))
        orch = _make_orchestrator({"chat": legacy_cap})
        monkeypatch.setattr("sparkweave.runtime.LangGraphRunner", _FakeLangGraphRunner)
        monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
        monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")

        ctx = UnifiedContext(user_message="hello", active_capability="chat")
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        assert events[0].source == "langgraph"
        assert _FakeLangGraphRunner.contexts == [ctx]
        legacy_cap.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_auto_keeps_non_allowlisted_capability_on_legacy(
        self,
        monkeypatch,
    ) -> None:
        echo = _EchoCapability()
        echo.manifest = CapabilityManifest(
            name="visualize",
            description="Visualize.",
            stages=["responding"],
        )
        orch = _make_orchestrator({"visualize": echo})
        monkeypatch.setattr("sparkweave.runtime.LangGraphRunner", _FakeLangGraphRunner)
        monkeypatch.setenv("SPARKWEAVE_RUNTIME", "auto")
        monkeypatch.setenv("SPARKWEAVE_NG_DEFAULT_CAPABILITIES", "chat")

        ctx = UnifiedContext(user_message="draw", active_capability="visualize")
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        assert events[0].source == "orchestrator"
        assert any(event.type == StreamEventType.CONTENT for event in events)
        assert _FakeLangGraphRunner.contexts == []

    @pytest.mark.asyncio
    async def test_langgraph_route_publishes_capability_complete(
        self,
        monkeypatch,
        _patch_event_bus,
    ) -> None:
        orch = _make_orchestrator({})
        monkeypatch.setattr("sparkweave.runtime.LangGraphRunner", _FakeLangGraphRunner)

        ctx = UnifiedContext(
            session_id="session-1",
            user_message="hello",
            active_capability="deep_solve",
            config_overrides={"_runtime": "langgraph"},
            metadata={"turn_id": "turn-1"},
        )
        async for _event in orch.handle(ctx):
            pass

        _patch_event_bus.publish.assert_awaited_once()
        event = _patch_event_bus.publish.await_args.args[0]
        assert event.type == EventType.CAPABILITY_COMPLETE
        assert event.task_id == "turn-1"
        assert event.user_input == "hello"
        assert event.metadata == {
            "capability": "deep_solve",
            "session_id": "session-1",
            "turn_id": "turn-1",
        }

    @pytest.mark.asyncio
    async def test_unknown_capability_yields_error(self) -> None:
        orch = _make_orchestrator({})

        ctx = UnifiedContext(
            user_message="hi",
            active_capability="nonexistent",
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "Unknown capability" in error_events[0].content


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestOrchestratorErrorHandling:
    @pytest.mark.asyncio
    async def test_capability_exception_yields_error_event(self) -> None:
        fail_cap = _FailingCapability()
        orch = _make_orchestrator({"fail": fail_cap})

        ctx = UnifiedContext(
            user_message="boom",
            active_capability="fail",
        )
        events: list[StreamEvent] = []
        async for event in orch.handle(ctx):
            events.append(event)

        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "intentional failure" in error_events[0].content

        done_events = [e for e in events if e.type == StreamEventType.DONE]
        assert len(done_events) == 1


# ---------------------------------------------------------------------------
# Session ID management
# ---------------------------------------------------------------------------


class TestOrchestratorSessionId:
    @pytest.mark.asyncio
    async def test_assigns_session_id_if_missing(self) -> None:
        echo = _EchoCapability()
        orch = _make_orchestrator({"echo": echo})

        ctx = UnifiedContext(user_message="test", active_capability="echo")
        assert ctx.session_id == ""

        async for _ in orch.handle(ctx):
            pass

        assert ctx.session_id != ""

    @pytest.mark.asyncio
    async def test_preserves_existing_session_id(self) -> None:
        echo = _EchoCapability()
        orch = _make_orchestrator({"echo": echo})

        ctx = UnifiedContext(
            session_id="my-session",
            user_message="test",
            active_capability="echo",
        )
        async for _ in orch.handle(ctx):
            pass

        assert ctx.session_id == "my-session"


# ---------------------------------------------------------------------------
# List helpers
# ---------------------------------------------------------------------------


class TestOrchestratorHelpers:
    def test_list_tools(self) -> None:
        orch = _make_orchestrator()
        assert orch.list_tools() == []

    def test_list_capabilities(self) -> None:
        echo = _EchoCapability()
        orch = _make_orchestrator({"echo": echo})
        assert orch.list_capabilities() == ["echo"]

    def test_get_tool_schemas(self) -> None:
        orch = _make_orchestrator()
        schemas = orch.get_tool_schemas()
        assert isinstance(schemas, list)


