from __future__ import annotations

import pytest

import sparkweave.services.vision_input as vision_input
from sparkweave.services.vision_input import (
    ImageError,
    fetch_image_from_url,
    guess_image_type_from_url,
    image_bytes_to_base64,
    is_base64_image,
    is_valid_image_url,
    resolve_image_input,
)


def test_vision_input_helpers_validate_image_sources():
    data_url = image_bytes_to_base64(b"abc", "image/png")

    assert data_url == "data:image/png;base64,YWJj"
    assert is_base64_image(data_url)
    assert is_valid_image_url("https://example.test/image.png")
    assert not is_valid_image_url("file:///tmp/image.png")
    assert not is_valid_image_url("http://localhost/image.png")
    assert not is_valid_image_url("http://127.0.0.1/image.png")
    assert not is_valid_image_url("http://169.254.169.254/latest/meta-data")
    assert not is_valid_image_url("http://[::1]/image.png")
    assert not is_valid_image_url("https://user:pass@example.test/image.png")
    assert guess_image_type_from_url("https://example.test/image.webp?x=1") == "image/webp"


def test_base64_image_validation_rejects_unsupported_or_invalid_payloads():
    assert not is_base64_image("data:image/svg+xml;base64,PHN2Zy8+")
    assert not is_base64_image("data:image/png;base64,not valid base64")


@pytest.mark.asyncio
async def test_resolve_image_input_prefers_valid_base64():
    data_url = "data:image/png;base64,YWJj"

    assert await resolve_image_input(image_base64=data_url, image_url="https://example.test/a.png")
    assert await resolve_image_input(image_base64=data_url, image_url=None) == data_url


@pytest.mark.asyncio
async def test_resolve_image_input_rejects_invalid_base64():
    with pytest.raises(ImageError, match="Invalid base64 image format"):
        await resolve_image_input(image_base64="YWJj")


@pytest.mark.asyncio
async def test_resolve_image_input_downloads_url(monkeypatch):
    async def fake_url_to_base64(url: str) -> str:
        assert url == "https://example.test/image.png"
        return "data:image/png;base64,YWJj"

    monkeypatch.setattr("sparkweave.services.vision_input.url_to_base64", fake_url_to_base64)

    assert await resolve_image_input(image_url="https://example.test/image.png") == (
        "data:image/png;base64,YWJj"
    )


@pytest.mark.asyncio
async def test_fetch_image_rejects_hosts_that_resolve_to_private_ips(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        return [(None, None, None, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(vision_input.socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ImageError, match="host resolves to a private"):
        await fetch_image_from_url("https://example.test/image.png")

