from __future__ import annotations

from sparkweave.services.rag_support import milvus_http


def test_milvus_http_bypasses_proxy_for_local_addresses() -> None:
    assert milvus_http._should_bypass_proxy("http://localhost:19530") is True
    assert milvus_http._should_bypass_proxy("http://127.0.0.1:19530") is True
    assert milvus_http._should_bypass_proxy("http://192.168.1.20:19530") is True
    assert milvus_http._should_bypass_proxy("https://in01.cloud.zilliz.com") is False


def test_milvus_http_caps_local_timeout(monkeypatch) -> None:
    monkeypatch.setenv("MILVUS_REST_LOCAL_TIMEOUT_SECONDS", "1.5")

    assert milvus_http._effective_timeout("http://localhost:19530", 30) == 1.5
    assert milvus_http._effective_timeout("http://localhost:19530", 0.5) == 0.5
    assert milvus_http._effective_timeout("https://in01.cloud.zilliz.com", 30) == 30


def test_collection_row_count_falls_back_to_count_query_when_stats_zero(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_rest_post(_uri, _token, path, payload, **_kwargs):
        calls.append((path, payload))
        if path.endswith("/collections/get_stats"):
            return {"data": {"rowCount": 0}}
        if path.endswith("/entities/query"):
            return {"data": [{"count(*)": 25}]}
        raise AssertionError(path)

    monkeypatch.setattr(milvus_http, "rest_post", fake_rest_post)

    assert milvus_http.collection_row_count("http://localhost:19530", None, "demo") == 25
    assert calls[1][1]["outputFields"] == ["count(*)"]


def test_collection_row_count_uses_positive_stats_without_count_query(monkeypatch) -> None:
    calls: list[str] = []

    def fake_rest_post(_uri, _token, path, _payload, **_kwargs):
        calls.append(path)
        return {"data": {"rowCount": 9}}

    monkeypatch.setattr(milvus_http, "rest_post", fake_rest_post)

    assert milvus_http.collection_row_count("http://localhost:19530", None, "demo") == 9
    assert calls == ["/v2/vectordb/collections/get_stats"]


def test_create_dense_collection_sends_sparkweave_schema(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_rest_post(_uri, _token, path, payload, **_kwargs):
        calls.append((path, payload))
        return {"data": {}}

    monkeypatch.setattr(milvus_http, "rest_post", fake_rest_post)

    milvus_http.create_dense_collection(
        "http://localhost:19530",
        None,
        "sparkweave_demo",
        dim=8,
        metric_type="IP",
    )

    path, payload = calls[0]
    assert path == "/v2/vectordb/collections/create"
    assert payload["collectionName"] == "sparkweave_demo"
    assert payload["schema"]["enableDynamicField"] is True
    assert [field["fieldName"] for field in payload["schema"]["fields"]] == [
        "id",
        "doc_id",
        "text",
        "embedding",
    ]
    assert payload["schema"]["fields"][-1]["elementTypeParams"] == {"dim": "8"}
    assert payload["indexParams"][0]["metricType"] == "IP"


def test_create_hybrid_collection_sends_bm25_schema(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_rest_post(_uri, _token, path, payload, **_kwargs):
        calls.append((path, payload))
        return {"data": {}}

    monkeypatch.setattr(milvus_http, "rest_post", fake_rest_post)

    milvus_http.create_hybrid_collection(
        "http://localhost:19530",
        None,
        "sparkweave_demo",
        dim=16,
        metric_type="IP",
    )

    path, payload = calls[0]
    assert path == "/v2/vectordb/collections/create"
    assert [field["fieldName"] for field in payload["schema"]["fields"]] == [
        "id",
        "doc_id",
        "text",
        "embedding",
        "sparse",
    ]
    text_field = payload["schema"]["fields"][2]
    assert text_field["elementTypeParams"]["enable_analyzer"] is True
    assert payload["schema"]["functions"] == [
        {
            "name": "text_bm25_emb",
            "type": "BM25",
            "inputFieldNames": ["text"],
            "outputFieldNames": ["sparse"],
            "params": {},
        }
    ]
    assert payload["indexParams"][0]["fieldName"] == "embedding"
    assert payload["indexParams"][1]["fieldName"] == "sparse"
    assert payload["indexParams"][1]["metricType"] == "BM25"
    assert "params" not in payload["indexParams"][1]


def test_insert_entities_returns_insert_count(monkeypatch) -> None:
    monkeypatch.setattr(
        milvus_http,
        "rest_post",
        lambda *_args, **_kwargs: {"data": {"insertCount": "3"}},
    )

    assert milvus_http.insert_entities(
        "http://localhost:19530",
        None,
        "demo",
        [{"id": "a"}, {"id": "b"}],
    ) == 3


def test_query_entity_count_accepts_common_count_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        milvus_http,
        "rest_post",
        lambda *_args, **_kwargs: {"data": [{"rowCount": "7"}]},
    )

    assert milvus_http.query_entity_count("http://localhost:19530", None, "demo") == 7


def test_hybrid_search_entities_sends_dense_and_bm25_requests(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_rest_post(_uri, _token, path, payload, **_kwargs):
        calls.append((path, payload))
        return {"data": [{"id": "chunk-1", "distance": 0.91, "text": "gradient descent"}]}

    monkeypatch.setattr(milvus_http, "rest_post", fake_rest_post)

    rows = milvus_http.hybrid_search_entities(
        "http://localhost:19530",
        None,
        "sparkweave_demo",
        dense_vector=[0.1, 0.2],
        query_text="gradient descent",
        dense_field="embedding",
        sparse_field="sparse",
        output_fields=["text", "file_name"],
        limit=3,
        metric_type="IP",
        ranker="WeightedRanker",
        ranker_params={"weights": [0.7, 1.3]},
    )

    path, payload = calls[0]
    assert path == "/v2/vectordb/entities/hybrid_search"
    assert payload["search"][0]["data"] == [[0.1, 0.2]]
    assert payload["search"][0]["annsField"] == "embedding"
    assert payload["search"][0]["metricType"] == "IP"
    assert payload["search"][1]["data"] == ["gradient descent"]
    assert payload["search"][1]["annsField"] == "sparse"
    assert payload["search"][1]["metricType"] == "BM25"
    assert payload["rerank"] == {"strategy": "weighted", "params": {"weights": [0.7, 1.0]}}
    assert payload["limit"] == 3
    assert rows[0]["id"] == "chunk-1"


def test_rest_post_wraps_connection_reset(monkeypatch) -> None:
    def _raise_connection_reset(*_args, **_kwargs):
        raise ConnectionResetError("connection reset by peer")

    monkeypatch.setattr(milvus_http, "_open_request", _raise_connection_reset)

    try:
        milvus_http.rest_post("http://localhost:19530", None, "/v2/vectordb/collections/list", {})
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("rest_post should wrap transport errors")

    assert "Milvus REST /v2/vectordb/collections/list failed" in message
    assert "connection reset by peer" in message
