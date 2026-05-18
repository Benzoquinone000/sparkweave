from __future__ import annotations

from sparkweave.core.contracts import UnifiedContext
from sparkweave.core.state import context_to_state


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


