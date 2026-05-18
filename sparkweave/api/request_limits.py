"""Shared request-size limits for learner-facing API payloads."""

from __future__ import annotations

import json
import re
from typing import Any

MAX_NOTEBOOK_ID_CHARS = 64
NOTEBOOK_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
MAX_NOTEBOOK_IDS = 20
MAX_NOTEBOOK_NAME_CHARS = 120
MAX_NOTEBOOK_DESCRIPTION_CHARS = 1_000
MAX_NOTEBOOK_COLOR_CHARS = 32
MAX_NOTEBOOK_ICON_CHARS = 64
MAX_NOTEBOOK_RECORD_TITLE_CHARS = 200
MAX_NOTEBOOK_RECORD_SUMMARY_CHARS = 2_000
MAX_NOTEBOOK_RECORD_QUERY_CHARS = 4_000
MAX_NOTEBOOK_RECORD_OUTPUT_CHARS = 100_000
MAX_NOTEBOOK_RECORD_METADATA_KEYS = 50
MAX_NOTEBOOK_RECORD_METADATA_JSON_CHARS = 20_000
MAX_NOTEBOOK_KB_NAME_CHARS = 180

MAX_QUIZ_RESULT_ITEMS = 100
MAX_QUIZ_SESSION_ID_CHARS = 160
MAX_QUIZ_QUESTION_ID_CHARS = 160
MAX_QUIZ_QUESTION_CHARS = 6_000
MAX_QUIZ_QUESTION_TYPE_CHARS = 80
MAX_QUIZ_OPTION_ITEMS = 20
MAX_QUIZ_OPTION_KEY_CHARS = 40
MAX_QUIZ_OPTION_VALUE_CHARS = 2_000
MAX_QUIZ_ANSWER_CHARS = 8_000
MAX_QUIZ_EXPLANATION_CHARS = 12_000
MAX_QUIZ_DIFFICULTY_CHARS = 80
MAX_QUIZ_LABEL_ITEMS = 30
MAX_QUIZ_LABEL_CHARS = 120
MAX_QUIZ_DURATION_SECONDS = 86_400
MAX_QUIZ_ATTEMPT_COUNT = 1_000

_LABEL_SPLIT_RE = re.compile(r"\s*(?:,|\uFF0C|\u3001|;|\uFF1B|\|)\s*")


def validate_notebook_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Reject metadata that cannot be stored as a bounded JSON object."""
    if value is None:
        return None
    try:
        encoded = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON serializable") from exc
    if len(encoded) > MAX_NOTEBOOK_RECORD_METADATA_JSON_CHARS:
        raise ValueError(
            f"metadata exceeds {MAX_NOTEBOOK_RECORD_METADATA_JSON_CHARS} characters when encoded"
        )
    return value


def coerce_limited_quiz_options(value: Any) -> dict[str, str]:
    """Normalize quiz options while keeping option maps small and renderable."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        return {}
    if len(value) > MAX_QUIZ_OPTION_ITEMS:
        raise ValueError(f"options cannot contain more than {MAX_QUIZ_OPTION_ITEMS} items")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        option = "" if raw_value is None else str(raw_value).strip()
        if not key:
            continue
        if len(key) > MAX_QUIZ_OPTION_KEY_CHARS:
            raise ValueError(f"option keys cannot exceed {MAX_QUIZ_OPTION_KEY_CHARS} characters")
        if len(option) > MAX_QUIZ_OPTION_VALUE_CHARS:
            raise ValueError(
                f"option values cannot exceed {MAX_QUIZ_OPTION_VALUE_CHARS} characters"
            )
        normalized[key] = option
    return normalized


def coerce_limited_quiz_labels(value: Any) -> list[str]:
    """Accept either a label list or a comma/semicolon separated label string."""
    if isinstance(value, list):
        labels = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        labels = [item.strip() for item in _LABEL_SPLIT_RE.split(value) if item.strip()]
    else:
        labels = []

    if len(labels) > MAX_QUIZ_LABEL_ITEMS:
        raise ValueError(f"labels cannot contain more than {MAX_QUIZ_LABEL_ITEMS} items")
    for label in labels:
        if len(label) > MAX_QUIZ_LABEL_CHARS:
            raise ValueError(f"labels cannot exceed {MAX_QUIZ_LABEL_CHARS} characters")
    return labels


def coerce_quiz_optional_text(value: Any) -> str:
    """Keep legacy behavior for nullable quiz text fields."""
    return value if isinstance(value, str) else ""


def strip_required_text(value: str, field_name: str) -> str:
    """Trim required user text and reject values that are only whitespace."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be blank")
    return stripped
