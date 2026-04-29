"""iFlytek ONE SEARCH provider."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from ..base import BaseSearchProvider
from ..types import Citation, SearchResult, WebSearchResponse
from . import register_provider


@register_provider("iflytek_spark")
class IflytekSparkSearchProvider(BaseSearchProvider):
    """iFlytek ONE SEARCH API provider."""

    display_name = "iFlytek ONE SEARCH"
    description = "iFlytek Spark ONE SEARCH API"
    supports_answer = False
    requires_api_key = True
    BASE_URL = "https://search-api-open.cn-huabei-1.xf-yun.com/v2/search"
    API_KEY_ENV_VARS = (
        "IFLYTEK_SEARCH_API_PASSWORD",
        "IFLYTEK_SPARK_SEARCH_API_PASSWORD",
        "XFYUN_SEARCH_API_PASSWORD",
        "IFLYTEK_SEARCH_APIPASSWORD",
        "SEARCH_API_KEY",
    )

    def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 30,
        open_full_text: bool = True,
        open_rerank: bool = True,
        **kwargs: Any,
    ) -> WebSearchResponse:
        """Search with iFlytek ONE SEARCH and return normalized results."""
        url = str(kwargs.get("base_url") or self.config.get("base_url") or self.BASE_URL).strip()
        limit = max(1, min(int(max_results), 20))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "search_params": {
                "query": query,
                "limit": limit,
                "enhance": {
                    "open_full_text": bool(open_full_text),
                    "open_rerank": bool(open_rerank),
                },
            }
        }
        request_kwargs: dict[str, Any] = {
            "headers": headers,
            "json": payload,
            "timeout": timeout,
        }
        if self.proxy:
            request_kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}

        response = requests.post(url, **request_kwargs)
        if response.status_code != 200:
            raise Exception(f"iFlytek ONE SEARCH API error: {response.status_code} - {response.text}")

        data = response.json()
        if data.get("success") is False or str(data.get("err_code", "0")) != "0":
            message = data.get("message") or response.text
            raise Exception(
                "iFlytek ONE SEARCH API error: "
                f"{data.get('err_code', response.status_code)} - {message}"
            )

        documents = (
            ((data.get("data") or {}).get("search_results") or {}).get("documents") or []
        )
        citations: list[Citation] = []
        search_results: list[SearchResult] = []
        for idx, document in enumerate(documents, 1):
            if not isinstance(document, dict):
                continue
            title = str(document.get("name") or document.get("title") or "")
            url_value = str(document.get("url") or "")
            snippet = str(document.get("summary") or "")
            content = str(document.get("content") or "")
            date = str(document.get("published_date") or document.get("date") or "")
            search_results.append(
                SearchResult(
                    title=title,
                    url=url_value,
                    snippet=snippet,
                    content=content,
                    date=date,
                    source="iFlytek ONE SEARCH",
                )
            )
            citations.append(
                Citation(
                    id=idx,
                    reference=f"[{idx}]",
                    url=url_value,
                    title=title,
                    snippet=snippet,
                    content=content,
                    date=date,
                    source="iFlytek ONE SEARCH",
                )
            )

        return WebSearchResponse(
            query=str(((data.get("data") or {}).get("meta") or {}).get("query") or query),
            answer="",
            provider="iflytek_spark",
            timestamp=datetime.now().isoformat(),
            model="one-search",
            citations=citations,
            search_results=search_results,
            metadata={
                "finish_reason": "stop",
                "sid": data.get("sid", ""),
                "err_code": data.get("err_code", "0"),
            },
        )
