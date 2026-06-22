from __future__ import annotations

import base64
import json

import pytest

from sparkweave.services.speech import (
    SpeechUnavailable,
    XfyunAsrConfig,
    XfyunSpeechEvalConfig,
    evaluate_speech_with_iflytek,
    extract_iflytek_asr_text,
    extract_speech_eval_scores,
    guess_iflytek_audio_encoding,
    prepare_iflytek_asr_audio,
    prepare_iflytek_speech_eval_audio,
    transcribe_audio_with_iflytek,
)


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
async def test_iflytek_asr_transcribes_incremental_result(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [
        json.dumps(
            {
                "code": 0,
                "sid": "asr-1",
                "data": {
                    "status": 1,
                    "result": {"sn": 1, "ws": [{"cw": [{"w": "你好"}]}]},
                },
            }
        ),
        json.dumps(
            {
                "code": 0,
                "sid": "asr-1",
                "data": {
                    "status": 2,
                    "result": {"sn": 2, "ws": [{"cw": [{"w": "世界"}]}]},
                },
            }
        ),
    ]
    fake = _FakeWebSocket(messages)
    monkeypatch.setattr("sparkweave.services.speech.connect", lambda *args, **kwargs: _FakeConnect(fake))
    config = XfyunAsrConfig(app_id="app", api_key="key", api_secret="secret", chunk_size=3)

    result = await transcribe_audio_with_iflytek(b"abcdef", config=config, audio_encoding="lame")

    assert result.text == "你好世界"
    assert result.sid == "asr-1"
    assert result.audio_encoding == "lame"
    assert result.audio_format == "audio/L16;rate=16000"
    assert len(fake.sent) == 2
    first = json.loads(fake.sent[0])
    assert first["common"]["app_id"] == "app"
    assert first["business"]["language"] == "zh_cn"
    assert first["data"]["encoding"] == "lame"
    assert first["data"]["audio"] == base64.b64encode(b"abc").decode("ascii")


@pytest.mark.asyncio
async def test_iflytek_speech_eval_decodes_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = '<xml_result><read_sentence total_score="87.5" accuracy_score="90" fluency_score="82"/></xml_result>'
    messages = [
        json.dumps(
            {
                "code": 0,
                "sid": "ise-1",
                "data": {"status": 2, "data": base64.b64encode(xml.encode("utf-8")).decode("ascii")},
            }
        )
    ]
    fake = _FakeWebSocket(messages)
    monkeypatch.setattr("sparkweave.services.speech.connect", lambda *args, **kwargs: _FakeConnect(fake))
    config = XfyunSpeechEvalConfig(app_id="app", api_key="key", api_secret="secret")

    result = await evaluate_speech_with_iflytek(b"pcm", reference_text="你好世界", config=config)

    assert result.sid == "ise-1"
    assert result.overall_score == 87.5
    assert result.normalized_score == 0.875
    assert result.dimensions["accuracy"] == 90
    sent = json.loads(fake.sent[0])
    assert sent["business"]["cmd"] == "ssb"
    assert sent["business"]["text"] == base64.b64encode("你好世界".encode("utf-8")).decode("ascii")


@pytest.mark.asyncio
async def test_iflytek_speech_raises_on_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sparkweave.services.speech.connect",
        lambda *args, **kwargs: _FakeConnect(_FakeWebSocket([json.dumps({"code": 101, "message": "bad"})])),
    )
    config = XfyunAsrConfig(app_id="app", api_key="key", api_secret="secret")

    with pytest.raises(SpeechUnavailable, match="bad"):
        await transcribe_audio_with_iflytek(b"audio", config=config)


def test_speech_extractors_are_tolerant() -> None:
    result = {
        "ws": [
            {"cw": [{"w": "深度"}]},
            {"cw": [{"w": "学习"}]},
        ]
    }
    assert extract_iflytek_asr_text(result) == "深度学习"
    assert extract_speech_eval_scores('<read_chapter total_score="91" integrity_score="88" />') == {
        "total": 91.0,
        "integrity": 88.0,
    }
    assert guess_iflytek_audio_encoding("answer.mp3") == "lame"
    assert guess_iflytek_audio_encoding("answer.wav") == "raw"
    assert guess_iflytek_audio_encoding("voice.pcm") == "raw"


def test_prepare_iflytek_asr_audio_strips_wav_header() -> None:
    wav = _make_wav(b"\x01\x02\x03\x04", sample_rate=16_000)

    audio, encoding, audio_format = prepare_iflytek_asr_audio(wav, audio_encoding="raw")

    assert audio == b"\x01\x02\x03\x04"
    assert encoding == "raw"
    assert audio_format == "audio/L16;rate=16000"


def test_prepare_iflytek_speech_eval_audio_strips_wav_header() -> None:
    wav = _make_wav(b"\x05\x06\x07\x08", sample_rate=16_000)

    audio, audio_format, encoding = prepare_iflytek_speech_eval_audio(
        wav,
        audio_format="audio/L16;rate=16000",
        audio_encoding="raw",
    )

    assert audio == b"\x05\x06\x07\x08"
    assert audio_format == "audio/L16;rate=16000"
    assert encoding == "raw"


def test_prepare_iflytek_asr_audio_rejects_webm_container() -> None:
    with pytest.raises(SpeechUnavailable, match="Unsupported browser audio container"):
        prepare_iflytek_asr_audio(b"\x1aE\xdf\xa3webm", audio_encoding="raw")


def _make_wav(payload: bytes, *, sample_rate: int) -> bytes:
    byte_rate = sample_rate * 2
    block_align = 2
    riff_size = 36 + len(payload)
    return (
        b"RIFF"
        + riff_size.to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + byte_rate.to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + len(payload).to_bytes(4, "little")
        + payload
    )
