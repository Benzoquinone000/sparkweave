from __future__ import annotations

import base64
import json

import pytest

from sparkweave.services.tts import TtsUnavailable, XfyunTtsConfig, synthesize_speech_with_iflytek


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    async def recv(self) -> str:
        if not self._messages:
            raise RuntimeError("no more messages")
        return self._messages.pop(0)


class _FakeConnect:
    def __init__(self, websocket: _FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> _FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_iflytek_tts_collects_audio_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [
        json.dumps(
            {
                "header": {"code": 0, "message": "success", "sid": "sid-1", "status": 1},
                "payload": {
                    "audio": {
                        "audio": base64.b64encode(b"abc").decode("ascii"),
                        "status": 1,
                    }
                },
            }
        ),
        json.dumps(
            {
                "header": {"code": 0, "message": "success", "sid": "sid-1", "status": 2},
                "payload": {
                    "audio": {
                        "audio": base64.b64encode(b"def").decode("ascii"),
                        "status": 2,
                    },
                    "pybuf": {
                        "text": base64.b64encode("拼音".encode("utf-8")).decode("ascii"),
                    },
                },
            }
        ),
    ]
    fake = _FakeWebSocket(messages)
    monkeypatch.setattr("sparkweave.services.tts.connect", lambda *args, **kwargs: _FakeConnect(fake))
    config = XfyunTtsConfig(app_id="app", api_key="key", api_secret="secret")

    result = await synthesize_speech_with_iflytek("hello", config=config)

    assert result.audio == b"abcdef"
    assert result.sid == "sid-1"
    assert result.phonetic_text == "拼音"
    assert result.content_type == "audio/mpeg"
    sent = json.loads(fake.sent[0])
    assert sent["payload"]["text"]["text"] == base64.b64encode(b"hello").decode("ascii")
    assert sent["parameter"]["tts"]["vcn"] == config.voice


@pytest.mark.asyncio
async def test_iflytek_tts_raises_on_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [
        json.dumps(
            {
                "header": {"code": 10001, "message": "bad request"},
            }
        )
    ]
    monkeypatch.setattr(
        "sparkweave.services.tts.connect",
        lambda *args, **kwargs: _FakeConnect(_FakeWebSocket(messages)),
    )
    config = XfyunTtsConfig(app_id="app", api_key="key", api_secret="secret")

    with pytest.raises(TtsUnavailable, match="bad request"):
        await synthesize_speech_with_iflytek("hello", config=config)
