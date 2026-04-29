import base64
import json

from sparkweave.services.ocr import XfyunOcrConfig, extract_iflytek_text


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
