"""Input bounds for interactive learner-facing turns."""

from __future__ import annotations

import json
from typing import Any

MAX_CHAT_MESSAGE_CHARS = 20_000
MAX_CHAT_SESSION_ID_CHARS = 160
MAX_CHAT_LABEL_CHARS = 180
MAX_CHAT_LIST_ITEMS = 20
MAX_CHAT_ATTACHMENT_COUNT = 5
MAX_CHAT_ATTACHMENT_BASE64_CHARS = 14_000_000
MAX_CHAT_ATTACHMENT_FILENAME_CHARS = 180
MAX_CHAT_ATTACHMENT_MIME_CHARS = 120
MAX_CHAT_ATTACHMENT_URL_CHARS = 2_048
MAX_CHAT_CONFIG_JSON_CHARS = 100_000
MAX_CHAT_REFERENCES_JSON_CHARS = 40_000


def bounded_text(
    value: Any,
    *,
    field_name: str,
    max_chars: int,
    required: bool = False,
) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field_name} is required")
    if len(text) > max_chars:
        raise ValueError(f"{field_name} cannot exceed {max_chars} characters")
    return text


def bounded_json(value: Any, *, field_name: str, max_chars: int) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON serializable") from exc
    if len(encoded) > max_chars:
        raise ValueError(f"{field_name} cannot exceed {max_chars} encoded characters")
    return value


def bounded_string_list(
    value: Any,
    *,
    field_name: str,
    max_items: int = MAX_CHAT_LIST_ITEMS,
    max_chars: int = MAX_CHAT_LABEL_CHARS,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if len(value) > max_items:
        raise ValueError(f"{field_name} cannot contain more than {max_items} items")
    result: list[str] = []
    for item in value:
        text = bounded_text(item, field_name=field_name, max_chars=max_chars)
        if text:
            result.append(text)
    return result


def normalize_attachments(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("attachments must be a list")
    if len(value) > MAX_CHAT_ATTACHMENT_COUNT:
        raise ValueError(f"attachments cannot contain more than {MAX_CHAT_ATTACHMENT_COUNT} files")

    records: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("attachments must contain objects")
        base64_payload = bounded_text(
            item.get("base64") or "",
            field_name="attachment.base64",
            max_chars=MAX_CHAT_ATTACHMENT_BASE64_CHARS,
        )
        records.append(
            {
                "type": bounded_text(
                    item.get("type") or "file",
                    field_name="attachment.type",
                    max_chars=20,
                )
                or "file",
                "url": bounded_text(
                    item.get("url") or "",
                    field_name="attachment.url",
                    max_chars=MAX_CHAT_ATTACHMENT_URL_CHARS,
                ),
                "base64": base64_payload,
                "filename": bounded_text(
                    item.get("filename") or "",
                    field_name="attachment.filename",
                    max_chars=MAX_CHAT_ATTACHMENT_FILENAME_CHARS,
                ),
                "mime_type": bounded_text(
                    item.get("mime_type") or "",
                    field_name="attachment.mime_type",
                    max_chars=MAX_CHAT_ATTACHMENT_MIME_CHARS,
                ),
            }
        )
    return records


def normalize_turn_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize and bound a runtime start-turn payload before execution."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    normalized = dict(payload)
    normalized["content"] = bounded_text(
        payload.get("content"),
        field_name="content",
        max_chars=MAX_CHAT_MESSAGE_CHARS,
        required=True,
    )
    if "session_id" in normalized:
        normalized["session_id"] = bounded_text(
            normalized.get("session_id"),
            field_name="session_id",
            max_chars=MAX_CHAT_SESSION_ID_CHARS,
        )
    normalized["capability"] = bounded_text(
        payload.get("capability") or "chat",
        field_name="capability",
        max_chars=MAX_CHAT_LABEL_CHARS,
    ) or "chat"
    normalized["tools"] = bounded_string_list(payload.get("tools"), field_name="tools")
    normalized["knowledge_bases"] = bounded_string_list(
        payload.get("knowledge_bases"),
        field_name="knowledge_bases",
    )
    normalized["history_references"] = bounded_string_list(
        payload.get("history_references"),
        field_name="history_references",
        max_chars=MAX_CHAT_SESSION_ID_CHARS,
    )
    normalized["attachments"] = normalize_attachments(payload.get("attachments"))

    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    normalized["config"] = bounded_json(
        dict(config),
        field_name="config",
        max_chars=MAX_CHAT_CONFIG_JSON_CHARS,
    )
    notebook_references = payload.get("notebook_references") or []
    if not isinstance(notebook_references, list):
        raise ValueError("notebook_references must be a list")
    if len(notebook_references) > MAX_CHAT_LIST_ITEMS:
        raise ValueError(f"notebook_references cannot contain more than {MAX_CHAT_LIST_ITEMS} items")
    normalized["notebook_references"] = bounded_json(
        notebook_references,
        field_name="notebook_references",
        max_chars=MAX_CHAT_REFERENCES_JSON_CHARS,
    )
    return normalized
