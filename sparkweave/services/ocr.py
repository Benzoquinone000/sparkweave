"""OCR providers used as an optional document parsing fallback."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

XFYUN_OCR_URL = "https://api.xf-yun.com/v1/private/sf8e6aca1"
XFYUN_OCR_SERVICE = "sf8e6aca1"
DEFAULT_MAX_PAGES = 20
DEFAULT_DPI = 180


class OcrUnavailable(RuntimeError):
    """Raised when an optional OCR provider is not configured or unavailable."""


@dataclass(frozen=True)
class XfyunOcrConfig:
    app_id: str
    api_key: str
    api_secret: str
    url: str = XFYUN_OCR_URL
    service_id: str = XFYUN_OCR_SERVICE
    category: str = "ch_en_public_cloud"
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "XfyunOcrConfig | None":
        provider = _env("SPARKWEAVE_OCR_PROVIDER", "iflytek").strip().lower()
        if provider and provider not in {"iflytek", "xunfei", "xfyun"}:
            return None

        app_id = _env("IFLYTEK_OCR_APPID") or _env("XFUN_OCR_APPID") or _env("XFYUN_OCR_APPID")
        api_key = (
            _env("IFLYTEK_OCR_API_KEY")
            or _env("IFLYTEK_OCR_APIKEY")
            or _env("XFUN_OCR_API_KEY")
            or _env("XFYUN_OCR_API_KEY")
        )
        api_secret = (
            _env("IFLYTEK_OCR_API_SECRET")
            or _env("IFLYTEK_OCR_APISECRET")
            or _env("XFUN_OCR_API_SECRET")
            or _env("XFYUN_OCR_API_SECRET")
        )
        if not (app_id and api_key and api_secret):
            return None

        timeout_raw = _env("SPARKWEAVE_OCR_TIMEOUT", "30").strip()
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = 30.0

        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=_env("IFLYTEK_OCR_URL", XFYUN_OCR_URL).strip() or XFYUN_OCR_URL,
            service_id=_env("IFLYTEK_OCR_SERVICE_ID", XFYUN_OCR_SERVICE).strip() or XFYUN_OCR_SERVICE,
            category=_env("IFLYTEK_OCR_CATEGORY", "ch_en_public_cloud").strip() or "ch_en_public_cloud",
            timeout=max(timeout, 1.0),
        )


def is_iflytek_ocr_configured() -> bool:
    return XfyunOcrConfig.from_env() is not None


def recognize_image_with_iflytek(image: bytes, *, encoding: str = "png", config: XfyunOcrConfig | None = None) -> str:
    """Recognize text in a single image using iFlytek OCR.

    The implementation targets the OCR Chinese/English WebAPI endpoint. It is
    intentionally dependency-free so the default parser can still run in lean
    installs.
    """

    resolved = config or XfyunOcrConfig.from_env()
    if resolved is None:
        raise OcrUnavailable("iFlytek OCR credentials are not configured")

    payload = _build_iflytek_payload(resolved, image, encoding=encoding)
    request = Request(
        _build_iflytek_auth_url(resolved),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=resolved.timeout) as response:  # noqa: S310 - endpoint is user-configured.
            response_text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise OcrUnavailable(f"iFlytek OCR request failed: {exc}") from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OcrUnavailable("iFlytek OCR returned non-JSON response") from exc

    header = data.get("header") if isinstance(data, dict) else {}
    if isinstance(header, dict) and int(header.get("code", -1)) != 0:
        raise OcrUnavailable(f"iFlytek OCR error: {header.get('message') or header.get('code')}")

    return extract_iflytek_text(data)


def extract_iflytek_text(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response, dict) else None
    if not isinstance(payload, dict):
        return ""

    result = payload.get("result")
    if not isinstance(result, dict):
        result = payload.get("recognizeDocumentRes")
    if not isinstance(result, dict):
        return ""

    encoded_text = result.get("text")
    if not isinstance(encoded_text, str) or not encoded_text:
        return ""

    decoded = base64.b64decode(encoded_text).decode("utf-8", errors="replace")
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return decoded.strip()
    return _extract_ocr_text(parsed).strip()


def ocr_pdf_with_iflytek(pdf_path: Path, *, max_pages: int | None = None, dpi: int | None = None) -> str:
    """Render a PDF to page images and OCR them with iFlyTek.

    Raises ``OcrUnavailable`` on any configuration, rendering, or network
    failure so callers can fall back to their default parser.
    """

    config = XfyunOcrConfig.from_env()
    if config is None:
        raise OcrUnavailable("iFlytek OCR credentials are not configured")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise OcrUnavailable("PyMuPDF is required to render PDF pages for OCR") from exc

    page_limit = max_pages if max_pages is not None else _env_int("SPARKWEAVE_OCR_MAX_PAGES", DEFAULT_MAX_PAGES)
    render_dpi = dpi if dpi is not None else _env_int("SPARKWEAVE_OCR_DPI", DEFAULT_DPI)
    texts: list[str] = []

    try:
        doc = fitz.open(pdf_path)
        try:
            for index, page in enumerate(doc):
                if page_limit > 0 and index >= page_limit:
                    break
                pixmap = page.get_pixmap(dpi=render_dpi, alpha=False)
                image_bytes = pixmap.tobytes("png")
                page_text = recognize_image_with_iflytek(image_bytes, encoding="png", config=config)
                if page_text.strip():
                    texts.append(f"## Page {index + 1}\n{page_text.strip()}")
        finally:
            doc.close()
    except OcrUnavailable:
        raise
    except Exception as exc:
        raise OcrUnavailable(f"Failed to OCR PDF with iFlytek: {exc}") from exc

    return "\n\n".join(texts).strip()


def _build_iflytek_payload(config: XfyunOcrConfig, image: bytes, *, encoding: str) -> dict[str, Any]:
    image_b64 = base64.b64encode(image).decode("ascii")
    if config.service_id == "hh_ocr_recognize_doc":
        return {
            "header": {"app_id": config.app_id, "status": 3},
            "parameter": {
                "hh_ocr_recognize_doc": {
                    "recognizeDocumentRes": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json",
                    }
                }
            },
            "payload": {
                "image": {
                    "encoding": encoding,
                    "image": image_b64,
                    "status": 3,
                }
            },
        }

    return {
        "header": {"app_id": config.app_id, "status": 3},
        "parameter": {
            config.service_id: {
                "category": config.category,
                "result": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "json",
                },
            }
        },
        "payload": {
            f"{config.service_id}_data_1": {
                "encoding": encoding,
                "status": 3,
                "image": image_b64,
            }
        },
    }


def _build_iflytek_auth_url(config: XfyunOcrConfig) -> str:
    parsed = urlparse(config.url)
    host = parsed.netloc
    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"
    date = formatdate(usegmt=True)
    request_line = f"POST {request_target} HTTP/1.1"
    signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
    signature_sha = hmac.new(
        config.api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("ascii")
    authorization_origin = (
        f'api_key="{config.api_key}",algorithm="hmac-sha256",'
        f'headers="host date request-line",signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
    query = urlencode({"authorization": authorization, "host": host, "date": date})
    separator = "&" if parsed.query else "?"
    return f"{config.url}{separator}{query}"


def _extract_ocr_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (_extract_ocr_text(item).strip() for item in value) if part)
    if not isinstance(value, dict):
        return ""

    whole_text = value.get("whole_text")
    if isinstance(whole_text, str) and whole_text.strip():
        return whole_text

    lines = value.get("lines")
    if isinstance(lines, list):
        parts: list[str] = []
        for line in lines:
            if not isinstance(line, dict):
                continue
            if isinstance(line.get("text"), str):
                parts.append(line["text"])
                continue
            words = line.get("words")
            if isinstance(words, list):
                word_text = "".join(str(word.get("content", "")) for word in words if isinstance(word, dict))
                if word_text:
                    parts.append(word_text)
        return "\n".join(parts)

    pages = value.get("pages")
    if isinstance(pages, list):
        return "\n\n".join(_extract_ocr_text(page) for page in pages)

    return ""


def _env_int(name: str, default: int) -> int:
    raw = _env(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", name, raw)
        return default
    return value if value > 0 else default


def _env(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


__all__ = [
    "OcrUnavailable",
    "XfyunOcrConfig",
    "extract_iflytek_text",
    "is_iflytek_ocr_configured",
    "ocr_pdf_with_iflytek",
    "recognize_image_with_iflytek",
]
