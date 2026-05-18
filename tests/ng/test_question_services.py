from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sparkweave.services import question as question_service


def test_load_parsed_paper_supports_nested_hybrid_auto_output(tmp_path: Path) -> None:
    paper_dir = tmp_path / "mimic_exam"
    parsed_dir = paper_dir / "hybrid_auto"
    images_dir = parsed_dir / "images"
    images_dir.mkdir(parents=True)

    (parsed_dir / "exam.md").write_text("# Exam content", encoding="utf-8")
    (parsed_dir / "exam_content_list.json").write_text(
        json.dumps([{"type": "text", "text": "Question 1"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (images_dir / "figure.png").write_text("image-bytes", encoding="utf-8")

    markdown_content, content_list, discovered_images_dir = question_service.load_parsed_paper(
        paper_dir
    )

    assert markdown_content == "# Exam content"
    assert content_list == [{"type": "text", "text": "Question 1"}]
    assert discovered_images_dir == images_dir


def test_parse_pdf_with_mineru_returns_false_when_cli_missing(monkeypatch, tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(question_service, "check_mineru_installed", lambda: None)

    assert question_service.parse_pdf_with_mineru(str(pdf_path), str(tmp_path)) is False


def test_check_mineru_installed_accepts_help_probe(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args == ["magic-pdf", "--version"]:
            return SimpleNamespace(returncode=2)
        if args == ["magic-pdf", "--help"]:
            return SimpleNamespace(returncode=0)
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.check_mineru_installed() == "magic-pdf"
    assert calls == [["magic-pdf", "--version"], ["magic-pdf", "--help"]]


def test_check_mineru_installed_falls_back_to_mineru_command(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[0] == "magic-pdf":
            raise FileNotFoundError
        if args == ["mineru", "--version"]:
            return SimpleNamespace(returncode=1)
        if args == ["mineru", "--help"]:
            return SimpleNamespace(returncode=0)
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.check_mineru_installed() == "mineru"
    assert calls == [
        ["magic-pdf", "--version"],
        ["mineru", "--version"],
        ["mineru", "--help"],
    ]


def test_check_mineru_installed_uses_configured_command(monkeypatch):
    calls: list[list[str]] = []
    configured = r"C:\Tools\MinerU\mineru.exe"

    def fake_run(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("SPARKWEAVE_MINERU_COMMAND", configured)
    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.check_mineru_installed() == configured
    assert calls == [[configured, "--version"]]


def test_check_mineru_installed_finds_current_python_scripts_dir(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    python_exe = tmp_path / "env" / "python.exe"
    expected = str(tmp_path / "env" / "Scripts" / "mineru.exe")

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[0] == expected:
            return SimpleNamespace(returncode=0)
        raise FileNotFoundError

    monkeypatch.setattr(question_service.sys, "executable", str(python_exe))
    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.check_mineru_installed() == expected
    attempted = [args[0] for args in calls]
    assert attempted[:2] == ["magic-pdf", "mineru"]
    assert attempted[-1] == expected


def test_parse_pdf_with_mineru_passes_extra_args(monkeypatch, tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        output_root = Path(args[args.index("-o") + 1])
        parsed = output_root / "exam" / "auto"
        parsed.mkdir(parents=True)
        (parsed / "exam.md").write_text("# Parsed", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setenv("SPARKWEAVE_MINERU_ARGS", "-m txt -b pipeline")
    monkeypatch.setattr(question_service, "check_mineru_installed", lambda: "mineru")
    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.parse_pdf_with_mineru(str(pdf_path), str(tmp_path)) is True
    assert calls[0][-4:] == ["-m", "txt", "-b", "pipeline"]
    assert (tmp_path / "exam" / "auto" / "exam.md").exists()


def test_parse_pdf_with_mineru_prefers_named_output_dir(monkeypatch, tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_run(args, **_kwargs):
        output_root = Path(args[args.index("-o") + 1])
        (output_root / "run.log").write_text("log", encoding="utf-8")
        (output_root / "other" / "auto").mkdir(parents=True)
        named = output_root / "exam" / "auto"
        named.mkdir(parents=True)
        (named / "exam.md").write_text("# Preferred", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(question_service, "check_mineru_installed", lambda: "mineru")
    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.parse_pdf_with_mineru(str(pdf_path), str(tmp_path)) is True
    assert (tmp_path / "exam" / "auto" / "exam.md").read_text(encoding="utf-8") == "# Preferred"
    assert not (tmp_path / "exam" / "exam").exists()
    assert not (tmp_path / "exam" / "run.log").exists()


def test_parse_pdf_with_mineru_honors_timeout(monkeypatch, tmp_path):
    pdf_path = tmp_path / "exam.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    timeouts: list[float | None] = []

    def fake_run(_args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        raise question_service.subprocess.TimeoutExpired(cmd="mineru", timeout=2.5)

    monkeypatch.setenv("SPARKWEAVE_MINERU_TIMEOUT", "2.5")
    monkeypatch.setattr(question_service, "check_mineru_installed", lambda: "mineru")
    monkeypatch.setattr(question_service.subprocess, "run", fake_run)

    assert question_service.parse_pdf_with_mineru(str(pdf_path), str(tmp_path)) is False
    assert timeouts == [2.5]


def test_extract_questions_from_paper_uses_ng_llm_facade(monkeypatch, tmp_path):
    paper_dir = tmp_path / "mimic_exam"
    images_dir = paper_dir / "images"
    images_dir.mkdir(parents=True)
    (paper_dir / "exam.md").write_text("1. What is 2+2?", encoding="utf-8")
    (images_dir / "figure.png").write_text("image-bytes", encoding="utf-8")
    calls: list[dict] = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return json.dumps(
            {
                "questions": [
                    {
                        "question_number": "1",
                        "question_text": "What is 2+2?",
                        "images": [],
                    }
                ]
            }
        )

    monkeypatch.setattr(
        question_service,
        "get_llm_config",
        lambda: SimpleNamespace(
            model="demo-model",
            api_key="key",
            base_url="https://example.test/v1",
            api_version=None,
            binding="openai",
        ),
    )
    monkeypatch.setattr(
        question_service,
        "get_token_limit_kwargs",
        lambda _model, max_tokens: {"max_tokens": max_tokens},
    )
    monkeypatch.setattr(question_service, "llm_complete", fake_complete)

    assert question_service.extract_questions_from_paper(str(paper_dir)) is True

    question_files = list(paper_dir.glob("*_questions.json"))
    assert question_files
    payload = json.loads(question_files[0].read_text(encoding="utf-8"))
    assert payload["questions"][0]["question_text"] == "What is 2+2?"
    assert calls[0]["model"] == "demo-model"
    assert calls[0]["max_tokens"] == 4096


