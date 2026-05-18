import json
from urllib.parse import parse_qs, urlparse

import pytest

from sparkweave.services.iflytek_spark_ws import (
    _extract_delta,
    build_auth_url,
    build_payload,
    resolve_ws_base_url,
    resolve_ws_request,
)


def test_iflytek_ws_auth_url_contains_required_query_fields() -> None:
    url = build_auth_url(
        "wss://spark-api.xf-yun.com/x2",
        api_key="key",
        api_secret="secret",
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "wss"
    assert parsed.netloc == "spark-api.xf-yun.com"
    assert "authorization" in query
    assert query["host"] == ["spark-api.xf-yun.com"]
    assert "date" in query


def test_iflytek_ws_payload_uses_domain_and_app_id() -> None:
    payload = build_payload(
        app_id="appid",
        domain="spark-x",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.5,
        max_tokens=100,
    )

    assert payload["header"]["app_id"] == "appid"
    assert payload["parameter"]["chat"]["domain"] == "spark-x"
    assert payload["payload"]["message"]["text"] == [{"role": "user", "content": "hello"}]
    json.dumps(payload)


def test_iflytek_ws_payload_supports_x2_thinking_and_web_search() -> None:
    payload = build_payload(
        app_id="appid",
        domain="spark-x",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.5,
        max_tokens=100,
        top_k=5,
        presence_penalty=1,
        frequency_penalty=0.02,
        chat_id="chat-1",
        thinking_type="auto",
        web_search=True,
        search_mode="normal",
    )
    chat = payload["parameter"]["chat"]

    assert chat["domain"] == "spark-x"
    assert chat["thinking"] == {"type": "auto"}
    assert chat["tools"][0]["type"] == "web_search"
    assert chat["chat_id"] == "chat-1"


def test_iflytek_ws_extracts_delta_and_completion() -> None:
    delta, done = _extract_delta(
        {
            "header": {"code": 0, "status": 2},
            "payload": {"choices": {"text": [{"content": "OK"}]}},
        }
    )

    assert delta == "OK"
    assert done is True


def test_iflytek_ws_ignores_reasoning_content_by_default() -> None:
    delta, done = _extract_delta(
        {
            "header": {"code": 0, "status": 1},
            "payload": {
                "choices": {
                    "status": 1,
                    "text": [{"reasoning_content": "private reasoning", "content": ""}],
                }
            },
        }
    )

    assert delta == ""
    assert done is False


def test_iflytek_ws_error_raises_message() -> None:
    with pytest.raises(ValueError, match="code=10013"):
        _extract_delta({"header": {"code": 10013, "message": "bad auth"}})


def test_iflytek_ws_base_url_defaults_from_model() -> None:
    assert resolve_ws_base_url("spark-x2", None) == "wss://spark-api.xf-yun.com/x2"
    assert resolve_ws_base_url("spark-x1.5", None) == "wss://spark-api.xf-yun.com/v1/x1"
    assert resolve_ws_base_url("4.0Ultra", "") == "wss://spark-api.xf-yun.com/x2"
    assert resolve_ws_base_url("generalv3.5", None) == "wss://spark-api.xf-yun.com/x2"
    assert resolve_ws_base_url("spark-x2", "wss://spark-api.xf-yun.com/v4.0/chat") == "wss://spark-api.xf-yun.com/x2"


def test_iflytek_ws_x_models_use_spark_x_domain() -> None:
    assert resolve_ws_request(model="spark-x2", base_url=None) == (
        "spark-x",
        "wss://spark-api.xf-yun.com/x2",
    )
    assert resolve_ws_request(model="spark-x1.5", base_url=None) == (
        "spark-x",
        "wss://spark-api.xf-yun.com/v1/x1",
    )
    assert resolve_ws_request(model="spark-x2", base_url=None, domain_override="spark-x2") == (
        "spark-x",
        "wss://spark-api.xf-yun.com/x2",
    )
