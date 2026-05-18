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
    assert '"user_message": "帮我安排一下梯度下降"' in user
    assert '"knowledge_bases": [' in user
    assert "学习率含义" in user


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
    generation = router.decide(
        UnifiedContext(user_message="Generate a short animation video about gradient descent")
    )

    assert search.capability == "chat"
    assert search.direct_tool == "external_video_search"
    assert generation.capability == "math_animator"


def test_router_sends_english_question_generation_to_deep_question() -> None:
    router = LearningCapabilityRouter()

    decision = router.decide(
        UnifiedContext(user_message="Generate 3 multiple choice questions about linear algebra")
    )

    assert decision.capability == "deep_question"
    assert decision.delegates is True
