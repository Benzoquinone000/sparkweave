from __future__ import annotations

import pytest

import sparkweave.services.solve_generation as solve_generation


class _FakeDeepSolveGraph:
    async def run(self, context, stream):  # noqa: ANN001
        assert context.active_capability == "deep_solve"
        assert context.enabled_tools == ["rag", "code_execution"]
        assert context.knowledge_bases == ["demo"]
        await stream.progress(
            "Planning",
            source="deep_solve",
            stage="planning",
            metadata={"trace_kind": "call_status"},
        )
        await stream.content("Solved", source="deep_solve", stage="writing")
        await stream.result(
            {"response": "Solved", "verification": "ok", "runtime": "langgraph"},
            source="deep_solve",
        )
        return {}


@pytest.mark.asyncio
async def test_main_solver_uses_ng_deep_solve_graph(monkeypatch, tmp_path):
    progress: list[tuple[str, dict]] = []
    traces: list[dict] = []

    monkeypatch.setattr(solve_generation, "DeepSolveGraph", _FakeDeepSolveGraph)

    solver = solve_generation.MainSolver(
        config_path="unused.yaml",
        kb_name="demo",
        output_base_dir=str(tmp_path),
        model="solver-model",
        enabled_tools=["rag", "code_execution"],
        disable_memory=True,
        max_tokens=1000,
        temperature=0.2,
    )
    solver._send_progress_update = lambda stage, payload: progress.append((stage, payload))
    solver.set_trace_callback(lambda payload: traces.append(payload))

    result = await solver.solve("Solve x^2=4")

    assert result["final_answer"] == "Solved"
    assert result["metadata"]["runtime"] == "langgraph"
    assert result["metadata"]["verification"] == "ok"
    assert result["output_dir"].startswith(str(tmp_path))
    assert progress[0][0] == "planning"
    assert progress[0][1]["message"] == "Planning"
    assert traces[0]["event"] == "llm_call"
    assert traces[0]["phase"] == "planning"
    assert traces[0]["trace_kind"] == "call_status"


def test_solver_session_manager_legacy_shape():
    manager = solve_generation.SolverSessionManager()
    session = manager.create_session(title="Demo", kb_name="kb")
    session_id = session["session_id"]
    manager.add_message(session_id=session_id, role="user", content="Q", output_dir="out")

    assert manager.get_session(session_id)["messages"][0]["output_dir"] == "out"
    assert manager.list_sessions()[0]["token_stats"]["model"] == "Unknown"
    assert manager.delete_session(session_id) is True

