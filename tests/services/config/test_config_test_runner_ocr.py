from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.services.config_test_runner import ConfigTestRunner, TestRun


@pytest.mark.asyncio
async def test_config_test_runner_ocr_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    config = SimpleNamespace(url="https://api.siliconflow.cn/v1/chat/completions", provider="siliconflow")
    calls: list[dict] = []
    monkeypatch.setattr(ocr_module, "resolve_ocr_config", lambda: config)

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "SparkWeave OCR"

    monkeypatch.setattr(ocr_module, "recognize_image", _fake_recognize)

    runner = ConfigTestRunner()
    run = TestRun(id="ocr-test", service="ocr")

    await runner._test_ocr(run, catalog={})

    assert calls
    assert calls[0]["encoding"] == "png"
    assert calls[0]["config"] is config
    assert any(event["type"] == "response" for event in run.events)


@pytest.mark.asyncio
async def test_config_test_runner_ocr_probe_requires_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    monkeypatch.setattr(ocr_module, "resolve_ocr_config", lambda: None)

    runner = ConfigTestRunner()
    run = TestRun(id="ocr-test", service="ocr")

    with pytest.raises(ValueError, match="credentials are not configured"):
        await runner._test_ocr(run, catalog={})


@pytest.mark.asyncio
async def test_config_test_runner_tts_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import tts as tts_module

    config = SimpleNamespace(url="wss://tts.example", voice="x5_lingxiaoxuan_flow", sample_rate=24000)
    calls: list[dict] = []
    monkeypatch.setattr(tts_module.XfyunTtsConfig, "from_env", classmethod(lambda cls: config))

    async def _fake_tts(text: str, **kwargs):
        calls.append({"text": text, **kwargs})
        return SimpleNamespace(
            audio=b"mp3",
            content_type="audio/mpeg",
            voice="x5_lingxiaoxuan_flow",
            sid="tts-1",
        )

    monkeypatch.setattr(tts_module, "synthesize_speech_with_iflytek", _fake_tts)

    runner = ConfigTestRunner()
    run = TestRun(id="tts-test", service="tts")

    await runner._test_tts(run, catalog={})

    assert calls == [{"text": tts_module.TTS_SMOKE_TEST_TEXT, "config": config}]
    assert any(event["type"] == "response" for event in run.events)


@pytest.mark.asyncio
async def test_config_test_runner_asr_probe_checks_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import speech as speech_module

    config = SimpleNamespace(
        url="wss://asr.example",
        language="zh_cn",
        accent="mandarin",
        domain="iat",
        vad_eos=2400,
    )
    monkeypatch.setattr(speech_module.XfyunAsrConfig, "from_env", classmethod(lambda cls: config))

    runner = ConfigTestRunner()
    run = TestRun(id="asr-test", service="asr")

    await runner._test_asr(run, catalog={})

    response = next(event for event in run.events if event["type"] == "response")
    assert response["language"] == "zh_cn"
    assert response["domain"] == "iat"


@pytest.mark.asyncio
async def test_config_test_runner_speech_eval_probe_checks_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import speech as speech_module

    config = SimpleNamespace(
        url="wss://ise.example",
        category="read_sentence",
        language="zh_cn",
        group="pupil",
        accent="mandarin",
    )
    monkeypatch.setattr(speech_module.XfyunSpeechEvalConfig, "from_env", classmethod(lambda cls: config))

    runner = ConfigTestRunner()
    run = TestRun(id="speech-eval-test", service="speech_eval")

    await runner._test_speech_eval(run, catalog={})

    response = next(event for event in run.events if event["type"] == "response")
    assert response["category"] == "read_sentence"
    assert response["language"] == "zh_cn"
