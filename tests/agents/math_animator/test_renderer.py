from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from sparkweave.services.math_animator_support import renderer as renderer_module
from sparkweave.services.math_animator_support.renderer import (
    DEFAULT_RENDER_TIMEOUT_SECONDS,
    ManimRenderError,
    ManimRenderService,
)


class _FakePathService:
    def __init__(self, root: Path) -> None:
        self.user_data_dir = root

    def get_agent_dir(self, name: str) -> Path:
        return self.user_data_dir / "workspace" / "chat" / name


def _patch_path_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(renderer_module, "get_path_service", lambda: _FakePathService(tmp_path))


def test_renderer_uses_render_timeout_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_path_service(monkeypatch, tmp_path)
    monkeypatch.delenv("SPARKWEAVE_MATH_ANIMATOR_RENDER_TIMEOUT", raising=False)

    renderer = ManimRenderService("turn-1")
    assert renderer.render_timeout_seconds == DEFAULT_RENDER_TIMEOUT_SECONDS

    monkeypatch.setenv("SPARKWEAVE_MATH_ANIMATOR_RENDER_TIMEOUT", "12.5")
    renderer = ManimRenderService("turn-1")
    assert renderer.render_timeout_seconds == 12.5


@pytest.mark.asyncio
async def test_run_manim_reports_missing_python_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_path_service(monkeypatch, tmp_path)
    missing_python = tmp_path / ("missing-python.exe" if os.name == "nt" else "missing-python")
    renderer = ManimRenderService("turn-1", python_executable=str(missing_python))
    code_path = tmp_path / "scene.py"
    code_path.write_text("from manim import *\n", encoding="utf-8")

    with pytest.raises(ManimRenderError, match="Failed to start Manim process"):
        await renderer._run_manim(
            code_path=code_path,
            scene_name="MainScene",
            quality="low",
            save_last_frame=False,
        )


@pytest.mark.asyncio
async def test_run_manim_times_out_and_stops_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_path_service(monkeypatch, tmp_path)

    class _BlockingStream:
        def __init__(self, process: "_FakeProcess") -> None:
            self.process = process

        def __iter__(self) -> "_BlockingStream":
            return self

        def __next__(self) -> bytes:
            while not self.process.stopped:
                time.sleep(0.005)
            raise StopIteration

    class _FakeProcess:
        def __init__(self) -> None:
            self.stopped = False
            self.returncode: int | None = None
            self.stdout = _BlockingStream(self)
            self.stderr = _BlockingStream(self)

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.stopped = True
            self.returncode = -15

        def kill(self) -> None:
            self.stopped = True
            self.returncode = -9

        def wait(self, timeout: float | None = None) -> int:
            self.stopped = True
            if self.returncode is None:
                self.returncode = -15
            return self.returncode

    fake_process = _FakeProcess()
    monkeypatch.setattr(renderer_module.subprocess, "Popen", lambda *args, **kwargs: fake_process)

    renderer = ManimRenderService("turn-1", render_timeout_seconds=0.01)
    code_path = tmp_path / "scene.py"
    code_path.write_text("from manim import *\n", encoding="utf-8")

    with pytest.raises(ManimRenderError, match="timed out"):
        await renderer._run_manim(
            code_path=code_path,
            scene_name="MainScene",
            quality="low",
            save_last_frame=False,
        )

    assert fake_process.stopped is True
