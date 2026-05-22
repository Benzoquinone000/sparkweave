"""iFlytek Xingchen workflow connector.

This service lets SparkWeave call workflows published from iFlytek Xingchen
Agent / workflow tooling as a normal learning tool.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DEFAULT_IFLYTEK_WORKFLOW_URL = "https://xingchen-api.xf-yun.com/workflow/v1/chat/completions"
DEFAULT_WORKFLOW_TIMEOUT = 60.0
DEFAULT_INPUT_KEY = "AGENT_USER_INPUT"


class IflytekWorkflowUnavailable(RuntimeError):
    """Raised when iFlytek Workflow is not configured or fails."""


@dataclass(frozen=True)
class IflytekWorkflowConfig:
    api_key: str
    api_secret: str
    flow_id: str
    url: str = DEFAULT_IFLYTEK_WORKFLOW_URL
    input_key: str = DEFAULT_INPUT_KEY
    timeout: float = DEFAULT_WORKFLOW_TIMEOUT
    uid: str = "sparkweave"

    @classmethod
    def from_env(cls) -> "IflytekWorkflowConfig | None":
        api_key = _first_env("IFLYTEK_WORKFLOW_API_KEY", "IFLYTEK_AGENT_API_KEY", "IFLYTEK_API_KEY")
        api_secret = _first_env(
            "IFLYTEK_WORKFLOW_API_SECRET",
            "IFLYTEK_AGENT_API_SECRET",
            "IFLYTEK_API_SECRET",
        )
        flow_id = _first_env("IFLYTEK_WORKFLOW_FLOW_ID", "IFLYTEK_AGENT_FLOW_ID")
        if not (api_key and api_secret and flow_id):
            return None
        return cls(
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            flow_id=flow_id.strip(),
            url=(_env("IFLYTEK_WORKFLOW_URL", DEFAULT_IFLYTEK_WORKFLOW_URL).strip() or DEFAULT_IFLYTEK_WORKFLOW_URL),
            input_key=(_env("IFLYTEK_WORKFLOW_INPUT_KEY", DEFAULT_INPUT_KEY).strip() or DEFAULT_INPUT_KEY),
            timeout=max(_env_float("IFLYTEK_WORKFLOW_TIMEOUT", DEFAULT_WORKFLOW_TIMEOUT), 1.0),
            uid=(_env("IFLYTEK_WORKFLOW_UID", "sparkweave").strip() or "sparkweave"),
        )


def is_iflytek_workflow_configured() -> bool:
    return IflytekWorkflowConfig.from_env() is not None


async def call_iflytek_workflow(
    prompt: str,
    *,
    config: IflytekWorkflowConfig | None = None,
    flow_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_key: str | None = None,
    uid: str | None = None,
    chat_id: str | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """Call an iFlytek Xingchen workflow and return normalized text + trace."""

    resolved = config or IflytekWorkflowConfig.from_env()
    if resolved is None:
        raise IflytekWorkflowUnavailable(
            "iFlytek workflow is not configured. Set IFLYTEK_WORKFLOW_API_KEY, "
            "IFLYTEK_WORKFLOW_API_SECRET and IFLYTEK_WORKFLOW_FLOW_ID."
        )

    payload = _build_workflow_payload(
        resolved,
        prompt,
        flow_id=flow_id,
        parameters=parameters,
        input_key=input_key,
        uid=uid,
        chat_id=chat_id,
        stream=stream,
    )
    response_text = await asyncio.to_thread(_post_workflow, resolved, payload)
    parsed = parse_iflytek_workflow_response(response_text)
    return {
        "success": bool(parsed.get("success", True)),
        "provider": "iflytek_workflow",
        "flow_id": payload["flow_id"],
        "content": str(parsed.get("content") or "").strip(),
        "raw": parsed.get("raw"),
        "events": parsed.get("events", []),
        "usage": parsed.get("usage", {}),
        "request": {
            "stream": bool(stream),
            "parameter_keys": sorted(str(key) for key in payload.get("parameters", {}).keys()),
            "uid": payload.get("uid", ""),
            "has_chat_id": bool(payload.get("chat_id")),
        },
    }


async def call_iflytek_workflow_with_fallback(
    prompt: str,
    *,
    config: IflytekWorkflowConfig | None = None,
    flow_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_key: str | None = None,
    uid: str | None = None,
    chat_id: str | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    try:
        return await call_iflytek_workflow(
            prompt,
            config=config,
            flow_id=flow_id,
            parameters=parameters,
            input_key=input_key,
            uid=uid,
            chat_id=chat_id,
            stream=stream,
        )
    except IflytekWorkflowUnavailable as exc:
        from sparkweave.services.iflytek_offline import (
            offline_fallback_enabled,
            offline_workflow_result,
        )

        if not offline_fallback_enabled():
            raise
        resolved_flow_id = flow_id or (config.flow_id if config else "")
        return offline_workflow_result(
            prompt,
            flow_id=resolved_flow_id,
            parameters=parameters,
            reason=exc,
        )


def parse_iflytek_workflow_response(response_text: str) -> dict[str, Any]:
    """Normalize JSON or SSE-style workflow responses into text and events."""

    text = response_text.strip()
    if not text:
        raise IflytekWorkflowUnavailable("iFlytek workflow returned an empty response")

    if text.startswith("{"):
        raw = _loads_json(text)
        _raise_if_provider_error(raw)
        return {
            "success": True,
            "content": _extract_content(raw),
            "raw": raw,
            "usage": raw.get("usage") if isinstance(raw, dict) and isinstance(raw.get("usage"), dict) else {},
            "events": [],
        }

    events: list[dict[str, Any]] = []
    content_parts: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped[5:].strip()
        if not data or data == "[DONE]":
            continue
        raw = _loads_json(data)
        _raise_if_provider_error(raw)
        events.append(raw)
        content = _extract_content(raw)
        if content:
            content_parts.append(content)
    if not events:
        raise IflytekWorkflowUnavailable("iFlytek workflow returned an unsupported response")
    return {
        "success": True,
        "content": "".join(content_parts).strip(),
        "raw": events[-1],
        "events": events,
        "usage": events[-1].get("usage") if isinstance(events[-1].get("usage"), dict) else {},
    }


def _post_workflow(config: IflytekWorkflowConfig, payload: dict[str, Any]) -> str:
    request = Request(
        config.url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}:{config.api_secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.timeout) as response:  # noqa: S310 - endpoint is user-configured.
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:  # pragma: no cover - network-specific branch
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:500] if body else str(exc)
        raise IflytekWorkflowUnavailable(f"iFlytek workflow request failed: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise IflytekWorkflowUnavailable(f"iFlytek workflow request failed: {exc}") from exc


def _build_workflow_payload(
    config: IflytekWorkflowConfig,
    prompt: str,
    *,
    flow_id: str | None,
    parameters: dict[str, Any] | None,
    input_key: str | None,
    uid: str | None,
    chat_id: str | None,
    stream: bool,
) -> dict[str, Any]:
    prompt_text = prompt.strip()
    params = dict(parameters or {})
    key = (input_key or config.input_key or DEFAULT_INPUT_KEY).strip() or DEFAULT_INPUT_KEY
    if prompt_text and not params.get(key):
        params[key] = prompt_text
    if not params:
        raise IflytekWorkflowUnavailable("iFlytek workflow requires prompt text or parameters")

    payload: dict[str, Any] = {
        "flow_id": (flow_id or config.flow_id).strip(),
        "uid": (uid or config.uid).strip() or "sparkweave",
        "parameters": params,
        "stream": bool(stream),
    }
    if chat_id:
        payload["chat_id"] = chat_id.strip()
    if not payload["flow_id"]:
        raise IflytekWorkflowUnavailable("iFlytek workflow flow_id is empty")
    return payload


def _extract_content(raw: Any) -> str:
    if not isinstance(raw, dict):
        return ""
    candidates = [
        raw.get("content"),
        raw.get("answer"),
        raw.get("output"),
        raw.get("response"),
        raw.get("text"),
    ]
    data = raw.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("content"),
                data.get("answer"),
                data.get("output"),
                data.get("response"),
                data.get("text"),
            ]
        )
    choices = raw.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            delta = choice.get("delta")
            if isinstance(message, dict):
                candidates.append(message.get("content"))
            if isinstance(delta, dict):
                candidates.append(delta.get("content"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return ""


def _raise_if_provider_error(raw: Any) -> None:
    if not isinstance(raw, dict):
        return
    code = raw.get("code")
    header = raw.get("header")
    if isinstance(header, dict):
        code = header.get("code", code)
    if code in (None, 0, "0"):
        return
    message = raw.get("message") or raw.get("error") or raw.get("desc")
    if isinstance(header, dict):
        message = header.get("message") or message
    raise IflytekWorkflowUnavailable(f"iFlytek workflow error {code}: {message or 'unknown error'}")


def _loads_json(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise IflytekWorkflowUnavailable("iFlytek workflow returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise IflytekWorkflowUnavailable("iFlytek workflow returned non-object JSON")
    return data


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _first_env(*names: str) -> str:
    for name in names:
        value = _env(name).strip()
        if value:
            return value
    return ""


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


__all__ = [
    "DEFAULT_IFLYTEK_WORKFLOW_URL",
    "IflytekWorkflowConfig",
    "IflytekWorkflowUnavailable",
    "call_iflytek_workflow",
    "call_iflytek_workflow_with_fallback",
    "is_iflytek_workflow_configured",
    "parse_iflytek_workflow_response",
]
