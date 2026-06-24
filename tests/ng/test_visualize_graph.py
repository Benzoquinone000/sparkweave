from __future__ import annotations

import json

import pytest

from sparkweave.core.contracts import StreamBus, StreamEventType, UnifiedContext
from sparkweave.graphs.visualize import VisualizeGraph


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    async def ainvoke(self, _messages):
        from langchain_core.messages import AIMessage

        return AIMessage(content=self.responses.pop(0))


@pytest.mark.asyncio
async def test_visualize_graph_generates_viewer_ready_svg_result():
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '{"render_type":"svg","description":"A simple concept map","data_description":"Two connected ideas","chart_type":"","visual_elements":["nodes","arrow"],"rationale":"custom schematic"}',
                '```svg\n<svg viewBox="0 0 200 100"><circle cx="50" cy="50" r="20"/></svg>\n```',
                '{"optimized_code":"<svg viewBox=\\"0 0 200 100\\"><circle cx=\\"50\\" cy=\\"50\\" r=\\"20\\"/><text x=\\"90\\" y=\\"55\\">Idea</text></svg>","changed":true,"review_notes":"Added label."}',
            ]
        )
    )
    context = UnifiedContext(
        user_message="Draw a small concept map",
        active_capability="visualize",
        config_overrides={"render_mode": "svg"},
    )

    state = await graph.run(context, bus)

    assert state["visualization_analysis"]["render_type"] == "svg"
    assert state["visualization_review"]["changed"] is True
    assert state["final_answer"].startswith("```svg")
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    assert len(result_events) == 1
    metadata = result_events[0].metadata
    assert metadata["render_type"] == "svg"
    assert not metadata["response"].startswith("```")
    assert metadata["code"]["language"] == "svg"
    assert metadata["code"]["content"].startswith("<svg")
    assert metadata["review"]["review_notes"] == "Added label."


@pytest.mark.asyncio
async def test_visualize_graph_strips_inline_svg_fence():
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '{"render_type":"svg","description":"Inline SVG","data_description":"","chart_type":"","visual_elements":["triangle"],"rationale":"custom schematic"}',
                '```svg <svg viewBox="0 0 20 20"><path d="M0 20 L10 0 L20 20"/></svg> ```',
                '{"optimized_code":"","changed":false,"review_notes":"Looks renderable."}',
            ]
        )
    )
    context = UnifiedContext(
        user_message="Draw a triangle",
        active_capability="visualize",
        config_overrides={"render_mode": "svg"},
    )

    state = await graph.run(context, bus)
    metadata = [event for event in bus._history if event.type == StreamEventType.RESULT][0].metadata

    assert state["visualization_code"].startswith("<svg")
    assert metadata["code"]["content"].startswith("<svg")
    assert "```" not in metadata["code"]["content"]


@pytest.mark.asyncio
async def test_visualize_graph_forces_render_mode_and_generates_chartjs():
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '{"render_type":"svg","description":"Quarterly revenue","data_description":"Q1 to Q3","chart_type":"bar","visual_elements":["bars"],"rationale":"model guessed wrong"}',
                json.dumps(
                    {
                        "type": "bar",
                        "data": {
                            "labels": ["Q1", "Q2", "Q3"],
                            "datasets": [{"label": "Revenue", "data": [4, 6, 7]}],
                        },
                    }
                ),
                '{"optimized_code":"","changed":false,"review_notes":"Looks renderable."}',
            ]
        )
    )
    context = UnifiedContext(
        user_message="Make a bar chart of revenue by quarter",
        active_capability="visualize",
        config_overrides={"render_mode": "chartjs"},
    )

    state = await graph.run(context, bus)

    assert state["visualization_analysis"]["render_type"] == "chartjs"
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    metadata = result_events[0].metadata
    assert metadata["render_type"] == "chartjs"
    assert metadata["code"]["language"] == "javascript"
    assert metadata["review"]["validation"]["passed"] is True
    assert json.loads(metadata["code"]["content"])["type"] == "bar"
    assert any(event.type == StreamEventType.CONTENT for event in bus._history)


@pytest.mark.asyncio
async def test_visualize_graph_repairs_chartjs_from_validation_feedback():
    bus = StreamBus()
    fixed_chart = {
        "type": "bar",
        "data": {
            "labels": ["Q1", "Q2", "Q3"],
            "datasets": [{"label": "Revenue", "data": [4, 6, 7]}],
        },
        "options": {"responsive": True},
    }
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '{"render_type":"chartjs","description":"Quarterly revenue","data_description":"Q1 to Q3","chart_type":"bar","visual_elements":["bars"],"rationale":"numeric comparison"}',
                "```javascript\n{ type: 'bar', data: { labels: ['Q1','Q2','Q3'], datasets: [{ label: 'Revenue', data: [4, 6, 7] }] } }\n```",
                '{"optimized_code":"","changed":false,"review_notes":"Looks renderable."}',
                json.dumps({"code": json.dumps(fixed_chart), "repair_notes": "Converted JS object literal to strict JSON."}),
            ]
        )
    )
    context = UnifiedContext(
        user_message="Make a bar chart of revenue by quarter",
        active_capability="visualize",
        config_overrides={"render_mode": "chartjs"},
    )

    await graph.run(context, bus)

    metadata = [event for event in bus._history if event.type == StreamEventType.RESULT][0].metadata
    assert metadata["review"]["repair_attempts"] == 1
    assert metadata["review"]["repair_history"][0]["passed"] is True
    assert metadata["validation"]["passed"] is True
    assert json.loads(metadata["code"]["content"])["data"]["labels"] == ["Q1", "Q2", "Q3"]
    assert any(
        event.type == StreamEventType.OBSERVATION
        and event.metadata.get("trace_kind") == "validation"
        and event.metadata.get("passed") is False
        for event in bus._history
    )


@pytest.mark.asyncio
async def test_visualize_graph_forces_render_mode_and_generates_mermaid():
    bus = StreamBus()
    graph = VisualizeGraph(
        model=FakeModel(
            [
                '{"render_type":"svg","description":"RAG flow","data_description":"Question to answer","chart_type":"flowchart","visual_elements":["steps"],"rationale":"model guessed wrong"}',
                "```mermaid\nflowchart TD\n  A[Question] --> B[Retrieve]\n  B --> C[Answer]\n```",
                '{"optimized_code":"","changed":false,"review_notes":"Mermaid syntax is renderable."}',
            ]
        )
    )
    context = UnifiedContext(
        user_message="Make a flowchart of a RAG pipeline",
        active_capability="visualize",
        config_overrides={"render_mode": "mermaid"},
    )

    state = await graph.run(context, bus)

    assert state["visualization_analysis"]["render_type"] == "mermaid"
    result_events = [event for event in bus._history if event.type == StreamEventType.RESULT]
    metadata = result_events[0].metadata
    assert metadata["render_type"] == "mermaid"
    assert metadata["code"]["language"] == "mermaid"
    assert metadata["code"]["content"].startswith("flowchart TD")
    assert "B --> C" in metadata["code"]["content"]


@pytest.mark.asyncio
async def test_visualize_graph_repairs_relation_map_mindmap_to_flowchart():
    bus = StreamBus()
    fixed = """flowchart TD
  C["深度学习入门"]
  C --> A["核心概念"]
  C --> B["关键步骤"]
  C --> D["常见混淆点"]
  C --> R["读图指引：概念 → 步骤 → 混淆"]
  A --> A1["神经元 / 权重 / 偏置"]
  A --> A2["激活函数 / 损失函数"]
  B --> B1["前向传播"]
  B1 --> B2["计算损失"]
  B2 --> B3["反向传播"]
  B3 --> B4["梯度下降更新参数"]
  D --> D1["反向传播不是梯度下降"]
  D --> D2["过拟合不是欠拟合"]
  A2 -.影响训练效果.-> B2
  B3 -.计算梯度.-> B4"""
    graph = VisualizeGraph(
        model=FakeModel(
            [
                json.dumps(
                    {
                        "render_type": "mermaid",
                        "description": "中心是深度学习入门，向外辐射核心概念、关键步骤、常见混淆点。",
                        "data_description": "以 mindmap 组织深度学习入门核心知识。",
                        "chart_type": "mindmap",
                        "visual_elements": ["核心概念", "关键步骤", "常见混淆点"],
                        "rationale": "概念关系图",
                    },
                    ensure_ascii=False,
                ),
                """```mermaid
mindmap
  root((深度学习入门 dl1))
    核心概念
    关键步骤
    常见混淆点
    读图指引
      从中心向外：概念 → 步骤 → 混淆
```""",
                '{"optimized_code":"","changed":false,"review_notes":"Looks renderable."}',
                json.dumps({"code": fixed, "repair_notes": "Rewrote hierarchical mindmap as a relationship flowchart."}, ensure_ascii=False),
            ]
        )
    )
    context = UnifiedContext(
        user_message="请为「dl1」生成一张面向初学者的学习图解。重点画出概念关系、关键步骤、常见混淆点，并用一句话说明怎么读图。",
        active_capability="visualize",
        config_overrides={"render_mode": "mermaid"},
    )

    await graph.run(context, bus)

    metadata = [event for event in bus._history if event.type == StreamEventType.RESULT][0].metadata
    assert metadata["review"]["repair_attempts"] == 1
    assert metadata["review"]["repair_history"][0]["passed"] is True
    assert metadata["validation"]["passed"] is True
    assert metadata["code"]["content"].startswith("flowchart TD")
    assert "读图指引" in metadata["code"]["content"]
    assert "核心概念" in metadata["code"]["content"]
    assert "关键步骤" in metadata["code"]["content"]
    assert "常见混淆点" in metadata["code"]["content"]
    assert "mindmap" not in metadata["code"]["content"]
    assert any(
        event.type == StreamEventType.OBSERVATION
        and event.metadata.get("trace_kind") == "validation"
        and event.metadata.get("passed") is False
        for event in bus._history
    )

