from __future__ import annotations

from typing import Any

from pydantic import BaseModel
import pytest

from sparkweave.core.contracts import Attachment
from sparkweave.llm import (
    ainvoke_json,
    ainvoke_json_with_attachments,
    chat_messages_with_attachments,
)


class FakeModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[Any]] = []

    async def ainvoke(self, messages: list[Any]) -> Any:
        from langchain_core.messages import AIMessage

        self.calls.append(messages)
        return AIMessage(content=self.response)


class StructuredPayload(BaseModel):
    value: str


class StructuredModel:
    def __init__(self) -> None:
        self.schema: type[BaseModel] | None = None
        self.calls: list[list[Any]] = []

    def with_structured_output(self, schema: type[BaseModel]) -> StructuredModel:
        self.schema = schema
        return self

    async def ainvoke(self, messages: list[Any]) -> Any:
        self.calls.append(messages)
        assert self.schema is not None
        return self.schema(value="structured")


@pytest.mark.asyncio
async def test_ainvoke_json_parses_json_fallback_response():
    model = FakeModel('{"ok": true, "count": 2}')

    payload = await ainvoke_json(model, system="system", user="user")

    assert payload == {"ok": True, "count": 2}
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_ainvoke_json_prefers_structured_output():
    model = StructuredModel()

    payload = await ainvoke_json(
        model,
        system="system",
        user="user",
        schema=StructuredPayload,
    )

    assert payload == {"value": "structured"}
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_ainvoke_json_with_attachments_builds_multimodal_message():
    model = FakeModel('{"passed": true}')
    attachment = Attachment(
        type="image",
        base64="abc123",
        filename="frame.png",
        mime_type="image/png",
    )

    payload = await ainvoke_json_with_attachments(
        model,
        system="review",
        user="look at this frame",
        attachments=[attachment],
    )

    assert payload == {"passed": True}
    human_message = model.calls[0][1]
    assert human_message.content[0] == {"type": "text", "text": "look at this frame"}
    assert human_message.content[1]["image_url"]["url"] == "data:image/png;base64,abc123"


def test_chat_messages_with_attachments_accepts_dict_urls():
    messages = chat_messages_with_attachments(
        system="system",
        user="user",
        attachments=[{"url": "https://example.test/frame.png"}],
    )

    assert messages[1].content[1]["image_url"]["url"] == "https://example.test/frame.png"


