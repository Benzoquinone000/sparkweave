"""OCR providers used as an optional document parsing fallback."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from email.utils import formatdate
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import struct
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
import zlib

logger = logging.getLogger(__name__)

XFYUN_OCR_URL = "https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm"
XFYUN_OCR_SERVICE = "se75ocrbm"
SILICONFLOW_OCR_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_DEEPSEEK_OCR_MODEL = "deepseek-ai/DeepSeek-OCR"
DEFAULT_SILICONFLOW_OCR_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."
DEFAULT_OCR_TIMEOUT = 90.0
# 0 means no page limit. Users should not have to tune page count for normal OCR.
DEFAULT_MAX_PAGES = 0
DEFAULT_DPI = 200
DEFAULT_SILICONFLOW_MAX_TOKENS = 8192


def _make_smoke_test_png() -> bytes:
    width = 340
    height = 96
    pixels = bytearray([255] * width * height * 3)

    def fill_rect(x: int, y: int, w: int, h: int, shade: int = 0) -> None:
        for row in range(max(y, 0), min(y + h, height)):
            start = (row * width + max(x, 0)) * 3
            end = (row * width + min(x + w, width)) * 3
            pixels[start:end] = bytes([shade]) * (end - start)

    glyphs = {
        "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
        "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
        "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    }

    fill_rect(0, 0, width, 4)
    fill_rect(0, height - 4, width, 4)
    fill_rect(0, 0, 4, height)
    fill_rect(width - 4, 0, 4, height)

    x = 24
    scale = 8
    for char in "OCR 123":
        if char == " ":
            x += scale * 3
            continue
        for row_index, row in enumerate(glyphs[char]):
            for col_index, bit in enumerate(row):
                if bit == "1":
                    fill_rect(x + col_index * scale, 20 + row_index * scale, scale, scale)
        x += scale * 7

    raw = bytearray()
    stride = width * 3
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row * stride : (row + 1) * stride])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
        + chunk(b"IEND", b"")
    )


OCR_SMOKE_TEST_PNG = _make_smoke_test_png()


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
    timeout: float = DEFAULT_OCR_TIMEOUT

    @property
    def provider(self) -> str:
        return "iflytek"

    @classmethod
    def from_env(cls) -> "XfyunOcrConfig | None":
        provider = _env("SPARKWEAVE_OCR_PROVIDER", "iflytek").strip().lower()
        if provider and provider not in {"iflytek", "xunfei", "xfyun"}:
            return None

        app_id = (
            _env("IFLYTEK_OCR_APPID")
            or _env("IFLYTEK_APPID")
            or _env("XFUN_OCR_APPID")
            or _env("XFYUN_OCR_APPID")
        )
        api_key = (
            _env("IFLYTEK_OCR_API_KEY")
            or _env("IFLYTEK_API_KEY")
            or _env("IFLYTEK_OCR_APIKEY")
            or _env("XFUN_OCR_API_KEY")
            or _env("XFYUN_OCR_API_KEY")
        )
        api_secret = (
            _env("IFLYTEK_OCR_API_SECRET")
            or _env("IFLYTEK_API_SECRET")
            or _env("IFLYTEK_OCR_APISECRET")
            or _env("XFUN_OCR_API_SECRET")
            or _env("XFYUN_OCR_API_SECRET")
        )
        if not (app_id and api_key and api_secret):
            return None

        timeout_raw = _env("SPARKWEAVE_OCR_TIMEOUT", str(int(DEFAULT_OCR_TIMEOUT))).strip()
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = DEFAULT_OCR_TIMEOUT

        return cls(
            app_id=app_id.strip(),
            api_key=api_key.strip(),
            api_secret=api_secret.strip(),
            url=_env("IFLYTEK_OCR_URL", XFYUN_OCR_URL).strip() or XFYUN_OCR_URL,
            service_id=_env("IFLYTEK_OCR_SERVICE_ID", XFYUN_OCR_SERVICE).strip() or XFYUN_OCR_SERVICE,
            category=_env("IFLYTEK_OCR_CATEGORY", "ch_en_public_cloud").strip() or "ch_en_public_cloud",
            timeout=max(timeout, 1.0),
        )


@dataclass(frozen=True)
class SiliconFlowOcrConfig:
    api_key: str
    base_url: str = SILICONFLOW_OCR_BASE_URL
    model: str = SILICONFLOW_DEEPSEEK_OCR_MODEL
    prompt: str = DEFAULT_SILICONFLOW_OCR_PROMPT
    timeout: float = DEFAULT_OCR_TIMEOUT
    max_tokens: int = DEFAULT_SILICONFLOW_MAX_TOKENS

    @property
    def provider(self) -> str:
        return "siliconflow"

    @property
    def url(self) -> str:
        return _siliconflow_chat_completions_url(self.base_url)

    @classmethod
    def from_env(cls) -> "SiliconFlowOcrConfig | None":
        provider = _normalize_ocr_provider(_env("SPARKWEAVE_OCR_PROVIDER", "iflytek"))
        if provider != "siliconflow":
            return None

        api_key = (
            _env("SILICONFLOW_OCR_API_KEY")
            or _env("SILICONFLOW_API_KEY")
            or _env("OPENAI_API_KEY")
        )
        if not api_key:
            return None

        timeout_raw = _env("SPARKWEAVE_OCR_TIMEOUT", str(int(DEFAULT_OCR_TIMEOUT))).strip()
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = DEFAULT_OCR_TIMEOUT

        return cls(
            api_key=api_key.strip(),
            base_url=(
                _env("SILICONFLOW_OCR_BASE_URL")
                or _env("SILICONFLOW_OCR_URL")
                or SILICONFLOW_OCR_BASE_URL
            ).strip()
            or SILICONFLOW_OCR_BASE_URL,
            model=(_env("SILICONFLOW_OCR_MODEL") or SILICONFLOW_DEEPSEEK_OCR_MODEL).strip()
            or SILICONFLOW_DEEPSEEK_OCR_MODEL,
            prompt=(_env("SILICONFLOW_OCR_PROMPT") or DEFAULT_SILICONFLOW_OCR_PROMPT).strip()
            or DEFAULT_SILICONFLOW_OCR_PROMPT,
            timeout=max(timeout, 1.0),
            max_tokens=_env_int("SILICONFLOW_OCR_MAX_TOKENS", DEFAULT_SILICONFLOW_MAX_TOKENS),
        )


OcrProviderConfig = XfyunOcrConfig | SiliconFlowOcrConfig


def resolve_ocr_config() -> OcrProviderConfig | None:
    provider = _normalize_ocr_provider(_env("SPARKWEAVE_OCR_PROVIDER", "iflytek"))
    if provider in {"disabled", "none", "off"}:
        return None
    if provider == "siliconflow":
        return SiliconFlowOcrConfig.from_env()
    return XfyunOcrConfig.from_env()


def is_iflytek_ocr_configured() -> bool:
    return XfyunOcrConfig.from_env() is not None


def is_ocr_configured() -> bool:
    return resolve_ocr_config() is not None


def recognize_image(
    image: bytes,
    *,
    encoding: str = "png",
    config: OcrProviderConfig | None = None,
) -> str:
    resolved = config or resolve_ocr_config()
    if resolved is None:
        raise OcrUnavailable("OCR credentials are not configured")
    if isinstance(resolved, SiliconFlowOcrConfig):
        return recognize_image_with_siliconflow(image, encoding=encoding, config=resolved)
    return recognize_image_with_iflytek(image, encoding=encoding, config=resolved)


def recognize_image_with_fallback(
    image: bytes,
    *,
    encoding: str = "png",
    config: OcrProviderConfig | None = None,
) -> str:
    try:
        return recognize_image(image, encoding=encoding, config=config)
    except OcrUnavailable as exc:
        from sparkweave.services.iflytek_offline import describe_image, offline_fallback_enabled

        if not offline_fallback_enabled():
            raise
        descriptor = describe_image(image, mime_type=f"image/{encoding}")
        size_text = (
            f"{descriptor.width}x{descriptor.height}"
            if descriptor.width and descriptor.height
            else f"{descriptor.bytes} bytes"
        )
        return (
            "离线 OCR 替补已启用：当前无法调用图片文字识别服务。"
            f"已接收 {descriptor.format} 图片（{size_text}）。"
            "请补充图片中的文字，或恢复讯飞/备用 OCR 服务后重新识别。"
            f"\n\n降级原因：{str(exc)[:300]}"
        )


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
    except HTTPError as exc:  # pragma: no cover - network-specific branch
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:500] if body else str(exc)
        raise OcrUnavailable(f"iFlytek OCR request failed: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise OcrUnavailable(f"iFlytek OCR request failed: {exc}") from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OcrUnavailable("iFlytek OCR returned non-JSON response") from exc

    header = data.get("header") if isinstance(data, dict) else {}
    if isinstance(header, dict) and int(header.get("code", -1)) != 0:
        raise OcrUnavailable(f"iFlytek OCR error: {header.get('message') or header.get('code')}")
    if isinstance(data, dict) and "code" in data and int(data.get("code", -1)) != 0:
        raise OcrUnavailable(f"iFlytek OCR error: {data.get('message') or data.get('code')}")

    try:
        return extract_iflytek_text(data)
    except ValueError as exc:
        raise OcrUnavailable(f"iFlytek OCR returned invalid payload: {exc}") from exc


def recognize_image_with_siliconflow(
    image: bytes,
    *,
    encoding: str = "png",
    config: SiliconFlowOcrConfig | None = None,
) -> str:
    """Recognize text in a single image using SiliconFlow DeepSeek-OCR."""

    resolved = config or SiliconFlowOcrConfig.from_env()
    if resolved is None:
        raise OcrUnavailable("SiliconFlow DeepSeek-OCR credentials are not configured")

    payload = _build_siliconflow_payload(resolved, image, encoding=encoding)
    request = Request(
        resolved.url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=resolved.timeout) as response:  # noqa: S310 - endpoint is user-configured.
            response_text = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:  # pragma: no cover - network-specific branch
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body[:500] if body else str(exc)
        raise OcrUnavailable(f"SiliconFlow DeepSeek-OCR request failed: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # pragma: no cover - network-specific branch
        raise OcrUnavailable(f"SiliconFlow DeepSeek-OCR request failed: {exc}") from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise OcrUnavailable("SiliconFlow DeepSeek-OCR returned non-JSON response") from exc

    if isinstance(data, dict) and data.get("error"):
        error = data.get("error")
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise OcrUnavailable(f"SiliconFlow DeepSeek-OCR error: {message}")

    return extract_siliconflow_text(data)


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

    try:
        decoded_bytes = base64.b64decode(encoded_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("response text is not valid base64") from exc
    decoded = decoded_bytes.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return decoded.strip()
    return _extract_ocr_text(parsed).strip()


def extract_siliconflow_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") if isinstance(response, dict) else None
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return _clean_deepseek_grounding(_strip_code_fence(content)).strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return _clean_deepseek_grounding(_strip_code_fence("\n".join(parts))).strip()
    return ""


def ocr_pdf(pdf_path: Path, *, max_pages: int | None = None, dpi: int | None = None) -> str:
    config = resolve_ocr_config()
    if config is None:
        raise OcrUnavailable("OCR credentials are not configured")
    if isinstance(config, SiliconFlowOcrConfig):
        return ocr_pdf_with_siliconflow(pdf_path, max_pages=max_pages, dpi=dpi, config=config)
    return ocr_pdf_with_iflytek(pdf_path, max_pages=max_pages, dpi=dpi)


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


def ocr_pdf_with_siliconflow(
    pdf_path: Path,
    *,
    max_pages: int | None = None,
    dpi: int | None = None,
    config: SiliconFlowOcrConfig | None = None,
) -> str:
    """Render a PDF to page images and OCR them with SiliconFlow DeepSeek-OCR."""

    resolved = config or SiliconFlowOcrConfig.from_env()
    if resolved is None:
        raise OcrUnavailable("SiliconFlow DeepSeek-OCR credentials are not configured")

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
                page_text = recognize_image_with_siliconflow(image_bytes, encoding="png", config=resolved)
                if page_text.strip():
                    texts.append(f"## Page {index + 1}\n{page_text.strip()}")
        finally:
            doc.close()
    except OcrUnavailable:
        raise
    except Exception as exc:
        raise OcrUnavailable(f"Failed to OCR PDF with SiliconFlow DeepSeek-OCR: {exc}") from exc

    return "\n\n".join(texts).strip()


def _build_siliconflow_payload(
    config: SiliconFlowOcrConfig,
    image: bytes,
    *,
    encoding: str,
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image).decode("ascii")
    content_type = _image_content_type(encoding)
    return {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{image_b64}", "detail": "high"},
                    },
                    {"type": "text", "text": config.prompt},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": max(1, config.max_tokens),
    }


def _build_iflytek_payload(config: XfyunOcrConfig, image: bytes, *, encoding: str) -> dict[str, Any]:
    image_b64 = base64.b64encode(image).decode("ascii")
    if config.service_id == XFYUN_OCR_SERVICE:
        return {
            "header": {
                "app_id": config.app_id,
                "status": 0,
            },
            "parameter": {
                "ocr": {
                    "result_option": "normal",
                    "result_format": "json",
                    "output_type": "one_shot",
                    "exif_option": "0",
                    "json_element_option": "",
                    "markdown_element_option": "watermark=0,page_header=0,page_footer=0,page_number=0,graph=0",
                    "sed_element_option": "watermark=0,page_header=0,page_footer=0,page_number=0,graph=0",
                    "alpha_option": "0",
                    "rotation_min_angle": 5,
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                }
            },
            "payload": {
                "image": {
                    "encoding": encoding,
                    "image": image_b64,
                    "status": 0,
                    "seq": 0,
                }
            },
        }

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


def _siliconflow_chat_completions_url(base_url: str) -> str:
    normalized = (base_url or SILICONFLOW_OCR_BASE_URL).strip().rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _image_content_type(encoding: str) -> str:
    normalized = (encoding or "png").strip().lower().lstrip(".")
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    if normalized in {"webp", "gif", "bmp", "png"}:
        return f"image/{normalized}"
    return "image/png"


def _normalize_ocr_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower().replace("-", "_")
    if normalized in {"siliconflow", "silicon_flow", "deepseekocr", "deepseek_ocr", "deepseek_ocr_vl"}:
        return "siliconflow"
    if normalized in {"iflytek", "xunfei", "xfyun", "spark"}:
        return "iflytek"
    if normalized in {"disabled", "none", "off"}:
        return "disabled"
    return normalized or "iflytek"


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _clean_deepseek_grounding(text: str) -> str:
    cleaned = re.sub(r"<\|ref\|>.*?<\|/ref\|>\s*", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"<\|det\|>.*?<\|/det\|>\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


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

    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return text
    if isinstance(text, list):
        return "\n".join(part for part in (_extract_ocr_text(item).strip() for item in text) if part)

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

    for key in ("document", "image", "content", "regions", "paragraphs", "blocks", "elements"):
        nested = value.get(key)
        if nested:
            nested_text = _extract_ocr_text(nested).strip()
            if nested_text:
                return nested_text

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
    process_value = os.getenv(name)
    if process_value not in (None, ""):
        return process_value
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


__all__ = [
    "OcrUnavailable",
    "OCR_SMOKE_TEST_PNG",
    "DEFAULT_SILICONFLOW_OCR_PROMPT",
    "SILICONFLOW_DEEPSEEK_OCR_MODEL",
    "SILICONFLOW_OCR_BASE_URL",
    "OcrProviderConfig",
    "SiliconFlowOcrConfig",
    "XfyunOcrConfig",
    "extract_iflytek_text",
    "extract_siliconflow_text",
    "is_iflytek_ocr_configured",
    "is_ocr_configured",
    "ocr_pdf",
    "ocr_pdf_with_iflytek",
    "ocr_pdf_with_siliconflow",
    "recognize_image",
    "recognize_image_with_fallback",
    "recognize_image_with_iflytek",
    "recognize_image_with_siliconflow",
    "resolve_ocr_config",
]
