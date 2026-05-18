"""Service facades used by the next-generation runtime."""

from .code_execution import run_python_code
from .config import LLMConfig, clear_llm_config_cache, get_llm_config, reload_config
from .context import ContextBuilder, NotebookAnalysisAgent
from .math_animator import (
    load_generated_code_model,
    load_rendering_components,
    load_visual_review_components,
)
from .learning_effect import create_learning_effect_service, get_learning_effect_service
from .memory import create_memory_service, get_memory
from .notebook import create_notebook_manager, get_notebooks
from .ocr import (
    OcrUnavailable,
    is_iflytek_ocr_configured,
    ocr_pdf_with_iflytek,
    recognize_image_with_iflytek,
)
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
from .tts import (
    TtsUnavailable,
    is_iflytek_tts_configured,
    synthesize_speech_with_iflytek,
)
from .validation import validate_capability_config
from .vision import analyze_geogebra_image
from .vision_input import ImageError, resolve_image_input


async def search_arxiv_papers(*args, **kwargs):
    """Search arXiv papers without importing the optional arxiv client at service import time."""

    from .papers import search_arxiv_papers as _search_arxiv_papers

    return await _search_arxiv_papers(*args, **kwargs)


__all__ = [
    "LLMConfig",
    "ContextBuilder",
    "ImageError",
    "CompatibilityRuntimeUnavailable",
    "LegacyRuntimeUnavailable",
    "NotebookAnalysisAgent",
    "OcrUnavailable",
    "QuestionParsingUnavailable",
    "SQLiteSessionStore",
    "analyze_geogebra_image",
    "brainstorm",
    "clear_llm_config_cache",
    "create_memory_service",
    "create_learning_effect_service",
    "create_notebook_manager",
    "create_session_store",
    "create_turn_runtime_manager",
    "get_compatibility_turn_runtime_manager",
    "extract_questions_from_paper",
    "get_legacy_turn_runtime_manager",
    "get_llm_config",
    "get_learning_effect_service",
    "get_memory",
    "get_notebooks",
    "is_iflytek_ocr_configured",
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
    "synthesize_speech_with_iflytek",
    "parse_pdf_with_mineru",
    "TtsUnavailable",
    "ocr_pdf_with_iflytek",
    "is_iflytek_tts_configured",
    "recognize_image_with_iflytek",
    "validate_capability_config",
    "web_search",
]
