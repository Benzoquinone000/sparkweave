"""Image input normalization for NG vision workflows."""

from __future__ import annotations

import base64
from urllib.parse import urlparse

import httpx

from sparkweave.logging import get_logger

logger = get_logger("vision_input")

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
REQUEST_TIMEOUT = 30


class ImageError(Exception):
    """Raised when an image input cannot be used by the vision pipeline."""


def is_valid_image_url(url: str) -> bool:
    """Return whether ``url`` looks like an HTTP image URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_base64_image(data: str) -> bool:
    """Return whether ``data`` is a data-URI base64 image."""
    return data.startswith("data:image/") and ";base64," in data


def guess_image_type_from_url(url: str) -> str:
    """Infer a MIME type from the URL path when headers are ambiguous."""
    url_lower = url.lower()
    if ".png" in url_lower:
        return "image/png"
    if ".jpg" in url_lower or ".jpeg" in url_lower:
        return "image/jpeg"
    if ".gif" in url_lower:
        return "image/gif"
    if ".webp" in url_lower:
        return "image/webp"
    return "image/jpeg"


async def fetch_image_from_url(url: str) -> tuple[bytes, str]:
    """Download an image URL and return its bytes plus MIME type."""
    if not is_valid_image_url(url):
        raise ImageError(f"Invalid image URL: {url}")

    logger.info("Fetching image from URL: %s...", url[:100])

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if not content_type or content_type == "application/octet-stream":
                content_type = guess_image_type_from_url(url)

            if content_type not in SUPPORTED_IMAGE_TYPES:
                raise ImageError(f"Unsupported image format: {content_type}")

            content = response.content
            if len(content) > MAX_IMAGE_SIZE:
                raise ImageError(
                    f"Image too large: {len(content) / 1024 / 1024:.1f}MB "
                    f"(max {MAX_IMAGE_SIZE / 1024 / 1024:.0f}MB)"
                )

            logger.info("Image fetched successfully: %s bytes, type: %s", len(content), content_type)
            return content, content_type

    except httpx.HTTPStatusError as exc:
        raise ImageError(f"Failed to download image: HTTP {exc.response.status_code}") from exc
    except httpx.TimeoutException as exc:
        raise ImageError(f"Image download timeout ({REQUEST_TIMEOUT}s)") from exc
    except httpx.RequestError as exc:
        raise ImageError(f"Failed to download image: {exc!s}") from exc


def image_bytes_to_base64(content: bytes, mime_type: str) -> str:
    """Convert image bytes to a data-URI base64 image."""
    b64_data = base64.b64encode(content).decode("utf-8")
    logger.debug(
        "image_bytes_to_base64: input=%s bytes, output=%s chars",
        len(content),
        len(b64_data),
    )
    return f"data:{mime_type};base64,{b64_data}"


async def url_to_base64(url: str) -> str:
    """Download and convert an image URL into a data-URI base64 image."""
    content, mime_type = await fetch_image_from_url(url)
    return image_bytes_to_base64(content, mime_type)


async def resolve_image_input(
    image_base64: str | None = None,
    image_url: str | None = None,
) -> str | None:
    """Resolve base64-or-URL image input into a data-URI base64 image."""
    logger.debug(
        "resolve_image_input: base64=%s, url=%s",
        "yes" if image_base64 else "no",
        image_url or "none",
    )

    if image_base64:
        if is_base64_image(image_base64):
            logger.debug("Using provided base64 image")
            return image_base64
        logger.error("Invalid base64 image format")
        raise ImageError("Invalid base64 image format, should be data:image/...;base64,...")

    if image_url:
        logger.debug("Downloading image from URL")
        result = await url_to_base64(image_url)
        logger.debug("Download complete, base64 length: %s", len(result))
        return result

    logger.debug("No image provided")
    return None


__all__ = [
    "ImageError",
    "fetch_image_from_url",
    "guess_image_type_from_url",
    "image_bytes_to_base64",
    "is_base64_image",
    "is_valid_image_url",
    "resolve_image_input",
    "url_to_base64",
]

