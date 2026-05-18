#!/usr/bin/env python
"""Prepare a repeatable local corpus for RAG quality evaluation.

The script downloads a small set of public machine-learning references into
``data/eval_corpora/`` and can optionally upload them through the same
knowledge-base HTTP API used by the frontend.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_OUTPUT_DIR = Path("data/eval_corpora/ml-course")
SUCCESS_STATES = {"complete", "completed", "done", "ready", "success"}
FAILURE_STATES = {"error", "failed", "failure", "cancelled", "canceled"}


@dataclass(frozen=True)
class CorpusSource:
    slug: str
    title: str
    url: str
    expected_source_aliases: tuple[str, ...]


SOURCES: tuple[CorpusSource, ...] = (
    CorpusSource(
        slug="gradient",
        title="Gradient Descent and Learning Rate",
        url="https://developers.google.com/machine-learning/crash-course/linear-regression/gradient-descent",
        expected_source_aliases=("gradient",),
    ),
    CorpusSource(
        slug="generalization",
        title="Generalization, Overfitting, and Dataset Splits",
        url="https://developers.google.com/machine-learning/crash-course/overfitting/overfitting",
        expected_source_aliases=("generalization", "bias_variance"),
    ),
    CorpusSource(
        slug="regularization",
        title="Regularization",
        url="https://developers.google.com/machine-learning/crash-course/overfitting/regularization",
        expected_source_aliases=("regularization",),
    ),
    CorpusSource(
        slug="logistic",
        title="Logistic Regression and Cross Entropy",
        url="https://developers.google.com/machine-learning/crash-course/logistic-regression/sigmoid-function",
        expected_source_aliases=("logistic", "cross_entropy"),
    ),
    CorpusSource(
        slug="metrics",
        title="Classification Metrics",
        url="https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall",
        expected_source_aliases=("metrics",),
    ),
    CorpusSource(
        slug="linear_regression",
        title="Linear Models in scikit-learn",
        url="https://scikit-learn.org/stable/modules/linear_model.html",
        expected_source_aliases=("linear_regression", "sklearn"),
    ),
    CorpusSource(
        slug="svm",
        title="Support Vector Machines in scikit-learn",
        url="https://scikit-learn.org/stable/modules/svm.html",
        expected_source_aliases=("svm",),
    ),
    CorpusSource(
        slug="pca",
        title="PCA and Matrix Decomposition in scikit-learn",
        url="https://scikit-learn.org/stable/modules/decomposition.html#pca",
        expected_source_aliases=("pca",),
    ),
    CorpusSource(
        slug="kmeans",
        title="K-Means Clustering in scikit-learn",
        url="https://scikit-learn.org/stable/modules/clustering.html#k-means",
        expected_source_aliases=("kmeans",),
    ),
    CorpusSource(
        slug="decision_tree",
        title="Decision Trees in scikit-learn",
        url="https://scikit-learn.org/stable/modules/tree.html",
        expected_source_aliases=("decision_tree",),
    ),
    CorpusSource(
        slug="naive_bayes",
        title="Naive Bayes in scikit-learn",
        url="https://scikit-learn.org/stable/modules/naive_bayes.html",
        expected_source_aliases=("naive_bayes",),
    ),
)


class MainTextExtractor(HTMLParser):
    """Small stdlib HTML-to-text extractor, good enough for docs pages."""

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag in {"h1", "h2", "h3", "p", "li", "tr", "pre", "code", "br"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag in {"h1", "h2", "h3", "p", "li", "tr", "pre"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        text = " ".join(self._parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)


def extract_text(html: str, *, max_chars: int) -> str:
    parser = MainTextExtractor()
    parser.feed(html)
    text = parser.text()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    line_trimmed = truncated.rsplit("\n", 1)[0] if "\n" in truncated else truncated
    return line_trimmed if len(line_trimmed) >= 500 else truncated


def write_corpus(output_dir: Path, *, max_chars: int, timeout: float, force: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "name": "ml-course",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [],
    }
    with httpx.Client(timeout=httpx.Timeout(timeout), follow_redirects=True) as client:
        for source in SOURCES:
            target = output_dir / f"{source.slug}.md"
            if target.exists() and not force:
                manifest["sources"].append({**asdict(source), "path": str(target), "cached": True})
                continue
            response = client.get(source.url)
            response.raise_for_status()
            text = extract_text(response.text, max_chars=max_chars)
            if len(text) < 500:
                raise RuntimeError(f"Downloaded source is unexpectedly short: {source.url}")
            body = "\n".join([
                f"# {source.title}",
                "",
                f"Source URL: {source.url}",
                f"Expected source aliases: {', '.join(source.expected_source_aliases)}",
                "",
                text,
                "",
            ])
            target.write_text(body, encoding="utf-8")
            manifest["sources"].append({
                **asdict(source),
                "path": str(target),
                "chars": len(body),
                "cached": False,
            })
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _knowledge_bases(client: httpx.Client) -> set[str]:
    response = client.get("/api/v1/knowledge/list")
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        items = payload.get("knowledge_bases") or payload.get("value") or []
    else:
        items = payload
    return {str(item.get("name")) for item in items if isinstance(item, dict) and item.get("name")}


def _wait_for_indexing(client: httpx.Client, kb_name: str, *, timeout: float) -> None:
    deadline = time.time() + timeout
    last: tuple[str, str, Any] | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/knowledge/{kb_name}/progress")
        response.raise_for_status()
        payload = response.json()
        state = str(payload.get("stage") or payload.get("status") or "").strip().lower()
        message = str(payload.get("message") or "")
        percent = payload.get("percent")
        current = (state, message, percent)
        if current != last:
            print(f"[prepare-rag-eval] progress {state or '-'} {percent or '-'}% {message}")
            last = current
        if state in SUCCESS_STATES:
            return
        if state in FAILURE_STATES:
            raise RuntimeError(f"Indexing failed for {kb_name}: {payload}")
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for {kb_name} indexing.")


def upload_corpus(
    output_dir: Path,
    *,
    kb_name: str,
    base_url: str,
    provider: str,
    recreate: bool,
    wait: bool,
    wait_timeout: float,
) -> dict[str, Any]:
    files = sorted(output_dir.glob("*.md"))
    if not files:
        raise RuntimeError(f"No Markdown corpus files found in {output_dir}")

    with httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(180.0)) as client:
        existing = _knowledge_bases(client)
        if kb_name in existing and recreate:
            delete_response = client.delete(f"/api/v1/knowledge/{kb_name}")
            delete_response.raise_for_status()
            existing.remove(kb_name)
        endpoint = "/api/v1/knowledge/create" if kb_name not in existing else f"/api/v1/knowledge/{kb_name}/upload"
        data = {"rag_provider": provider}
        if kb_name not in existing:
            data["name"] = kb_name

        handles = []
        try:
            multipart = []
            for path in files:
                handle = path.open("rb")
                handles.append(handle)
                multipart.append(("files", (path.name, handle, "text/markdown")))
            response = client.post(endpoint, data=data, files=multipart)
            response.raise_for_status()
            payload = response.json()
        finally:
            for handle in handles:
                handle.close()

        if wait:
            _wait_for_indexing(client, kb_name, timeout=wait_timeout)
        return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-chars-per-source", type=int, default=30000)
    parser.add_argument("--http-timeout", type=float, default=30.0)
    parser.add_argument("--force", action="store_true", help="Redownload sources even when local files exist.")
    parser.add_argument("--upload", action="store_true", help="Upload the prepared corpus through the knowledge API.")
    parser.add_argument("--kb", default="ml-course")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--provider", default="milvus")
    parser.add_argument("--recreate", action="store_true", help="Delete the target KB before uploading.")
    parser.add_argument("--wait", action="store_true", help="Wait for indexing after upload.")
    parser.add_argument("--wait-timeout", type=float, default=420.0)
    parser.add_argument("--json-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = write_corpus(
            args.output_dir,
            max_chars=args.max_chars_per_source,
            timeout=args.http_timeout,
            force=args.force,
        )
        result: dict[str, Any] = {"corpus": manifest}
        print(f"[prepare-rag-eval] wrote {len(manifest['sources'])} source file(s) to {args.output_dir}")
        if args.upload:
            upload_result = upload_corpus(
                args.output_dir,
                kb_name=args.kb,
                base_url=args.base_url,
                provider=args.provider,
                recreate=args.recreate,
                wait=args.wait,
                wait_timeout=args.wait_timeout,
            )
            result["upload"] = upload_result
            print(f"[prepare-rag-eval] uploaded corpus to KB {args.kb}")
        if args.json_output:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"RAG eval corpus preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
