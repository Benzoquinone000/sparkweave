"""RAG service exports."""

from .agentic_activity import build_agentic_activity_plan
from .agentic_explanation import attach_agentic_explanation, build_agentic_explanation
from .agentic_merge import fallback_search_kwargs, merge_agentic_results
from .agentic_quality import (
    agentic_relevance_report,
    attach_agentic_quality,
    build_agentic_quality_report,
    result_has_evidence,
)
from .agentic_repair import (
    agentic_branch_repair_indexes,
    should_accept_agentic_repair,
    should_attempt_agentic_branch_repair,
)
from .evaluation import (
    DEFAULT_STRATEGIES,
    QUICK_CHECK_STRATEGIES,
    EvalRecord,
    Strategy,
    run_evaluation,
    summarize_dataset_profile,
)
from .factory import (
    DEFAULT_PROVIDER,
    LOCAL_PROVIDER,
    SUPPORTED_PROVIDERS,
    get_pipeline,
    list_pipelines,
    normalize_provider_name,
    reset_pipeline_cache,
)
from .file_routing import DocumentType, FileClassification, FileTypeRouter
from .query_planner import RagQueryPlan, RagSubQuery, plan_rag_queries
from .query_transform import QueryTransformResult, transform_rag_query
from .retrieval_policy import RetrievalPolicy, build_retrieval_policy, infer_retrieval_profile
from .service import RAGService


def __getattr__(name: str):
    """Lazy import pipeline implementation classes."""
    if name == "LlamaIndexPipeline":
        from .pipelines.llamaindex import LlamaIndexPipeline

        return LlamaIndexPipeline
    if name == "MilvusPipeline":
        from .pipelines.milvus import MilvusPipeline

        return MilvusPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RAGService",
    "build_agentic_activity_plan",
    "attach_agentic_explanation",
    "build_agentic_explanation",
    "fallback_search_kwargs",
    "merge_agentic_results",
    "agentic_relevance_report",
    "attach_agentic_quality",
    "build_agentic_quality_report",
    "result_has_evidence",
    "agentic_branch_repair_indexes",
    "should_accept_agentic_repair",
    "should_attempt_agentic_branch_repair",
    "FileTypeRouter",
    "FileClassification",
    "DocumentType",
    "Strategy",
    "EvalRecord",
    "DEFAULT_STRATEGIES",
    "QUICK_CHECK_STRATEGIES",
    "run_evaluation",
    "summarize_dataset_profile",
    "QueryTransformResult",
    "transform_rag_query",
    "RagSubQuery",
    "RagQueryPlan",
    "plan_rag_queries",
    "RetrievalPolicy",
    "build_retrieval_policy",
    "infer_retrieval_profile",
    "get_pipeline",
    "list_pipelines",
    "normalize_provider_name",
    "reset_pipeline_cache",
    "DEFAULT_PROVIDER",
    "LOCAL_PROVIDER",
    "SUPPORTED_PROVIDERS",
    "LlamaIndexPipeline",
    "MilvusPipeline",
]
