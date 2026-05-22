from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.services.iflytek_formula import (
    IflytekFormulaConfig,
    IflytekFormulaUnavailable,
    parse_iflytek_formula_response,
    recognize_formula_image,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


@pytest.mark.asyncio
async def test_iflytek_formula_posts_signed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "code": 0,
                "sid": "formula-1",
                "data": {
                    "region": [
                        {
                            "type": "formula",
                            "recog": {
                                "content": "ifly-latex-begin x+1=2 ifly-latex-end",
                                "confidence": 0.98,
                            },
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr("sparkweave.services.iflytek_formula.urlopen", _fake_urlopen)

    config = IflytekFormulaConfig(
        app_id="app",
        api_key="key",
        api_secret="secret",
        url="https://example.test/v2/itr",
        timeout=11,
    )
    result = await recognize_formula_image(b"image-bytes", config=config)

    assert result["text"] == "$x+1=2$"
    assert result["regions"][0]["confidence"] == 0.98
    assert result["sid"] == "formula-1"
    assert captured["url"] == "https://example.test/v2/itr"
    assert captured["payload"]["common"]["app_id"] == "app"
    assert captured["payload"]["business"]["ent"] == "teach-photo-print"
    assert captured["payload"]["business"]["aue"] == "raw"
    assert captured["payload"]["data"]["image"]
    assert captured["headers"]["Authorization"].startswith('api_key="key"')
    assert captured["headers"]["Digest"].startswith("SHA-256=")
    assert captured["timeout"] == 11


def test_iflytek_formula_parse_rejects_provider_error() -> None:
    with pytest.raises(IflytekFormulaUnavailable, match="error 11200"):
        parse_iflytek_formula_response('{"code":11200,"message":"invalid image"}')

