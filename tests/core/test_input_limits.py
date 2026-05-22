from __future__ import annotations

import pytest

from sparkweave.core.input_limits import (
    MAX_CHAT_ATTACHMENT_BASE64_CHARS,
    MAX_CHAT_ATTACHMENT_COUNT,
    MAX_CHAT_CANVAS_CONTEXT_CHARS,
    MAX_CHAT_MESSAGE_CHARS,
    normalize_turn_payload,
)


def test_normalize_turn_payload_trims_content_and_lists() -> None:
    payload = normalize_turn_payload(
        {
            "content": "  explain Fourier  ",
            "capability": "chat",
            "tools": [" rag ", ""],
            "knowledge_bases": [" notes "],
            "history_references": [" session-1 "],
            "attachments": [
                {
                    "type": "image",
                    "filename": " diagram.png ",
                    "mime_type": " image/png ",
                    "base64": "abc",
                }
            ],
            "config": {"mode": "short"},
        }
    )

    assert payload["content"] == "explain Fourier"
    assert payload["tools"] == ["rag"]
    assert payload["knowledge_bases"] == ["notes"]
    assert payload["history_references"] == ["session-1"]
    assert payload["attachments"][0]["filename"] == "diagram.png"


def test_normalize_turn_payload_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="content is required"):
        normalize_turn_payload({"content": "   "})


def test_normalize_turn_payload_rejects_oversized_content() -> None:
    with pytest.raises(ValueError, match="content cannot exceed"):
        normalize_turn_payload({"content": "x" * (MAX_CHAT_MESSAGE_CHARS + 1)})


def test_normalize_turn_payload_rejects_too_many_attachments() -> None:
    with pytest.raises(ValueError, match="attachments cannot contain"):
        normalize_turn_payload(
            {
                "content": "hello",
                "attachments": [{"filename": f"{index}.txt"} for index in range(MAX_CHAT_ATTACHMENT_COUNT + 1)],
            }
        )


def test_normalize_turn_payload_rejects_oversized_attachment_base64() -> None:
    with pytest.raises(ValueError, match="attachment.base64 cannot exceed"):
        normalize_turn_payload(
            {
                "content": "hello",
                "attachments": [{"filename": "big.txt", "base64": "x" * (MAX_CHAT_ATTACHMENT_BASE64_CHARS + 1)}],
            }
        )


def test_normalize_turn_payload_accepts_canvas_context() -> None:
    payload = normalize_turn_payload(
        {
            "content": "revise this",
            "canvas_context": {
                "id": " canvas-1 ",
                "message_id": " assistant-1 ",
                "title": " Study plan ",
                "content": " # Draft plan ",
                "updated_at": 1_700_000_000,
            },
        }
    )

    assert payload["canvas_context"] == {
        "id": "canvas-1",
        "message_id": "assistant-1",
        "title": "Study plan",
        "content": "# Draft plan",
        "updated_at": 1_700_000_000,
    }


def test_normalize_turn_payload_rejects_oversized_canvas_context() -> None:
    with pytest.raises(ValueError, match="canvas_context.content cannot exceed"):
        normalize_turn_payload(
            {
                "content": "revise this",
                "canvas_context": {"content": "x" * (MAX_CHAT_CANVAS_CONTEXT_CHARS + 1)},
            }
        )
