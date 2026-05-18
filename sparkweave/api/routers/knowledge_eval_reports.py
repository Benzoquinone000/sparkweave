"""RAG evaluation helpers for knowledge-base API routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sparkweave.api.routers.knowledge_models import RagEvaluationStrategyRequest
from sparkweave.services.rag_support.evaluation import Strategy, strategies_for_preset


def evaluation_strategies_or_default(
    strategies: list[RagEvaluationStrategyRequest] | None,
    preset: str | None = None,
) -> list[Strategy]:
    if not strategies:
        return strategies_for_preset(preset)

    parsed: list[Strategy] = []
    for item in strategies:
        name = item.name.strip()
        if not name:
            raise ValueError("Strategy name cannot be empty")
        parsed.append(Strategy(name=name, params=dict(item.params or {})))
    return parsed


def model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def save_latest_rag_eval_report(manager: Any, kb_name: str, report: dict[str, Any]) -> None:
    path = rag_eval_report_path(manager, kb_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def rag_eval_report_path(manager: Any, kb_name: str) -> Path:
    return manager.get_knowledge_base_path(kb_name) / "rag_eval" / "latest.json"
