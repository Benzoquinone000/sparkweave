from __future__ import annotations

from types import SimpleNamespace

import pytest

from sparkweave.services.notebook_summary import NotebookSummarizeAgent


@pytest.mark.asyncio
async def test_notebook_summary_uses_ng_llm_stream_and_cleans_thinking(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        "sparkweave.services.notebook_summary.get_llm_config",
        lambda: SimpleNamespace(
            model="gpt-4o-mini",
            api_key="key",
            base_url="https://example.test/v1",
            api_version=None,
            binding="openai",
            extra_headers={"x-test": "1"},
        ),
    )

    async def _fake_stream(**kwargs):
        calls.append(kwargs)
        yield "<think>hidden scratchpad</think>"
        yield "Reusable summary."

    monkeypatch.setattr("sparkweave.services.notebook_summary.llm_stream", _fake_stream)

    agent = NotebookSummarizeAgent(language="en")
    summary = await agent.summarize(
        title="Fourier draft",
        record_type="co_writer",
        user_query="Explain Fourier",
        output="Fourier transform notes",
        metadata={"source": "test"},
    )

    assert summary == "Reusable summary."
    assert calls
    assert calls[0]["model"] == "gpt-4o-mini"
    assert calls[0]["extra_headers"] == {"x-test": "1"}
    assert "Fourier draft" in calls[0]["prompt"]

