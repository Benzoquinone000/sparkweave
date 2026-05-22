"""iFlytek Spark image understanding connector."""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
import json
import os
from typing import Any

import websockets

from sparkweave.services.iflytek_spark_ws import build_auth_url

DEFAULT_IFLYTEK_VISION_URL = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
DEFAULT_IFLYTEK_VISION_DOMAIN = "imagev3"
DEFAULT_IFLYTEK_VISION_PROTOCOL = "spark_image"
DEFAULT_IFLYTEK_VISION_TIMEOUT = 45.0
DEFAULT_IFLYTEK_VISION_TEMPERATURE = 0.2
DEFAULT_IFLYTEK_VISION_TOP_K = 4
DEFAULT_IFLYTEK_VISION_MAX_TOKENS = 2048
MAX_VISION_IMAGE_BYTES = 4 * 1024 * 1024


class IflytekVisionUnavailable(RuntimeError):
    """Raised when iFlytek image understanding is not configured or fails."""


@dataclass(frozen=True)
class IflytekVisionConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = DEFAULT_IFLYTEK_VISION_URL
    domain: str = DEFAULT_IFLYTEK_VISION_DOMAIN
    protocol: str = DEFAULT_IFLYTEK_VISION_PROTOCOL
    timeout: float = DEFAULT_IFLYTEK_VISION_TIMEOUT
    temperature: float = DEFAULT_IFLYTEK_VISION_TEMPERATURE
    top_k: int = DEFAULT_IFLYTEK_VISION_TOP_K
    max_tokens: int = DEFAULT_IFLYTEK_VISION_MAX_TOKENS
    uid: str = "sparkweave"

    @property
    def provider(self) -> str:
        return "iflytek_image_understanding"

    @classmethod
    def from_env(cls) -> "IflytekVisionConfig | None":
        provider = _env("SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER", "iflytek").strip().lower()
        if provider in {"disabled", "none", "off"}:
            return None
        if provider not in {"", "iflytek", "xunfei", "xfyun", "spark"}:
            return None

        app_id = _first_env("IFLYTEK_VISION_APPID", "IFLYTEK_APPID")
        api_key = _first_env("IFLYTEK_VISION_API_KEY", "IFLYTEK_API_KEY")
        api_secret = _first_env("IFLYTEK_VISION_API_SECRET", "IFLYTEK_API_SECRET")
        if not (app_id and api_key and api_secret):
            return None

        protocol = (
            _env("IFLYTEK_VISION_PROTOCOL", DEFAULT_IFLYTEK_VISION_PROTOCOL).strip().lower()
            or DEFAULT_IFLYTEK_VISION_PROTOCOL
        )
        if protocol not in {"spark_image", "maas_vl"}:
            protocol = DEFAULT_IFLYTEK_VISION_PROTOCOL

        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=(_env("IFLYTEK_VISION_URL", DEFAULT_IFLYTEK_VISION_URL).strip())
            or DEFAULT_IFLYTEK_VISION_URL,
            domain=(_env("IFLYTEK_VISION_DOMAIN", DEFAULT_IFLYTEK_VISION_DOMAIN).strip())
            or DEFAULT_IFLYTEK_VISION_DOMAIN,
            protocol=protocol,
            timeout=max(_env_float("IFLYTEK_VISION_TIMEOUT", DEFAULT_IFLYTEK_VISION_TIMEOUT), 1.0),
            temperature=_env_float(
                "IFLYTEK_VISION_TEMPERATURE",
                DEFAULT_IFLYTEK_VISION_TEMPERATURE,
            ),
            top_k=_env_int("IFLYTEK_VISION_TOP_K", DEFAULT_IFLYTEK_VISION_TOP_K),
            max_tokens=_env_int("IFLYTEK_VISION_MAX_TOKENS", DEFAULT_IFLYTEK_VISION_MAX_TOKENS),
            uid=(_env("IFLYTEK_VISION_UID", "sparkweave").strip() or "sparkweave"),
        )


def is_iflytek_vision_configured() -> bool:
    return IflytekVisionConfig.from_env() is not None


async def understand_image(
    image: bytes,
    *,
    prompt: str,
    mime_type: str = "image/png",
    config: IflytekVisionConfig | None = None,
) -> dict[str, Any]:
    resolved = config or IflytekVisionConfig.from_env()
    if resolved is None:
        raise IflytekVisionUnavailable(
            "iFlytek image understanding is not configured. Set IFLYTEK_VISION_APPID, "
            "IFLYTEK_VISION_API_KEY and IFLYTEK_VISION_API_SECRET, or shared IFLYTEK_* keys."
        )
    if not image:
        raise IflytekVisionUnavailable("Image understanding input is empty")
    if len(image) > MAX_VISION_IMAGE_BYTES:
        raise IflytekVisionUnavailable("Image understanding input exceeds 4 MB")

    question = prompt.strip() or "请描述这张图片，并指出其中与学习任务相关的信息。"
    payload = build_vision_payload(
        resolved,
        image=image,
        prompt=question,
        mime_type=mime_type,
    )
    parsed = await _run_ws(resolved, payload)
    return {
        "success": True,
        "provider": resolved.provider,
        "model": resolved.domain,
        "protocol": resolved.protocol,
        "content": parsed["content"],
        "usage": parsed.get("usage", {}),
        "events": parsed.get("events", []),
        "sid": parsed.get("sid", ""),
    }


async def understand_image_with_fallback(
    image: bytes,
    *,
    prompt: str,
    mime_type: str = "image/png",
    config: IflytekVisionConfig | None = None,
) -> dict[str, Any]:
    try:
        return await understand_image(image, prompt=prompt, mime_type=mime_type, config=config)
    except IflytekVisionUnavailable as exc:
        from sparkweave.services.iflytek_offline import (
            offline_fallback_enabled,
            offline_image_understanding_result,
        )

        if not offline_fallback_enabled():
            raise
        return offline_image_understanding_result(
            image,
            prompt=prompt,
            mime_type=mime_type,
            reason=exc,
        )


def build_vision_payload(
    config: IflytekVisionConfig,
    *,
    image: bytes,
    prompt: str,
    mime_type: str = "image/png",
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image).decode("ascii")
    chat = {
        "domain": config.domain,
        "temperature": config.temperature,
        "top_k": config.top_k,
        "max_tokens": config.max_tokens,
    }
    if config.protocol == "maas_vl":
        message_text: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
    else:
        message_text = [
            {"role": "user", "content": image_b64, "content_type": "image"},
            {"role": "user", "content": prompt, "content_type": "text"},
        ]

    return {
        "header": {"app_id": config.app_id, "uid": config.uid},
        "parameter": {"chat": chat},
        "payload": {"message": {"text": message_text}},
    }


def extract_vision_delta(data: dict[str, Any]) -> tuple[str, bool, dict[str, Any], str]:
    header = data.get("header") if isinstance(data, dict) else None
    if isinstance(header, dict):
        code = int(header.get("code", 0) or 0)
        if code != 0:
            raise IflytekVisionUnavailable(
                "iFlytek image understanding returned error: "
                f"code={header.get('code')}, message={header.get('message')}, sid={header.get('sid')}"
            )

    content = _extract_content_from_openai_shape(data)
    usage: dict[str, Any] = {}
    payload = data.get("payload") if isinstance(data, dict) else None
    choices = (payload or {}).get("choices") if isinstance(payload, dict) else None
    if isinstance(choices, dict):
        text = choices.get("text")
        if isinstance(text, list):
            content += "".join(str(item.get("content") or "") for item in text if isinstance(item, dict))
        usage_value = (payload or {}).get("usage") if isinstance(payload, dict) else None
        if isinstance(usage_value, dict):
            usage = usage_value.get("text") if isinstance(usage_value.get("text"), dict) else usage_value

    status = None
    sid = ""
    if isinstance(header, dict):
        status = header.get("status")
        sid = str(header.get("sid") or "")
    if status is None and isinstance(choices, dict):
        status = choices.get("status")
    done = int(status or 0) == 2
    return content, done, usage, sid


def decode_image_base64(value: str) -> tuple[bytes, str]:
    raw = value.strip()
    mime_type = "image/png"
    if raw.startswith("data:"):
        header, separator, data = raw.partition(",")
        if not separator:
            raise IflytekVisionUnavailable("Invalid image data URI")
        if ";base64" not in header.lower():
            raise IflytekVisionUnavailable("Image data URI must be base64 encoded")
        detected = header[5:].split(";", 1)[0].strip().lower()
        if detected:
            mime_type = detected
        raw = data
    try:
        return base64.b64decode(raw, validate=True), mime_type
    except (binascii.Error, ValueError) as exc:
        raise IflytekVisionUnavailable("Invalid base64 image") from exc


async def _run_ws(config: IflytekVisionConfig, payload: dict[str, Any]) -> dict[str, Any]:
    auth_url = build_auth_url(config.url, api_key=config.api_key, api_secret=config.api_secret)
    events: list[dict[str, Any]] = []
    content_parts: list[str] = []
    usage: dict[str, Any] = {}
    sid = ""

    try:
        async with asyncio.timeout(config.timeout):
            async with websockets.connect(auth_url, open_timeout=min(config.timeout, 20), close_timeout=5) as ws:
                await ws.send(json.dumps(payload, ensure_ascii=False))
                async for raw in ws:
                    data = _loads_ws_json(raw)
                    events.append(data)
                    delta, done, event_usage, event_sid = extract_vision_delta(data)
                    if delta:
                        content_parts.append(delta)
                    if event_usage:
                        usage = event_usage
                    if event_sid:
                        sid = event_sid
                    if done:
                        break
    except TimeoutError as exc:
        raise IflytekVisionUnavailable("iFlytek image understanding request timed out") from exc
    except IflytekVisionUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise IflytekVisionUnavailable(f"iFlytek image understanding request failed: {exc}") from exc

    content = "".join(content_parts).strip()
    if not events:
        raise IflytekVisionUnavailable("iFlytek image understanding returned no events")
    return {"content": content, "usage": usage, "events": events, "sid": sid}


def _extract_content_from_openai_shape(data: dict[str, Any]) -> str:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list):
        return ""
    parts: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        for key in ("delta", "message"):
            value = choice.get(key)
            if isinstance(value, dict) and isinstance(value.get("content"), str):
                parts.append(value["content"])
    return "".join(parts)


def _loads_ws_json(value: Any) -> dict[str, Any]:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    try:
        data = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise IflytekVisionUnavailable("iFlytek image understanding returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise IflytekVisionUnavailable("iFlytek image understanding returned non-object JSON")
    return data


def _env(name: str, default: str = "") -> str:
    process_value = os.getenv(name)
    if process_value not in (None, ""):
        return process_value
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
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


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


__all__ = [
    "DEFAULT_IFLYTEK_VISION_DOMAIN",
    "DEFAULT_IFLYTEK_VISION_PROTOCOL",
    "DEFAULT_IFLYTEK_VISION_URL",
    "IflytekVisionConfig",
    "IflytekVisionUnavailable",
    "build_vision_payload",
    "decode_image_base64",
    "extract_vision_delta",
    "is_iflytek_vision_configured",
    "understand_image",
    "understand_image_with_fallback",
]
