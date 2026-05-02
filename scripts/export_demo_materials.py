#!/usr/bin/env python
"""Generate offline demo deck, recording script, and defense notes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE_ID = "ai_learning_agents_systems"
DEFAULT_OUTPUT = ROOT / "dist" / "demo_materials"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=DEFAULT_TEMPLATE_ID, help="Course template id.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory.")
    args = parser.parse_args()

    template = load_template(args.template)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)

    deck = build_deck_outline(template)
    script = build_recording_script(template)
    qa = build_defense_qa(template)
    index = build_index(template, output)

    (output / "sparkweave-demo-deck-outline.md").write_text(deck, encoding="utf-8")
    (output / "sparkweave-7min-recording-script.md").write_text(script, encoding="utf-8")
    (output / "sparkweave-defense-qa.md").write_text(qa, encoding="utf-8")
    (output / "README.md").write_text(index, encoding="utf-8")

    print(f"[demo-materials] exported template {template.get('id')} to {output}")
    return 0


def load_template(template_id: str) -> dict[str, Any]:
    path = ROOT / "data" / "course_templates" / f"{template_id}.json"
    if not path.exists():
        candidates = ", ".join(sorted(item.stem for item in (ROOT / "data" / "course_templates").glob("*.json")))
        raise SystemExit(f"Unknown template {template_id!r}. Available: {candidates}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_deck_outline(template: dict[str, Any]) -> str:
    course = text(template.get("course_name") or template.get("title"), "大模型教育智能体系统开发")
    outcomes = list_of_text(template.get("learning_outcomes"))[:5]
    seed = template.get("demo_seed") if isinstance(template.get("demo_seed"), dict) else {}
    persona = seed.get("persona") if isinstance(seed.get("persona"), dict) else {}
    weak_points = list_of_text(persona.get("weak_points"))[:3]
    preferences = list_of_text(persona.get("preferences"))[:3]
    tasks = task_lookup(template)
    chain = [tasks.get(task_id, {"title": task_id}) for task_id in list_of_text(seed.get("task_chain"))]

    slides = [
        {
            "title": "项目价值：从聊天机器人到学习闭环",
            "purpose": "先告诉评委系统解决什么真实问题。",
            "bullets": [
                "学生不需要自己在一堆工具里选择下一步。",
                "系统围绕学习画像组织导学、资源、练习、反馈和报告。",
                "目标是服务高校课程中的个性化、多模态、可评估学习。",
            ],
            "visual": "首页或导学页截图，建议使用 screenshots-simplified-guide.png。",
        },
        {
            "title": "赛题五项要求对齐",
            "purpose": "把项目叙事直接对齐评分点。",
            "bullets": [
                "对话式学习画像：从对话、练习、反思、资源行为形成证据。",
                "多智能体资源生成：画像、规划、检索、图解、视频、出题、评估接力。",
                "个性化路径：当前任务、补基任务、下一步推荐。",
                "智能辅导与效果评估：图解、短视频、练习反馈、学习报告。",
            ],
            "visual": "系统架构图或赛题对齐卡片。",
        },
        {
            "title": f"完整课程样例：{course}",
            "purpose": "证明系统不是单点 Demo，而是一门课程。",
            "bullets": outcomes or ["课程模板包含目标、知识点、任务、评估和演示种子。"],
            "visual": "导学课程卡片或课程路线截图。",
        },
        {
            "title": "学习画像：让系统知道学生当下需要什么",
            "purpose": "突出画像不是静态标签。",
            "bullets": [
                f"演示学习者目标：{text(persona.get('goal'), text(template.get('default_goal'), '完成课程项目'))}",
                f"主要卡点：{join_or(weak_points, '概念边界、证据链和评估处方')}",
                f"资源偏好：{join_or([resource_preference_label(item) for item in preferences], '图解、练习、短视频')}",
                "每次提交练习和反思后，画像会形成新的证据。",
            ],
            "visual": "学习画像页、画像证据卡或报告里的画像驱动产出。",
        },
        {
            "title": "多智能体接力：把一个学习请求拆给专业角色",
            "purpose": "让评委看懂多智能体不是口号。",
            "bullets": [
                "协调智能体判断请求意图和当前画像。",
                "规划智能体选择当前任务和补基顺序。",
                "检索、图解、视频、出题智能体生成不同资源。",
                "评估智能体把结果压缩成下一步学习处方。",
            ],
            "visual": "聊天协作明细或导学资源卡里的接力路线。",
        },
        {
            "title": "多模态资源：只围绕当前任务生成",
            "purpose": "证明资源生成服务学习，而不是炫技。",
            "bullets": [f"{index + 1}. {text(item.get('title'), '演示任务')}" for index, item in enumerate(chain[:4])]
            or ["图解、短视频和互动练习都围绕当前任务产生。"],
            "visual": "图解结果、Manim 视频或互动练习截图。",
        },
        {
            "title": "学习效果评估：从分数到学习处方",
            "purpose": "覆盖可选加分项。",
            "bullets": [
                "练习结果、错因、反思和资源使用行为形成学习证据。",
                "报告给出掌握度、主要卡点、下一步动作和演示就绪度。",
                "评估结果反向影响后续资源推送和学习路径。",
            ],
            "visual": "学习报告、演示就绪度或课程产出包截图。",
        },
        {
            "title": "提交材料与稳定性",
            "purpose": "收束到比赛交付。",
            "bullets": [
                "可运行源码、依赖配置、课程模板和文档均在仓库中。",
                "提交包导出器可整理文档、截图、模板和运行配置。",
                "Markdown 导出支持把课程产出包和学习报告整理到 PPT 或提交文档。",
            ],
            "visual": "competition_package 索引或课程产出包下载按钮。",
        },
    ]

    lines = [
        "# SparkWeave 演示 PPT 骨架",
        "",
        f"- 课程：{course}",
        f"- 生成时间：{now()}",
        "- 建议页数：8 页",
        "",
    ]
    for index, slide in enumerate(slides, start=1):
        lines.extend(
            [
                f"## P{index}. {slide['title']}",
                "",
                f"**本页目的：** {slide['purpose']}",
                "",
                "**要点：**",
            ]
        )
        lines.extend(f"- {item}" for item in slide["bullets"])
        lines.extend(["", f"**建议画面：** {slide['visual']}", ""])
    return "\n".join(lines).strip() + "\n"


def build_recording_script(template: dict[str, Any]) -> str:
    course = text(template.get("course_name") or template.get("title"), "大模型教育智能体系统开发")
    seed = template.get("demo_seed") if isinstance(template.get("demo_seed"), dict) else {}
    scenario = text(seed.get("scenario"), "从画像、导学、资源、练习、报告到产出包跑通完整闭环。")
    tasks = task_lookup(template)
    chain = [tasks.get(task_id, {"title": task_id}) for task_id in list_of_text(seed.get("task_chain"))]
    first_task = text(chain[0].get("title") if chain else "", "当前任务")
    resource_task = text(chain[2].get("title") if len(chain) >= 3 else first_task, "多智能体资源生成")

    segments = [
        ("0:00-0:40", "/guide", "开场与课程选择", f"打开导学页，选择「{course}」赛题主线课程。", "SparkWeave 不是普通聊天机器人，而是围绕学习画像组织路径、资源、练习和评估的学习闭环。"),
        ("0:40-1:30", "当前任务", "懒人式导学", f"展示「先做这一件事」和任务：{first_task}。", "学生不用理解工具箱，系统直接告诉他现在最该完成哪一步。"),
        ("1:30-2:40", "画像/路线", "画像驱动", "展示目标、薄弱点、资源偏好和路线节点。", "画像来自对话、练习、反思和资源行为，并会影响当前任务选择。"),
        ("2:40-4:00", "资源生成", "多智能体协作", f"围绕任务「{resource_task}」生成图解、视频或练习。", "协调智能体把请求交给图解、视频、出题或检索智能体，再由评估智能体接回闭环。"),
        ("4:00-5:10", "提交页", "互动练习与反馈", "提交示例评分和一句反思。", "练习不是展示题目而已，提交后会形成学习证据并回写画像。"),
        ("5:10-6:10", "学习报告", "效果评估", "展示学习处方、错因和演示就绪度。", "系统把分数、错因和画像信号压缩成下一步可执行建议。"),
        ("6:10-7:00", "课程产出包", "比赛交付收束", "展示 PPT 骨架、录屏讲稿、赛题对齐、答辩问答和下载 Markdown。", "最后把学习过程整理成比赛可提交材料，包含源码、课程样例、文档、视频脚本和 AI Coding 说明。"),
    ]

    lines = [
        "# SparkWeave 7 分钟录屏讲稿",
        "",
        f"- 课程：{course}",
        f"- 演示故事：{scenario}",
        f"- 生成时间：{now()}",
        "",
    ]
    for time_range, screen, title, action, narration in segments:
        lines.extend(
            [
                f"## {time_range} {title}",
                "",
                f"- 页面：{screen}",
                f"- 动作：{action}",
                f"- 讲述：{narration}",
                "- 兜底：如果现场生成慢，展示课程产出包中的稳定素材或历史截图。",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_defense_qa(template: dict[str, Any]) -> str:
    course = text(template.get("course_name") or template.get("title"), "大模型教育智能体系统开发")
    qa = [
        ("为什么不是普通聊天机器人？", "因为系统围绕学习画像形成导学、资源、练习、反馈和报告闭环，而不是只回答单轮问题。"),
        ("学习画像如何构建？", "画像来自对话、前测、练习、反思、Notebook 和资源使用证据，并保留可信度与用户校准入口。"),
        ("多智能体协作体现在哪里？", "协调智能体会根据意图和画像唤醒规划、检索、图解、视频、出题和评估智能体，前端用用户可读的接力路线展示。"),
        ("个性化路径如何产生？", "系统结合目标、时间预算、薄弱点、掌握度和资源偏好，生成当前任务、补基任务和下一步推荐。"),
        ("智能辅导如何体现多模态？", "同一学习卡点可以生成文字讲解、图解、Manim 短视频、互动练习和公开视频推荐。"),
        ("学习效果如何评估？", "系统汇总练习正确率、错因、反思质量、资源行为和画像趋势，输出学习处方并调整路径。"),
        ("如果现场模型或视频生成不稳定怎么办？", "导学课程模板包含稳定任务链、资源提示词、兜底素材、历史产物和录屏讲稿，保证演示不因单次生成波动中断。"),
        ("AI Coding 工具如何说明？", "文档中单独说明 AI Coding 的辅助范围、人工复核、密钥边界和可追溯材料，最终提交仍由人工复核。"),
    ]

    lines = [
        "# SparkWeave 答辩问答预案",
        "",
        f"- 课程：{course}",
        f"- 生成时间：{now()}",
        "",
    ]
    for index, (question, answer) in enumerate(qa, start=1):
        lines.extend([f"## Q{index}. {question}", "", answer, ""])
    return "\n".join(lines).strip() + "\n"


def build_index(template: dict[str, Any], output: Path) -> str:
    course = text(template.get("course_name") or template.get("title"), "大模型教育智能体系统开发")
    return "\n".join(
        [
            "# SparkWeave 演示材料",
            "",
            f"- 课程：{course}",
            f"- 输出目录：`{output}`",
            f"- 生成时间：{now()}",
            "",
            "## 文件",
            "",
            "- `sparkweave-demo-deck-outline.md`：8 页答辩 PPT 骨架。",
            "- `sparkweave-7min-recording-script.md`：7 分钟录屏分段讲稿。",
            "- `sparkweave-defense-qa.md`：评委追问回答预案。",
            "",
            "这些材料是离线兜底版本。正式演示时，优先使用导学页课程产出包里的 Markdown 导出，因为它会包含当前真实 session 的画像、任务、报告和产物证据。",
        ]
    ) + "\n"


def task_lookup(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = template.get("tasks") if isinstance(template.get("tasks"), list) else []
    return {str(item.get("task_id")): item for item in tasks if isinstance(item, dict) and item.get("task_id")}


def list_of_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def text(value: Any, fallback: str) -> str:
    stripped = str(value).strip() if value is not None else ""
    return stripped or fallback


def join_or(items: list[str], fallback: str) -> str:
    return "、".join(items) if items else fallback


def resource_preference_label(value: str) -> str:
    aliases = {
        "visual": "图解",
        "practice": "练习",
        "video": "短视频",
        "external_video": "公开视频",
        "quiz": "互动题",
    }
    return aliases.get(value, value)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    raise SystemExit(main())
