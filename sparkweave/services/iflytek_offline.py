"""Offline fallbacks for iFlytek-powered learning features.

These helpers keep demos usable when iFlytek credentials, network access, or
specific product entitlements are unavailable. They are intentionally honest:
offline fallbacks mark themselves as fallback results and avoid pretending that
real OCR/vision recognition happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import math
import os
import struct
from typing import Any
import wave

OFFLINE_FALLBACK_ENV = "SPARKWEAVE_IFLYTEK_OFFLINE_FALLBACK"
OFFLINE_PROVIDER_PREFIX = "offline_iflytek_fallback"


def offline_fallback_enabled() -> bool:
    value = _env(OFFLINE_FALLBACK_ENV, "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def fallback_reason_text(reason: object | None) -> str:
    from sparkweave.services.diagnostics import redact_sensitive_text

    text = redact_sensitive_text(reason).strip()
    if not text:
        return "iFlytek service is unavailable"
    return text[:500]


def offline_formula_result(image: bytes, *, reason: object | None = None) -> dict[str, Any]:
    descriptor = describe_image(image)
    message = (
        "离线公式识别替补已启用：当前没有调用科大讯飞公式识别服务。"
        "请让学习者补充公式文本，或在网络/密钥恢复后重新识别。"
    )
    return {
        "success": True,
        "provider": f"{OFFLINE_PROVIDER_PREFIX}:formula_ocr",
        "model": "offline-heuristic",
        "fallback": True,
        "fallback_reason": fallback_reason_text(reason),
        "text": message,
        "regions": [
            {
                "type": "fallback_notice",
                "content": message,
                "confidence": 0.0,
            }
        ],
        "raw": {"offline": True, "image": descriptor.as_dict()},
        "sid": f"offline-formula-{descriptor.digest}",
    }


def offline_image_understanding_result(
    image: bytes,
    *,
    prompt: str = "",
    mime_type: str = "image/png",
    reason: object | None = None,
) -> dict[str, Any]:
    descriptor = describe_image(image, mime_type=mime_type)
    prompt_text = prompt.strip() or "描述图片中的学习信息"
    size_text = (
        f"{descriptor.width}x{descriptor.height}"
        if descriptor.width and descriptor.height
        else f"{descriptor.bytes} bytes"
    )
    content = (
        "离线图片理解替补已启用。"
        f"已接收 {descriptor.format} 图片（{size_text}），但未进行真实视觉识别。"
        f"当前任务：{prompt_text}。"
        "系统会继续把图片作为学习证据占位，建议补充题干文字或恢复讯飞图片理解后重试。"
    )
    return {
        "success": True,
        "provider": f"{OFFLINE_PROVIDER_PREFIX}:image_understanding",
        "model": "offline-image-summary",
        "protocol": "offline",
        "fallback": True,
        "fallback_reason": fallback_reason_text(reason),
        "content": content,
        "usage": {"offline": True},
        "events": [{"type": "offline_fallback", "image": descriptor.as_dict()}],
        "sid": f"offline-image-{descriptor.digest}",
    }


def offline_workflow_result(
    prompt: str,
    *,
    flow_id: str = "",
    parameters: dict[str, Any] | None = None,
    reason: object | None = None,
) -> dict[str, Any]:
    prompt_text = prompt.strip()
    parameter_keys = sorted(str(key) for key in (parameters or {}).keys())
    focus = prompt_text or "当前学习任务"
    content = (
        "离线星辰工作流替补已启用。"
        f"我会按本地规则继续处理：1. 明确目标；2. 拆分学习步骤；3. 生成可执行资源；4. 给出下一步检查。"
        f"任务：{focus[:240]}"
    )
    return {
        "success": True,
        "provider": f"{OFFLINE_PROVIDER_PREFIX}:workflow",
        "flow_id": flow_id or "offline-workflow",
        "fallback": True,
        "fallback_reason": fallback_reason_text(reason),
        "content": content,
        "raw": {"offline": True, "parameter_keys": parameter_keys},
        "events": [{"type": "offline_fallback", "parameter_keys": parameter_keys}],
        "usage": {"offline": True},
        "request": {
            "stream": False,
            "parameter_keys": parameter_keys,
            "uid": "sparkweave-offline",
            "has_chat_id": False,
        },
    }


def offline_transcription_text(audio: bytes, *, audio_encoding: str = "", reason: object | None = None) -> str:
    descriptor = audio_descriptor(audio, audio_encoding=audio_encoding)
    configured_text = _env("SPARKWEAVE_OFFLINE_ASR_TEXT", "").strip()
    if configured_text:
        return configured_text
    return (
        "离线语音识别替补已启用：已接收音频"
        f"（{descriptor['bytes']} bytes，{descriptor['encoding']}），"
        "但无法在本地可靠转写真实语音。请在文本框补充口述内容后继续学习。"
    )


def offline_speech_eval_result(audio: bytes, *, reference_text: str) -> dict[str, Any]:
    text_len = len(reference_text.strip())
    audio_len = len(audio or b"")
    expected = max(1_600, text_len * 350)
    ratio = min(audio_len / expected, 1.35)
    fluency = max(55.0, min(92.0, 58.0 + ratio * 22.0))
    integrity = max(50.0, min(95.0, 62.0 + min(text_len, 120) / 4.0))
    accuracy = max(55.0, min(90.0, (fluency + integrity) / 2.0 - 2.0))
    total = round((accuracy * 0.45) + (fluency * 0.3) + (integrity * 0.25), 2)
    return {
        "overall_score": total,
        "normalized_score": round(total / 100, 4),
        "dimensions": {
            "accuracy": round(accuracy, 2),
            "fluency": round(fluency, 2),
            "integrity": round(integrity, 2),
            "offline_confidence": 0.35,
        },
        "raw_text": (
            "<offline_speech_eval provider=\"offline\" "
            f"audio_bytes=\"{audio_len}\" reference_chars=\"{text_len}\" />"
        ),
    }


def make_offline_tts_audio(text: str, *, sample_rate: int = 16_000) -> bytes:
    content = (text or "").strip()
    duration = min(2.4, max(0.55, 0.35 + len(content) / 55.0))
    frames = int(sample_rate * duration)
    digest = int(sha256(content.encode("utf-8")).hexdigest()[:4], 16)
    base_frequency = 420 + (digest % 180)
    amplitude = 8_000

    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frames):
            envelope = min(1.0, index / max(1, sample_rate * 0.05), (frames - index) / max(1, sample_rate * 0.08))
            tone = math.sin(2.0 * math.pi * base_frequency * (index / sample_rate))
            sample = int(amplitude * envelope * tone)
            wav.writeframesraw(struct.pack("<h", sample))
    return buffer.getvalue()


def audio_descriptor(audio: bytes, *, audio_encoding: str = "") -> dict[str, Any]:
    digest = sha256(audio or b"").hexdigest()[:12]
    encoding = (audio_encoding or "unknown").strip() or "unknown"
    return {"bytes": len(audio or b""), "digest": digest, "encoding": encoding}


@dataclass(frozen=True)
class ImageDescriptor:
    bytes: int
    digest: str
    format: str
    width: int | None = None
    height: int | None = None
    mime_type: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "bytes": self.bytes,
            "digest": self.digest,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "mime_type": self.mime_type,
        }


def describe_image(image: bytes, *, mime_type: str = "") -> ImageDescriptor:
    raw = image or b""
    digest = sha256(raw).hexdigest()[:12]
    image_format, width, height = _detect_image_shape(raw)
    return ImageDescriptor(
        bytes=len(raw),
        digest=digest,
        format=image_format or _format_from_mime(mime_type) or "image",
        width=width,
        height=height,
        mime_type=mime_type,
    )


def _detect_image_shape(raw: bytes) -> tuple[str, int | None, int | None]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        return "png", int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    if raw.startswith((b"GIF87a", b"GIF89a")) and len(raw) >= 10:
        return "gif", int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp", None, None
    if raw.startswith(b"\xff\xd8"):
        width, height = _jpeg_shape(raw)
        return "jpeg", width, height
    return "", None, None


def _jpeg_shape(raw: bytes) -> tuple[int | None, int | None]:
    index = 2
    while index + 9 < len(raw):
        if raw[index] != 0xFF:
            index += 1
            continue
        marker = raw[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(raw):
            break
        size = int.from_bytes(raw[index : index + 2], "big")
        if size < 2:
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 <= len(raw):
                height = int.from_bytes(raw[index + 3 : index + 5], "big")
                width = int.from_bytes(raw[index + 5 : index + 7], "big")
                return width, height
            break
        index += size
    return None, None


def _format_from_mime(mime_type: str) -> str:
    value = mime_type.strip().lower()
    if "/" not in value:
        return ""
    return value.rsplit("/", 1)[-1].replace("jpg", "jpeg")


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
    "OFFLINE_FALLBACK_ENV",
    "audio_descriptor",
    "describe_image",
    "fallback_reason_text",
    "make_offline_tts_audio",
    "offline_fallback_enabled",
    "offline_formula_result",
    "offline_image_understanding_result",
    "offline_speech_eval_result",
    "offline_transcription_text",
    "offline_workflow_result",
]
