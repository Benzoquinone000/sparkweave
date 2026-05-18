"""Error formatting helpers."""

from __future__ import annotations

import json


def _find_json_block(message: str) -> str | None:
    start_idx = message.find("{")
    if start_idx == -1:
        return None

    brace_count = 0
    in_string = False
    escape_next = False

    for char_idx in range(start_idx, len(message)):
        char = message[char_idx]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                return message[start_idx : char_idx + 1]

    return None


def format_exception_message(exc: Exception) -> str:
    """Format API-style exception payloads into a compact message."""
    message = str(exc)
    potential_json = _find_json_block(message)
    if potential_json:
        try:
            error_data = json.loads(potential_json)
        except (json.JSONDecodeError, AttributeError):
            return message

        if isinstance(error_data, dict) and "error" in error_data:
            error_info = error_data["error"]
            if isinstance(error_info, dict):
                parts = []
                if "message" in error_info:
                    parts.append(f"Message: {error_info['message']}")
                if "type" in error_info:
                    parts.append(f"Type: {error_info['type']}")
                if "code" in error_info:
                    parts.append(f"Code: {error_info['code']}")
                if parts:
                    return " | ".join(parts)

    return message


__all__ = ["format_exception_message"]
