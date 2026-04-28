"""Service facades used by the next-generation runtime."""

from .code_execution import run_python_code
from .config import LLMConfig, clear_llm_config_cache, get_llm_config, reload_config
from .context import ContextBuilder, NotebookAnalysisAgent
from .math_animator import (
    load_generated_code_model,
    load_rendering_components,
    load_visual_review_components,
)
from .memory import create_memory_service, get_memory
from .notebook import create_notebook_manager, get_notebooks
from .papers import search_arxiv_papers
from .paths import get_path_service, get_research_checkpoint_db_path
from .prompting import load_prompt_hints
from .question import (
    QuestionParsingUnavailable,
    extract_questions_from_paper,
    parse_pdf_with_mineru,
)
from .rag import rag_search
from .reasoning import brainstorm, reason
from .search import web_search
from .session import (
    CompatibilityRuntimeUnavailable,
    LegacyRuntimeUnavailable,
    SQLiteSessionStore,
    create_session_store,
    create_turn_runtime_manager,
    get_compatibility_turn_runtime_manager,
    get_legacy_turn_runtime_manager,
    get_runtime_manager,
    get_session_store,
)
from .validation import validate_capability_config
from .vision import analyze_geogebra_image
from .vision_input import ImageError, resolve_image_input

__all__ = [
    "LLMConfig",
    "ContextBuilder",
    "ImageError",
    "CompatibilityRuntimeUnavailable",
    "LegacyRuntimeUnavailable",
    "NotebookAnalysisAgent",
    "QuestionParsingUnavailable",
    "SQLiteSessionStore",
    "analyze_geogebra_image",
    "brainstorm",
    "clear_llm_config_cache",
    "create_memory_service",
    "create_notebook_manager",
    "create_session_store",
    "create_turn_runtime_manager",
    "get_compatibility_turn_runtime_manager",
    "extract_questions_from_paper",
    "get_legacy_turn_runtime_manager",
    "get_llm_config",
    "get_memory",
    "get_notebooks",
    "get_path_service",
    "get_research_checkpoint_db_path",
    "get_runtime_manager",
    "get_session_store",
    "load_generated_code_model",
    "load_prompt_hints",
    "load_rendering_components",
    "load_visual_review_components",
    "rag_search",
    "reason",
    "reload_config",
    "resolve_image_input",
    "run_python_code",
    "search_arxiv_papers",
    "parse_pdf_with_mineru",
    "validate_capability_config",
    "web_search",
]
