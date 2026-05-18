"""Unified RAG service entry point."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from .agentic_explanation import attach_agentic_explanation
from .agentic_merge import fallback_search_kwargs, merge_agentic_results
from .agentic_quality import (
    agentic_relevance_report,
    attach_agentic_quality,
    build_agentic_quality_report,
)
from .agentic_repair import (
    agentic_branch_repair_indexes,
    should_accept_agentic_repair,
    should_attempt_agentic_branch_repair,
)
from .factory import DEFAULT_PROVIDER, get_pipeline, list_pipelines, normalize_provider_name
from .query_planner import RagQueryPlan, plan_rag_queries
from .query_transform import transform_rag_query
from .retrieval_policy import build_retrieval_policy


class _RAGRawLogHandler(logging.Handler):
    def __init__(self, event_sink, loop) -> None:
        super().__init__(level=logging.DEBUG)
        self._event_sink = event_sink
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        if self._event_sink is None:
            return
        try:
            module_name = getattr(record, "module_name", record.name.split(".")[-1])
            level_name = getattr(record, "display_level", record.levelname)
            message = record.getMessage()
            line = f"[{module_name}] {level_name}: {message}".strip()
            if not line:
                return

            async def _emit() -> None:
                await self._event_sink(
                    "raw_log",
                    line,
                    {
                        "trace_layer": "raw",
                        "logger_name": record.name,
                        "log_level": level_name,
                        "module_name": module_name,
                    },
                )

            self._loop.create_task(_emit())
        except Exception:
            pass


DEFAULT_KB_BASE_DIR = str(
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases"
)


def _env_value(name: str, default: str = "") -> str:
    try:
        from sparkweave.services.config import get_env_store

        return get_env_store().get(name, default)
    except Exception:
        return os.getenv(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_value(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class RAGService:
    """Unified RAG service backed by the configured vector pipeline."""

    def __init__(
        self,
        kb_base_dir: Optional[str] = None,
        provider: Optional[str] = None,  # accepted for backward compatibility
    ):
        self.logger = logging.getLogger("sparkweave.rag.service")
        self.kb_base_dir = kb_base_dir or DEFAULT_KB_BASE_DIR
        self.requested_provider = normalize_provider_name(provider) if provider else None
        self.provider = self.requested_provider or self._default_provider()
        self._pipeline = None
        self._pipelines: dict[str, Any] = {}

    @staticmethod
    def _default_provider() -> str:
        return normalize_provider_name(_env_value("RAG_PROVIDER", DEFAULT_PROVIDER))

    def _provider_for_kb(self, kb_name: str | None) -> str:
        if self.requested_provider:
            return self.requested_provider
        kb_provider = self._read_kb_provider(kb_name)
        return kb_provider or self.provider

    def _read_kb_provider(self, kb_name: str | None) -> str | None:
        if not kb_name:
            return None
        try:
            from sparkweave.knowledge.manager import KnowledgeBaseManager

            info = KnowledgeBaseManager(base_dir=self.kb_base_dir).get_info(kb_name)
        except Exception:
            return None

        metadata = info.get("metadata") if isinstance(info, dict) else None
        statistics = info.get("statistics") if isinstance(info, dict) else None
        raw_provider = None
        if isinstance(metadata, dict):
            raw_provider = metadata.get("rag_provider")
        if not raw_provider and isinstance(statistics, dict):
            raw_provider = statistics.get("rag_provider")
        return normalize_provider_name(raw_provider) if raw_provider else None

    def _get_pipeline(self, provider: str | None = None):
        resolved_provider = normalize_provider_name(provider or self.provider)
        if (
            self._pipeline is not None
            and resolved_provider == self.provider
            and not self._pipelines
        ):
            return self._pipeline
        if resolved_provider not in self._pipelines:
            self._pipelines[resolved_provider] = get_pipeline(
                resolved_provider,
                kb_base_dir=self.kb_base_dir,
            )
        return self._pipelines[resolved_provider]

    async def initialize(
        self, kb_name: str, file_paths: List[str], **kwargs
    ) -> bool:
        provider = self._provider_for_kb(kb_name)
        self.logger.info("Initializing KB '%s' with provider '%s'", kb_name, provider)
        pipeline = self._get_pipeline(provider)
        return await pipeline.initialize(
            kb_name=kb_name, file_paths=file_paths, **kwargs
        )

    async def search(
        self,
        query: str,
        kb_name: str,
        event_sink=None,
        **kwargs,
    ) -> Dict[str, Any]:
        provider = self._provider_for_kb(kb_name)
        retrieval_profile = kwargs.pop("retrieval_profile", kwargs.pop("strategy_profile", None))
        explicit_params = dict(kwargs)
        if explicit_params.get("mode") is not None and explicit_params.get("retrieval_mode") is None:
            explicit_params["retrieval_mode"] = explicit_params["mode"]
        policy = build_retrieval_policy(query, profile=retrieval_profile, explicit_params=explicit_params)
        for key, value in policy.params.items():
            kwargs.setdefault(key, value)
        if (
            explicit_params.get("top_k") is not None
            and explicit_params.get("rerank_top_n") is None
            and kwargs.get("top_k") is not None
        ):
            kwargs["rerank_top_n"] = kwargs["top_k"]
        policy_trace = policy.trace()

        mode = kwargs.pop("mode", None)
        if mode is not None:
            kwargs.setdefault("retrieval_mode", mode)
        agentic_mode = kwargs.pop("agentic_rag", kwargs.pop("agentic_mode", kwargs.pop("query_planning", None)))
        agentic_max_subqueries = kwargs.pop("agentic_max_subqueries", None)
        agentic_timeout_seconds = kwargs.pop("agentic_timeout_seconds", None)
        agentic_max_concurrency = kwargs.pop("agentic_max_concurrency", None)
        agentic_fallback_to_single = kwargs.pop("agentic_fallback_to_single", None)
        agentic_merge_options = {
            "max_context_chars": kwargs.pop("agentic_max_context_chars", None),
            "max_sources": kwargs.pop("agentic_max_sources", None),
        }
        agentic_quality_options = {
            "min_sources": kwargs.pop("agentic_min_sources", None),
            "min_coverage_ratio": kwargs.pop("agentic_min_coverage_ratio", None),
            "min_relevant_coverage_ratio": kwargs.pop("agentic_min_relevant_coverage_ratio", None),
            "min_context_chars": kwargs.pop("agentic_min_context_chars", None),
            "min_score": kwargs.pop("agentic_min_score", None),
        }
        transform_strategy = kwargs.pop("query_transform", None)
        hyde_max_chars = kwargs.pop("hyde_max_chars", None)
        hyde_timeout_seconds = kwargs.pop("hyde_timeout_seconds", None)

        with self._capture_raw_logs(event_sink):
            await self._emit_tool_event(
                event_sink,
                "status",
                f"Retrieval policy: {policy.profile}",
                {
                    **policy_trace,
                    "provider": provider,
                    "kb_name": kb_name,
                    "trace_layer": "summary",
                },
            )
            plan = await plan_rag_queries(
                query,
                mode=agentic_mode,
                max_subqueries=agentic_max_subqueries,
                timeout_seconds=agentic_timeout_seconds,
            )
            if plan.enabled:
                return await self._agentic_search(
                    query=query,
                    kb_name=kb_name,
                    provider=provider,
                    plan=plan,
                    event_sink=event_sink,
                    transform_strategy=transform_strategy,
                    hyde_max_chars=hyde_max_chars,
                    hyde_timeout_seconds=hyde_timeout_seconds,
                    search_kwargs=kwargs,
                    policy_trace=policy_trace,
                    max_concurrency=agentic_max_concurrency,
                    fallback_to_single=agentic_fallback_to_single,
                    merge_options=agentic_merge_options,
                    quality_options=agentic_quality_options,
                )

            result = await self._single_search(
                query=query,
                kb_name=kb_name,
                provider=provider,
                event_sink=event_sink,
                transform_strategy=transform_strategy,
                hyde_max_chars=hyde_max_chars,
                hyde_timeout_seconds=hyde_timeout_seconds,
                search_kwargs=kwargs,
                policy_trace=policy_trace,
            )
            result["agentic_rag"] = False
            result["query_plan"] = plan.trace()
            return result

    async def _single_search(
        self,
        *,
        query: str,
        kb_name: str,
        provider: str,
        event_sink,
        transform_strategy: str | None,
        hyde_max_chars: int | None,
        hyde_timeout_seconds: float | None,
        search_kwargs: dict[str, Any],
        policy_trace: dict[str, Any] | None = None,
        max_concurrency: int | None = None,
        fallback_to_single: Any = None,
    ) -> Dict[str, Any]:
        transformed = await transform_rag_query(
            query,
            strategy=transform_strategy,
            max_chars=hyde_max_chars,
            timeout_seconds=hyde_timeout_seconds,
        )
        kwargs = dict(search_kwargs)
        await self._emit_tool_event(
            event_sink,
            "status",
            f"Query: {query}",
            {
                "query": query,
                "retrieval_query": transformed.retrieval_query,
                "query_transform": transformed.strategy,
                "query_transform_applied": transformed.applied,
                "kb_name": kb_name,
                "trace_layer": "summary",
            },
        )
        if transformed.applied:
            await self._emit_tool_event(
                event_sink,
                "status",
                "Query transformed with HyDE before retrieval.",
                {
                    "query_transform": transformed.strategy,
                    "trace_layer": "summary",
                },
            )

        self.logger.info(f"Searching KB '{kb_name}' with query: {query[:50]}...")
        pipeline = self._get_pipeline(provider)

        await self._emit_tool_event(
            event_sink,
            "status",
            f"Retrieving from knowledge base '{kb_name}'...",
            {"provider": provider, "trace_layer": "summary"},
        )

        result = await pipeline.search(query=transformed.retrieval_query, kb_name=kb_name, **kwargs)

        result.update(transformed.trace())
        if policy_trace:
            result.update(policy_trace)
        result["query"] = query
        if "answer" not in result and "content" in result:
            result["answer"] = result["content"]
        if "content" not in result and "answer" in result:
            result["content"] = result["answer"]
        result["provider"] = provider
        if "source_count" not in result and isinstance(result.get("sources"), list):
            result["source_count"] = len(result["sources"])

        answer = result.get("answer") or result.get("content") or ""
        await self._emit_tool_event(
            event_sink,
            "status",
            f"Retrieved {len(answer)} characters of grounded context.",
            {
                "provider": provider,
                "kb_name": kb_name,
                "trace_layer": "summary",
            },
        )

        return result

    async def _agentic_search(
        self,
        *,
        query: str,
        kb_name: str,
        provider: str,
        plan: RagQueryPlan,
        event_sink,
        transform_strategy: str | None,
        hyde_max_chars: int | None,
        hyde_timeout_seconds: float | None,
        search_kwargs: dict[str, Any],
        policy_trace: dict[str, Any] | None = None,
        max_concurrency: int | None = None,
        fallback_to_single: Any = None,
        merge_options: dict[str, Any] | None = None,
        quality_options: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        await self._emit_tool_event(
            event_sink,
            "status",
            f"Agentic RAG planned {len(plan.subqueries)} focused retrieval queries.",
            {"query_plan": plan.trace(), "trace_layer": "summary"},
        )

        concurrency = _coerce_positive_int(
            max_concurrency,
            _coerce_positive_int(_env_value("RAG_AGENTIC_MAX_CONCURRENCY"), 3),
        )
        semaphore = asyncio.Semaphore(max(1, min(concurrency, max(1, len(plan.subqueries)))))
        allow_fallback = _coerce_bool(
            fallback_to_single,
            _env_bool("RAG_AGENTIC_FALLBACK_TO_SINGLE", True),
        )

        async def _run_subquery(index: int, subquery) -> dict[str, Any]:
            try:
                async with semaphore:
                    result = await self._single_search(
                        query=subquery.query,
                        kb_name=kb_name,
                        provider=provider,
                        event_sink=event_sink,
                        transform_strategy=transform_strategy,
                        hyde_max_chars=hyde_max_chars,
                        hyde_timeout_seconds=hyde_timeout_seconds,
                        search_kwargs=search_kwargs,
                        policy_trace=policy_trace,
                    )
            except Exception as exc:
                result = {
                    "query": subquery.query,
                    "answer": "",
                    "content": "",
                    "sources": [],
                    "success": False,
                    "error": str(exc),
                }
            result["subquery_index"] = index
            result["subquery_purpose"] = subquery.purpose
            return result

        results = await asyncio.gather(
            *[_run_subquery(index, subquery) for index, subquery in enumerate(plan.subqueries, start=1)]
        )

        merged = merge_agentic_results(
            query=query,
            provider=provider,
            plan=plan,
            results=results,
            search_kwargs=search_kwargs,
            merge_options=merge_options,
        )
        quality = build_agentic_quality_report(
            plan=plan,
            results=results,
            merged=merged,
            options=quality_options,
        )
        attach_agentic_quality(merged, quality)

        if allow_fallback and quality.get("needs_fallback"):
            repair_trace: list[dict[str, Any]] = []
            if should_attempt_agentic_branch_repair(quality):
                await self._emit_tool_event(
                    event_sink,
                    "status",
                    "Agentic RAG is repairing weak retrieval branches.",
                    {
                        "provider": provider,
                        "trace_layer": "summary",
                        "agentic_quality": quality,
                    },
                )
                repaired_results, repair_trace = await self._repair_agentic_branches(
                    kb_name=kb_name,
                    provider=provider,
                    plan=plan,
                    results=results,
                    quality=quality,
                    event_sink=event_sink,
                    transform_strategy=transform_strategy,
                    hyde_max_chars=hyde_max_chars,
                    hyde_timeout_seconds=hyde_timeout_seconds,
                    search_kwargs=search_kwargs,
                    policy_trace=policy_trace,
                    max_concurrency=concurrency,
                )
                if repair_trace:
                    repaired = merge_agentic_results(
                        query=query,
                        provider=provider,
                        plan=plan,
                        results=repaired_results,
                        search_kwargs=search_kwargs,
                        merge_options=merge_options,
                    )
                    repaired_quality = build_agentic_quality_report(
                        plan=plan,
                        results=repaired_results,
                        merged=repaired,
                        options=quality_options,
                    )
                    attach_agentic_quality(repaired, repaired_quality)
                    repaired["agentic_repaired"] = True
                    repaired["agentic_repair"] = {
                        "strategy": "subquery_repair",
                        "triggered_by": list(quality.get("reasons") or []),
                        "attempted_branches": len(repair_trace),
                        "accepted_branches": sum(1 for item in repair_trace if item.get("accepted")),
                        "branch_repairs": repair_trace,
                        "before_quality": quality,
                        "after_quality": repaired_quality,
                    }
                    attach_agentic_explanation(repaired, repaired_quality)
                    if not repaired_quality.get("needs_fallback"):
                        if policy_trace:
                            repaired.update(policy_trace)
                        await self._emit_tool_event(
                            event_sink,
                            "status",
                            "Agentic RAG repaired weak branches and kept the multi-query evidence.",
                            {
                                "provider": provider,
                                "trace_layer": "summary",
                                "agentic_quality": repaired_quality,
                            },
                        )
                        return repaired
                    merged = repaired
                    quality = repaired_quality

            await self._emit_tool_event(
                event_sink,
                "status",
                "Agentic RAG evidence was weak; retrying the original query with baseline retrieval.",
                {
                    "provider": provider,
                    "trace_layer": "summary",
                    "agentic_quality": quality,
                },
            )
            fallback = await self._single_search(
                query=query,
                kb_name=kb_name,
                provider=provider,
                event_sink=event_sink,
                transform_strategy="none" if transform_strategy is None else transform_strategy,
                hyde_max_chars=hyde_max_chars,
                hyde_timeout_seconds=hyde_timeout_seconds,
                search_kwargs=fallback_search_kwargs(search_kwargs),
                policy_trace=policy_trace,
            )
            fallback["agentic_rag"] = False
            fallback["agentic_fallback"] = True
            fallback["agentic_fallback_reason"] = ",".join(quality.get("reasons") or [])
            fallback["failed_query_plan"] = plan.trace()
            fallback["agentic_activity_plan"] = merged.get("agentic_activity_plan")
            fallback["agentic_evidence_groups"] = merged.get("agentic_evidence_groups", [])
            fallback["agentic_context_pack"] = merged.get("agentic_context_pack")
            fallback["subquery_results"] = merged.get("subquery_results", [])
            fallback["agentic_quality"] = quality
            fallback["agentic_repair"] = {
                "strategy": "single_search_fallback",
                "triggered_by": list(quality.get("reasons") or []),
                "branch_repairs": repair_trace,
                "fallback_source_count": fallback.get("source_count"),
                "fallback_context_chars": len(str(fallback.get("content") or fallback.get("answer") or "")),
            }
            attach_agentic_quality(fallback, quality)
            return fallback
        if policy_trace:
            merged.update(policy_trace)
        await self._emit_tool_event(
            event_sink,
            "status",
            f"Agentic RAG merged {len(merged.get('sources') or [])} sources.",
            {"provider": provider, "trace_layer": "summary"},
        )
        return merged

    async def _repair_agentic_branches(
        self,
        *,
        kb_name: str,
        provider: str,
        plan: RagQueryPlan,
        results: list[dict[str, Any]],
        quality: dict[str, Any],
        event_sink,
        transform_strategy: str | None,
        hyde_max_chars: int | None,
        hyde_timeout_seconds: float | None,
        search_kwargs: dict[str, Any],
        policy_trace: dict[str, Any] | None,
        max_concurrency: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        repair_indexes = agentic_branch_repair_indexes(quality, results)
        if not repair_indexes:
            return results, []

        limit = max(1, min(max_concurrency, len(repair_indexes)))
        semaphore = asyncio.Semaphore(limit)
        repair_kwargs = fallback_search_kwargs(search_kwargs)

        async def _repair(index: int) -> tuple[int, dict[str, Any], dict[str, Any]]:
            subquery = plan.subqueries[index]
            original = results[index]
            original_report = agentic_relevance_report(original)
            try:
                async with semaphore:
                    candidate = await self._single_search(
                        query=subquery.query,
                        kb_name=kb_name,
                        provider=provider,
                        event_sink=event_sink,
                        transform_strategy=transform_strategy,
                        hyde_max_chars=hyde_max_chars,
                        hyde_timeout_seconds=hyde_timeout_seconds,
                        search_kwargs=repair_kwargs,
                        policy_trace=policy_trace,
                    )
            except Exception as exc:
                candidate = {
                    "query": subquery.query,
                    "answer": "",
                    "content": "",
                    "sources": [],
                    "success": False,
                    "error": str(exc),
                }
            candidate["subquery_index"] = index + 1
            candidate["subquery_purpose"] = subquery.purpose
            candidate["agentic_repair_attempted"] = True
            candidate_report = agentic_relevance_report(candidate)
            accepted = should_accept_agentic_repair(
                original=original,
                candidate=candidate,
                original_report=original_report,
                candidate_report=candidate_report,
            )
            chosen = candidate if accepted else original
            if accepted:
                chosen["agentic_repair_accepted"] = True
            trace = {
                "subquery_index": index + 1,
                "query": subquery.query,
                "purpose": subquery.purpose,
                "accepted": accepted,
                "original_source_count": len(original.get("sources") or []),
                "candidate_source_count": len(candidate.get("sources") or []),
                "original_relevance_score": original_report.get("score"),
                "candidate_relevance_score": candidate_report.get("score"),
                "candidate_relevant": candidate_report.get("relevant"),
                "error": candidate.get("error") or "",
            }
            return index, chosen, trace

        repaired = list(results)
        repair_trace: list[dict[str, Any]] = []
        for index, chosen, trace in await asyncio.gather(*[_repair(index) for index in repair_indexes]):
            repaired[index] = chosen
            repair_trace.append(trace)
        repair_trace.sort(key=lambda item: int(item.get("subquery_index") or 0))
        return repaired, repair_trace

    async def _emit_tool_event(
        self,
        event_sink,
        event_type: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if event_sink is None:
            return
        await event_sink(event_type, message, metadata or {})

    def _capture_raw_logs(self, event_sink):
        import asyncio
        from contextlib import ExitStack, contextmanager

        @contextmanager
        def _manager():
            if event_sink is None:
                yield
                return

            loop = asyncio.get_running_loop()
            handler = _RAGRawLogHandler(event_sink, loop)
            handler.setLevel(logging.DEBUG)
            targets = [
                logging.getLogger(name)
                for name in (
                    "sparkweave.RAGService",
                    "sparkweave.RAGForward",
                    "sparkweave.LlamaIndexPipeline",
                    "sparkweave.rag.milvus",
                )
            ]
            with ExitStack() as stack:
                for logger in targets:
                    logger.addHandler(handler)
                    stack.callback(logger.removeHandler, handler)
                try:
                    yield
                finally:
                    handler.close()

        return _manager()

    async def delete(self, kb_name: str) -> bool:
        provider = self._provider_for_kb(kb_name)
        self.logger.info("Deleting KB '%s' with provider '%s'", kb_name, provider)
        pipeline = self._get_pipeline(provider)

        if hasattr(pipeline, "delete"):
            return await pipeline.delete(kb_name=kb_name)

        kb_dir = Path(self.kb_base_dir) / kb_name
        if kb_dir.exists():
            shutil.rmtree(kb_dir)
            self.logger.info(f"Deleted KB directory: {kb_dir}")
            return True
        return False

    async def smart_retrieve(
        self,
        context: str,
        kb_name: str,
        query_hints: Optional[List[str]] = None,
        max_queries: int = 3,
    ) -> Dict[str, Any]:
        import asyncio

        queries = query_hints if query_hints else await self._generate_queries(context, max_queries)

        tasks = [self.search(query=q, kb_name=kb_name) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        passages: list[str] = []
        all_sources: list[dict] = []
        for r in results:
            if isinstance(r, Exception):
                continue
            content = r.get("content") or r.get("answer") or ""
            if content:
                passages.append(content)
                all_sources.append({"query": r.get("query", ""), "provider": r.get("provider", "")})

        if not passages:
            return {"answer": "", "sources": []}

        aggregated = await self._aggregate(context, passages)
        return {"answer": aggregated, "sources": all_sources}

    async def _generate_queries(self, context: str, n: int) -> list[str]:
        try:
            from sparkweave.services.llm import complete

            prompt = (
                f"Generate {n} diverse search queries to retrieve information relevant "
                f"to the following context. Return ONLY the queries, one per line.\n\n"
                f"Context:\n{context[:2000]}"
            )
            raw = await complete(prompt, system_prompt="You are a search query generator.")
            lines = [
                line.strip().lstrip("0123456789.-) ")
                for line in raw.strip().split("\n")
                if line.strip()
            ]
            return lines[:n] if lines else [context[:200]]
        except Exception:
            return [context[:200]]

    async def _aggregate(self, context: str, passages: list[str]) -> str:
        try:
            from sparkweave.services.llm import complete

            combined = "\n---\n".join(passages)
            prompt = (
                "Synthesise the following retrieved passages into a concise, "
                "relevant summary for the given context.\n\n"
                f"Context:\n{context[:1000]}\n\n"
                f"Passages:\n{combined[:6000]}"
            )
            return await complete(prompt, system_prompt="You are a knowledge synthesiser.")
        except Exception:
            return "\n\n".join(passages)

    @staticmethod
    def list_providers() -> List[Dict[str, str]]:
        return list_pipelines()

    @staticmethod
    def get_current_provider() -> str:
        return normalize_provider_name(_env_value("RAG_PROVIDER", DEFAULT_PROVIDER))

    @staticmethod
    def has_provider(name: str) -> bool:
        return (name or "").strip().lower() in {
            item["id"] for item in list_pipelines()
        }

