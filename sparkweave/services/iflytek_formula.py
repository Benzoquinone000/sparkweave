"""iFlytek formula recognition connector.

The API is useful for math-heavy learning flows where a screenshot or
handwritten formula should become structured evidence before the tutor answers.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_IFLYTEK_FORMULA_URL = "https://rest-api.xfyun.cn/v2/itr"
DEFAULT_IFLYTEK_FORMULA_ENT = "teach-photo-print"
DEFAULT_IFLYTEK_FORMULA_AUE = "raw"
DEFAULT_IFLYTEK_FORMULA_TIMEOUT = 30.0
MAX_FORMULA_IMAGE_BYTES = 10 * 1024 * 1024


class IflytekFormulaUnavailable(RuntimeError):
    """Raised when iFlytek formula recognition is not configured or fails."""


@dataclass(frozen=True)
class IflytekFormulaConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = DEFAULT_IFLYTEK_FORMULA_URL
    ent: str = DEFAULT_IFLYTEK_FORMULA_ENT
    aue: str = DEFAULT_IFLYTEK_FORMULA_AUE
    timeout: float = DEFAULT_IFLYTEK_FORMULA_TIMEOUT

    @property
    def provider(self) -> str:
        return "iflytek_formula"

    @classmethod
    def from_env(cls) -> "IflytekFormulaConfig | None":
        provider = _env("SPARKWEAVE_FORMULA_OCR_PROVIDER", "iflytek").strip().lower()
        if provider in {"disabled", "none", "off"}:
            return None
        if provider not in {"", "iflytek", "xunfei", "xfyun", "spark"}:
            return None

        app_id = _first_env("IFLYTEK_FORMULA_APPID", "IFLYTEK_OCR_APPID", "IFLYTEK_APPID")
        api_key = _first_env(
            "IFLYTEK_FORMULA_API_KEY",
            "IFLYTEK_OCR_API_KEY",
            "IFLYTEK_API_KEY",
        )
        api_secret = _first_env(
            "IFLYTEK_FORMULA_API_SECRET",
            "IFLYTEK_OCR_API_SECRET",
            "IFLYTEK_API_SECRET",
        )
        if not (app_id and api_key and api_secret):
            return None

        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=(_env("IFLYTEK_FORMULA_URL", DEFAULT_IFLYTEK_FORMULA_URL).strip())
            or DEFAULT_IFLYTEK_FORMULA_URL,
            ent=(_env("IFLYTEK_FORMULA_ENT", DEFAULT_IFLYTEK_FORMULA_ENT).strip())
            or DEFAULT_IFLYTEK_FORMULA_ENT,
            aue=(_env("IFLYTEK_FORMULA_AUE", DEFAULT_IFLYTEK_FORMULA_AUE).strip())
            or DEFAULT_IFLYTEK_FORMULA_AUE,
            timeout=max(_env_float("IFLYTEK_FORMULA_TIMEOUT", DEFAULT_IFLYTEK_FORMULA_TIMEOUT), 1.0),
        )


def is_iflytek_formula_configured() -> bool:
    return IflytekFormulaConfig.from_env() is not None


async def recognize_formula_image(
    image: bytes,
    *,
    config: IflytekFormulaConfig | None = None,
) -> dict[str, Any]:
    resolved = config or IflytekFormulaConfig.from_env()
    if resolved is None:
        raise IflytekFormulaUnavailable(
            "iFlytek formula recognition is not configured. Set IFLYTEK_FORMULA_APPID, "
            "IFLYTEK_FORMULA_API_KEY and IFLYTEK_FORMULA_API_SECRET, or shared IFLYTEK_* keys."
        )
    if not image:
        raise IflytekFormulaUnavailable("Formula recognition image is empty")
    if len(image) > MAX_FORMULA_IMAGE_BYTES:
        raise IflytekFormulaUnavailable("Formula recognition image exceeds 10 MB")

    payload = _build_formula_payload(resolved, image)
    response_text = await asyncio.to_thread(_post_formula, resolved, payload)
    parsed = parse_iflytek_formula_response(response_text)
    return {
        "success": True,
        "provider": resolved.provider,
        "model": resolved.ent,
        "text": parsed["text"],
        "regions": parsed["regions"],
        "raw": parsed["raw"],
        "sid": parsed.get("sid", ""),
    }


async def recognize_formula_image_with_fallback(
    image: bytes,
    *,
    config: IflytekFormulaConfig | None = None,
) -> dict[str, Any]:
    try:
        return await recognize_formula_image(image, config=config)
    except IflytekFormulaUnavailable as exc:
        from sparkweave.services.iflytek_offline import (
            offline_fallback_enabled,
            offline_formula_result,
        )

        if not offline_fallback_enabled():
            raise
        return offline_formula_result(image, reason=exc)


def parse_iflytek_formula_response(response_text: str) -> dict[str, Any]:
    try:
        raw = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise IflytekFormulaUnavailable("iFlytek formula recognition returned invalid JSON") from exc
    if not isinstance(raw, dict):
        raise IflytekFormulaUnavailable("iFlytek formula recognition returned non-object JSON")

    code = raw.get("code", 0)
    if code not in (0, "0", None):
        message = raw.get("message") or raw.get("desc") or "unknown error"
        raise IflytekFormulaUnavailable(f"iFlytek formula recognition error {code}: {message}")

    data = raw.get("data")
    regions = _extract_regions(data)
    text = _regions_to_text(regions)
    return {
        "text": text,
        "regions": regions,
        "raw": raw,
        "sid": raw.get("sid", ""),
    }


def decode_image_base64(value: str) -> bytes:
    raw = value.strip()
    if raw.startswith("data:"):
        _header, separator, data = raw.partition(",")
        if not separator:
            raise IflytekFormulaUnavailable("Invalid image data URI")
        raw = data
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IflytekFormulaUnavailable("Invalid base64 image") from exc


def _build_formula_payload(config: IflytekFormulaConfig, image: bytes) -> bytes:
    payload = {
        "common": {"app_id": config.app_id},
        "business": {"ent": config.ent, "aue": config.aue},
        "data": {"image": base64.b64encode(image).decode("ascii")},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _post_formula(config: IflytekFormulaConfig, payload: bytes) -> str:
    headers = _build_auth_headers(config, payload)
    request = Request(config.url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=config.timeout) as response:  # noqa: S310
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:  # pragma: no cover - network-specific branch
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:500] if body else str(exc)
        raise IflytekFormulaUnavailable(
            f"iFlytek formula recognition request failed: HTTP {exc.code}: {detail}"
        ) from exc
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise IflytekFormulaUnavailable(
            f"iFlytek formula recognition request failed: {exc}"
        ) from exc


def _build_auth_headers(config: IflytekFormulaConfig, payload: bytes) -> dict[str, str]:
    parsed = urlparse(config.url)
    host = parsed.netloc
    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"
    date = formatdate(usegmt=True)
    digest = "SHA-256=" + base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    request_line = f"POST {request_target} HTTP/1.1"
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}\ndigest: {digest}"
    signature = base64.b64encode(
        hmac.new(
            config.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("ascii")
    authorization_origin = (
        f'api_key="{config.api_key}",algorithm="hmac-sha256",'
        f'headers="host date request-line digest",signature="{signature}"'
    )
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Host": host,
        "Date": date,
        "Digest": digest,
        "Authorization": authorization_origin,
    }


def _extract_regions(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    region_value = data.get("region") or data.get("regions") or data.get("result")
    if isinstance(region_value, dict):
        for key in ("region", "regions", "list", "items"):
            nested = region_value.get(key)
            if isinstance(nested, list):
                region_value = nested
                break
    if not isinstance(region_value, list):
        return []

    regions: list[dict[str, Any]] = []
    for item in region_value:
        if not isinstance(item, dict):
            continue
        recognition = item.get("recog") if isinstance(item.get("recog"), dict) else {}
        content = (
            item.get("content")
            or item.get("text")
            or recognition.get("content")
            or recognition.get("text")
            or ""
        )
        region_type = item.get("type") or item.get("region_type") or recognition.get("type") or "formula"
        normalized = {
            "type": str(region_type),
            "content": _normalize_formula_text(str(content)),
        }
        confidence = item.get("confidence") or recognition.get("confidence")
        if confidence is not None:
            normalized["confidence"] = confidence
        coordinates = item.get("coord") or item.get("coordinates") or item.get("bbox")
        if coordinates is not None:
            normalized["coordinates"] = coordinates
        if normalized["content"]:
            regions.append(normalized)
    return regions


def _regions_to_text(regions: list[dict[str, Any]]) -> str:
    parts = [str(item.get("content") or "").strip() for item in regions]
    return "\n".join(part for part in parts if part).strip()


def _normalize_formula_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"ifly-latex-begin\s*", "$", text)
    text = re.sub(r"\s*ifly-latex-end", "$", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


__all__ = [
    "DEFAULT_IFLYTEK_FORMULA_AUE",
    "DEFAULT_IFLYTEK_FORMULA_ENT",
    "DEFAULT_IFLYTEK_FORMULA_URL",
    "IflytekFormulaConfig",
    "IflytekFormulaUnavailable",
    "decode_image_base64",
    "is_iflytek_formula_configured",
    "parse_iflytek_formula_response",
    "recognize_formula_image",
    "recognize_formula_image_with_fallback",
]
