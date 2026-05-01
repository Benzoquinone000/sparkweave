from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.services.config_test_runner import ConfigTestRunner, TestRun


@pytest.mark.asyncio
async def test_config_test_runner_ocr_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    config = SimpleNamespace(url="https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm")
    calls: list[dict] = []
    monkeypatch.setattr(ocr_module.XfyunOcrConfig, "from_env", classmethod(lambda cls: config))

    def _fake_recognize(image: bytes, **kwargs):
        calls.append({"image": image, **kwargs})
        return "SparkWeave OCR"

    monkeypatch.setattr(ocr_module, "recognize_image_with_iflytek", _fake_recognize)

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

    monkeypatch.setattr(ocr_module.XfyunOcrConfig, "from_env", classmethod(lambda cls: None))

    runner = ConfigTestRunner()
    run = TestRun(id="ocr-test", service="ocr")

    with pytest.raises(ValueError, match="credentials are not configured"):
        await runner._test_ocr(run, catalog={})
