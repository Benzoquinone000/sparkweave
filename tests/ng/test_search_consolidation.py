from sparkweave.services.search_support.consolidation import AnswerConsolidator
from sparkweave.services.search_support.types import SearchResult, WebSearchResponse


def test_jina_template_slices_metadata_items_safely():
    response = WebSearchResponse(
        query="graph tutoring",
        answer="",
        provider="jina",
        search_results=[
            SearchResult(
                title="LangGraph tutorial",
                url="https://example.test/langgraph",
                snippet="A tutorial about graphs.",
                content="Long form tutorial content.",
                attributes={"date": "2026-01-01", "tokens": 1200},
            )
        ],
        metadata={
            "links": {f"link-{index}": f"https://example.test/{index}" for index in range(12)},
            "images": {f"image-{index}": f"https://example.test/{index}.png" for index in range(7)},
        },
    )

    result = AnswerConsolidator().consolidate(response)

    assert "Extracted Links" in result.answer
    assert "link-0" in result.answer
    assert "link-10" not in result.answer
    assert "Images Found" in result.answer
    assert "image-0" in result.answer
    assert "image-5" not in result.answer


def test_jina_template_ignores_non_mapping_metadata_items():
    response = WebSearchResponse(
        query="graph tutoring",
        answer="",
        provider="jina",
        search_results=[
            SearchResult(
                title="LangGraph tutorial",
                url="https://example.test/langgraph",
                snippet="A tutorial about graphs.",
            )
        ],
        metadata={"links": ["not", "a", "mapping"], "images": None},
    )

    result = AnswerConsolidator().consolidate(response)

    assert "Search Results for" in result.answer
    assert "Extracted Links" not in result.answer
    assert "Images Found" not in result.answer

