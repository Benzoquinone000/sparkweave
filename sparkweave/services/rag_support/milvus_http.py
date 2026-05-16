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
        if field.get("primaryKey") or field.get("is_primary"):
            return str(field.get("name") or "id")
    return "id"


def query_output_fields(description: dict[str, Any]) -> list[str]:
    if description.get("enableDynamicField"):
        return ["*"]

    fields = description.get("fields") if isinstance(description, dict) else []
    if not isinstance(fields, list):
        return ["*"]
    excluded_names = {"embedding", "vector", "sparse_embedding"}
    names: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "")
        field_type = str(field.get("type") or "").lower()
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
    "should_bypass_proxy",
]
