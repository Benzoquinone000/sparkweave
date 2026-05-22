from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.services.iflytek_vision import (
    IflytekVisionConfig,
    IflytekVisionUnavailable,
    build_vision_payload,
    extract_vision_delta,
    understand_image,
)


class _FakeWebSocket:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = [json.dumps(event, ensure_ascii=False) for event in events]
        self.sent_payload: dict[str, Any] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def send(self, value: str) -> None:
        self.sent_payload = json.loads(value)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)


def test_iflytek_vision_payload_uses_spark_image_protocol() -> None:
    config = IflytekVisionConfig(
        app_id="app",
        api_key="key",
        api_secret="secret",
        domain="imagev3",
        protocol="spark_image",
    )
    payload = build_vision_payload(config, image=b"image", prompt="描述图片")
    messages = payload["payload"]["message"]["text"]

    assert payload["header"]["app_id"] == "app"
    assert payload["parameter"]["chat"]["domain"] == "imagev3"
    assert messages[0]["content_type"] == "image"
    assert messages[1] == {"role": "user", "content": "描述图片", "content_type": "text"}


def test_iflytek_vision_payload_can_use_maas_multimodal_shape() -> None:
    config = IflytekVisionConfig(
        app_id="app",
        api_key="key",
        api_secret="secret",
        protocol="maas_vl",
    )
    payload = build_vision_payload(config, image=b"image", prompt="描述图片", mime_type="image/jpeg")
    content = payload["payload"]["message"]["text"][0]["content"]

    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert content[1] == {"type": "text", "text": "描述图片"}


def test_iflytek_vision_extracts_delta_and_usage() -> None:
    delta, done, usage, sid = extract_vision_delta(
        {
            "header": {"code": 0, "status": 2, "sid": "sid-1"},
            "payload": {
                "choices": {"status": 2, "text": [{"content": "图中有公式"}]},
                "usage": {"text": {"total_tokens": 8}},
            },
        }
    )

    assert delta == "图中有公式"
    assert done is True
    assert usage == {"total_tokens": 8}
    assert sid == "sid-1"


def test_iflytek_vision_provider_error_is_readable() -> None:
    with pytest.raises(IflytekVisionUnavailable, match="code=10013"):
        extract_vision_delta({"header": {"code": 10013, "message": "bad auth"}})


@pytest.mark.asyncio
async def test_iflytek_vision_streams_websocket_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = _FakeWebSocket(
        [
            {
                "header": {"code": 0, "status": 1},
                "payload": {"choices": {"text": [{"content": "图中"}]}},
            },
            {
                "header": {"code": 0, "status": 2, "sid": "sid-2"},
                "payload": {
                    "choices": {"text": [{"content": "有板书"}]},
                    "usage": {"total_tokens": 12},
                },
            },
        ]
    )

    def _fake_connect(*_args, **_kwargs):
        return fake_ws

    monkeypatch.setattr("sparkweave.services.iflytek_vision.websockets.connect", _fake_connect)

    config = IflytekVisionConfig(
        app_id="app",
        api_key="key",
        api_secret="secret",
        url="wss://example.test/v2.1/image",
        timeout=5,
    )
    result = await understand_image(b"image", prompt="描述图片", config=config)

    assert result["content"] == "图中有板书"
    assert result["sid"] == "sid-2"
    assert result["usage"] == {"total_tokens": 12}
    assert fake_ws.sent_payload is not None
    assert fake_ws.sent_payload["payload"]["message"]["text"][1]["content"] == "描述图片"

