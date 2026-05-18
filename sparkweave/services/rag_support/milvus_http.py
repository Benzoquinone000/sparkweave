"""Small Milvus REST helpers used where importing pymilvus is risky."""

from __future__ import annotations

import ipaddress
import json
import os
from typing import Any
import urllib.error
from urllib.parse import urlparse
import urllib.request

DEFAULT_TIMEOUT_SECONDS = 8
LOCAL_TIMEOUT_SECONDS = 3.0


def _compact_error_detail(value: object) -> str:
    """Return a short, display-safe transport error detail."""
    if isinstance(value, urllib.error.URLError):
        reason = getattr(value, "reason", None)
        text = str(reason or value).strip()
    else:
        text = str(value).strip()
    return text or "no response"


def is_http_uri(uri: str) -> bool:
    normalized = str(uri or "").strip().lower()
    return normalized.startswith("http://") or normalized.startswith("https://")


def _should_bypass_proxy(uri: str) -> bool:
    """Return true for Milvus endpoints that should never go through HTTP proxies."""
    parsed = urlparse(str(uri or ""))
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1", "host.docker.internal", "milvus"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def should_bypass_proxy(uri: str) -> bool:
    """Return whether REST calls to ``uri`` bypass process HTTP proxies."""
    return _should_bypass_proxy(uri)


def _local_timeout_seconds() -> float:
    raw = os.getenv("MILVUS_REST_LOCAL_TIMEOUT_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return LOCAL_TIMEOUT_SECONDS


def _effective_timeout(uri: str, timeout: float) -> float:
    if _should_bypass_proxy(uri):
        return min(float(timeout), _local_timeout_seconds())
    return float(timeout)


def _open_request(request: urllib.request.Request, *, uri: str, timeout: float):
    timeout = _effective_timeout(uri, timeout)
    if _should_bypass_proxy(uri):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def rest_post(
    uri: str,
    token: str | None,
    path: str,
    payload: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if not is_http_uri(uri):
        raise RuntimeError(f"Milvus REST requires an HTTP URI, got: {uri}")
    url = f"{uri.rstrip('/')}/{path.lstrip('/')}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _open_request(request, uri=uri, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body.strip() or getattr(exc, "reason", "") or "empty response body"
        raise RuntimeError(f"Milvus REST {path} failed: HTTP {exc.code} {detail}") from exc
    except (urllib.error.URLError, OSError, TimeoutError, ConnectionError) as exc:
        detail = _compact_error_detail(exc)
        raise RuntimeError(f"Milvus REST {path} failed: {detail}") from exc

    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Milvus REST {path} returned non-JSON response: {raw[:200]}") from exc
    if int(parsed.get("code", 0) or 0) != 0:
        raise RuntimeError(str(parsed.get("message") or parsed))
    return parsed


def describe_collection(uri: str, token: str | None, collection_name: str) -> dict[str, Any]:
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/collections/describe",
        {"collectionName": collection_name},
    )
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def collection_stats(uri: str, token: str | None, collection_name: str) -> dict[str, Any]:
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/collections/get_stats",
        {"collectionName": collection_name},
    )
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def collection_row_count(uri: str, token: str | None, collection_name: str) -> int | None:
    stats = collection_stats(uri, token, collection_name)
    value = stats.get("rowCount")
    try:
        row_count = int(value)
    except (TypeError, ValueError):
        row_count = None
    if row_count and row_count > 0:
        return row_count

    # Milvus REST can report rowCount=0 immediately after LlamaIndex inserts,
    # even though query already sees the rows. Use an aggregate query as the
    # authoritative HTTP-path fallback.
    counted = query_entity_count(uri, token, collection_name)
    return counted if counted is not None else row_count


def query_entity_count(uri: str, token: str | None, collection_name: str) -> int | None:
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/entities/query",
        {
            "collectionName": collection_name,
            "filter": "",
            "outputFields": ["count(*)"],
        },
    )
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    for key in ("count(*)", "count", "rowCount", "row_count", "num_entities"):
        try:
            return int(first[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def list_collections(uri: str, token: str | None) -> list[str]:
    payload = rest_post(uri, token, "/v2/vectordb/collections/list", {})
    data = payload.get("data")
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, dict):
        names = data.get("collectionNames") or data.get("collections") or []
        if isinstance(names, list):
            return [str(item) for item in names]
    return []


def has_collection(uri: str, token: str | None, collection_name: str) -> bool:
    return collection_name in set(list_collections(uri, token))


def drop_collection(uri: str, token: str | None, collection_name: str) -> None:
    rest_post(
        uri,
        token,
        "/v2/vectordb/collections/drop",
        {"collectionName": collection_name},
        timeout=30,
    )


def create_dense_collection(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    dim: int,
    metric_type: str = "IP",
) -> None:
    """Create the dense-vector schema used by SparkWeave's HTTP Milvus path."""
    schema = {
        "autoId": False,
        "enableDynamicField": True,
        "fields": [
            {
                "fieldName": "id",
                "dataType": "VarChar",
                "isPrimary": True,
                "elementTypeParams": {"max_length": "65535"},
            },
            {
                "fieldName": "doc_id",
                "dataType": "VarChar",
                "elementTypeParams": {"max_length": "65535"},
            },
            {
                "fieldName": "text",
                "dataType": "VarChar",
                "elementTypeParams": {"max_length": "65535"},
            },
            {
                "fieldName": "embedding",
                "dataType": "FloatVector",
                "elementTypeParams": {"dim": str(int(dim))},
            },
        ],
    }
    index_params = [
        {
            "fieldName": "embedding",
            "indexName": "embedding",
            "metricType": metric_type,
        }
    ]
    rest_post(
        uri,
        token,
        "/v2/vectordb/collections/create",
        {
            "collectionName": collection_name,
            "schema": schema,
            "indexParams": index_params,
        },
        timeout=30,
    )


def create_hybrid_collection(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    dim: int,
    dense_field: str = "embedding",
    sparse_field: str = "sparse",
    text_field: str = "text",
    metric_type: str = "IP",
) -> None:
    """Create the dense+BM25 sparse schema used by true HTTP hybrid retrieval."""
    schema = {
        "autoId": False,
        "enableDynamicField": True,
        "fields": [
            {
                "fieldName": "id",
                "dataType": "VarChar",
                "isPrimary": True,
                "elementTypeParams": {"max_length": "65535"},
            },
            {
                "fieldName": "doc_id",
                "dataType": "VarChar",
                "elementTypeParams": {"max_length": "65535"},
            },
            {
                "fieldName": text_field,
                "dataType": "VarChar",
                "elementTypeParams": {
                    "max_length": "65535",
                    "enable_analyzer": True,
                },
            },
            {
                "fieldName": dense_field,
                "dataType": "FloatVector",
                "elementTypeParams": {"dim": str(int(dim))},
            },
            {
                "fieldName": sparse_field,
                "dataType": "SparseFloatVector",
            },
        ],
        "functions": [
            {
                "name": "text_bm25_emb",
                "type": "BM25",
                "inputFieldNames": [text_field],
                "outputFieldNames": [sparse_field],
                "params": {},
            }
        ],
    }
    index_params = [
        {
            "fieldName": dense_field,
            "indexName": dense_field,
            "metricType": metric_type,
        },
        {
            "fieldName": sparse_field,
            "indexName": sparse_field,
            "metricType": "BM25",
            "indexType": "AUTOINDEX",
        },
    ]
    rest_post(
        uri,
        token,
        "/v2/vectordb/collections/create",
        {
            "collectionName": collection_name,
            "schema": schema,
            "indexParams": index_params,
        },
        timeout=30,
    )


def load_collection(uri: str, token: str | None, collection_name: str) -> None:
    rest_post(
        uri,
        token,
        "/v2/vectordb/collections/load",
        {"collectionName": collection_name},
        timeout=30,
    )


def primary_field(description: dict[str, Any]) -> str:
    fields = description.get("fields") if isinstance(description, dict) else []
    if not isinstance(fields, list):
        return "id"
    for field in fields:
        if not isinstance(field, dict):
            continue
        if field.get("primaryKey") or field.get("is_primary") or field.get("isPrimary"):
            return str(field.get("name") or field.get("fieldName") or "id")
    return "id"


def query_output_fields(description: dict[str, Any]) -> list[str]:
    if description.get("enableDynamicField"):
        return ["*"]

    fields = description.get("fields") if isinstance(description, dict) else []
    if not isinstance(fields, list):
        return ["*"]
    excluded_names = {"embedding", "vector", "sparse_embedding", "sparse"}
    names: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or field.get("fieldName") or "")
        field_type = str(field.get("type") or field.get("dataType") or "").lower()
        if not name or name in excluded_names or "vector" in field_type:
            continue
        names.append(name)
    return names or ["*"]


def query_entities(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    output_fields: list[str],
    limit: int,
    offset: int = 0,
) -> list[dict[str, Any]]:
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/entities/query",
        {
            "collectionName": collection_name,
            "filter": "",
            "outputFields": output_fields,
            "limit": max(1, int(limit)),
            "offset": max(0, int(offset)),
        },
    )
    data = payload.get("data")
    return list(data) if isinstance(data, list) else []


def insert_entities(
    uri: str,
    token: str | None,
    collection_name: str,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/entities/insert",
        {
            "collectionName": collection_name,
            "data": rows,
        },
        timeout=30,
    )
    data = payload.get("data")
    if isinstance(data, dict):
        try:
            return int(data.get("insertCount"))
        except (TypeError, ValueError):
            pass
    return len(rows)


def _hybrid_rerank_payload(ranker: str, ranker_params: dict[str, Any] | None) -> dict[str, Any]:
    raw = str(ranker or "").strip().lower().replace("_", "").replace("-", "")
    params = dict(ranker_params or {})
    if raw in {"weighted", "weightedranker", "weight"}:
        weights = _bounded_hybrid_weights(params.get("weights"))
        return {"strategy": "weighted", "params": {"weights": weights}}
    k = params.get("k", params.get("rrf_k", 60))
    try:
        resolved_k = int(k)
    except (TypeError, ValueError):
        resolved_k = 60
    return {"strategy": "rrf", "params": {"k": max(1, resolved_k)}}


def _bounded_hybrid_weights(value: object) -> list[float]:
    raw = value if isinstance(value, list) else [1.0, 0.6]
    weights: list[float] = []
    for index in range(2):
        try:
            parsed = float(raw[index])
        except (IndexError, TypeError, ValueError):
            parsed = 1.0 if index == 0 else 0.6
        weights.append(min(1.0, max(0.0, parsed)))
    if weights == [0.0, 0.0]:
        return [1.0, 0.6]
    return weights


def hybrid_search_entities(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    dense_vector: list[float],
    query_text: str,
    dense_field: str,
    sparse_field: str,
    output_fields: list[str],
    limit: int,
    metric_type: str = "IP",
    ranker: str = "RRFRanker",
    ranker_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = rest_post(
        uri,
        token,
        "/v2/vectordb/entities/hybrid_search",
        {
            "collectionName": collection_name,
            "search": [
                {
                    "data": [dense_vector],
                    "annsField": dense_field,
                    "limit": max(1, int(limit)),
                    "outputFields": output_fields,
                    "metricType": metric_type,
                    "params": {},
                },
                {
                    "data": [query_text],
                    "annsField": sparse_field,
                    "limit": max(1, int(limit)),
                    "outputFields": output_fields,
                    "metricType": "BM25",
                    "params": {},
                },
            ],
            "rerank": _hybrid_rerank_payload(ranker, ranker_params),
            "limit": max(1, int(limit)),
            "outputFields": output_fields,
        },
        timeout=30,
    )
    data = payload.get("data")
    return list(data) if isinstance(data, list) else []


def delete_entities(
    uri: str,
    token: str | None,
    collection_name: str,
    *,
    filter_expr: str,
) -> None:
    rest_post(
        uri,
        token,
        "/v2/vectordb/entities/delete",
        {"collectionName": collection_name, "filter": filter_expr},
    )


__all__ = [
    "collection_row_count",
    "collection_stats",
    "create_dense_collection",
    "create_hybrid_collection",
    "delete_entities",
    "describe_collection",
    "drop_collection",
    "has_collection",
    "insert_entities",
    "is_http_uri",
    "list_collections",
    "load_collection",
    "primary_field",
    "query_entity_count",
    "query_entities",
    "query_output_fields",
    "rest_post",
    "hybrid_search_entities",
    "should_bypass_proxy",
]
