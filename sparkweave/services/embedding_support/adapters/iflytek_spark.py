"""iFlytek Spark llm embedding adapter."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import struct
from email.utils import formatdate
from typing import Any, Dict
from urllib.parse import urlencode, urlparse

import httpx

from .base import BaseEmbeddingAdapter, EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)


class IflytekSparkEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for iFlytek's signed llm embedding protocol."""

    DEFAULT_MODEL = "llm-embedding"
    DEFAULT_DIMENSIONS = 2560

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        app_id = self._setting("app_id", "appid", "x-app-id", "iflytek_app_id")
        api_secret = self._setting("api_secret", "x-api-secret", "iflytek_api_secret")
        api_key = self.api_key or self._setting("api_key", "x-api-key", "iflytek_api_key")
        if not app_id or not api_key or not api_secret:
            raise ValueError(
                "iFlytek Spark Embedding requires app_id, api_key and api_secret. "
                "Set IFLYTEK_EMBEDDING_APPID, EMBEDDING_API_KEY/IFLYTEK_EMBEDDING_API_KEY, "
                "and IFLYTEK_EMBEDDING_API_SECRET."
            )

        embeddings: list[list[float]] = []
        usage = {"total_texts": len(request.texts)}
        for text in request.texts:
            payload = self._build_payload(app_id=app_id, text=text, domain=self._domain(request))
            url = self._build_auth_url(api_key=api_key, api_secret=api_secret)
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if response.status_code >= 400:
                logger.error("iFlytek embedding HTTP %s response body: %s", response.status_code, response.text)
            response.raise_for_status()
            data = response.json()
            embeddings.append(self._extract_embedding(data))

        actual_dims = len(embeddings[0]) if embeddings else 0
        expected_dims = request.dimensions or self.dimensions or self.DEFAULT_DIMENSIONS
        if actual_dims and expected_dims and actual_dims != expected_dims:
            logger.warning("iFlytek embedding dimension mismatch: expected %s, got %s", expected_dims, actual_dims)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=request.model or self.model or self.DEFAULT_MODEL,
            dimensions=actual_dims or self.DEFAULT_DIMENSIONS,
            usage=usage,
        )

    def _setting(self, *names: str) -> str:
        lowered = {str(k).lower().replace("-", "_"): str(v).strip() for k, v in self.extra_headers.items()}
        for name in names:
            value = lowered.get(name.lower().replace("-", "_"), "")
            if value:
                return value
        return ""

    def _domain(self, request: EmbeddingRequest) -> str:
        raw = (request.input_type or self._setting("domain", "iflytek_domain") or "para").strip().lower()
        if raw in {"query", "search_query", "question"}:
            return "query"
        return "para"

    def _build_payload(self, *, app_id: str, text: str, domain: str) -> dict[str, Any]:
        text_payload = {"messages": [{"content": text, "role": "user"}]}
        encoded_text = base64.b64encode(json.dumps(text_payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
        return {
            "header": {
                "app_id": app_id,
                "status": 3,
            },
            "parameter": {
                "emb": {
                    "domain": domain,
                    "feature": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                }
            },
            "payload": {
                "messages": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "json",
                    "status": 3,
                    "text": encoded_text,
                }
            },
        }

    def _build_auth_url(self, *, api_key: str, api_secret: str) -> str:
        base_url = (self.base_url or "https://emb-cn-huabei-1.xf-yun.com/").strip()
        parsed = urlparse(base_url)
        host = parsed.netloc
        request_target = parsed.path or "/"
        if parsed.query:
            request_target = f"{request_target}?{parsed.query}"
        date = formatdate(usegmt=True)
        request_line = f"POST {request_target} HTTP/1.1"
        signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
        signature_sha = hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode("ascii")
        authorization_origin = (
            f'api_key="{api_key}",algorithm="hmac-sha256",'
            f'headers="host date request-line",signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
        query = urlencode({"authorization": authorization, "host": host, "date": date})
        separator = "&" if parsed.query else "?"
        return f"{base_url}{separator}{query}"

    def _extract_embedding(self, data: dict[str, Any]) -> list[float]:
        header = data.get("header") if isinstance(data, dict) else None
        if isinstance(header, dict) and int(header.get("code", 0) or 0) != 0:
            raise ValueError(
                "iFlytek embedding returned error: "
                f"code={header.get('code')}, message={header.get('message')}, sid={header.get('sid')}"
            )
        text = (((data.get("payload") or {}).get("feature") or {}).get("text") or "").strip()
        if not text:
            raise ValueError("iFlytek embedding response did not contain payload.feature.text")
        raw = base64.b64decode(text)
        if len(raw) % 4 != 0:
            raise ValueError(f"iFlytek embedding payload byte length is not float32-aligned: {len(raw)}")
        return list(struct.unpack(f"<{len(raw) // 4}f", raw))

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model": self.model or self.DEFAULT_MODEL,
            "dimensions": self.dimensions or self.DEFAULT_DIMENSIONS,
            "supports_variable_dimensions": False,
            "provider": "iflytek_spark",
        }
