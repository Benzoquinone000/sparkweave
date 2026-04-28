from __future__ import annotations

import pytest

from sparkweave.services.vision_input import (
    ImageError,
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
    assert guess_image_type_from_url("https://example.test/image.webp?x=1") == "image/webp"


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

