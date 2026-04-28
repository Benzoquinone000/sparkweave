from __future__ import annotations

import sys

from sparkweave.knowledge import manager as manager_module


def test_knowledge_manager_list_cli_uses_ascii_bullets(monkeypatch, capsys, tmp_path) -> None:
    class FakeManager:
        def __init__(self, base_dir: str) -> None:
            self.base_dir = base_dir

        def list_knowledge_bases(self) -> list[str]:
            return ["demo"]

        def get_default(self) -> str:
            return "demo"

    monkeypatch.setattr(manager_module, "KnowledgeBaseManager", FakeManager)
    monkeypatch.setattr(
        sys,
        "argv",
        ["kb-manager", "--base-dir", str(tmp_path), "list"],
    )

    manager_module.main()

    output = capsys.readouterr().out
    assert "  - demo (default)" in output
    assert "鈥" not in output

