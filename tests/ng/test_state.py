from __future__ import annotations

from sparkweave.core.contracts import UnifiedContext
from sparkweave.core.state import build_langchain_messages, context_to_state


def test_context_to_state_preserves_legacy_context_fields(monkeypatch):
    def fake_messages(context, *, system_prompt):
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context.user_message},
        ]

    monkeypatch.setattr("sparkweave.core.state.build_langchain_messages", fake_messages)

    context = UnifiedContext(
        session_id="session-1",
        user_message="Explain eigenvalues",
        enabled_tools=["rag"],
        knowledge_bases=["linear-algebra"],
        language="en",
        metadata={"turn_id": "turn-1"},
    )

    state = context_to_state(context, stream="stream")

    assert state["session_id"] == "session-1"
    assert state["turn_id"] == "turn-1"
    assert state["user_message"] == "Explain eigenvalues"
    assert state["enabled_tools"] == ["rag"]
    assert state["knowledge_bases"] == ["linear-algebra"]
    assert state["context"] is context
    assert state["stream"] == "stream"
    assert state["tool_results"] == []


def test_chat_system_prompt_includes_turn_tool_policy() -> None:
    messages = build_langchain_messages(
        UnifiedContext(
            user_message="Explain gradient descent",
            enabled_tools=["rag"],
            knowledge_bases=["ml-course"],
        )
    )

    system_prompt = messages[0].content

    assert "Turn tool policy:" in system_prompt
    assert "You may only call tools listed here for this turn: rag." in system_prompt
    assert "The canvas tool is not enabled for this turn." in system_prompt
    assert "Selected knowledge bases: ml-course" in system_prompt


def test_chat_system_prompt_disables_all_tools_when_none_enabled() -> None:
    messages = build_langchain_messages(
        UnifiedContext(
            user_message="Just answer directly",
            enabled_tools=[],
        )
    )

    system_prompt = messages[0].content

    assert "No tools are enabled for this turn." in system_prompt
    assert "Do not call tools" in system_prompt


