from __future__ import annotations

import pytest

from sparkweave.services.search_support.providers.iflytek_spark import (
    IflytekSparkSearchProvider,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


def test_iflytek_spark_search_posts_official_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _FakeResponse(
            200,
            {
                "success": True,
                "err_code": "0",
                "sid": "sid-1",
                "data": {
                    "meta": {"query": "美国现任总统是谁"},
                    "search_results": {
                        "documents": [
                            {
                                "name": "Result title",
                                "summary": "Result summary",
                                "content": "Full content",
                                "url": "https://example.com/a",
                                "published_date": "2026年04月29日",
                            }
                        ]
                    },
                },
            },
        )

    monkeypatch.setattr(
        "sparkweave.services.search_support.providers.iflytek_spark.requests.post",
        fake_post,
    )

    provider = IflytekSparkSearchProvider(api_key="api-password")
    result = provider.search("美国现任总统是谁", max_results=30, open_full_text=False)

    assert captured["url"] == "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"
    kwargs = captured["kwargs"]
    assert kwargs["headers"]["Authorization"] == "Bearer api-password"
    assert kwargs["json"]["search_params"]["query"] == "美国现任总统是谁"
    assert kwargs["json"]["search_params"]["limit"] == 20
    assert kwargs["json"]["search_params"]["enhance"]["open_full_text"] is False
    assert kwargs["json"]["search_params"]["enhance"]["open_rerank"] is True
    assert result.provider == "iflytek_spark"
    assert result.query == "美国现任总统是谁"
    assert result.search_results[0].title == "Result title"
    assert result.search_results[0].content == "Full content"
    assert result.citations[0].source == "iFlytek ONE SEARCH"
    assert result.metadata["sid"] == "sid-1"


def test_iflytek_spark_search_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs):
        return _FakeResponse(
            200,
            {"success": False, "err_code": "11200", "message": "unauthorized"},
        )

    monkeypatch.setattr(
        "sparkweave.services.search_support.providers.iflytek_spark.requests.post",
        fake_post,
    )

    provider = IflytekSparkSearchProvider(api_key="api-password")
    with pytest.raises(Exception, match="11200"):
        provider.search("query")
