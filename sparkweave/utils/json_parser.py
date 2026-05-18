"""Robust JSON parsing helpers for LLM responses."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

logger = logging.getLogger(__name__)

_UNSET = object()


def parse_json_response(
    response: str,
    logger_instance: logging.Logger | None = None,
    fallback: Any = _UNSET,
) -> Any:
    """Parse JSON from raw or markdown-wrapped LLM output."""
    log = logger_instance or logger
    if fallback is _UNSET:
        fallback = {}

    if not response or not response.strip():
        log.warning("LLM returned empty response")
        return fallback

    extracted_response = response.strip()
    if "```" in response:
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", response, re.DOTALL)
        if json_match:
            extracted_response = json_match.group(1).strip()
            log.debug("Extracted JSON from markdown code block")
        elif extracted_response.startswith("```"):
            # Some streaming/model responses start a JSON fence but omit the
            # closing fence. Treat the first line as markdown syntax and parse
            # the remaining body.
            extracted_response = "\n".join(extracted_response.splitlines()[1:]).strip()
            log.debug("Extracted JSON from unterminated markdown code block")

    try:
        return json.loads(extracted_response)
    except json.JSONDecodeError as parse_error:
        log.debug("Direct JSON parse failed: %s", parse_error)

    if repair_json is None:
        log.warning("json-repair library not installed, cannot repair malformed JSON")
        log.debug("Response: %s", extracted_response[:200])
        return fallback

    try:
        repaired = repair_json(extracted_response)
        result = json.loads(repaired)
        log.info("Successfully repaired malformed JSON")
        return result
    except Exception as repair_error:
        log.error("JSON repair failed: %s", repair_error)
        log.debug("Response: %s", extracted_response[:200])
        return fallback


def safe_json_loads(data: str, fallback: Any = _UNSET) -> Any:
    """Safely call ``json.loads`` with a default fallback."""
    if fallback is _UNSET:
        fallback = {}
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s", exc)
        return fallback


def _escape_triple_quoted_strings(text: str) -> str:
    """Convert Python triple-quoted string literals into JSON strings."""

    def replacer(match: re.Match[str]) -> str:
        return json.dumps(match.group(1))

    return re.sub(r'"""([\s\S]*?)"""', replacer, text)


def extract_json_from_text(text: str) -> dict[str, Any] | list[Any] | None:
    """Extract a JSON object or array from model output text."""
    if not text:
        return None

    sanitized = _escape_triple_quoted_strings(text)
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", sanitized)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    object_match = re.search(r"\{[\s\S]*\}", sanitized)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError:
            pass

    array_match = re.search(r"\[[\s\S]*\]", sanitized)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def clean_json_string(json_str: str) -> str:
    """Remove illegal JSON control characters from a string."""
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", json_str)


__all__ = [
    "clean_json_string",
    "extract_json_from_text",
    "parse_json_response",
    "safe_json_loads",
]
