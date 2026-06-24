from __future__ import annotations

from sparkweave.core.contracts import Attachment, UnifiedContext
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


def test_chat_system_prompt_prioritizes_conversation_context_before_tool_policy() -> None:
    messages = build_langchain_messages(
        UnifiedContext(
            user_message="继续按刚才的薄弱点讲",
            conversation_history=[
                {"role": "system", "content": "Learner is reviewing backpropagation."},
                {"role": "user", "content": "我对链式法则不太熟。"},
                {"role": "assistant", "content": "我们先从局部导数开始。"},
            ],
            enabled_tools=["rag"],
            memory_context="Learner prefers step-by-step explanations.",
            knowledge_bases=["deep-learning"],
        )
    )

    system_prompt = messages[0].content

    assert "Conversation context:" in system_prompt
    assert "Learner is reviewing backpropagation." in system_prompt
    assert system_prompt.index("Conversation context:") < system_prompt.index("Turn tool policy:")
    assert system_prompt.index("Memory context:") < system_prompt.index("Turn tool policy:")
    assert [type(message).__name__ for message in messages[1:]] == [
        "HumanMessage",
        "AIMessage",
        "HumanMessage",
    ]
    assert messages[-1].content == "继续按刚才的薄弱点讲"


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


def test_chat_messages_include_image_attachments_as_multimodal_content() -> None:
    messages = build_langchain_messages(
        UnifiedContext(
            user_message="请解答附件里的题目",
            attachments=[
                Attachment(
                    type="image",
                    filename="problem.png",
                    mime_type="image/png",
                    base64="YWJj",
                ),
                Attachment(
                    type="file",
                    filename="notes.txt",
                    mime_type="text/plain",
                    base64="bm90ZXM=",
                ),
            ],
        )
    )

    content = messages[-1].content

    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "请解答附件里的题目"}
    assert content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,YWJj"},
    }
    assert len(content) == 2


