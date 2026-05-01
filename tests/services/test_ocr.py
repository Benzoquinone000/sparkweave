import base64
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from sparkweave.services.ocr import OCR_SMOKE_TEST_PNG, XfyunOcrConfig, extract_iflytek_text


def _encoded(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")


def test_extract_iflytek_standard_ocr_text() -> None:
    response = {
        "header": {"code": 0, "message": "success"},
        "payload": {
            "result": {
                "text": _encoded(
                    {
                        "pages": [
                            {
                                "lines": [
                                    {"words": [{"content": "函数"}, {"content": "极限"}]},
                                    {"words": [{"content": "连续"}]},
                                ]
                            }
                        ]
                    }
                )
            }
        },
    }

    assert extract_iflytek_text(response) == "函数极限\n连续"


def test_extract_iflytek_intsig_whole_text() -> None:
    response = {
        "header": {"code": 0, "message": "success"},
        "payload": {
            "recognizeDocumentRes": {
                "text": _encoded({"whole_text": "桃夭《诗经》\n河广《诗经》\n"})
            }
        },
    }

    assert extract_iflytek_text(response) == "桃夭《诗经》\n河广《诗经》"


def test_extract_iflytek_ocr_for_llm_plain_text() -> None:
    response = {
        "header": {"code": 0, "message": "success"},
        "payload": {
            "result": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "plain",
                "text": _encoded({"pages": [{"lines": [{"text": "OCR for LLM"}]}]}),
            }
        },
    }

    assert extract_iflytek_text(response) == "OCR for LLM"


def test_extract_iflytek_ocr_for_llm_nested_content_text() -> None:
    response = {
        "header": {"code": 0, "message": "success"},
        "payload": {
            "result": {
                "text": _encoded(
                    {
                        "image": [
                            {
                                "content": [
                                    [
                                        {
                                            "type": "paragraph",
                                            "text": ["OCR 123"],
                                        }
                                    ]
                                ]
                            }
                        ]
                    }
                )
            }
        },
    }

    assert extract_iflytek_text(response) == "OCR 123"


def test_build_iflytek_ocr_for_llm_payload_uses_document_model_schema() -> None:
    from sparkweave.services import ocr as ocr_module

    config = XfyunOcrConfig(
        app_id="appid",
        api_key="apikey",
        api_secret="apisecret",
    )

    payload = ocr_module._build_iflytek_payload(config, b"image", encoding="png")

    assert payload["header"] == {"app_id": "appid", "status": 0}
    assert payload["parameter"]["ocr"]["result"]["format"] == "plain"
    assert payload["payload"]["image"]["encoding"] == "png"
    assert payload["payload"]["image"]["status"] == 0


def test_ocr_smoke_test_image_is_real_png() -> None:
    assert OCR_SMOKE_TEST_PNG.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(OCR_SMOKE_TEST_PNG) > 400


def test_iflytek_http_error_body_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    def _raise_http_error(*args, **kwargs):
        raise HTTPError(
            url="https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=BytesIO(b'{"message":"server detail"}'),
        )

    monkeypatch.setattr(ocr_module, "urlopen", _raise_http_error)
    config = XfyunOcrConfig(app_id="appid", api_key="apikey", api_secret="apisecret")

    with pytest.raises(ocr_module.OcrUnavailable, match="HTTP 500.*server detail"):
        ocr_module.recognize_image_with_iflytek(OCR_SMOKE_TEST_PNG, config=config)


def test_iflytek_auth_url_does_not_embed_secret_values() -> None:
    from sparkweave.services import ocr as ocr_module

    config = XfyunOcrConfig(
        app_id="appid",
        api_key="apikey",
        api_secret="apisecret",
        url="https://api.xf-yun.com/v1/private/sf8e6aca1",
    )

    url = ocr_module._build_iflytek_auth_url(config)

    assert "authorization=" in url
    assert "host=api.xf-yun.com" in url
    assert "date=" in url
    assert "apisecret" not in url
