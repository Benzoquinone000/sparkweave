from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prepare_rag_eval_corpus.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("prepare_rag_eval_corpus", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare = _load_module()


def test_extract_text_strips_non_content() -> None:
    html = """
    <html><head><style>.x{}</style><script>alert(1)</script></head>
    <body><main><h1>Gradient Descent</h1><p>Use the negative gradient.</p></main></body></html>
    """

    text = prepare.extract_text(html, max_chars=500)

    assert "Gradient Descent" in text
    assert "negative gradient" in text
    assert "alert" not in text


def test_corpus_source_aliases_cover_ml_course_dataset() -> None:
    aliases = {
        alias
        for source in prepare.SOURCES
        for alias in source.expected_source_aliases
    }
    expected = set()
    for line in (ROOT / "docs" / "examples" / "rag_eval_dataset.ml_course.sample.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected.update(json.loads(line).get("expected_sources", []))

    assert expected <= aliases


def test_write_corpus_uses_cache_and_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    class _Response:
        text = "<html><body><h1>Title</h1><p>" + ("machine learning content " * 80) + "</p></body></html>"

        def raise_for_status(self) -> None:
            pass

    class _Client:
        calls: list[str] = []

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def get(self, url: str):
            self.calls.append(url)
            return _Response()

    monkeypatch.setattr(prepare.httpx, "Client", _Client)

    manifest = prepare.write_corpus(tmp_path, max_chars=2000, timeout=1, force=False)
    cached_manifest = prepare.write_corpus(tmp_path, max_chars=2000, timeout=1, force=False)

    assert len(manifest["sources"]) == len(prepare.SOURCES)
    assert all((tmp_path / f"{source.slug}.md").exists() for source in prepare.SOURCES)
    assert (tmp_path / "manifest.json").exists()
    assert any(not item["cached"] for item in manifest["sources"])
    assert all(item["cached"] for item in cached_manifest["sources"])
