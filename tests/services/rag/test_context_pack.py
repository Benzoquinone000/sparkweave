from __future__ import annotations

from types import SimpleNamespace

from sparkweave.services.rag_support.context_pack import build_context_pack


def _node(text: str, *, node_id: str, score: float = 0.8, file_name: str = "course.md"):
    return SimpleNamespace(
        score=score,
        node=SimpleNamespace(
            text=text,
            node_id=node_id,
            metadata={"file_name": file_name, "file_path": f"/kb/{file_name}", "page": 3},
        ),
    )


def test_context_pack_filters_threshold_dedups_and_adds_evidence_reason() -> None:
    nodes = [
        _node("梯度下降沿负梯度方向更新参数，目标是让损失函数下降。", node_id="a", score=0.91),
        _node("重复片段不会进入上下文。", node_id="a", score=0.9),
        _node("低分片段会被过滤。", node_id="b", score=0.2),
    ]

    pack = build_context_pack(
        query="为什么梯度下降沿负梯度方向？",
        nodes=nodes,
        max_context_chars=200,
        score_threshold=0.5,
    )

    assert pack.trace["source_count"] == 1
    assert pack.trace["skipped_duplicate"] == 1
    assert pack.trace["skipped_threshold"] == 1
    assert "负梯度" in pack.content
    assert pack.sources[0]["matched_keywords"]
    assert pack.sources[0]["evidence_reason"].startswith("命中问题关键词")
    assert pack.sources[0]["source"] == "/kb/course.md"


def test_context_pack_respects_budget() -> None:
    nodes = [
        _node("a" * 80, node_id="a"),
        _node("b" * 80, node_id="b"),
    ]

    pack = build_context_pack(query="anything", nodes=nodes, max_context_chars=50)

    assert len(pack.content) == 50
    assert pack.trace["source_count"] == 1
    assert pack.sources[0]["context_chars"] == 50


def test_context_pack_uses_similarity_reason_without_keyword_match() -> None:
    nodes = [_node("完全无关的英文字段 optimizer momentum", node_id="a", score=0.77)]

    pack = build_context_pack(query="傅里叶变换", nodes=nodes, max_context_chars=200)

    assert pack.sources[0]["matched_keywords"] == []
    assert "相似度较高" in pack.sources[0]["evidence_reason"]
