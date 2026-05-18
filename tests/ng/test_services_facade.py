from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sparkweave.services import paths
from sparkweave.tools.builtin import CodeExecutionTool


def test_research_checkpoint_path_uses_env_override(monkeypatch, tmp_path):
    checkpoint = tmp_path / "custom.sqlite"
    monkeypatch.setenv("SPARKWEAVE_NG_CHECKPOINT_DB", str(checkpoint))

    assert paths.get_research_checkpoint_db_path() == checkpoint.resolve()


def test_research_checkpoint_path_uses_research_workspace(monkeypatch, tmp_path):
    research_dir = tmp_path / "research"
    monkeypatch.delenv("SPARKWEAVE_NG_CHECKPOINT_DB", raising=False)

    class FakePathService:
        def get_research_dir(self) -> Path:
            return research_dir

    monkeypatch.setattr(paths, "get_path_service", lambda: FakePathService())

    assert paths.get_research_checkpoint_db_path() == (
        research_dir / "checkpoints.sqlite"
    ).resolve()


def test_ng_path_service_owns_runtime_layout(tmp_path):
    paths.PathService.reset_instance()
    try:
        service = paths.PathService.get_instance()
        service._project_root = tmp_path
        service._user_data_dir = (tmp_path / "data" / "user").resolve()

        service.ensure_all_directories()
        artifact = service.get_solve_task_dir("task-1") / "artifacts" / "plot.png"
        private = service.get_solve_task_dir("task-1") / "artifacts" / "state.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"png")
        private.write_text("{}", encoding="utf-8")

        assert paths.get_path_service() is service
        assert service.get_chat_history_db() == service.user_data_dir / "chat_history.db"
        assert service.get_research_dir() == (
            service.user_data_dir / "workspace" / "chat" / "deep_research"
        )
        assert service.get_memory_dir() == tmp_path / "data" / "memory"
        assert service.get_research_reports_dir().is_dir()
        assert service.is_public_output_path(artifact)
        assert not service.is_public_output_path(private)
        assert not service.is_public_output_path(tmp_path / "outside.png")
    finally:
        paths.PathService.reset_instance()


@pytest.mark.asyncio
async def test_code_execution_codegen_uses_ng_llm_facade(monkeypatch):
    calls: list[dict] = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return "```python\nprint(1)\n```"

    monkeypatch.setattr(
        "sparkweave.services.llm.get_llm_config",
        lambda: SimpleNamespace(
            model="demo-model",
            api_key="key",
            base_url="https://example.test/v1",
            api_version=None,
            binding="openai",
        ),
    )
    monkeypatch.setattr(
        "sparkweave.services.llm.get_token_limit_kwargs",
        lambda _model, max_tokens: {"max_tokens": max_tokens},
    )
    monkeypatch.setattr("sparkweave.services.llm.complete", fake_complete)

    code = await CodeExecutionTool()._generate_code("print one")

    assert code == "print(1)"
    assert calls[0]["model"] == "demo-model"
    assert calls[0]["max_tokens"] == 1200



