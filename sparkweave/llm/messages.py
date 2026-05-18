"""Shared LangChain message and JSON helpers for next-gen graphs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from sparkweave.core.dependencies import dependency_error
from sparkweave.core.json import parse_json_response
from sparkweave.core.state import message_text


def chat_messages(*, system: str, user: str) -> list[Any]:
    """Build a simple system + human LangChain message pair."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError as exc:
        raise dependency_error("langchain-core") from exc

    return [SystemMessage(content=system), HumanMessage(content=user)]


def chat_messages_with_attachments(
    *,
    system: str,
    user: str,
    attachments: list[Any],
) -> list[Any]:
    """Build LangChain multimodal messages from SparkWeave attachments."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
    except ImportError as exc:
        raise dependency_error("langchain-core") from exc

    content: list[dict[str, Any]] = [{"type": "text", "text": user}]
    for attachment in attachments:
        url = _attachment_url(attachment)
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
    return [SystemMessage(content=system), HumanMessage(content=content)]


async def ainvoke_json(
    model: Any,
    *,
    system: str,
    user: str,
    schema: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Invoke a chat model and parse a JSON object response."""
    messages = chat_messages(system=system, user=user)
    if schema is not None and hasattr(model, "with_structured_output"):
        try:
            value = await model.with_structured_output(schema).ainvoke(messages)
            structured = _value_to_dict(value)
            if structured is not None:
                return structured
        except Exception:
            pass
    return await _ainvoke_json_messages(model, messages)


async def ainvoke_json_with_attachments(
    model: Any,
    *,
    system: str,
    user: str,
    attachments: list[Any],
    schema: type[BaseModel] | None = None,
) -> dict[str, Any]:
    """Invoke a chat model with multimodal messages and parse JSON output."""
    messages = chat_messages_with_attachments(
        system=system,
        user=user,
        attachments=attachments,
    )
    if schema is not None and hasattr(model, "with_structured_output"):
        try:
            value = await model.with_structured_output(schema).ainvoke(messages)
            structured = _value_to_dict(value)
            if structured is not None:
                return structured
        except Exception:
            pass
    return await _ainvoke_json_messages(model, messages)


async def _ainvoke_json_messages(model: Any, messages: list[Any]) -> dict[str, Any]:
    response = await model.ainvoke(messages)
    parsed = parse_json_response(message_text(response), fallback={})
    return parsed if isinstance(parsed, dict) else {}


def _value_to_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, BaseModel):
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value.dict()
    if isinstance(value, dict):
        return value
    return None


def _attachment_url(attachment: Any) -> str:
    mime_type = _attachment_value(attachment, "mime_type") or "image/png"
    base64_data = _attachment_value(attachment, "base64")
    url = _attachment_value(attachment, "url")
    if base64_data:
        return f"data:{mime_type};base64,{base64_data}"
    return url


def _attachment_value(attachment: Any, key: str) -> str:
    if isinstance(attachment, Mapping):
        value = attachment.get(key, "")
    else:
        value = getattr(attachment, key, "")
    return str(value or "")

