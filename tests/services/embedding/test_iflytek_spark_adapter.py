from __future__ import annotations

import base64
import struct

import httpx
import pytest

from sparkweave.services.embedding_support.adapters.base import EmbeddingRequest
from sparkweave.services.embedding_support.adapters.iflytek_spark import (
    IflytekSparkEmbeddingAdapter,
)


def _encoded_vector(values: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode("ascii")


def test_iflytek_spark_extracts_float32_embedding() -> None:
    adapter = IflytekSparkEmbeddingAdapter(
        {
            "api_key": "api-key",
            "base_url": "https://emb-cn-huabei-1.xf-yun.com/",
            "model": "llm-embedding",
            "dimensions": 3,
            "extra_headers": {"app_id": "appid", "api_secret": "secret"},
        }
    )
    embedding = adapter._extract_embedding(
        {
            "header": {"code": 0, "message": "success"},
            "payload": {"feature": {"text": _encoded_vector([0.25, -1.5, 3.0])}},
        }
    )
    assert embedding == pytest.approx([0.25, -1.5, 3.0])


def test_iflytek_spark_maps_query_and_document_domains() -> None:
    adapter = IflytekSparkEmbeddingAdapter(
        {
            "api_key": "api-key",
            "base_url": "https://emb-cn-huabei-1.xf-yun.com/",
            "model": "llm-embedding",
            "dimensions": 2560,
            "extra_headers": {"app_id": "appid", "api_secret": "secret"},
        }
    )
    assert adapter._domain(EmbeddingRequest(texts=["q"], model="llm-embedding", input_type="search_query")) == "query"
    assert adapter._domain(EmbeddingRequest(texts=["d"], model="llm-embedding", input_type="search_document")) == "para"


@pytest.mark.asyncio
async def test_iflytek_spark_requires_signed_credentials() -> None:
    adapter = IflytekSparkEmbeddingAdapter(
        {
            "api_key": "api-key",
            "base_url": "https://emb-cn-huabei-1.xf-yun.com/",
            "model": "llm-embedding",
            "dimensions": 2560,
            "extra_headers": {"app_id": "appid"},
        }
    )
    with pytest.raises(ValueError, match="app_id, api_key and api_secret"):
        await adapter.embed(EmbeddingRequest(texts=["hello"], model="llm-embedding"))


def test_iflytek_spark_formats_license_error() -> None:
    response = httpx.Response(
        500,
        json={"header": {"code": 11202, "message": "licc failed", "sid": "emb-test"}},
        request=httpx.Request("POST", "https://emb-cn-huabei-1.xf-yun.com/"),
    )

    message = IflytekSparkEmbeddingAdapter._format_http_error(response)

    assert "licc failed" in message
    assert "code=11202" in message
    assert "未通过 Embedding 服务许可校验" in message
