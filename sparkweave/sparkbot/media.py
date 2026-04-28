"""Media helpers for NG SparkBot prompts and channels."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

MAX_INLINE_IMAGE_BYTES = 10 * 1024 * 1024


def detect_image_mime(data: bytes) -> str | None:
    """Detect a common image MIME type from magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _attachment_ref(attachment: dict[str, Any]) -> str:
    ref = (
        attachment.get("path")
        or attachment.get("file_path")
        or attachment.get("filePath")
        or attachment.get("url")
        or attachment.get("uri")
        or attachment.get("file")
        or ""
    )
    return str(ref).strip()


def _looks_like_image_ref(ref: str, *, attachment_type: str = "") -> bool:
    if ref.startswith("data:image/"):
        return True
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        suffix = Path(parsed.path).suffix.lower()
        return attachment_type == "image" or suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    suffix = Path(ref).suffix.lower()
    return attachment_type == "image" or suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _is_windows_drive_scheme(scheme: str) -> bool:
    return len(scheme) == 1 and scheme.isalpha()


def _resolve_local_ref(ref: str, workspace: Path) -> Path | None:
    parsed = urlparse(ref)
    if parsed.scheme == "file":
        raw_path = unquote(parsed.path or "")
        if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
            raw_path = raw_path[1:]
        candidate = Path(raw_path)
    elif parsed.scheme and not _is_windows_drive_scheme(parsed.scheme):
        return None
    else:
        candidate = Path(ref).expanduser()

    candidates = [candidate] if candidate.is_absolute() else [workspace / candidate, candidate]
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def _local_image_to_data_url(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_INLINE_IMAGE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    mime = detect_image_mime(data) or mimetypes.guess_type(path.name)[0]
    if not mime or not mime.startswith("image/"):
        return None
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _image_url_for_ref(ref: str, workspace: Path) -> str | None:
    if not ref:
        return None
    if ref.startswith("data:image/"):
        return ref
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        return ref
    if parsed.scheme and not _is_windows_drive_scheme(parsed.scheme) and parsed.scheme != "file":
        return None
    local_path = _resolve_local_ref(ref, workspace)
    if local_path is None:
        return None
    return _local_image_to_data_url(local_path)


def build_image_content_blocks(
    *,
    media: list[str] | None,
    attachments: list[dict[str, Any]] | None,
    workspace: Path,
) -> list[dict[str, Any]]:
    """Build OpenAI-compatible image content blocks for local or remote images."""
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(ref: str, *, attachment_type: str = "") -> None:
        if not ref or ref in seen or not _looks_like_image_ref(ref, attachment_type=attachment_type):
            return
        image_url = _image_url_for_ref(ref, workspace)
        if not image_url or image_url in seen:
            return
        seen.add(ref)
        seen.add(image_url)
        blocks.append({"type": "image_url", "image_url": {"url": image_url}})

    for ref in media or []:
        add(str(ref).strip())
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("type") or attachment.get("mime_type") or "").lower()
        add(_attachment_ref(attachment), attachment_type=attachment_type)
    return blocks


__all__ = [
    "MAX_INLINE_IMAGE_BYTES",
    "build_image_content_blocks",
    "detect_image_mime",
]
