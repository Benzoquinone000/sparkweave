"""Capability routing policy for learning-agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Any

from sparkweave.core.contracts import UnifiedContext

DELEGABLE_CAPABILITIES = {
    "deep_question",
    "deep_research",
    "deep_solve",
    "math_animator",
    "visualize",
}

SPECIALIST_LABELS = {
    "deep_question": "Question Generation Agent",
    "deep_research": "Research and Learning Path Agent",
    "deep_solve": "Deep Solve Agent",
    "external_image_search": "Curated Image Search Tool",
    "external_video_search": "Curated Video Search Tool",
    "math_animator": "Math Animation Agent",
    "visualize": "Knowledge Visualization Agent",
}

SPECIALIST_COLLABORATION_ROUTES: dict[str, list[dict[str, str]]] = {
    "deep_question": [
        {"key": "question", "label": "出题智能体", "detail": "生成选择、判断、填空、简答等练习。"},
        {"key": "validation", "label": "校验智能体", "detail": "检查答案、解析、难度和题型结构。"},
        {"key": "feedback", "label": "评估智能体", "detail": "把答题结果回写画像并建议下一步。"},
    ],
    "deep_research": [
        {"key": "decompose", "label": "主题拆解智能体", "detail": "把学习目标拆成可执行子问题。"},
        {"key": "research", "label": "资料检索智能体", "detail": "从知识库和网络中收集证据。"},
        {"key": "report", "label": "报告智能体", "detail": "整理学习路径、资源依据和引用。"},
    ],
    "deep_solve": [
        {"key": "planner", "label": "解题规划智能体", "detail": "拆解题意并选择求解路线。"},
        {"key": "tool", "label": "工具智能体", "detail": "按需检索、计算或运行代码验证。"},
        {"key": "writer", "label": "讲解智能体", "detail": "把推理过程整理成学生可读答案。"},
    ],
    "external_video_search": [
        {"key": "search", "label": "视频检索智能体", "detail": "检索公开视频和公开课候选链接。"},
        {"key": "rank", "label": "筛选智能体", "detail": "按主题、时长、可播放性和画像偏好排序。"},
        {"key": "card", "label": "学习卡片智能体", "detail": "生成观看计划、反思问题和资源卡片。"},
    ],
    "external_image_search": [
        {"key": "search", "label": "图片检索智能体", "detail": "检索公开图片、图解和示意图候选链接。"},
        {"key": "rank", "label": "筛选智能体", "detail": "按主题、清晰度、来源和画像偏好排序。"},
        {"key": "card", "label": "图片卡片智能体", "detail": "生成查看计划、反思问题和资源卡片。"},
    ],
    "math_animator": [
        {"key": "concept", "label": "概念分析智能体", "detail": "提取数学对象、公式和讲解重点。"},
        {"key": "scene", "label": "分镜智能体", "detail": "规划动画节奏、画面和叙事顺序。"},
        {"key": "render", "label": "渲染智能体", "detail": "生成 Manim 代码并产出视频或图解。"},
    ],
    "visualize": [
        {"key": "analysis", "label": "结构分析智能体", "detail": "识别概念关系和图解重点。"},
        {"key": "design", "label": "图解设计智能体", "detail": "选择 Mermaid、SVG 或结构图表达方式。"},
        {"key": "render", "label": "可视化渲染智能体", "detail": "生成可展示、可保存的图解产物。"},
    ],
}

VISUALIZE_TERMS = (
    "可视化",
    "图示",
    "图解",
    "画图",
    "画一个",
    "生成图",
    "流程图",
    "结构图",
    "关系图",
    "思维导图",
    "知识图谱",
    "mermaid",
    "flowchart",
    "diagram",
    "visualize",
    "chart",
    "graph",
)
ANIMATION_TERMS = (
    "动画",
    "动态演示",
    "视频讲解",
    "短视频",
    "manim",
    "animation",
    "animate",
    "video",
)
VIDEO_SEARCH_TERMS = (
    "找视频",
    "推荐视频",
    "视频推荐",
    "视频讲解",
    "学习视频",
    "课程视频",
    "视频资源",
    "精选视频",
    "公开视频",
    "公开课视频",
    "公开课",
    "网课",
    "网课视频",
    "讲解视频",
    "教学视频",
    "b站",
    "哔哩哔哩",
    "bilibili",
    "youtube",
    "external video",
    "public video",
    "public lecture",
    "public course",
    "online course",
    "find video",
    "find a video",
    "find public video",
    "recommend video",
    "recommend lecture",
    "learning video",
    "lecture video",
    "video lecture",
    "lecture link",
    "video resource",
    "video link",
)
IMAGE_SEARCH_TERMS = (
    "找图片",
    "推荐图片",
    "图片推荐",
    "图片素材",
    "图片资源",
    "图片参考",
    "找图",
    "搜图",
    "配图",
    "参考图",
    "示意图素材",
    "示意图参考",
    "图像资源",
    "公开图片",
    "学习图片",
    "视觉素材",
    "image search",
    "find image",
    "find an image",
    "find picture",
    "recommend image",
    "recommend picture",
    "show image",
    "show me an image",
    "image resource",
    "picture resource",
    "picture reference",
    "image reference",
    "reference image",
    "image diagram",
    "diagram image",
    "diagram reference",
    "illustration reference",
    "visual resource",
    "visual reference",
)
QUESTION_TERMS = (
    "出题",
    "生成题",
    "题目生成",
    "练习题",
    "测试题",
    "选择题",
    "判断题",
    "填空题",
    "quiz",
    "multiple choice",
    "multiple-choice",
    "mcq",
    "practice questions",
    "exam questions",
    "quiz questions",
    "question set",
    "generate questions",
)
RESEARCH_TERMS = (
    "调研",
    "研究报告",
    "综述",
    "学习路径",
    "学习路线",
    "学习计划",
    "资源推荐",
    "规划",
    "research",
    "report",
    "learning path",
    "study plan",
)
SOLVE_TERMS = (
    "求解",
    "解题",
    "证明",
    "推导",
    "计算",
    "求极限",
    "求导",
    "积分",
    "答案是",
    "怎么做",
    "solve",
    "prove",
    "derive",
    "calculate",
)
NO_DELEGATE_TERMS = (
    "不用调用",
    "不要调用",
    "不要画图",
    "不用画图",
    "只回答",
    "直接回答",
    "just answer",
    "no diagram",
    "no tools",
)
DIRECT_CHAT_NO_TOOL_TERMS = (
    "不用工具",
    "不要用工具",
    "不要调用工具",
    "不用调用工具",
    "不用调用",
    "不要调用",
    "只回答",
    "直接回答",
    "just answer",
    "no tools",
    "without tools",
    "don't use tools",
    "do not use tools",
)
NO_CANVAS_TERMS = (
    "不要打开画布",
    "不用画布",
    "不要用画布",
    "不要画布",
    "别打开画布",
    "在聊天里写",
    "直接写在聊天里",
    "no canvas",
    "without canvas",
    "don't open canvas",
    "do not open canvas",
)
NO_RETRIEVAL_TERMS = (
    "不要联网",
    "不用联网",
    "别联网",
    "不要搜索",
    "不用搜索",
    "别搜索",
    "不要检索",
    "不用检索",
    "不要查资料",
    "不查资料",
    "不要用知识库",
    "不用知识库",
    "不要引用资料",
    "no search",
    "without search",
    "don't search",
    "do not search",
    "no web",
    "without web",
    "offline",
    "no retrieval",
    "without retrieval",
    "no rag",
    "without rag",
)
PROFILE_GUIDED_TERMS = (
    "继续",
    "开始学习",
    "继续学习",
    "下一步",
    "下一步学什么",
    "我该学什么",
    "我该做什么",
    "按画像",
    "根据画像",
    "按我的画像",
    "帮我安排",
    "开始今天",
    "继续今天",
    "start learning",
    "continue learning",
    "next step",
    "what should i learn",
    "what should i do next",
)
CANVAS_EDIT_TERMS = (
    "画布",
    "这份",
    "这篇",
    "当前文档",
    "当前草稿",
    "这个文档",
    "这个草稿",
    "文档",
    "草稿",
    "修改",
    "润色",
    "续写",
    "改写",
    "压缩",
    "扩写",
    "调整",
    "完善",
    "整理",
    "polish",
    "revise",
    "rewrite",
    "shorten",
    "expand",
    "continue",
    "this draft",
    "this document",
    "canvas",
    "current draft",
    "current document",
)
CANVAS_CREATE_TERMS = (
    "画布",
    "文档",
    "草稿",
    "写一份",
    "起草",
    "撰写",
    "学习计划",
    "复习计划",
    "研究报告",
    "报告",
    "提纲",
    "讲稿",
    "笔记",
    "方案",
    "draft",
    "document",
    "canvas",
    "write a",
    "create a",
    "draft a",
    "study plan",
    "learning plan",
    "report",
    "outline",
    "notes",
    "proposal",
)

COORDINATOR_INTENT_SYSTEM_PROMPT = """\
You are SparkWeave's intent coordinator. Your only job is to decide how a
learning request should be routed inside a multi-agent learning system.

Return strict JSON only. Do not answer the learner.

Available routes:
- chat: ordinary explanation, clarification, short factual answer, or when the
  learner explicitly asks for a direct answer / no tools.
- deep_solve: problem solving, proof, derivation, equation, calculation,
  verification, or step-by-step solution.
- deep_question: generate practice, quiz, exam-style questions, mimic
  questions, validation questions, or interactive assessment.
- deep_research: research report, learning path, study plan, comparison,
  resource organization, broad multi-source investigation.
- visualize: diagram, concept map, flowchart, Mermaid, SVG, Chart.js, graph,
  or visual explanation artifact.
- math_animator: animation, Manim, video-style generated explanation,
  storyboard, rendered math scene.
- external_video_search: find/recommend existing public videos, public courses,
  Bilibili/YouTube/web lectures. This is a direct tool under chat, not a
  specialist capability.
- external_image_search: find/recommend existing public images, diagrams,
  illustrations, visual references, or image assets. This is a direct tool
  under chat, not a specialist capability.
- canvas: open/update the right-side editable document canvas. This is a chat
  tool, not a specialist capability.

Decision rules:
1. Respect explicit user constraints first: if the user says direct answer or
   no tools, choose chat with no tools. If the user says no canvas, do not
   include the canvas tool. If the user says no search, no retrieval, no web,
   offline, or no RAG, do not include retrieval tools such as rag, web_search,
   paper_search, external_video_search, or external_image_search. If the user
   says no diagram or no delegation, choose chat unless another explicit route
   is requested.
2. Do not route to a specialist just because a topic is mathematical. Use
   deep_solve only when the learner asks to solve/prove/derive/calculate/check.
3. Distinguish generated video from existing video search:
   - "generate/make/animate a video" -> math_animator
   - "find/recommend public video/course/link" -> external_video_search
4. Distinguish generated diagrams/images from existing image search:
   - "draw/generate/create a diagram/image/flowchart" -> visualize
   - "find/recommend/search image/reference/material" -> external_image_search
5. Use learner profile only when it helps disambiguate a vague request such as
   "continue learning" or "what should I do next". Do not over-personalize when
   evidence is weak.
6. Prefer chat when confidence is low or the request is simply asking for an
   explanation.
7. Keep routing user-centered: choose the path that produces the next useful
   learning action, not the most complex engineering capability.
8. If `canvas_context.present` is true and the learner asks to revise, polish,
   continue, summarize, shorten, expand, or otherwise edit the current canvas
   document, choose chat so the main conversation can update the document. If
   they ask to create a new diagram, quiz, video, or external resource from the
   canvas, route to the appropriate specialist/tool.
9. If the learner asks to write, draft, create, or revise a substantial
   editable document such as a study plan, report, outline, notes, proposal, or
   manuscript, choose chat and include the canvas tool. Do not use canvas for
   ordinary short explanations or small snippets.

Examples:
- "帮我找一个梯度下降公开视频" -> capability chat, direct_tool external_video_search.
- "请生成一个梯度下降动画视频" -> capability math_animator.
- "Find a diagram reference for backpropagation" -> capability chat,
  direct_tool external_image_search.
- "Show me a diagram of gradient descent" -> capability visualize.
- "Generate 5 multiple choice questions" -> capability deep_question.
- "Write a study plan draft" -> capability chat, tools ["canvas"].
- "直接解释一下，不用工具" -> capability chat, tools [].
- "写一份学习计划，不要打开画布" -> capability chat, tools without canvas.

JSON schema:
{
  "capability": "chat | deep_solve | deep_question | deep_research | visualize | math_animator",
  "direct_tool": "external_video_search | external_image_search | null",
  "confidence": 0.0,
  "reason": "short reason",
  "rewritten_user_message": "optional clearer task for the selected agent",
  "tools": ["canvas", "rag", "web_search", "paper_search", "external_video_search", "external_image_search"],
  "config": {
    "render_mode": "auto | mermaid | chartjs | svg",
    "output_mode": "video | image",
    "mode": "report | learning_path | notes | comparison",
    "num_questions": 3,
    "question_type": "choice | true_false | fill_blank | coding |",
    "sources": ["kb", "web", "papers"]
  },
  "profile_hints_applied": true
}
"""


@dataclass(frozen=True)
class CoordinatorDecision:
    capability: str = "chat"
    confidence: float = 0.0
    reason: str = "Use the default chat agent."
    config: dict[str, Any] | None = None
    tools: list[str] | None = None

    @property
    def delegates(self) -> bool:
        return self.capability in DELEGABLE_CAPABILITIES

    @property
    def direct_tool(self) -> str:
        return str((self.config or {}).get("_direct_tool") or "").strip()


class LearningCapabilityRouter:
    """Central routing policy for chat-to-specialist handoff decisions."""

    def decide(self, context: UnifiedContext) -> CoordinatorDecision:
        overrides = dict(context.config_overrides or {})
        if not self.truthy(overrides.get("auto_delegate", True)):
            return CoordinatorDecision(reason="Automatic specialist delegation is disabled.")

        if context.metadata.get("delegated_by_coordinator"):
            return CoordinatorDecision(reason="This turn has already been delegated once.")

        forced = str(
            overrides.get("delegate_capability")
            or overrides.get("coordinator_capability")
            or ""
        ).strip()
        if forced:
            return self.forced_decision(forced)

        text = self.normalized_text(context)
        if not text:
            return CoordinatorDecision(reason="Empty user request.")
        canvas_disabled = self.contains_any(text, NO_CANVAS_TERMS)
        retrieval_disabled = self.contains_any(text, NO_RETRIEVAL_TERMS)
        if self.contains_any(text, DIRECT_CHAT_NO_TOOL_TERMS):
            return CoordinatorDecision(
                reason="The learner asked for a direct answer without tools.",
                tools=[],
            )
        if self.contains_any(text, NO_DELEGATE_TERMS):
            return CoordinatorDecision(reason="The learner asked for a direct answer.")

        if retrieval_disabled and (
            self.looks_like_external_video_request(text)
            or self.looks_like_external_image_request(text)
        ):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.82,
                reason="The learner asked not to search or retrieve external resources.",
                tools=self.without_retrieval_tools(context),
            )

        if self.looks_like_external_video_request(text):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.9,
                reason="The learner asked to find or recommend public learning videos, so the chat graph will call the curated video tool.",
                tools=["external_video_search"],
                config=self.external_video_tool_config(context, context.user_message),
            )

        if self.looks_like_external_image_request(text):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.9,
                reason="The learner asked to find or recommend public learning images, so the chat graph will call the curated image tool.",
                tools=["external_image_search"],
                config=self.external_image_tool_config(context, context.user_message),
            )

        if self.contains_any(text, ANIMATION_TERMS):
            return CoordinatorDecision(
                capability="math_animator",
                confidence=0.92,
                reason="The learner asked for an animation or video-style explanation.",
                config=self.math_animator_config(context, text),
            )

        if self.contains_any(text, QUESTION_TERMS) or self.looks_like_question_generation_request(text):
            return CoordinatorDecision(
                capability="deep_question",
                confidence=0.9,
                reason="The learner asked to generate interactive practice questions.",
                config=self.question_config(context, context.user_message, text),
            )

        if self.contains_any(text, VISUALIZE_TERMS) and self.has_visual_action(text):
            return CoordinatorDecision(
                capability="visualize",
                confidence=0.88,
                reason="The learner asked for a diagram or knowledge visualization.",
                config=self.visualize_config(context, text),
            )

        if canvas_disabled and (
            self.looks_like_canvas_create_request(text)
            or (self.has_canvas_context(context) and self.looks_like_canvas_edit_request(text))
        ):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.84,
                reason="The learner asked for an editable document but explicitly disabled the canvas tool.",
                tools=self.without_canvas_tools(context),
            )

        if self.has_canvas_context(context) and self.looks_like_canvas_edit_request(text):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.86,
                reason="The learner is continuing or revising the current canvas document in the main conversation.",
                tools=self.canvas_tools(context),
            )

        if self.looks_like_canvas_create_request(text):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.78,
                reason="The learner asked for a substantial editable document, so chat should use the canvas tool.",
                tools=self.canvas_tools(context),
            )

        if retrieval_disabled and self.contains_any(text, RESEARCH_TERMS):
            return CoordinatorDecision(
                capability="chat",
                confidence=0.74,
                reason="The learner asked for planning or research but explicitly disabled retrieval tools.",
                tools=self.without_retrieval_tools(context),
            )

        if self.contains_any(text, RESEARCH_TERMS):
            return CoordinatorDecision(
                capability="deep_research",
                confidence=0.82,
                reason="The learner asked for research, planning, or resource organization.",
                config=self.research_config(context, text),
                tools=self.research_tools(context),
            )

        if self.looks_like_solve_request(text):
            return CoordinatorDecision(
                capability="deep_solve",
                confidence=0.8,
                reason="The learner asked for a problem-solving or derivation workflow.",
                config={"detailed_answer": True},
            )

        profile_guided = self.profile_guided_decision(context, text)
        if profile_guided is not None:
            return profile_guided

        if retrieval_disabled:
            return CoordinatorDecision(
                capability="chat",
                confidence=0.64,
                reason="The learner explicitly disabled retrieval tools for this chat turn.",
                tools=self.without_retrieval_tools(context),
            )

        if canvas_disabled:
            return CoordinatorDecision(
                capability="chat",
                confidence=0.66,
                reason="The learner explicitly disabled the canvas tool for this chat turn.",
                tools=self.without_canvas_tools(context),
            )

        return CoordinatorDecision()

    def should_consult_llm(
        self,
        context: UnifiedContext,
        prior: CoordinatorDecision,
        *,
        auto_allowed: bool,
    ) -> bool:
        """Return whether the LLM classifier should refine this decision."""
        overrides = dict(context.config_overrides or {})
        if not self.truthy(overrides.get("auto_delegate", True)):
            return False
        if context.metadata.get("delegated_by_coordinator"):
            return False
        if overrides.get("delegate_capability") or overrides.get("coordinator_capability"):
            return False

        text = self.normalized_text(context)
        if not text or self.contains_any(text, NO_DELEGATE_TERMS):
            return False

        raw_mode = overrides.get("coordinator_llm", overrides.get("intent_classifier", "auto"))
        mode = str(raw_mode).strip().lower() if raw_mode is not None else "auto"
        if mode in {"0", "false", "no", "off", "disabled", "rules"}:
            return False
        if mode in {"1", "true", "yes", "on", "llm", "force", "always"}:
            return True
        if mode not in {"", "auto", "hybrid"}:
            return False
        if not auto_allowed:
            return False
        if prior.direct_tool or prior.delegates:
            return prior.confidence < 0.65
        return prior.confidence < 0.55

    def build_llm_classifier_prompt(
        self,
        context: UnifiedContext,
        prior: CoordinatorDecision,
    ) -> tuple[str, str]:
        """Build the structured prompt used by the LLM intent classifier."""
        hints = self.learner_profile_hints(context)
        payload = {
            "user_message": context.user_message,
            "language": context.language or "zh",
            "enabled_tools": list(context.enabled_tools or []),
            "knowledge_bases": list(context.knowledge_bases or []),
            "attachments_present": bool(context.attachments),
            "learner_profile_hints": self._classifier_hints(hints),
            "memory_context_excerpt": self.hint_text(context.memory_context, limit=600),
            "notebook_context_excerpt": self.hint_text(context.notebook_context, limit=500),
            "history_context_excerpt": self.hint_text(context.history_context, limit=500),
            "canvas_context": self.classifier_canvas_context(context),
            "prior_rule_decision": {
                "capability": prior.capability,
                "direct_tool": prior.direct_tool,
                "confidence": prior.confidence,
                "reason": prior.reason,
            },
        }
        return COORDINATOR_INTENT_SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False, indent=2)

    def decision_from_llm_payload(
        self,
        context: UnifiedContext,
        payload: dict[str, Any],
        prior: CoordinatorDecision,
    ) -> CoordinatorDecision:
        """Normalize an LLM classifier JSON payload into CoordinatorDecision."""
        capability = str(payload.get("capability") or "chat").strip().lower()
        direct_tool_capabilities = {"external_video_search", "external_image_search"}
        if capability in direct_tool_capabilities:
            direct_tool = capability
            capability = "chat"
            payload = {**payload, "direct_tool": direct_tool}
        if capability not in {"chat", *DELEGABLE_CAPABILITIES}:
            return prior

        confidence = self._clamp_confidence(payload.get("confidence"))
        if confidence < 0.55:
            return prior

        reason = self.hint_text(payload.get("reason"), limit=260) or "LLM intent classifier selected this route."
        rewritten = self.hint_text(payload.get("rewritten_user_message"), limit=420)
        text = self.normalized_text(context)
        no_tools_requested = self.contains_any(text, DIRECT_CHAT_NO_TOOL_TERMS)
        no_canvas_requested = self.contains_any(text, NO_CANVAS_TERMS)
        no_retrieval_requested = self.contains_any(text, NO_RETRIEVAL_TERMS)
        if no_tools_requested:
            return CoordinatorDecision(
                capability="chat",
                confidence=confidence,
                reason="The learner explicitly asked for a direct answer without tools.",
                config={
                    "llm_classified": True,
                    "llm_classifier_confidence": confidence,
                    "constraint": "no_tools",
                },
                tools=[],
            )

        tools = self._normalize_tool_names(payload.get("tools"))
        config = self._config_from_classifier_payload(context, capability, payload, rewritten)
        direct_tool = str(payload.get("direct_tool") or "").strip().lower()
        if no_retrieval_requested and (
            direct_tool in direct_tool_capabilities or capability == "deep_research"
        ):
            direct_tool = ""
            capability = "chat"
            tools = self._remove_retrieval_tool_names(
                tools if tools is not None else self.without_retrieval_tools(context)
            )
            config = {}
        if direct_tool in direct_tool_capabilities:
            prompt = rewritten or context.user_message
            direct_tool_config = (
                self.external_image_tool_config(context, prompt)
                if direct_tool == "external_image_search"
                else self.external_video_tool_config(context, prompt)
            )
            config = {
                **direct_tool_config,
                **config,
                "_direct_tool": direct_tool,
            }
            tools = [direct_tool]
            capability = "chat"

        if no_canvas_requested:
            tools = self._remove_canvas_tool_names(
                tools if tools is not None else self.without_canvas_tools(context)
            )
        if no_retrieval_requested:
            tools = self._remove_retrieval_tool_names(
                tools if tools is not None else self.without_retrieval_tools(context)
            )

        if rewritten:
            config["_coordinator_user_message"] = rewritten
        config["llm_classified"] = True
        config["llm_classifier_confidence"] = confidence
        if no_canvas_requested:
            config["constraint"] = "no_canvas"
        if no_retrieval_requested:
            config["constraint"] = "no_retrieval"
        if payload.get("profile_hints_applied"):
            config["profile_guided"] = True

        return CoordinatorDecision(
            capability=capability,
            confidence=confidence,
            reason=reason,
            config=config or None,
            tools=tools,
        )

    @staticmethod
    def _classifier_hints(hints: dict[str, Any]) -> dict[str, Any]:
        if not hints:
            return {}
        keep = (
            "current_focus",
            "level",
            "preferred_resource",
            "goals",
            "preferences",
            "weak_points",
            "mastery_needs_attention",
            "next_action",
            "time_budget_minutes",
            "decision_scores",
        )
        return {key: hints[key] for key in keep if key in hints}

    @staticmethod
    def _clamp_confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.0
        return min(max(confidence, 0.0), 1.0)

    @staticmethod
    def _normalize_tool_names(value: Any) -> list[str] | None:
        if not isinstance(value, list):
            return None
        allowed = {
            "rag",
            "web_search",
            "paper_search",
            "external_video_search",
            "external_image_search",
            "code_execution",
            "reason",
            "brainstorm",
            "geogebra_analysis",
            "canvas",
        }
        tools: list[str] = []
        for item in value:
            name = str(item or "").strip()
            if name in allowed and name not in tools:
                tools.append(name)
        if tools:
            return tools
        return [] if not value else None

    @staticmethod
    def _remove_canvas_tool_names(tools: list[str] | None) -> list[str]:
        canvas_aliases = {"canvas", "document_canvas", "editable_canvas"}
        return [
            tool
            for tool in dict.fromkeys(tools or [])
            if str(tool or "").strip().lower() not in canvas_aliases
        ]

    @staticmethod
    def _remove_retrieval_tool_names(tools: list[str] | None) -> list[str]:
        retrieval_aliases = {
            "rag",
            "web_search",
            "paper_search",
            "external_video_search",
            "external_image_search",
        }
        return [
            tool
            for tool in dict.fromkeys(tools or [])
            if str(tool or "").strip().lower() not in retrieval_aliases
        ]

    def _config_from_classifier_payload(
        self,
        context: UnifiedContext,
        capability: str,
        payload: dict[str, Any],
        rewritten: str,
    ) -> dict[str, Any]:
        raw_config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        text = (rewritten or context.user_message or "").strip().lower()
        if capability == "deep_question":
            config = self.question_config(context, rewritten or context.user_message, text)
            if raw_config.get("num_questions") is not None:
                try:
                    config["num_questions"] = min(max(int(raw_config["num_questions"]), 1), 20)
                except (TypeError, ValueError):
                    pass
            question_type = self.hint_text(raw_config.get("question_type"))
            if question_type in {"choice", "true_false", "fill_blank", "coding"}:
                config["question_type"] = question_type
            return config
        if capability == "deep_research":
            config = self.research_config(context, text)
            mode = self.hint_text(raw_config.get("mode"))
            if mode in {"report", "learning_path", "notes", "comparison"}:
                config["mode"] = mode
            sources = raw_config.get("sources")
            if isinstance(sources, list):
                normalized = [
                    source
                    for source in (self.hint_text(item) for item in sources)
                    if source in {"kb", "web", "papers"}
                ]
                if normalized:
                    config["sources"] = list(dict.fromkeys(normalized))
            return config
        if capability == "visualize":
            config = self.visualize_config(context, text)
            render_mode = self.hint_text(raw_config.get("render_mode"))
            if render_mode in {"auto", "mermaid", "chartjs", "svg"}:
                config["render_mode"] = render_mode
            return config
        if capability == "math_animator":
            config = self.math_animator_config(context, text)
            output_mode = self.hint_text(raw_config.get("output_mode"))
            if output_mode in {"video", "image"}:
                config["output_mode"] = output_mode
            return config
        if capability == "deep_solve":
            return {"detailed_answer": True}
        return {}

    @staticmethod
    def collaboration_metadata(
        decision: CoordinatorDecision,
        context: UnifiedContext,
        *,
        profile_hints: dict[str, Any] | None = None,
        rewritten_prompt: str = "",
    ) -> dict[str, Any]:
        profile_aware = bool(profile_hints)
        route_capability = decision.direct_tool or decision.capability
        target = SPECIALIST_LABELS.get(route_capability, "Dialogue Coordinator Agent")
        goal = (rewritten_prompt or context.user_message or "").strip()
        summary = (
            f"画像先提供学习依据，协调智能体再唤醒 {target} 接力。"
            if profile_aware
            else f"协调智能体根据当前请求唤醒 {target} 接力。"
        )
        return {
            "collaboration_route_version": 1,
            "collaboration_route": LearningCapabilityRouter.collaboration_route(
                route_capability,
                profile_aware,
            ),
            "collaboration_summary": summary,
            "collaboration_goal": goal[:260],
        }

    @staticmethod
    def collaboration_route(capability: str, profile_aware: bool) -> list[dict[str, str]]:
        route: list[dict[str, str]] = []
        if profile_aware:
            route.append(
                {
                    "key": "profile",
                    "label": "学习画像智能体",
                    "detail": "提供薄弱点、偏好、时间预算和下一步任务。",
                }
            )
        route.append(
            {
                "key": "coordinator",
                "label": "对话协调智能体",
                "detail": "识别意图并决定唤醒哪个专门智能体。",
            }
        )
        route.extend(
            SPECIALIST_COLLABORATION_ROUTES.get(
                capability,
                [
                    {
                        "key": "answer",
                        "label": "讲解智能体",
                        "detail": "组织适合当前学生阅读的回答。",
                    }
                ],
            )
        )
        return route[:6]

    @staticmethod
    def delegated_context(
        context: UnifiedContext,
        decision: CoordinatorDecision,
    ) -> UnifiedContext:
        config = {
            **dict(context.config_overrides or {}),
            **dict(decision.config or {}),
        }
        rewritten_user_message = str(config.pop("_coordinator_user_message", "") or "").strip()
        config.pop("auto_delegate", None)
        config.pop("delegate_capability", None)
        config.pop("coordinator_capability", None)
        tools = decision.tools if decision.tools is not None else context.enabled_tools
        return replace(
            context,
            user_message=rewritten_user_message or context.user_message,
            active_capability=decision.capability,
            enabled_tools=list(tools) if tools is not None else None,
            config_overrides=config,
            metadata={
                **dict(context.metadata or {}),
                "delegated_by_coordinator": "chat",
                "coordinator_decision": {
                    "capability": decision.capability,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                },
                "coordinator_rewritten_prompt": rewritten_user_message,
            },
        )

    @staticmethod
    def forced_decision(value: str) -> CoordinatorDecision:
        capability = value.strip().lower()
        if capability in {"none", "off", "chat", "default"}:
            return CoordinatorDecision(reason="Forced to stay in chat.")
        if capability not in DELEGABLE_CAPABILITIES:
            return CoordinatorDecision(
                confidence=0.0,
                reason=f"Requested delegate capability `{value}` is not available.",
            )
        return CoordinatorDecision(
            capability=capability,
            confidence=1.0,
            reason="The request explicitly forced this specialist capability.",
        )

    @staticmethod
    def normalized_text(context: UnifiedContext) -> str:
        text = context.user_message or ""
        if context.attachments:
            text += " attached_media"
        return text.strip().lower()

    @staticmethod
    def has_canvas_context(context: UnifiedContext) -> bool:
        raw = context.metadata.get("canvas_context") if isinstance(context.metadata, dict) else None
        return isinstance(raw, dict) and bool(str(raw.get("content") or "").strip())

    @classmethod
    def looks_like_canvas_edit_request(cls, text: str) -> bool:
        return cls.contains_any(text, CANVAS_EDIT_TERMS)

    @classmethod
    def looks_like_canvas_create_request(cls, text: str) -> bool:
        if not cls.contains_any(text, CANVAS_CREATE_TERMS):
            return False
        return cls.contains_any(
            text,
            (
                "写",
                "生成",
                "创建",
                "起草",
                "撰写",
                "整理",
                "做一份",
                "帮我做",
                "帮我写",
                "write",
                "create",
                "draft",
                "prepare",
                "compose",
                "make",
            ),
        )

    @staticmethod
    def canvas_tools(context: UnifiedContext) -> list[str]:
        tools = list(dict.fromkeys(context.enabled_tools or []))
        if "canvas" not in tools:
            tools.insert(0, "canvas")
        return tools

    @staticmethod
    def without_canvas_tools(context: UnifiedContext) -> list[str]:
        return LearningCapabilityRouter._remove_canvas_tool_names(context.enabled_tools or [])

    @staticmethod
    def without_retrieval_tools(context: UnifiedContext) -> list[str]:
        return LearningCapabilityRouter._remove_retrieval_tool_names(context.enabled_tools or [])

    @classmethod
    def classifier_canvas_context(cls, context: UnifiedContext) -> dict[str, Any]:
        raw = context.metadata.get("canvas_context") if isinstance(context.metadata, dict) else None
        if not isinstance(raw, dict):
            return {"present": False}
        content = str(raw.get("content") or "").strip()
        if not content:
            return {"present": False}
        return {
            "present": True,
            "title": cls.hint_text(raw.get("title"), limit=160),
            "content_excerpt": cls.hint_text(content, limit=700),
            "truncated": bool(raw.get("truncated")),
        }

    @staticmethod
    def contains_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term.lower() in text for term in terms)

    @staticmethod
    def has_visual_action(text: str) -> bool:
        action_terms = (
            "画",
            "生成",
            "做一个",
            "展示",
            "呈现",
            "可视化",
            "图解",
            "diagram",
            "visualize",
            "draw",
            "generate",
            "create",
            "show",
        )
        return LearningCapabilityRouter.contains_any(text, action_terms)

    @staticmethod
    def looks_like_question_generation_request(text: str) -> bool:
        return bool(
            re.search(
                r"\b(generate|create|make|write|build)\b.{0,40}"
                r"\b(question|questions|quiz|quizzes|mcq|practice|exercise|exam)\b",
                text,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b(question|questions|quiz|quizzes|mcq|practice|exercise|exam)\b.{0,40}"
                r"\b(generate|create|make|write|build)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    @staticmethod
    def looks_like_external_video_request(text: str) -> bool:
        video_search_pattern = re.search(
            r"(找|推荐|检索|搜|公开|资源|链接|b站|哔哩哔哩|youtube).{0,12}(视频|网课|公开课)"
            r"|(?:视频|网课|公开课).{0,12}(找|推荐|检索|搜|资源|链接|公开)",
            text,
            flags=re.IGNORECASE,
        )
        english_video_search_pattern = re.search(
            r"\b(find|recommend|search|show|list|suggest|look\s+up)\b.{0,40}"
            r"\b(public\s+)?(video|lecture|course|lesson|youtube|bilibili)\b"
            r"|\b(public\s+)?(video|lecture|course|lesson|youtube|bilibili)\b.{0,40}"
            r"\b(find|recommend|search|show|list|suggest|link|resource)\b",
            text,
            flags=re.IGNORECASE,
        )
        if (
            not LearningCapabilityRouter.contains_any(text, VIDEO_SEARCH_TERMS)
            and not video_search_pattern
            and not english_video_search_pattern
        ):
            return False
        generate_markers = (
            "生成视频",
            "生成一个视频",
            "生成个视频",
            "制作视频",
            "做一个视频",
            "做个视频",
            "生成短视频",
            "动画",
            "manim",
            "generate video",
            "create video",
            "make video",
            "animation",
            "animate",
        )
        find_markers = (
            "找",
            "推荐",
            "检索",
            "搜",
            "公开",
            "资源",
            "链接",
            "find",
            "recommend",
            "search",
            "link",
            "resource",
        )
        generate_pattern = re.search(r"(生成|制作|做).{0,8}(视频|短视频|动画)", text, flags=re.IGNORECASE)
        if (LearningCapabilityRouter.contains_any(text, generate_markers) or generate_pattern) and not (
            LearningCapabilityRouter.contains_any(text, find_markers)
            or video_search_pattern
            or english_video_search_pattern
        ):
            return False
        return True

    @staticmethod
    def looks_like_external_image_request(text: str) -> bool:
        image_search_pattern = re.search(
            r"(找|推荐|检索|搜|公开|资源|链接|素材|参考|配|find|recommend|search|list|suggest|look\s+up).{0,18}(图片|图像|图示|图解|示意图|插图|配图|picture|image|illustration|diagram)"
            r"|(?:图片|图像|图示|图解|示意图|插图|配图|picture|image|illustration|diagram).{0,18}(找|推荐|检索|搜|资源|链接|公开|素材|参考|find|recommend|search|list|suggest|reference|resource)",
            text,
            flags=re.IGNORECASE,
        )
        english_image_show_pattern = re.search(
            r"\bshow\b.{0,45}\b(public\s+)?(image|picture|illustration|reference\s+image|visual\s+reference|image\s+diagram|diagram\s+image)\b"
            r"|\b(public\s+)?(image|picture|illustration|reference\s+image|visual\s+reference|image\s+diagram|diagram\s+image)\b.{0,45}\b(show|link|resource|reference)\b",
            text,
            flags=re.IGNORECASE,
        )
        if (
            not LearningCapabilityRouter.contains_any(text, IMAGE_SEARCH_TERMS)
            and not image_search_pattern
            and not english_image_show_pattern
        ):
            return False
        generate_markers = (
            "生成图片",
            "生成一张图",
            "生成图解",
            "生成示意图",
            "生成流程图",
            "画图",
            "画一个",
            "画一张",
            "制作图片",
            "做一张图",
            "draw",
            "create image",
            "generate image",
            "generate diagram",
            "draw diagram",
            "make diagram",
        )
        find_markers = (
            "找",
            "推荐",
            "检索",
            "搜",
            "公开",
            "资源",
            "链接",
            "素材",
            "参考",
            "配图",
            "find",
            "recommend",
            "search",
            "link",
            "resource",
            "reference",
            "material",
        )
        generate_pattern = re.search(r"(生成|制作|画|做).{0,8}(图片|图像|图解|示意图|流程图|插图)", text, flags=re.IGNORECASE)
        if (LearningCapabilityRouter.contains_any(text, generate_markers) or generate_pattern) and not (
            LearningCapabilityRouter.contains_any(text, find_markers)
            or image_search_pattern
            or english_image_show_pattern
        ):
            return False
        return True

    @staticmethod
    def looks_like_solve_request(text: str) -> bool:
        if not LearningCapabilityRouter.contains_any(text, SOLVE_TERMS):
            return False
        math_markers = (
            "=",
            "\\frac",
            "\\lim",
            "\\int",
            "\\sum",
            "^",
            "x",
            "函数",
            "极限",
            "导数",
            "积分",
            "矩阵",
            "概率",
            "方程",
        )
        return LearningCapabilityRouter.contains_any(text, math_markers)

    @staticmethod
    def profile_guided_decision(
        context: UnifiedContext,
        text: str,
    ) -> CoordinatorDecision | None:
        if not LearningCapabilityRouter.looks_like_profile_guided_request(text):
            return None
        hints = LearningCapabilityRouter.learner_profile_hints(context)
        if not hints:
            return None
        capability = LearningCapabilityRouter.capability_from_profile_hints(hints)
        if not capability:
            return None

        target_prompt = LearningCapabilityRouter.profile_guided_prompt(hints, context.user_message)
        if not target_prompt or target_prompt.strip().lower() == text.strip().lower():
            focus = LearningCapabilityRouter.hint_text(hints.get("current_focus"))
            if focus:
                target_prompt = f"围绕「{focus}」安排下一步学习材料和验证任务。"
        if not target_prompt:
            return None

        config = LearningCapabilityRouter.profile_guided_config(context, capability, target_prompt)
        preferred = LearningCapabilityRouter.hint_text(hints.get("preferred_resource")) or "current learner profile"
        if capability in {"external_video_search", "external_image_search"}:
            return CoordinatorDecision(
                capability="chat",
                confidence=0.72,
                reason=f"The learner asked for a next step; the learner profile prefers {preferred}.",
                tools=[capability],
                config=config,
            )
        return CoordinatorDecision(
            capability=capability,
            confidence=0.72,
            reason=f"The learner asked for a next step; the learner profile prefers {preferred}.",
            config=config,
        )

    @staticmethod
    def looks_like_profile_guided_request(text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False
        if LearningCapabilityRouter.contains_any(normalized, PROFILE_GUIDED_TERMS):
            return True
        return bool(re.fullmatch(r"(go|start|continue|next|继续|开始|下一步)[\s。.!！?？]*", normalized))

    @staticmethod
    def capability_from_profile_hints(hints: dict[str, Any]) -> str:
        action = hints.get("next_action") if isinstance(hints.get("next_action"), dict) else {}
        preferred = LearningCapabilityRouter.capability_from_resource_text(
            LearningCapabilityRouter.hint_text(hints.get("preferred_resource")).lower()
        )
        if preferred:
            return preferred
        candidates: list[Any] = [
            *(hints.get("preferences") or []),
            action.get("kind"),
            action.get("title"),
            action.get("summary"),
            action.get("suggested_prompt"),
        ]
        joined = " ".join(
            LearningCapabilityRouter.hint_text(item, limit=260).lower()
            for item in candidates
            if item
        )
        if not joined:
            return ""
        return LearningCapabilityRouter.capability_from_resource_text(joined)

    @staticmethod
    def capability_from_resource_text(joined: str) -> str:
        if any(
            term in joined
            for term in (
                "curated_public_video",
                "external_video",
                "public_video",
                "公开视频",
                "公开课",
                "bilibili",
                "youtube",
            )
        ):
            return "external_video_search"
        if any(
            term in joined
            for term in (
                "external_image",
                "public_image",
                "image_resource",
                "picture_reference",
                "diagram_reference",
                "illustration_reference",
                "图片",
                "配图",
                "参考图",
                "图片素材",
                "示意图素材",
            )
        ):
            return "external_image_search"
        if any(term in joined for term in ("interactive_practice", "practice", "quiz", "question", "练习", "题", "复测", "测试")):
            return "deep_question"
        if any(term in joined for term in ("visual_explanation", "visual", "diagram", "图解", "可视化", "关系图")):
            return "visualize"
        if any(term in joined for term in ("short_video", "video", "animation", "manim", "短视频", "动画", "视频讲解")):
            return "math_animator"
        return ""

    @staticmethod
    def profile_guided_prompt(hints: dict[str, Any], fallback: str) -> str:
        action = hints.get("next_action") if isinstance(hints.get("next_action"), dict) else {}
        for value in (
            action.get("suggested_prompt"),
            action.get("summary"),
            action.get("title"),
            hints.get("current_focus"),
            hints.get("summary"),
            fallback,
        ):
            text = LearningCapabilityRouter.hint_text(value, limit=360)
            if text:
                return text
        return ""

    @staticmethod
    def profile_guided_config(
        context: UnifiedContext,
        capability: str,
        prompt: str,
    ) -> dict[str, Any]:
        if capability == "external_video_search":
            config = LearningCapabilityRouter.external_video_tool_config(context, prompt)
        elif capability == "external_image_search":
            config = LearningCapabilityRouter.external_image_tool_config(context, prompt)
        elif capability == "deep_question":
            config = LearningCapabilityRouter.question_config(context, prompt, "生成 3 道练习题")
        elif capability == "visualize":
            config = LearningCapabilityRouter.visualize_config(context, "生成图解 visual diagram")
        elif capability == "math_animator":
            config = LearningCapabilityRouter.math_animator_config(context, "生成短视频 animation video")
        else:
            config = {}
        config["_coordinator_user_message"] = prompt
        config["profile_guided"] = True
        return config

    @staticmethod
    def visualize_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        config: dict[str, Any]
        if LearningCapabilityRouter.contains_any(text, ("流程图", "关系图", "思维导图", "mermaid", "flowchart", "diagram")):
            config = {"render_mode": "mermaid"}
        elif LearningCapabilityRouter.contains_any(text, ("图表", "柱状图", "折线图", "饼图", "chart", "bar", "line", "pie", "trend")):
            config = {"render_mode": "chartjs"}
        else:
            config = {"render_mode": "auto"}
        hints = LearningCapabilityRouter.learner_profile_hints(context)
        guidance = LearningCapabilityRouter.learner_profile_guidance(context)
        if guidance:
            config["style_hint"] = guidance
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def math_animator_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        output_mode = "video"
        if LearningCapabilityRouter.contains_any(text, ("分镜", "插图", "图片", "image", "storyboard")):
            output_mode = "image"
        config = {"output_mode": output_mode, "quality": "high"}
        hints = LearningCapabilityRouter.learner_profile_hints(context)
        guidance = LearningCapabilityRouter.learner_profile_guidance(context)
        if guidance:
            config["style_hint"] = guidance
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def question_config(context: UnifiedContext, original: str, text: str) -> dict[str, Any]:
        preference = "Generate interactive practice questions for the learner."
        guidance = LearningCapabilityRouter.learner_profile_guidance(context)
        if guidance:
            preference = f"{preference} Personalize with: {guidance}"
        return {
            "mode": "custom",
            "topic": original.strip(),
            "num_questions": LearningCapabilityRouter.extract_question_count(text),
            "difficulty": "",
            "question_type": LearningCapabilityRouter.infer_question_type(text),
            "preference": preference,
        }

    @staticmethod
    def research_config(context: UnifiedContext, text: str) -> dict[str, Any]:
        mode = (
            "learning_path"
            if LearningCapabilityRouter.contains_any(
                text,
                ("学习路径", "学习路线", "学习计划", "study plan", "learning path"),
            )
            else "report"
        )
        sources: list[str] = []
        enabled = set(context.enabled_tools or [])
        if context.knowledge_bases and (not enabled or "rag" in enabled):
            sources.append("kb")
        if not enabled or "web_search" in enabled:
            sources.append("web")
        if "paper_search" in enabled:
            sources.append("papers")
        config: dict[str, Any] = {
            "mode": mode,
            "depth": "standard",
            "sources": sources or ["web"],
        }
        hints = LearningCapabilityRouter.learner_profile_hints(context)
        if hints:
            config["learner_profile_hints"] = hints
        return config

    @staticmethod
    def research_tools(context: UnifiedContext) -> list[str] | None:
        tools = list(dict.fromkeys(context.enabled_tools or []))
        if context.knowledge_bases and "rag" not in tools:
            tools.insert(0, "rag")
        if "web_search" not in tools:
            tools.append("web_search")
        return tools

    @staticmethod
    def external_video_config(context: UnifiedContext) -> dict[str, Any]:
        profile_text = "\n".join(
            item
            for item in (
                context.memory_context,
                context.history_context,
                context.notebook_context,
            )
            if item
        )
        hints: dict[str, Any] = {
            **LearningCapabilityRouter.learner_profile_hints(context),
            "max_results": 3,
        }
        hints.setdefault("preferences", [])
        hints.setdefault("weak_points", [])
        if profile_text and not hints.get("profile_context"):
            hints["profile_context"] = profile_text[:1200]
        if context.knowledge_bases:
            hints["knowledge_bases"] = list(context.knowledge_bases)
        return hints

    @staticmethod
    def external_video_tool_config(context: UnifiedContext, prompt: str) -> dict[str, Any]:
        hints = LearningCapabilityRouter.external_video_config(context)
        try:
            max_results = int(hints.get("max_results") or 3)
        except (TypeError, ValueError):
            max_results = 3
        try:
            search_depth = int(hints.get("search_depth") or 8)
        except (TypeError, ValueError):
            search_depth = 8
        return {
            "_direct_tool": "external_video_search",
            "topic": prompt.strip() or context.user_message,
            "prompt": prompt.strip() or context.user_message,
            "language": context.language or "zh",
            "max_results": max_results,
            "search_depth": max(4, min(search_depth, 12)),
            "learner_hints": hints,
        }

    @staticmethod
    def external_image_config(context: UnifiedContext) -> dict[str, Any]:
        profile_text = "\n".join(
            item
            for item in (
                context.memory_context,
                context.history_context,
                context.notebook_context,
            )
            if item
        )
        hints: dict[str, Any] = {
            **LearningCapabilityRouter.learner_profile_hints(context),
            "max_results": 4,
        }
        hints.setdefault("preferences", [])
        hints.setdefault("weak_points", [])
        if profile_text and not hints.get("profile_context"):
            hints["profile_context"] = profile_text[:1200]
        if context.knowledge_bases:
            hints["knowledge_bases"] = list(context.knowledge_bases)
        return hints

    @staticmethod
    def external_image_tool_config(context: UnifiedContext, prompt: str) -> dict[str, Any]:
        hints = LearningCapabilityRouter.external_image_config(context)
        try:
            max_results = int(hints.get("max_results") or 4)
        except (TypeError, ValueError):
            max_results = 4
        try:
            search_depth = int(hints.get("search_depth") or 8)
        except (TypeError, ValueError):
            search_depth = 8
        return {
            "_direct_tool": "external_image_search",
            "topic": prompt.strip() or context.user_message,
            "prompt": prompt.strip() or context.user_message,
            "language": context.language or "zh",
            "max_results": max_results,
            "search_depth": max(4, min(search_depth, 12)),
            "learner_hints": hints,
        }

    @staticmethod
    def learner_profile_hints(context: UnifiedContext) -> dict[str, Any]:
        profile = context.metadata.get("learner_profile_context")
        if not isinstance(profile, dict):
            return {}
        raw_hints = profile.get("hints")
        if not isinstance(raw_hints, dict):
            raw_hints = {}

        hints: dict[str, Any] = {}
        for key in ("current_focus", "summary", "level", "preferred_resource"):
            value = LearningCapabilityRouter.hint_text(raw_hints.get(key), limit=220)
            if value:
                hints[key] = value
        time_budget = raw_hints.get("time_budget_minutes")
        if isinstance(time_budget, (int, float)) and int(time_budget) > 0:
            hints["time_budget_minutes"] = int(time_budget)

        for key in ("goals", "preferences", "strengths", "weak_points", "mastery_needs_attention"):
            values = LearningCapabilityRouter.hint_strings(raw_hints.get(key), limit=4)
            if values:
                hints[key] = values

        progress_style = raw_hints.get("progress_style")
        if isinstance(progress_style, dict):
            style = {
                "label": LearningCapabilityRouter.hint_text(progress_style.get("label")),
                "strategy": LearningCapabilityRouter.hint_text(progress_style.get("strategy"), limit=260),
                "preferred_resource": LearningCapabilityRouter.hint_text(progress_style.get("preferred_resource")),
            }
            style = {key: value for key, value in style.items() if value}
            if style:
                hints["progress_style"] = style

        next_action = raw_hints.get("next_action")
        if isinstance(next_action, dict):
            action = {
                "kind": LearningCapabilityRouter.hint_text(next_action.get("kind")),
                "title": LearningCapabilityRouter.hint_text(next_action.get("title")),
                "summary": LearningCapabilityRouter.hint_text(next_action.get("summary"), limit=260),
                "suggested_prompt": LearningCapabilityRouter.hint_text(next_action.get("suggested_prompt"), limit=360),
                "source_type": LearningCapabilityRouter.hint_text(next_action.get("source_type")),
                "source_label": LearningCapabilityRouter.hint_text(next_action.get("source_label")),
                "estimated_minutes": next_action.get("estimated_minutes"),
                "priority": next_action.get("priority"),
            }
            action = {key: value for key, value in action.items() if value}
            if action:
                hints["next_action"] = action

        decision_scores = raw_hints.get("decision_scores")
        if isinstance(decision_scores, dict):
            scores = {
                key: decision_scores.get(key)
                for key in ("profile_confidence", "evidence", "weakness", "mastery", "preference", "next_action_priority")
                if decision_scores.get(key) is not None
            }
            if scores:
                hints["decision_scores"] = scores

        concepts = LearningCapabilityRouter.merge_hint_strings(
            [
                hints.get("current_focus"),
                *(hints.get("weak_points") or []),
                *(hints.get("mastery_needs_attention") or []),
            ],
            limit=6,
        )
        if concepts:
            hints["concepts"] = concepts

        profile_text = LearningCapabilityRouter.hint_text(profile.get("text"), limit=1200)
        if profile_text:
            hints["profile_context"] = profile_text
        return hints

    @staticmethod
    def learner_profile_guidance(context: UnifiedContext) -> str:
        hints = LearningCapabilityRouter.learner_profile_hints(context)
        if not hints:
            return ""
        parts: list[str] = []
        level = hints.get("level")
        if level:
            parts.append(f"level={level}")
        weak_points = hints.get("weak_points") or hints.get("mastery_needs_attention")
        if weak_points:
            parts.append(f"focus weak points: {', '.join(LearningCapabilityRouter.hint_strings(weak_points, limit=3))}")
        preferences = hints.get("preferences")
        if preferences:
            parts.append(f"respect preferences: {', '.join(LearningCapabilityRouter.hint_strings(preferences, limit=3))}")
        preferred_resource = hints.get("preferred_resource")
        if preferred_resource:
            parts.append(f"preferred resource: {preferred_resource}")
        progress_style = hints.get("progress_style")
        if isinstance(progress_style, dict) and progress_style.get("label"):
            parts.append(f"progress style: {progress_style['label']}")
        time_budget = hints.get("time_budget_minutes")
        if time_budget:
            parts.append(f"fit within about {time_budget} minutes")
        action = hints.get("next_action")
        if isinstance(action, dict) and action.get("title"):
            parts.append(f"align with next action: {action['title']}")
        return "; ".join(part for part in parts if part)[:500]

    @staticmethod
    def hint_text(value: Any, *, limit: int = 180) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = " ".join(text.split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    @staticmethod
    def hint_strings(value: Any, *, limit: int = 4) -> list[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        items: list[str] = []
        for item in raw_items:
            text = LearningCapabilityRouter.hint_text(item)
            if text and text not in items:
                items.append(text)
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def merge_hint_strings(values: list[Any], *, limit: int) -> list[str]:
        merged: list[str] = []
        for value in values:
            for item in LearningCapabilityRouter.hint_strings(value, limit=limit):
                if item not in merged:
                    merged.append(item)
                if len(merged) >= limit:
                    return merged
        return merged

    @staticmethod
    def extract_question_count(text: str) -> int:
        match = re.search(r"(\d{1,2})\s*(?:道|个|题|questions?)", text)
        if not match:
            return 5 if LearningCapabilityRouter.contains_any(text, ("一组", "几道", "练习题", "题目")) else 3
        return min(max(int(match.group(1)), 1), 20)

    @staticmethod
    def infer_question_type(text: str) -> str:
        if LearningCapabilityRouter.contains_any(text, ("选择题", "单选", "multiple choice", "choice")):
            return "choice"
        if LearningCapabilityRouter.contains_any(text, ("判断题", "true false", "true/false")):
            return "true_false"
        if LearningCapabilityRouter.contains_any(text, ("填空题", "fill blank", "fill-in")):
            return "fill_blank"
        if LearningCapabilityRouter.contains_any(text, ("编程题", "coding")):
            return "coding"
        return ""

    @staticmethod
    def truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
        return bool(value)


__all__ = [
    "CoordinatorDecision",
    "DELEGABLE_CAPABILITIES",
    "LearningCapabilityRouter",
    "SPECIALIST_LABELS",
]
