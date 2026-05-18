#!/usr/bin/env python
"""Run an end-to-end RAG acceptance check through the public HTTP API.

The check follows the same path as the web UI:

1. Create a knowledge base with an uploaded document.
2. Wait for the background indexing task to finish.
3. Verify raw document inventory.
4. Verify vector rows are visible.
5. Verify RAG diagnostics are healthy.
6. Run one RAG search and require sources plus expected evidence text.

Optional: add ``--chat-check`` to also verify the chat WebSocket can use the
knowledge base with the RAG tool enabled.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime
import ipaddress
import json
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_QUESTION = "In the SparkWeave RAG acceptance fixture, who named the Quasar Lantern?"
DEFAULT_EXPECTED_KEYWORDS = ["Quasar Lantern", "Ada Lovelace"]
DEFAULT_FIXTURE_NAME = "sparkweave-rag-acceptance-fixture.md"
DEFAULT_FIXTURE_TEXT = """# SparkWeave RAG Acceptance Fixture

This document exists only to validate the SparkWeave RAG pipeline.

The verification phrase is Quasar Lantern. In this fixture, Ada Lovelace named
the Quasar Lantern during a retrieval reliability review. A correct retrieval
should surface both "Quasar Lantern" and "Ada Lovelace" from this document.

Operational expectation: after this file is uploaded, SparkWeave should create
raw document inventory, write searchable vector rows, return this document as a
source, and provide evidence text to the LLM-facing RAG tool.
"""

SUCCESS_STATES = {"complete", "completed", "done", "ready", "success"}
FAILURE_STATES = {"error", "failed", "failure", "cancelled", "canceled"}


class AcceptanceError(RuntimeError):
    """Raised when a required RAG acceptance check fails."""


@dataclass
class StepResult:
    name: str
    status: str
    details: dict[str, Any]


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _state_of(payload: dict[str, Any]) -> str:
    return str(payload.get("stage") or payload.get("status") or "").strip().lower()


def _source_count(payload: dict[str, Any]) -> int:
    explicit = _coerce_int(payload.get("source_count"))
    if explicit is not None:
        return explicit
    sources = payload.get("sources")
    return len(sources) if isinstance(sources, list) else 0


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {".txt", ".text"}:
        return "text/plain"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _json_summary(payload: Any, max_chars: int = 12000) -> Any:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return payload
    return {"truncated": True, "preview": text[:max_chars]}


class RagAcceptanceRunner:
    def __init__(self, args: argparse.Namespace, client: httpx.Client | None = None) -> None:
        self.args = args
        self.steps: list[StepResult] = []
        self.kb_name = args.kb or f"sparkweave-rag-e2e-{datetime.now():%Y%m%d%H%M%S}"
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=httpx.Timeout(args.http_timeout),
            trust_env=args.use_proxy or not _should_bypass_api_proxy(args.base_url),
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(self) -> dict[str, Any]:
        temp_dir: tempfile.TemporaryDirectory[str] | None = None
        created_by_script = False
        try:
            files, temp_dir = self._resolve_files()
            expected_keywords = self._expected_keywords(using_default_fixture=temp_dir is not None)
            self._record("configuration", "passed", {
                "base_url": self.args.base_url.rstrip("/"),
                "kb_name": self.kb_name,
                "files": [path.name for path in files],
                "provider": self.args.provider or "server-default",
                "require_vectors": self.args.require_vectors,
                "chat_check": self.args.chat_check,
                "preflight": self.args.preflight,
                "proxy_bypassed": _should_bypass_api_proxy(self.args.base_url) and not self.args.use_proxy,
            })

            if self.args.preflight:
                self._run_step("rag_preflight", self._check_preflight)

            if self.args.reuse_existing:
                self._record("knowledge_base", "passed", {
                    "mode": "reuse-existing",
                    "kb_name": self.kb_name,
                })
            else:
                created_by_script = True
                create_payload = self._run_step("create_knowledge_base", lambda: self._create_kb(files))
                task_id = str(create_payload.get("task_id") or "")
                if task_id:
                    self._run_step("wait_for_indexing", lambda: self._wait_for_progress(task_id))
                else:
                    self._record("wait_for_indexing", "passed", {"skipped": True, "reason": "no task_id"})

            document_payload = self._run_step("document_inventory", lambda: self._check_documents(files))
            vector_payload = None
            if self.args.require_vectors:
                vector_payload = self._run_step("vector_inventory", self._check_vectors)
            else:
                self._record("vector_inventory", "passed", {"skipped": True, "reason": "disabled"})

            diagnostic_payload = self._run_step("rag_diagnostics", self._check_diagnostics)
            rag_payload = self._run_step(
                "rag_search",
                lambda: self._check_rag_search(expected_keywords),
            )
            chat_payload = None
            if self.args.chat_check:
                chat_payload = self._run_step(
                    "chat_rag_tool",
                    lambda: asyncio.run(self._check_chat(expected_keywords)),
                )

            if self.args.cleanup and created_by_script:
                self._run_step("cleanup", self._delete_kb)

            return {
                "status": "passed",
                "kb_name": self.kb_name,
                "steps": [asdict(step) for step in self.steps],
                "artifacts": {
                    "documents": _json_summary(document_payload),
                    "vectors": _json_summary(vector_payload),
                    "diagnostics": _json_summary(diagnostic_payload),
                    "rag_search": _json_summary(rag_payload),
                    "chat": _json_summary(chat_payload),
                },
            }
        except Exception:
            if self.args.cleanup and created_by_script:
                try:
                    cleanup_payload = self._delete_kb()
                    self._record("cleanup", "passed", _json_summary(cleanup_payload))
                except Exception as cleanup_exc:
                    self._record("cleanup", "failed", {"error": str(cleanup_exc)})
            raise
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()
            self.close()

    def _resolve_files(self) -> tuple[list[Path], tempfile.TemporaryDirectory[str] | None]:
        if self.args.files:
            files = [Path(item).expanduser().resolve() for item in self.args.files]
            missing = [str(path) for path in files if not path.exists() or not path.is_file()]
            if missing:
                raise AcceptanceError(f"Upload file not found: {', '.join(missing)}")
            return files, None

        if self.args.reuse_existing:
            return [], None

        temp_dir = tempfile.TemporaryDirectory(prefix="sparkweave-rag-e2e-")
        fixture = Path(temp_dir.name) / DEFAULT_FIXTURE_NAME
        fixture.write_text(DEFAULT_FIXTURE_TEXT, encoding="utf-8")
        return [fixture], temp_dir

    def _expected_keywords(self, *, using_default_fixture: bool) -> list[str]:
        if self.args.expected_keywords:
            return list(self.args.expected_keywords)
        return list(DEFAULT_EXPECTED_KEYWORDS) if using_default_fixture else []

    def _run_step(self, name: str, action) -> dict[str, Any]:
        try:
            details = action()
        except Exception as exc:
            self._record(name, "failed", {"error": str(exc)})
            raise
        self._record(name, "passed", _json_summary(details))
        return details

    def _record(self, name: str, status: str, details: dict[str, Any]) -> None:
        self.steps.append(StepResult(name=name, status=status, details=details))

    def _request_json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            try:
                parsed = exc.response.json()
                detail = json.dumps(parsed, ensure_ascii=False)
            except Exception:
                pass
            raise AcceptanceError(f"{method} {path} failed with HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise AcceptanceError(f"{method} {path} failed: {exc}") from exc
        except ValueError as exc:
            raise AcceptanceError(f"{method} {path} did not return JSON") from exc
        if not isinstance(data, dict):
            raise AcceptanceError(f"{method} {path} returned non-object JSON")
        return data

    def _create_kb(self, files: list[Path]) -> dict[str, Any]:
        data = {"name": self.kb_name}
        if self.args.provider:
            data["rag_provider"] = self.args.provider
        with ExitStack() as stack:
            upload_files = [
                (
                    "files",
                    (path.name, stack.enter_context(path.open("rb")), _content_type(path)),
                )
                for path in files
            ]
            payload = self._request_json(
                "POST",
                "/api/v1/knowledge/create",
                data=data,
                files=upload_files,
            )
        if str(payload.get("name") or "") != self.kb_name:
            raise AcceptanceError(f"Create returned unexpected KB name: {payload.get('name')!r}")
        return payload

    def _wait_for_progress(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.args.timeout
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            payload = self._request_json("GET", f"/api/v1/knowledge/{self.kb_name}/progress")
            last_payload = payload
            state = _state_of(payload)
            if state in FAILURE_STATES:
                raise AcceptanceError(f"Indexing failed: {payload.get('message') or payload}")
            percent = _coerce_int(payload.get("percent")) or 0
            if state in SUCCESS_STATES or percent >= 100:
                return payload
            time.sleep(self.args.poll_interval)
        raise AcceptanceError(f"Timed out waiting for indexing task {task_id}. Last progress: {last_payload}")

    def _check_documents(self, files: list[Path]) -> dict[str, Any]:
        expected_names = {path.name for path in files}
        payload = self._poll_json(
            "GET",
            f"/api/v1/knowledge/{self.kb_name}/documents?include_vectors=true",
            lambda item: expected_names.issubset(_document_names(item)),
            "documents to appear in inventory",
        )
        documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
        if not documents:
            raise AcceptanceError("Document inventory is empty")
        missing = sorted(expected_names.difference(_document_names(payload)))
        if missing:
            raise AcceptanceError(f"Uploaded documents missing from inventory: {missing}")
        return {
            "document_count": payload.get("document_count", len(documents)),
            "vector_count": payload.get("vector_count"),
            "vectors_available": payload.get("vectors_available"),
            "documents": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "vector_count": item.get("vector_count"),
                    "content_available": item.get("content_available"),
                }
                for item in documents
                if isinstance(item, dict)
            ],
        }

    def _check_vectors(self) -> dict[str, Any]:
        payload = self._poll_json(
            "GET",
            f"/api/v1/knowledge/{self.kb_name}/vectors?limit={max(self.args.min_vectors, 5)}",
            lambda item: _vector_total(item) >= self.args.min_vectors,
            "vector rows to become visible",
        )
        if payload.get("available") is False:
            raise AcceptanceError(f"Vector inventory unavailable: {payload.get('error') or payload}")
        total = _vector_total(payload)
        if total < self.args.min_vectors:
            raise AcceptanceError(f"Expected at least {self.args.min_vectors} vector rows, got {total}")
        return {
            "total": total,
            "available": payload.get("available", True),
            "collection": payload.get("collection"),
            "sample_count": len(payload.get("chunks") or []),
        }

    def _check_diagnostics(self) -> dict[str, Any]:
        query = "true" if self.args.check_connection else "false"
        payload = self._request_json(
            "GET",
            f"/api/v1/knowledge/{self.kb_name}/diagnostics?check_connection={query}",
        )
        if str(payload.get("status") or "").lower() == "error":
            raise AcceptanceError(f"RAG diagnostics reported error: {payload.get('message') or payload}")
        provider = str(payload.get("provider") or "")
        if self.args.require_vectors and provider == "milvus":
            if payload.get("marker_present") is False:
                raise AcceptanceError("Milvus metadata marker is missing")
            if payload.get("collection_present") is False:
                raise AcceptanceError("Milvus collection is missing")
            vector_rows = _coerce_int(payload.get("vector_row_count"))
            if vector_rows is not None and vector_rows < self.args.min_vectors:
                raise AcceptanceError(f"Diagnostics saw only {vector_rows} vector rows")
        readiness = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else {}
        return {
            "status": payload.get("status"),
            "provider": provider,
            "readiness": readiness,
            "marker_present": payload.get("marker_present"),
            "collection_present": payload.get("collection_present"),
            "vector_row_count": payload.get("vector_row_count"),
            "checks": payload.get("checks", []),
        }

    def _check_preflight(self) -> dict[str, Any]:
        connection = "true" if self.args.check_connection else "false"
        docker = "true" if self.args.preflight_check_docker else "false"
        if self.args.reuse_existing:
            path = f"/api/v1/knowledge/{self.kb_name}/preflight"
        else:
            path = "/api/v1/knowledge/preflight"
        payload = self._request_json(
            "GET",
            f"{path}?check_connection={connection}&check_docker={docker}",
        )
        status = str(payload.get("status") or "").strip().lower()
        diagnostic = payload.get("diagnostic") if isinstance(payload.get("diagnostic"), dict) else {}
        readiness = diagnostic.get("readiness") if isinstance(diagnostic.get("readiness"), dict) else {}
        readiness_state = str(readiness.get("state") or "").strip().lower()
        if status == "error" or readiness_state == "error":
            label = payload.get("label") or readiness.get("label") or "RAG preflight failed"
            summary = payload.get("summary") or readiness.get("summary") or ""
            action = payload.get("primary_action") or readiness.get("primary_action") or ""
            commands = payload.get("recommended_commands") if isinstance(payload.get("recommended_commands"), list) else []
            command_hint = f" Recommended: {'; '.join(str(item) for item in commands[:3])}" if commands else ""
            raise AcceptanceError(f"{label}: {summary} {action}{command_hint}".strip())
        return {
            "status": payload.get("status"),
            "label": payload.get("label"),
            "summary": payload.get("summary"),
            "primary_action": payload.get("primary_action"),
            "docker": payload.get("docker"),
            "recommended_commands": payload.get("recommended_commands", []),
            "diagnostic": _json_summary(diagnostic, max_chars=4000),
        }

    def _check_rag_search(self, expected_keywords: list[str]) -> dict[str, Any]:
        payload = self._request_json(
            "POST",
            f"/api/v1/knowledge/{self.kb_name}/rag-test",
            json={
                "query": self.args.question,
                "provider": self.args.provider,
                "retrieval_profile": self.args.retrieval_profile,
                "retrieval_mode": self.args.retrieval_mode,
                "top_k": self.args.top_k,
                "candidate_top_k": max(self.args.top_k * 3, self.args.top_k),
                "reranker": self.args.reranker,
                "agentic_rag": self.args.agentic_rag,
                "agentic_max_context_chars": self.args.agentic_max_context_chars,
                "agentic_max_sources": self.args.agentic_max_sources,
                "agentic_min_relevant_coverage_ratio": self.args.agentic_min_relevant_coverage,
                "max_context_chars": self.args.agentic_max_context_chars,
            },
        )
        if payload.get("success") is False:
            raise AcceptanceError(f"RAG search failed: {payload.get('error') or payload}")
        sources = _source_count(payload)
        if sources < self.args.min_sources:
            raise AcceptanceError(f"Expected at least {self.args.min_sources} RAG sources, got {sources}")
        content = str(payload.get("content") or payload.get("answer") or "").strip()
        if self.args.require_content and not content:
            raise AcceptanceError("RAG search returned sources but no LLM-facing content")
        missing = _missing_keywords(payload, expected_keywords)
        if missing:
            raise AcceptanceError(f"Expected keyword(s) missing from RAG evidence: {missing}")
        return {
            "success": payload.get("success", True),
            "provider": payload.get("provider"),
            "source_count": sources,
            "content_chars": len(content),
            "retrieval_profile": payload.get("retrieval_profile"),
            "retrieval_mode": payload.get("retrieval_mode"),
            "agentic_rag": payload.get("agentic_rag"),
            "agentic_quality": payload.get("agentic_quality"),
            "matched_keywords": expected_keywords,
        }

    async def _check_chat(self, expected_keywords: list[str]) -> dict[str, Any]:
        try:
            import websockets
        except Exception as exc:  # pragma: no cover - depends on optional install
            raise AcceptanceError("Install the server extra to use --chat-check (missing websockets)") from exc

        ws_url = _chat_ws_url(self.args.base_url)
        result_text = ""
        rag_sources: list[Any] = []
        saw_rag_status = False
        deadline = time.monotonic() + self.args.chat_timeout
        async with websockets.connect(ws_url, open_timeout=self.args.http_timeout) as websocket:
            await websocket.send(
                json.dumps({
                    "message": self.args.question,
                    "session_id": None,
                    "history": [],
                    "kb_name": self.kb_name,
                    "enable_rag": True,
                    "enable_web_search": False,
                })
            )
            while time.monotonic() < deadline:
                timeout = max(0.1, deadline - time.monotonic())
                message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                payload = json.loads(str(message))
                if payload.get("type") == "status" and payload.get("stage") == "rag":
                    saw_rag_status = True
                elif payload.get("type") == "sources":
                    rag_sources = payload.get("rag") if isinstance(payload.get("rag"), list) else []
                elif payload.get("type") == "result":
                    result_text = str(payload.get("content") or "")
                    break
                elif payload.get("type") == "error":
                    raise AcceptanceError(f"Chat returned error: {payload.get('message')}")
            else:
                raise AcceptanceError("Timed out waiting for chat result")

        if not saw_rag_status:
            raise AcceptanceError("Chat did not report a RAG retrieval stage")
        if len(rag_sources) < self.args.min_sources:
            raise AcceptanceError(f"Chat returned {len(rag_sources)} RAG source(s)")
        missing = [keyword for keyword in expected_keywords if keyword.lower() not in result_text.lower()]
        if expected_keywords and missing and not _payload_contains_keywords({"sources": rag_sources}, expected_keywords):
            raise AcceptanceError(f"Chat result and sources are missing expected keyword(s): {missing}")
        return {
            "result_chars": len(result_text),
            "rag_source_count": len(rag_sources),
            "saw_rag_status": saw_rag_status,
        }

    def _poll_json(self, method: str, path: str, predicate, label: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.args.timeout
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            payload = self._request_json(method, path)
            last_payload = payload
            if predicate(payload):
                return payload
            time.sleep(self.args.poll_interval)
        raise AcceptanceError(f"Timed out waiting for {label}. Last payload: {last_payload}")

    def _delete_kb(self) -> dict[str, Any]:
        return self._request_json("DELETE", f"/api/v1/knowledge/{self.kb_name}")


def _document_names(payload: dict[str, Any]) -> set[str]:
    documents = payload.get("documents")
    if not isinstance(documents, list):
        return set()
    return {
        str(item.get("name"))
        for item in documents
        if isinstance(item, dict) and item.get("name")
    }


def _vector_total(payload: dict[str, Any]) -> int:
    total = _coerce_int(payload.get("total"))
    if total is not None:
        return total
    chunks = payload.get("chunks")
    return len(chunks) if isinstance(chunks, list) else 0


def _payload_contains_keywords(payload: dict[str, Any], keywords: Iterable[str]) -> bool:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    return all(str(keyword).lower() in text for keyword in keywords)


def _missing_keywords(payload: dict[str, Any], keywords: Iterable[str]) -> list[str]:
    text = json.dumps(payload, ensure_ascii=False, default=str).lower()
    return [str(keyword) for keyword in keywords if str(keyword).lower() not in text]


def _chat_ws_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/") + "/api/v1/chat")
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))


def _should_bypass_api_proxy(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        parsed = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith(".localhost") or host.endswith(".local")
    return parsed.is_loopback or parsed.is_private or parsed.is_link_local


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="SparkWeave API base URL.")
    parser.add_argument("--http-timeout", type=float, default=30.0, help="Per-request HTTP timeout in seconds.")
    parser.add_argument("--use-proxy", action="store_true", help="Allow HTTP(S)_PROXY for API calls. Local API URLs bypass proxies by default.")
    parser.add_argument("--timeout", type=float, default=300.0, help="Maximum wait time for async indexing.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument("--kb", help="Knowledge base name. Defaults to a unique acceptance KB.")
    parser.add_argument("--provider", help="RAG provider to pass to create/rag-test, e.g. milvus.")
    parser.add_argument("--file", dest="files", action="append", default=[], help="File to upload. Repeatable.")
    parser.add_argument("--reuse-existing", action="store_true", help="Skip create/upload and validate an existing KB.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the created KB after a successful run.")
    parser.add_argument("--question", default=DEFAULT_QUESTION, help="Question used for RAG and optional chat checks.")
    parser.add_argument("--expected-keyword", dest="expected_keywords", action="append", default=[], help="Keyword that must appear in RAG evidence. Repeatable.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-sources", type=int, default=1)
    parser.add_argument("--min-vectors", type=int, default=1)
    parser.add_argument("--retrieval-profile", default="auto")
    parser.add_argument("--retrieval-mode", default="hybrid")
    parser.add_argument("--reranker", default="keyword")
    parser.add_argument("--agentic-rag", default="auto")
    parser.add_argument("--agentic-max-context-chars", type=int, default=5000)
    parser.add_argument("--agentic-max-sources", type=int, default=8)
    parser.add_argument("--agentic-min-relevant-coverage", type=float, default=0.67)
    parser.add_argument("--no-require-vectors", dest="require_vectors", action="store_false", help="Skip vector-row assertions.")
    parser.add_argument("--no-require-content", dest="require_content", action="store_false", help="Allow RAG sources without returned content.")
    parser.add_argument("--no-check-connection", dest="check_connection", action="store_false", help="Do not ask diagnostics to connect to Milvus.")
    parser.add_argument("--no-preflight", dest="preflight", action="store_false", help="Skip the RAG runtime preflight before creating/reusing a KB.")
    parser.add_argument("--preflight-check-docker", action="store_true", help="Also ask the server to check Docker availability during preflight.")
    parser.add_argument("--chat-check", action="store_true", help="Also verify /api/v1/chat WebSocket can use RAG.")
    parser.add_argument("--chat-timeout", type=float, default=120.0)
    parser.add_argument("--json-output", type=Path, help="Write full acceptance report JSON.")
    parser.set_defaults(require_vectors=True, require_content=True, check_connection=True, preflight=True)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.reuse_existing and not args.kb:
        raise SystemExit("--reuse-existing requires --kb")
    if args.reuse_existing and args.cleanup:
        raise SystemExit("--cleanup is only allowed for KBs created by this script")
    if args.top_k < 1:
        raise SystemExit("--top-k must be >= 1")
    if args.min_sources < 0 or args.min_vectors < 0:
        raise SystemExit("--min-sources and --min-vectors must be >= 0")


def _print_report(report: dict[str, Any]) -> None:
    print(f"RAG acceptance {report['status']}: {report['kb_name']}")
    for step in report["steps"]:
        status = step["status"].upper()
        print(f"- {status}: {step['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_args(args)
    runner = RagAcceptanceRunner(args)
    try:
        report = runner.run()
    except Exception as exc:
        report = {
            "status": "failed",
            "kb_name": getattr(runner, "kb_name", args.kb or ""),
            "error": str(exc),
            "steps": [asdict(step) for step in runner.steps],
        }
        if args.json_output:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"RAG acceptance failed: {exc}", file=sys.stderr)
        for step in report["steps"]:
            print(f"- {step['status'].upper()}: {step['name']}", file=sys.stderr)
        return 1

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
