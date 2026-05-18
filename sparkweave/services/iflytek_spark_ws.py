"""Native iFlytek Spark WebSocket LLM client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from email.utils import formatdate
from typing import Any, AsyncGenerator
from urllib.parse import urlencode, urlparse

import websockets


DEFAULT_IFLYTEK_WS_MODEL = "spark-x2"

DEFAULT_REQUEST_BY_MODEL = {
    "spark-x": ("spark-x", "wss://spark-api.xf-yun.com/x2"),
    "spark-x2": ("spark-x", "wss://spark-api.xf-yun.com/x2"),
    "spark_x2": ("spark-x", "wss://spark-api.xf-yun.com/x2"),
    "x2": ("spark-x", "wss://spark-api.xf-yun.com/x2"),
    "spark-x1.5": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
    "spark_x1_5": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
    "spark-x15": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
    "x1.5": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
    "x1_5": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
    "x15": ("spark-x", "wss://spark-api.xf-yun.com/v1/x1"),
}


def build_auth_url(base_url: str, *, api_key: str, api_secret: str) -> str:
    """Build iFlytek WebSocket HMAC authentication URL."""
    parsed = urlparse(base_url)
    host = parsed.netloc
    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"
    date = formatdate(usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {request_target} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("ascii")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    separator = "&" if parsed.query else "?"
    return f"{base_url}{separator}{query}"


def resolve_ws_base_url(model: str, base_url: str | None) -> str:
    return resolve_ws_request(model=model, base_url=base_url)[1]


def resolve_ws_request(
    *,
    model: str,
    base_url: str | None,
    domain_override: str = "",
) -> tuple[str, str]:
    """Resolve request domain and WebSocket URL for Spark model labels."""
    value = (base_url or "").strip()
    key = (model or DEFAULT_IFLYTEK_WS_MODEL).strip().lower()
    domain, default_url = DEFAULT_REQUEST_BY_MODEL.get(
        key, DEFAULT_REQUEST_BY_MODEL[DEFAULT_IFLYTEK_WS_MODEL]
    )
    override_key = (domain_override or "").strip().lower()
    if override_key in DEFAULT_REQUEST_BY_MODEL:
        domain = DEFAULT_REQUEST_BY_MODEL[override_key][0]
        domain_override = ""
    elif domain_override and domain_override != "spark-x":
        domain_override = ""
    if value.startswith("ws://") or value.startswith("wss://"):
        value_lower = value.lower()
        if "/x2" in value_lower or "/v1/x1" in value_lower:
            return domain_override or domain, value
    return domain_override or domain, default_url


def build_payload(
    *,
    app_id: str,
    domain: str,
    messages: list[dict[str, object]],
    temperature: float,
    max_tokens: int,
    top_k: int | None = None,
    top_p: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    chat_id: str = "",
    thinking_type: str = "",
    web_search: bool = False,
    search_mode: str = "normal",
) -> dict[str, Any]:
    chat: dict[str, Any] = {
        "domain": domain,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if top_k is not None:
        chat["top_k"] = top_k
    if top_p is not None:
        chat["top_p"] = top_p
    if presence_penalty is not None:
        chat["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        chat["frequency_penalty"] = frequency_penalty
    if chat_id:
        chat["chat_id"] = chat_id
    if thinking_type in {"enabled", "disabled", "auto"}:
        chat["thinking"] = {"type": thinking_type}
    if web_search:
        chat["tools"] = [
            {
                "type": "web_search",
                "web_search": {
                    "enable": True,
                    "search_mode": search_mode if search_mode in {"normal", "deep"} else "normal",
                },
            }
        ]
    return {
        "header": {"app_id": app_id, "uid": "sparkweave"},
        "parameter": {"chat": chat},
        "payload": {"message": {"text": normalize_messages(messages)}},
    }


def normalize_messages(messages: list[dict[str, object]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in messages:
        role = str(item.get("role") or "user")
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = item.get("content", "")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or part.get("content") or "")
                if isinstance(part, dict)
                else str(part)
                for part in content
            )
        normalized.append({"role": role, "content": str(content)})
    return normalized


def _setting(extra_headers: dict[str, str], *names: str) -> str:
    lowered = {str(k).lower().replace("-", "_"): str(v).strip() for k, v in extra_headers.items()}
    for name in names:
        value = lowered.get(name.lower().replace("-", "_"), "")
        if value:
            return value
    return ""


def _extract_delta(data: dict[str, Any]) -> tuple[str, bool]:
    header = data.get("header") if isinstance(data, dict) else None
    if isinstance(header, dict):
        code = int(header.get("code", 0) or 0)
        if code != 0:
            raise ValueError(
                "iFlytek Spark WebSocket returned error: "
                f"code={header.get('code')}, message={header.get('message')}, sid={header.get('sid')}"
            )
    payload = data.get("payload") if isinstance(data, dict) else None
    choices = (payload or {}).get("choices") if isinstance(payload, dict) else None
    text = choices.get("text") if isinstance(choices, dict) else None
    content = ""
    if isinstance(text, list):
        content = "".join(str(item.get("content") or "") for item in text if isinstance(item, dict))
    status = None
    if isinstance(header, dict):
        status = header.get("status")
    if status is None and isinstance(choices, dict):
        status = choices.get("status")
    return content, int(status or 0) == 2


async def ws_stream(
    *,
    prompt: str,
    system_prompt: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
    messages: list[dict[str, object]] | None,
    extra_headers: dict[str, str],
    kwargs: dict[str, object],
    **_: object,
) -> AsyncGenerator[str, None]:
    app_id = _setting(extra_headers, "app_id", "appid", "x_app_id", "iflytek_app_id")
    api_secret = _setting(extra_headers, "api_secret", "x_api_secret", "iflytek_api_secret")
    resolved_key = (api_key or _setting(extra_headers, "api_key", "x_api_key", "iflytek_api_key")).strip()
    if not app_id or not api_secret or not resolved_key:
        raise ValueError(
            "iFlytek Spark WebSocket requires app_id, api_key and api_secret. "
            "Set IFLYTEK_SPARK_WS_APPID, IFLYTEK_SPARK_WS_API_KEY/LLM_API_KEY, "
            "and IFLYTEK_SPARK_WS_API_SECRET."
        )

    domain_override = _setting(extra_headers, "domain", "iflytek_domain")
    domain, resolved_url = resolve_ws_request(
        model=model or DEFAULT_IFLYTEK_WS_MODEL,
        base_url=base_url,
        domain_override=domain_override,
    )
    auth_url = build_auth_url(resolved_url, api_key=resolved_key, api_secret=api_secret)
    request_messages = messages or [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    max_tokens = int(kwargs.pop("max_tokens", kwargs.pop("max_completion_tokens", 4096)) or 4096)
    temperature = float(kwargs.pop("temperature", 0.5) or 0.5)
    top_k_raw = kwargs.pop("top_k", None)
    top_k = int(top_k_raw) if top_k_raw is not None else None
    top_p = _optional_float(kwargs.pop("top_p", None))
    presence_penalty = _optional_float(kwargs.pop("presence_penalty", None))
    frequency_penalty = _optional_float(kwargs.pop("frequency_penalty", None))
    chat_id = str(kwargs.pop("chat_id", "") or _setting(extra_headers, "chat_id"))
    thinking_type = str(
        kwargs.pop("thinking", "")
        or kwargs.pop("thinking_type", "")
        or _setting(extra_headers, "thinking", "thinking_type")
    ).strip().lower()
    web_search = _truthy(kwargs.pop("web_search", "") or _setting(extra_headers, "web_search"))
    search_mode = str(kwargs.pop("search_mode", "") or _setting(extra_headers, "search_mode") or "normal").strip()
    payload = build_payload(
        app_id=app_id,
        domain=domain,
        messages=request_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_k=top_k,
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        chat_id=chat_id,
        thinking_type=thinking_type,
        web_search=web_search,
        search_mode=search_mode,
    )

    async with websockets.connect(auth_url, open_timeout=20, close_timeout=5) as ws:
        await ws.send(json.dumps(payload, ensure_ascii=False))
        async for raw in ws:
            data = json.loads(raw)
            delta, done = _extract_delta(data)
            if delta:
                yield delta
            if done:
                break


async def ws_complete(**kwargs: object) -> str:
    chunks: list[str] = []
    async for chunk in ws_stream(**kwargs):  # type: ignore[arg-type]
        chunks.append(chunk)
    return "".join(chunks)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}
