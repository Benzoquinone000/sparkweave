"""Web-search service facade for NG tools."""

from __future__ import annotations

import asyncio
from typing import Any

from sparkweave.services.search_support import (
    PROVIDER_TEMPLATES,
    SEARCH_API_KEY_ENV,
    AnswerConsolidator,
    BaseSearchProvider,
    Citation,
    SearchProvider,
    SearchResult,
    WebSearchResponse,
    get_available_providers,
    get_current_config,
    get_default_provider,
    get_provider,
    get_providers_info,
    list_providers,
)
from sparkweave.services.search_support import web_search as _sync_web_search


async def web_search(
    *,
    query: str,
    output_dir: str | None = None,
    verbose: bool = False,
    provider: str | None = None,
    consolidation_custom_template: str | None = None,
    consolidation_llm_model: str | None = None,
    **provider_kwargs: Any,
) -> Any:
    return await asyncio.to_thread(
        _sync_web_search,
        query=query,
        output_dir=output_dir,
        verbose=verbose,
        provider=provider,
        consolidation_custom_template=consolidation_custom_template,
        consolidation_llm_model=consolidation_llm_model,
        **provider_kwargs,
    )


__all__ = [
    "PROVIDER_TEMPLATES",
    "SEARCH_API_KEY_ENV",
    "AnswerConsolidator",
    "BaseSearchProvider",
    "Citation",
    "SearchProvider",
    "SearchResult",
    "WebSearchResponse",
    "get_available_providers",
    "get_current_config",
    "get_default_provider",
    "get_provider",
    "get_providers_info",
    "list_providers",
    "web_search",
]

