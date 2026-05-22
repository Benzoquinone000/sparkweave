from __future__ import annotations

from sparkweave.core.contracts import UnifiedContext
from sparkweave.runtime.capability_router import LearningCapabilityRouter


def test_router_forced_delegate_to_specialist() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="普通问题",
            config_overrides={"delegate_capability": "deep_solve"},
        )
    )

    assert decision.capability == "deep_solve"
    assert decision.delegates is True
    assert decision.confidence == 1.0


def test_router_keeps_video_generation_out_of_video_search_tool() -> None:
    router = LearningCapabilityRouter()

    search = router.decide(UnifiedContext(user_message="帮我找一个视频讲解梯度下降"))
    generation = router.decide(UnifiedContext(user_message="请生成一个视频讲解梯度下降"))

    assert search.capability == "chat"
    assert search.direct_tool == "external_video_search"
    assert generation.capability == "math_animator"


def test_router_distinguishes_image_search_from_image_generation() -> None:
    router = LearningCapabilityRouter()

    search = router.decide(UnifiedContext(user_message="帮我找几张梯度下降示意图"))
    generation = router.decide(UnifiedContext(user_message="请画一个梯度下降流程图"))

    assert search.capability == "chat"
    assert search.direct_tool == "external_image_search"
    assert generation.capability == "visualize"


def test_router_uses_profile_hints_for_next_step() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="继续学习",
            metadata={
                "learner_profile_context": {
                    "text": "当前在学习梯度下降。",
                    "hints": {
                        "current_focus": "梯度下降",
                        "preferred_resource": "公开视频",
                        "weak_points": ["学习率含义"],
                        "next_action": {
                            "title": "精选公开视频",
                            "suggested_prompt": "找一个梯度下降公开课视频",
                        },
                    },
                }
            },
        )
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == "external_video_search"
    assert decision.config
    assert decision.config["profile_guided"] is True
    assert decision.config["topic"] == "找一个梯度下降公开课视频"
    assert decision.config["learner_hints"]["weak_points"] == ["学习率含义"]


def test_router_builds_strict_llm_classifier_prompt() -> None:
    router = LearningCapabilityRouter()
    prior = router.decide(UnifiedContext(user_message="帮我安排一下梯度下降"))

    system, user = router.build_llm_classifier_prompt(
        UnifiedContext(
            user_message="帮我安排一下梯度下降",
            enabled_tools=["rag", "web_search"],
            knowledge_bases=["ml-course"],
            metadata={
                "learner_profile_context": {
                    "hints": {
                        "current_focus": "梯度下降",
                        "weak_points": ["学习率含义"],
                    }
                }
            },
        ),
        prior,
    )

    assert "Return strict JSON only" in system
    assert "external_video_search" in system
    assert "external_image_search" in system
    assert "Find a diagram reference for backpropagation" in system
    assert '"direct_tool": "external_video_search | external_image_search | null"' in system
    assert '"user_message": "帮我安排一下梯度下降"' in user
    assert '"knowledge_bases": [' in user
    assert "学习率含义" in user


def test_router_keeps_canvas_editing_in_chat() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="帮我润色这份学习计划",
            metadata={
                "canvas_context": {
                    "title": "梯度下降学习计划",
                    "content": "# 梯度下降学习计划\n\n- 先看图解，再做练习。",
                }
            },
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""


def test_router_routes_document_drafts_to_chat_canvas_tool() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="请写一份梯度下降学习计划草稿",
            enabled_tools=["rag"],
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""
    assert decision.tools
    assert decision.tools[0] == "canvas"
    assert "rag" in decision.tools


def test_router_respects_no_tools_constraint() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="直接回答什么是梯度下降，不要用工具",
            enabled_tools=["canvas", "rag", "web_search"],
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""
    assert decision.tools == []


def test_router_respects_no_canvas_constraint_for_document_draft() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="请写一份梯度下降学习计划，不要打开画布",
            enabled_tools=["canvas", "rag", "web_search"],
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""
    assert decision.tools == ["rag", "web_search"]


def test_router_respects_no_canvas_constraint_for_normal_chat() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="详细解释梯度下降，不要打开画布",
            enabled_tools=["canvas", "rag", "web_search"],
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""
    assert decision.tools == ["rag", "web_search"]


def test_router_respects_no_retrieval_for_external_resource_requests() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="Find a public video about gradient descent, no search",
            enabled_tools=["canvas", "rag", "web_search", "external_video_search", "code_execution"],
        )
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == ""
    assert decision.tools == ["canvas", "code_execution"]


def test_router_respects_no_retrieval_for_research_requests() -> None:
    router = LearningCapabilityRouter()
    decision = router.decide(
        UnifiedContext(
            user_message="Plan a machine learning study path without web",
            enabled_tools=["canvas", "rag", "web_search", "paper_search", "reason"],
        )
    )

    assert decision.capability == "chat"
    assert decision.delegates is False
    assert decision.direct_tool == ""
    assert decision.tools == ["canvas", "reason"]


def test_router_llm_payload_cannot_override_no_tools_constraint() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(
        user_message="Just answer what gradient descent is, no tools",
        enabled_tools=["canvas", "rag", "web_search"],
    )

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "chat",
            "direct_tool": "external_image_search",
            "confidence": 0.96,
            "reason": "The classifier wanted to search images.",
            "tools": ["canvas", "external_image_search"],
        },
        router.decide(context),
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == ""
    assert decision.tools == []
    assert decision.config
    assert decision.config["constraint"] == "no_tools"


def test_router_llm_payload_cannot_reenable_canvas_constraint() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(
        user_message="Write a gradient descent study plan draft, no canvas",
        enabled_tools=["canvas", "rag", "web_search"],
    )

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "chat",
            "confidence": 0.91,
            "reason": "The classifier wanted a document draft.",
            "tools": ["canvas", "rag"],
        },
        router.decide(context),
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == ""
    assert decision.tools == ["rag"]
    assert decision.config
    assert decision.config["constraint"] == "no_canvas"


def test_router_llm_payload_cannot_override_no_retrieval_constraint() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(
        user_message="Make a gradient descent study plan offline",
        enabled_tools=["canvas", "rag", "web_search", "external_video_search", "reason"],
    )

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "chat",
            "direct_tool": "external_video_search",
            "confidence": 0.93,
            "reason": "The classifier wanted to search public videos.",
            "tools": ["external_video_search", "rag", "canvas"],
        },
        router.decide(context),
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == ""
    assert decision.tools == ["canvas"]
    assert decision.config
    assert decision.config["constraint"] == "no_retrieval"


def test_router_llm_payload_removes_canvas_when_tools_are_omitted() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(
        user_message="Explain gradient descent in chat, no canvas",
        enabled_tools=["canvas", "rag", "web_search"],
    )

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "chat",
            "confidence": 0.88,
            "reason": "The classifier kept the default chat route.",
        },
        router.decide(context),
    )

    assert decision.capability == "chat"
    assert decision.tools == ["rag", "web_search"]


def test_router_classifier_prompt_includes_canvas_context() -> None:
    router = LearningCapabilityRouter()
    prior = router.decide(UnifiedContext(user_message="润色这份草稿"))
    _system, user = router.build_llm_classifier_prompt(
        UnifiedContext(
            user_message="润色这份草稿",
            metadata={
                "canvas_context": {
                    "title": "梯度下降解释草稿",
                    "content": "# 草稿\n\n学习率控制每一步的步长。",
                }
            },
        ),
        prior,
    )

    assert '"present": true' in user
    assert "梯度下降解释草稿" in user
    assert "学习率控制每一步的步长" in user


def test_router_normalizes_llm_classifier_payload() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(
        user_message="帮我系统理解梯度下降",
        enabled_tools=["rag"],
        knowledge_bases=["ml-course"],
    )
    prior = router.decide(context)

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "deep_research",
            "confidence": 0.84,
            "reason": "需要学习路径和资料组织。",
            "rewritten_user_message": "围绕梯度下降整理学习路径",
            "tools": ["rag", "web_search"],
            "config": {"mode": "learning_path", "sources": ["kb", "web"]},
        },
        prior,
    )

    assert decision.capability == "deep_research"
    assert decision.confidence == 0.84
    assert decision.tools == ["rag", "web_search"]
    assert decision.config
    assert decision.config["mode"] == "learning_path"
    assert decision.config["sources"] == ["kb", "web"]
    assert decision.config["_coordinator_user_message"] == "围绕梯度下降整理学习路径"


def test_router_normalizes_llm_classifier_payload_for_external_image_search() -> None:
    router = LearningCapabilityRouter()
    context = UnifiedContext(user_message="帮我找几张梯度下降示意图")
    prior = router.decide(context)

    decision = router.decision_from_llm_payload(
        context,
        {
            "capability": "chat",
            "direct_tool": "external_image_search",
            "confidence": 0.9,
            "reason": "The learner wants existing image references.",
            "rewritten_user_message": "找梯度下降示意图参考",
            "tools": ["external_image_search"],
        },
        prior,
    )

    assert decision.capability == "chat"
    assert decision.direct_tool == "external_image_search"
    assert decision.tools == ["external_image_search"]
    assert decision.config
    assert decision.config["topic"] == "找梯度下降示意图参考"


def test_router_sends_english_public_video_requests_to_search_tool() -> None:
    router = LearningCapabilityRouter()

    search = router.decide(
        UnifiedContext(user_message="Find a public video or lecture about gradient descent")
    )
    course = router.decide(
        UnifiedContext(user_message="Show me a YouTube lesson link for backpropagation")
    )
    generation = router.decide(
        UnifiedContext(user_message="Generate a short animation video about gradient descent")
    )

    assert search.capability == "chat"
    assert search.direct_tool == "external_video_search"
    assert course.capability == "chat"
    assert course.direct_tool == "external_video_search"
    assert generation.capability == "math_animator"


def test_router_sends_english_public_image_requests_to_search_tool() -> None:
    router = LearningCapabilityRouter()

    search = router.decide(
        UnifiedContext(user_message="Show me an image diagram for gradient descent")
    )
    reference = router.decide(
        UnifiedContext(user_message="Find a diagram reference for backpropagation")
    )
    generation = router.decide(
        UnifiedContext(user_message="Show me a diagram of gradient descent")
    )

    assert search.capability == "chat"
    assert search.direct_tool == "external_image_search"
    assert reference.capability == "chat"
    assert reference.direct_tool == "external_image_search"
    assert generation.capability == "visualize"


def test_router_sends_english_question_generation_to_deep_question() -> None:
    router = LearningCapabilityRouter()

    decision = router.decide(
        UnifiedContext(user_message="Generate 3 multiple choice questions about linear algebra")
    )

    assert decision.capability == "deep_question"
    assert decision.delegates is True
