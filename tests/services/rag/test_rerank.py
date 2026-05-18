from __future__ import annotations

import json
from types import SimpleNamespace

from sparkweave.services.rag_support.rerank import RerankConfig, normalize_reranker, rerank_nodes


def _node(text: str, score: float = 0.0):
    return SimpleNamespace(score=score, node=SimpleNamespace(text=text, node_id=text[:8], metadata={}))


def test_normalize_reranker_aliases() -> None:
    assert normalize_reranker("") == "none"
    assert normalize_reranker("off") == "none"
    assert normalize_reranker("lexical") == "keyword"
    assert normalize_reranker("bm25-lite") == "keyword"
    assert normalize_reranker("cross-encoder") == "cross_encoder"
    assert normalize_reranker("jina-rerank") == "jina"


def test_keyword_reranker_promotes_exact_concept_match() -> None:
    nodes = [
        _node("这段资料讲模型训练和优化器。"),
        _node("梯度下降沿负梯度方向更新参数，可以让损失函数下降。"),
        _node("这段资料讲数据清洗。"),
    ]

    reranked, trace = rerank_nodes(
        "为什么梯度下降要沿负梯度方向？",
        nodes,
        RerankConfig(provider="keyword", lexical_weight=0.85, vector_weight=0.15),
    )

    assert trace.applied is True
    assert trace.input_count == 3
    assert reranked[0] is nodes[1]


def test_keyword_reranker_supports_code_like_terms_and_top_n() -> None:
    nodes = [
        _node("vector push_back 会在容量不足时重新分配。"),
        _node("std::move 将对象转换为右值引用，常用于移动语义。"),
        _node("RAII 通过析构函数释放资源。"),
    ]

    reranked, trace = rerank_nodes(
        "std::move 的作用是什么？",
        nodes,
        RerankConfig(provider="keyword", top_n=1, lexical_weight=0.9, vector_weight=0.1),
    )

    assert trace.output_count == 1
    assert reranked == [nodes[1]]


def test_none_reranker_keeps_original_order_and_ignores_top_n() -> None:
    nodes = [_node("a"), _node("b")]

    reranked, trace = rerank_nodes("anything", nodes, RerankConfig(provider="none", top_n=1))

    assert trace.applied is False
    assert reranked == nodes


def test_external_reranker_uses_provider_order(monkeypatch) -> None:
    nodes = [_node("first candidate"), _node("best candidate"), _node("third candidate")]

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "results": [
                        {"index": 1, "relevance_score": 0.99},
                        {"index": 0, "relevance_score": 0.5},
                    ]
                }
            ).encode("utf-8")

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setenv("RAG_RERANKER_BASE_URL", "http://reranker.local")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    reranked, trace = rerank_nodes(
        "which candidate is best?",
        nodes,
        RerankConfig(provider="cross_encoder", top_n=2),
    )

    assert trace.applied is True
    assert trace.provider == "cross_encoder"
    assert [node.node.text for node in reranked] == ["best candidate", "first candidate"]
    assert captured["url"] == "http://reranker.local/rerank"
    assert captured["payload"]["query"] == "which candidate is best?"


def test_external_reranker_falls_back_to_keyword_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("RAG_RERANKER_BASE_URL", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    nodes = [_node("unrelated"), _node("梯度下降会更新参数")]

    reranked, trace = rerank_nodes(
        "梯度下降",
        nodes,
        RerankConfig(provider="cross_encoder", lexical_weight=0.9, vector_weight=0.1),
    )

    assert trace.provider == "cross_encoder:keyword_fallback"
    assert trace.applied is True
    assert reranked[0] is nodes[1]
