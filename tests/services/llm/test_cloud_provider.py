"""Tests for NG LLM SDK executor helpers."""

from __future__ import annotations

from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch
import pytest

from sparkweave.services import llm
from sparkweave.services.llm import LLMAPIError


class _FakeCompletions:
    def __init__(self, result: object) -> None:
        self.result = result

    async def create(self, **_kwargs: object) -> object:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _FakeClient:
    result: object = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
    )

    def __init__(self, **_kwargs: object) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(self.result))


class _AsyncStream:
    def __init__(self, items: list[object]) -> None:
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> object:
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


def _patch_client(monkeypatch: MonkeyPatch, result: object) -> None:
    _FakeClient.result = result
    monkeypatch.setattr(llm, "_client_kwargs", lambda **_kwargs: (_FakeClient, {}))


@pytest.mark.asyncio
async def test_sdk_complete_extracts_message_content(monkeypatch: MonkeyPatch) -> None:
    """SDK complete should parse message content from OpenAI-style responses."""
    _patch_client(
        monkeypatch,
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]),
    )

    result = await llm.sdk_complete(
        prompt="hello",
        system_prompt="sys",
        model="gpt-test",
        api_key="",
        base_url="https://api.openai.com/v1",
        api_version=None,
        provider_name="openai",
        messages=None,
        extra_headers={},
        reasoning_effort=None,
        kwargs={},
    )

    assert result == "ok"


@pytest.mark.asyncio
async def test_sdk_stream_yields_delta_content(monkeypatch: MonkeyPatch) -> None:
    """SDK stream should yield delta content from streamed chunks."""
    stream_result = _AsyncStream(
        [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hi"))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="!"))]),
        ]
    )
    _patch_client(monkeypatch, stream_result)

    chunks = []
    async for chunk in llm.sdk_stream(
        prompt="hello",
        system_prompt="sys",
        model="gpt-test",
        api_key="",
        base_url="https://api.openai.com/v1",
        api_version=None,
        provider_name="openai",
        messages=None,
        extra_headers={},
        reasoning_effort=None,
        kwargs={},
    ):
        chunks.append(chunk)

    assert "".join(chunks) == "hi!"


@pytest.mark.asyncio
async def test_sdk_complete_propagates_api_error(monkeypatch: MonkeyPatch) -> None:
    """SDK complete should propagate typed NG LLM errors."""
    _patch_client(monkeypatch, LLMAPIError("boom", status_code=500, provider="openai"))

    with pytest.raises(LLMAPIError):
        await llm.sdk_complete(
            prompt="hello",
            system_prompt="sys",
            model="gpt-test",
            api_key="",
            base_url="https://api.openai.com/v1",
            api_version=None,
            provider_name="openai",
            messages=None,
            extra_headers={},
            reasoning_effort=None,
            kwargs={},
        )


@pytest.mark.asyncio
async def test_fetch_models(monkeypatch: MonkeyPatch) -> None:
    """Fetch models should parse ids from OpenAI-compatible model payloads."""

    class _FakeModels:
        async def list(self) -> object:
            return SimpleNamespace(
                data=[
                    SimpleNamespace(id="m1"),
                    SimpleNamespace(id="m2"),
                ]
            )

    class _FakeOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            self.models = _FakeModels()

    monkeypatch.setattr("openai.AsyncOpenAI", _FakeOpenAI)

    models = await llm.fetch_models("openai", "https://api.openai.com/v1")

    assert models == ["m1", "m2"]

