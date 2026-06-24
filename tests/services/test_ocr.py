import base64
from io import BytesIO
import json
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from sparkweave.services.ocr import (
    OCR_SMOKE_TEST_PNG,
    SiliconFlowOcrConfig,
    XfyunOcrConfig,
    extract_iflytek_text,
    extract_siliconflow_text,
)


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


def test_extract_iflytek_rejects_invalid_base64_text() -> None:
    response = {
        "header": {"code": 0, "message": "success"},
        "payload": {
            "result": {
                "text": "not valid ocr payload",
            }
        },
    }

    with pytest.raises(ValueError, match="not valid base64"):
        extract_iflytek_text(response)


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


def test_iflytek_ocr_config_ignores_siliconflow_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    monkeypatch.setenv("SPARKWEAVE_OCR_PROVIDER", "iflytek")
    monkeypatch.setenv("IFLYTEK_OCR_APPID", "appid")
    monkeypatch.setenv("IFLYTEK_OCR_API_KEY", "apikey")
    monkeypatch.setenv("IFLYTEK_OCR_API_SECRET", "apisecret")
    monkeypatch.setenv("IFLYTEK_OCR_URL", "https://api.siliconflow.cn/v1")

    config = XfyunOcrConfig.from_env()

    assert config is not None
    assert config.url == ocr_module.XFYUN_OCR_URL


def test_extract_siliconflow_openai_compatible_text() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": "```markdown\n# OCR\n题目：1 + 1 = 2\n```",
                }
            }
        ]
    }

    assert extract_siliconflow_text(response) == "# OCR\n题目：1 + 1 = 2"


def test_extract_siliconflow_removes_grounding_tags() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": (
                        "# 标题\n\n"
                        "<|ref|>title<|/ref|><|det|>[[1, 2, 3, 4]]<|/det|>\n"
                        "正文内容"
                    ),
                }
            }
        ]
    }

    assert extract_siliconflow_text(response) == "# 标题\n\n正文内容"


def test_siliconflow_ocr_builds_openai_compatible_vision_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from sparkweave.services import ocr as ocr_module

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "OCR 123"}}]},
                ensure_ascii=False,
            ).encode("utf-8")

    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(ocr_module, "urlopen", _fake_urlopen)
    config = SiliconFlowOcrConfig(
        api_key="sf-key",
        base_url="https://api.siliconflow.cn/v1",
        model="deepseek-ai/DeepSeek-OCR",
        prompt="只输出文字",
        timeout=12,
    )

    text = ocr_module.recognize_image_with_siliconflow(b"image", encoding="png", config=config)

    assert text == "OCR 123"
    assert captured["url"] == "https://api.siliconflow.cn/v1/chat/completions"
    assert captured["authorization"] == "Bearer sf-key"
    assert captured["timeout"] == 12
    payload = captured["payload"]
    assert payload["model"] == "deepseek-ai/DeepSeek-OCR"
    content = payload["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[0]["image_url"]["detail"] == "high"
    assert content[1] == {"type": "text", "text": "只输出文字"}
    assert payload["max_tokens"] == 8192


def test_pdf_ocr_has_no_default_page_limit(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from sparkweave.services import ocr as ocr_module

    class _FakePixmap:
        def tobytes(self, _encoding):
            return b"image"

    class _FakePage:
        def __init__(self, page_no: int):
            self.page_no = page_no

        def get_pixmap(self, *, dpi: int, alpha: bool):
            assert dpi == 200
            assert alpha is False
            return _FakePixmap()

    class _FakeDoc:
        def __iter__(self):
            return iter([_FakePage(1), _FakePage(2), _FakePage(3)])

        def close(self):
            return None

    fake_fitz = SimpleNamespace(open=lambda _path: _FakeDoc())
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)
    monkeypatch.setattr(ocr_module, "_env", lambda _name, default="": "")
    monkeypatch.setattr(
        ocr_module.XfyunOcrConfig,
        "from_env",
        lambda: XfyunOcrConfig(app_id="appid", api_key="apikey", api_secret="apisecret"),
    )

    calls: list[bytes] = []

    def _fake_recognize(image_bytes, *, encoding, config):
        calls.append(image_bytes)
        return f"page {len(calls)}"

    monkeypatch.setattr(ocr_module, "recognize_image_with_iflytek", _fake_recognize)

    result = ocr_module.ocr_pdf_with_iflytek(tmp_path / "book.pdf")

    assert len(calls) == 3
    assert "## Page 3" in result
