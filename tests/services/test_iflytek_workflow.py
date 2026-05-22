from __future__ import annotations

import json
from typing import Any

import pytest

from sparkweave.services.iflytek_workflow import (
    IflytekWorkflowConfig,
    IflytekWorkflowUnavailable,
    call_iflytek_workflow,
    parse_iflytek_workflow_response,
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
async def test_iflytek_workflow_posts_official_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse({"choices": [{"message": {"content": "工作流结果"}}], "usage": {"total_tokens": 8}})

    monkeypatch.setattr("sparkweave.services.iflytek_workflow.urlopen", _fake_urlopen)

    config = IflytekWorkflowConfig(
        api_key="key",
        api_secret="secret",
        flow_id="flow-1",
        url="https://example.test/workflow/v1/chat/completions",
        timeout=12,
    )
    result = await call_iflytek_workflow("生成学习资源", config=config, parameters={"course_id": "AIED301"})

    assert result["content"] == "工作流结果"
    assert result["usage"] == {"total_tokens": 8}
    assert captured["url"] == "https://example.test/workflow/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer key:secret"
    assert captured["payload"]["flow_id"] == "flow-1"
    assert captured["payload"]["parameters"]["AGENT_USER_INPUT"] == "生成学习资源"
    assert captured["payload"]["parameters"]["course_id"] == "AIED301"
    assert captured["payload"]["stream"] is False
    assert captured["timeout"] == 12


def test_iflytek_workflow_parses_sse_chunks() -> None:
    parsed = parse_iflytek_workflow_response(
        'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"第二段"}}],"usage":{"total_tokens":6}}\n\n'
        "data: [DONE]\n\n"
    )

    assert parsed["content"] == "第一段第二段"
    assert parsed["usage"] == {"total_tokens": 6}
    assert len(parsed["events"]) == 2


def test_iflytek_workflow_reports_provider_error() -> None:
    with pytest.raises(IflytekWorkflowUnavailable, match="workflow error 10019"):
        parse_iflytek_workflow_response('{"code":10019,"message":"invalid flow"}')
