"""Image input normalization for NG vision workflows."""

from __future__ import annotations

import base64
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

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
MAX_REDIRECTS = 5
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "host.docker.internal"}


class ImageError(Exception):
    """Raised when an image input cannot be used by the vision pipeline."""


def _is_blocked_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _url_validation_error(url: str, *, resolve_dns: bool = False) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return "URL could not be parsed"

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "URL must use http/https and include a host"
    if parsed.username or parsed.password:
        return "URL credentials are not allowed"

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return "URL is missing host"
    if host in BLOCKED_HOSTNAMES or host.endswith(".local"):
        return "local hosts are not allowed"
    if _is_blocked_address(host):
        return "private, local, or reserved IP addresses are not allowed"

    if resolve_dns:
        try:
            addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            return f"host could not be resolved: {exc}"
        for address in {item[4][0] for item in addresses}:
            if _is_blocked_address(address):
                return "host resolves to a private, local, or reserved IP address"

    return ""


def is_valid_image_url(url: str) -> bool:
    """Return whether ``url`` looks like an HTTP image URL."""
    return not _url_validation_error(url, resolve_dns=False)


def is_base64_image(data: str) -> bool:
    """Return whether ``data`` is a data-URI base64 image."""
    return _base64_image_validation_error(data) == ""


def _base64_image_validation_error(data: str) -> str:
    if not data.startswith("data:image/") or ";base64," not in data:
        return "Invalid base64 image format, should be data:image/...;base64,..."

    header, _, encoded = data.partition(",")
    mime_type = header[5:].split(";", 1)[0].strip().lower()
    if mime_type not in SUPPORTED_IMAGE_TYPES:
        return f"Unsupported image format: {mime_type or 'unknown'}"
    if not encoded:
        return "Base64 image payload is empty"

    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception:
        return "Base64 image payload is invalid"
    if len(decoded) > MAX_IMAGE_SIZE:
        return (
            f"Image too large: {len(decoded) / 1024 / 1024:.1f}MB "
            f"(max {MAX_IMAGE_SIZE / 1024 / 1024:.0f}MB)"
        )
    return ""


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
    current_url = url
    logger.info("Fetching image from URL: %s...", current_url[:100])

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            response: httpx.Response | None = None
            for _ in range(MAX_REDIRECTS + 1):
                validation_error = _url_validation_error(current_url, resolve_dns=True)
                if validation_error:
                    raise ImageError(f"Invalid image URL: {validation_error}")

                response = await client.get(current_url)
                if not response.is_redirect:
                    break
                location = response.headers.get("location", "").strip()
                if not location:
                    raise ImageError("Image URL redirected without a Location header")
                current_url = urljoin(str(response.url), location)
            else:
                raise ImageError(f"Image URL redirected more than {MAX_REDIRECTS} times")

            if response is None:
                raise ImageError("Image download failed before receiving a response")

            response.raise_for_status()

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if not content_type or content_type == "application/octet-stream":
                content_type = guess_image_type_from_url(str(response.url))

            if content_type not in SUPPORTED_IMAGE_TYPES:
                raise ImageError(f"Unsupported image format: {content_type}")

            content_length = response.headers.get("content-length")
            try:
                declared_size = int(content_length) if content_length else 0
            except ValueError:
                declared_size = 0
            if declared_size > MAX_IMAGE_SIZE:
                raise ImageError(
                    f"Image too large: {declared_size / 1024 / 1024:.1f}MB "
                    f"(max {MAX_IMAGE_SIZE / 1024 / 1024:.0f}MB)"
                )

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
        base64_error = _base64_image_validation_error(image_base64)
        if not base64_error:
            logger.debug("Using provided base64 image")
            return image_base64
        logger.error("Invalid base64 image: %s", base64_error)
        raise ImageError(base64_error)

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

