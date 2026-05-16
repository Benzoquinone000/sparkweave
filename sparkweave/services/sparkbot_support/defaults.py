"""Default SparkBot workspace files and souls."""

from __future__ import annotations

from sparkweave.services.sparkbot_support.config_models import (
    _COMPETITION_DEMO_SOUL,
    COMPETITION_DEMO_BOT_ID,
)

DEFAULT_TEMPLATES = {
    "SOUL.md": "# Soul\n\nI am SparkBot, a personal learning companion.\n",
    "USER.md": "# User\n\nKeep track of the learner's preferences, goals, and context here.\n",
    "TOOLS.md": "# Tools\n\nUse SparkWeave capabilities, knowledge bases, and local files responsibly.\n",
    "AGENTS.md": "# Agent Notes\n\nWork carefully, explain clearly, and preserve user privacy.\n",
    "HEARTBEAT.md": "# Heartbeat\n\nReview reminders and proactive learning opportunities here.\n",
    "NOTES.md": "# Notes\n\nCapture useful learner notes, generated resources, and follow-up questions here.\n",
    "COURSE.md": "# Course\n\nDescribe the course goals, target learners, modules, and assessment plan here.\n",
    "LESSONS.md": "# Lessons\n\nList weekly lessons, learning outcomes, activities, and demo prompts here.\n",
    "QUESTION_BANK.md": "# Question Bank\n\nKeep reusable quizzes, practice tasks, rubrics, and answer keys here.\n",
    "RUBRIC.md": "# Rubric\n\nDefine grading criteria for the course project and demo artifacts here.\n",
    "RESOURCES.md": "# Resources\n\nCollect course readings, videos, tools, and extension materials here.\n",
}

COMPETITION_DEMO_WORKSPACE_FILES = {
    "SOUL.md": _COMPETITION_DEMO_SOUL,
    "USER.md": """# User

演示学习者：

- 课程：大模型与智能学习系统
- 当前目标：完成个性化学习智能体原型设计
- 当前卡点：RAG 证据链、多智能体任务拆分、学习效果评估闭环
- 偏好资源：图解、短练习、语音讲解脚本、真实案例
- 时间预算：每次 8 到 12 分钟

助教要优先回答：

1. 今天先做哪一步。
2. 为什么推荐这一步。
3. 需要参考哪些课程资料。
4. 完成后如何回写画像和学习效果。
""",
    "TOOLS.md": """# Tools

比赛演示工具链：

- 讯飞星火大模型：用于对话式辅导、资源生成、讲解改写和学习处方。
- SparkWeave RAG / 星火知识库：用于课程资料检索和来源约束答疑。
- 科大讯飞 OCR / 公式识别：用于讲义截图、题目图片和板书内容识别。
- 科大讯飞语音听写：用于学生语音提问、课堂口述笔记和录音转写。
- 科大讯飞 TTS：用于 60 秒语音讲解、短视频旁白和移动端复习。
- deep_question：用于围绕薄弱点生成小测和复测题。
- deep_solve / reason：用于分步讲解复杂题目。

回答时不要暴露原始 JSON、密钥或调试日志。需要说明工具时，用“正在查看课程资料”“正在生成练习”“正在写入学习证据”等学习语言。
""",
    "AGENTS.md": """# Agent Notes

演示协作路线：

学习画像智能体 -> 路径规划智能体 -> 课程资料检索智能体 -> 讲解/图解/出题智能体 -> 学习效果评估智能体

默认产物：

- 今日学习建议
- 来源可追溯讲解
- 3 道小测
- 图解结构说明
- 讯飞 TTS 语音讲解脚本
- 错因复盘与下一步计划

协作原则：

1. 先给学生一个主行动，再给可选支线。
2. 生成练习后必须等待学生作答或要求学生自评。
3. 学生反馈“太难了”时降低难度并给例子。
4. 学生反馈“不准确”时主动回到课程资料和来源检查。
5. 演示时始终把功能映射到画像、资源、路径、辅导、评估五项赛题要求。
""",
    "HEARTBEAT.md": """# Heartbeat

演示前主动检查：

- 当前助教是否在线。
- 工作区是否包含 NOTES.md。
- 今日建议是否能解释推荐原因。
- 是否能生成图解、练习和讯飞 TTS 脚本。
- 是否能把反馈写入学习效果事件。

如果学生长时间没有继续，提醒：

> 我建议先完成 8 分钟小测，再根据结果决定是否回到图解讲解。
""",
    "NOTES.md": """# Notes

今日演示目标：

1. 展示 AI 助教中心给出“今天先做什么”。
2. 展示建议依据：学习画像、最近练习、课程资料。
3. 展示多智能体资源生成：讲解、图解、练习、语音脚本。
4. 展示科大讯飞工具链：星火、OCR、语音听写、TTS。
5. 展示学习效果闭环：反馈写入证据，下一步动态调整。

稳定提示词：

- 请基于我的学习画像和课程资料，告诉我今天最应该完成的一步。
- 请把 RAG 证据链用图解方式讲清楚。
- 请生成 3 道多智能体协作机制小测，并等我作答后分析错因。
- 请生成一段适合科大讯飞 TTS 合成的 60 秒语音讲解脚本。
- 请复盘我刚才的回答，把错因和下一步写入学习记录。
""",
    "COURSE.md": """# 大模型与智能学习系统

课程标识：`ai_learning_agents_systems`

## 课程定位

这是一门面向人工智能、软件工程和教育技术方向本科高年级或研究生的项目式课程。学生将在 8 周内完成一个可运行的个性化学习智能体原型，系统展示学习画像、课程资料 RAG、多智能体资源生成、个性化路径规划、智能辅导和学习效果评估闭环。

## 学习对象

- 具备 Python 或 Web 开发基础。
- 了解大模型 API 或提示词基本概念。
- 希望完成一个教育智能体课程项目或比赛 Demo。

## 课程目标

1. 能解释学习画像如何由对话、练习、反思和资源使用证据持续更新。
2. 能设计课程知识库 RAG 流程，并说明来源约束、召回、重排和引用依据。
3. 能拆分画像、规划、检索、讲解、出题、图解、语音和评估等智能体角色。
4. 能生成图解、语音讲解、互动练习和学习报告等多模态资源。
5. 能基于学习证据给出下一步学习处方，并回写学习画像。

## 课程项目

项目名称：面向高校课程的个性化 AI 助教

项目产物：

- 一套课程资料包。
- 一个长期 AI 助教。
- 一条多智能体协作路线。
- 至少三类学习资源：文字讲解、图解、练习或语音讲解。
- 一份学习效果评估报告。
- 7 分钟项目演示脚本和答辩材料。

## 考核结构

| 模块 | 权重 | 说明 |
| --- | ---: | --- |
| 学习画像设计说明 | 20% | 字段、证据、可信度、用户校准 |
| RAG 与多智能体流程图 | 25% | 资料检索、协作路线、来源依据 |
| 多模态资源生成 Demo | 25% | 图解、语音、练习、短视频脚本 |
| 学习效果评估报告 | 20% | 掌握度、错因、下一步处方 |
| 项目答辩 | 10% | 7 分钟演示与技术问答 |
""",
    "LESSONS.md": """# Lessons

## 8 周课程安排

| 周次 | 模块 | 学习目标 | 助教可展示能力 |
| --- | --- | --- | --- |
| 1 | 教育智能体系统全景 | 画出用户、画像、资料、智能体、评估的数据流 | 今日建议、系统全景图 |
| 2 | 学习画像与证据建模 | 区分对话证据、练习证据、反思证据和用户校准 | 对话式画像、证据解释 |
| 3 | 课程知识库与 RAG | 理解分块、召回、重排、引用依据和风险控制 | 来源约束答疑、资料追溯 |
| 4 | 多智能体协作编排 | 拆分画像、规划、检索、图解、出题和评估角色 | 学习协作路线 |
| 5 | 多模态学习资源生成 | 生成图解、TTS 脚本、短视频脚本和互动练习 | 讯飞 OCR、TTS、多模态资源动作 |
| 6 | 个性化路径规划 | 根据目标、薄弱点、时间预算和偏好选择下一步 | 学习效果 next action |
| 7 | 学习效果评估与处方 | 把练习、反馈和资源使用转成掌握度与错因 | 反馈回写、错因复盘 |
| 8 | 项目演示与答辩 | 用 7 分钟展示完整闭环和创新价值 | 演示 Runbook、答辩清单 |

## 课堂活动样例

1. 让助教生成“教育智能体系统全景图”并检查是否覆盖六个模块。
2. 上传一张讲义截图，使用 OCR 识别后让助教讲解关键概念。
3. 点击“讯飞语音脚本”，生成 60 秒口语化讲解并试听。
4. 让练习智能体生成 3 道小测，学生作答后写入错因。
5. 打开“学习协作路线”，向评审说明每个智能体的职责。

## 录屏稳定提示词

- 请基于我的学习画像和课程资料，告诉我今天最应该完成的一步。
- 请把 RAG 证据链用图解方式讲清楚。
- 请生成 3 道多智能体协作机制小测，并等我作答后分析错因。
- 请生成一段适合科大讯飞 TTS 合成的 60 秒语音讲解脚本。
- 请复盘我刚才的回答，把错因和下一步写入学习记录。
""",
    "QUESTION_BANK.md": """# Question Bank

## A. 概念理解题

1. 学习画像为什么不能只由一次对话生成？
   - 参考答案：画像需要多源证据，包括对话、练习、反思、资源使用和用户校准；一次对话容易受上下文偶然因素影响。
2. RAG 中“来源可追溯”主要解决什么问题？
   - 参考答案：降低无依据回答和幻觉风险，让学生和教师能检查答案来自哪些课程资料。
3. 多智能体协作相比单一聊天助手的优势是什么？
   - 参考答案：可以把画像、规划、检索、资源生成和评估拆成职责清晰的角色，提升可解释性和可扩展性。

## B. 判断题

1. 只要大模型回答流畅，就可以认为学习效果已经提升。错误。
2. OCR 识别讲义后，仍需要结合课程资料和学习画像进行讲解。正确。
3. TTS 语音讲解适合把复杂脚本原样朗读，不需要口语化改写。错误。

## C. 实践任务

### 任务 1：画像证据表

列出一个学生“RAG 证据链薄弱”的证据表，至少包含证据来源、可信度、时间和下一步建议。

评分点：

- 字段清晰。
- 能区分强证据与弱证据。
- 给出可执行下一步。

### 任务 2：多智能体接力路线

把“我想补齐多智能体资源生成流程”拆分为 5 个智能体步骤。

参考步骤：

1. 画像智能体读取薄弱点和偏好。
2. 路径规划智能体选择 8 分钟任务。
3. 资料检索智能体查找课程依据。
4. 图解/出题智能体生成资源。
5. 评估智能体根据反馈更新画像。

### 任务 3：学习效果评估

给定学生小测正确率 60%、反馈“太难了”、偏好“图解”，写出下一步学习处方。

优秀答案应包含：

- 当前掌握度判断。
- 可能错因。
- 一条降低难度的图解资源。
- 一条短练习复测。
""",
    "RUBRIC.md": """# Rubric

## 项目评分 Rubric

| 维度 | 优秀 | 合格 | 需改进 |
| --- | --- | --- | --- |
| 学习画像 | 有多源证据、可信度和用户校准 | 有基础画像字段 | 只做静态标签 |
| 课程资料/RAG | 能展示来源、召回依据和风险控制 | 能基于资料回答 | 回答与资料关联弱 |
| 多智能体协作 | 角色职责清晰，页面可见协作路线 | 有多个能力模块 | 只是普通聊天 |
| 个性化路径 | 推荐原因明确，能动态调整 | 有下一步建议 | 推荐泛泛而谈 |
| 多模态资源 | 文本、图解、OCR、TTS 或视频脚本能串联 | 有单项资源生成 | 资源不可复用 |
| 学习评估 | 能回写反馈、错因和掌握度 | 有简单记录 | 无闭环 |
| 演示表达 | 7 分钟覆盖赛题五项要求 | 能跑通主要功能 | 演示路线不稳定 |

## 赛题评分映射

- 创新价值与实用性：长期助教、画像驱动、资源可复用、学习闭环。
- 功能实现及技术要求：SparkBot、RAG、多智能体、讯飞 OCR/TTS/星火、学习效果评估。
- 配套文档：计划书、Runbook、AI Coding 说明、课程资料包。
- PPT/视频效果：7 分钟路线、稳定提示词、兜底素材。
""",
    "RESOURCES.md": """# Resources

## 课程资料

- `COURSE.md`：课程定位、目标、项目产物和考核结构。
- `LESSONS.md`：8 周课程安排和录屏稳定提示词。
- `QUESTION_BANK.md`：概念题、判断题、实践任务和参考答案。
- `RUBRIC.md`：课程项目评分标准和赛题映射。
- `NOTES.md`：演示当天的固定目标和提示词。

## SparkWeave 页面入口

- `/agents`：AI 助教中心，演示长期助教、资料与产物、多模态资源动作。
- `/memory`：学习画像与证据账本。
- `/knowledge`：课程资料库和 RAG 检索。
- `/question`：题目生成与练习。
- `/vision`：OCR 与图像题解析。
- `/settings`：讯飞、LLM、Embedding、OCR、TTS 等 provider 配置。

## 科大讯飞工具链讲法

- 星火大模型：对话式讲解、资源生成、学习处方。
- OCR/公式识别：讲义截图和题目图片识别。
- 语音听写：学生语音提问、课堂口述笔记。
- TTS：60 秒语音讲解和短视频旁白。
- 星火知识库或 SparkWeave RAG：课程私域资料问答和来源追溯。

## 演示兜底

如果真实服务暂不可用，先展示课程资料包、学习协作路线、稳定提示词和已生成的产物卡，再说明 provider 可降级且不阻断文字助教闭环。
""",
}

DEFAULT_SOULS = [
    {
        "id": "default-sparkbot",
        "name": "Default SparkBot",
        "content": (
            "# Soul\n\nI am SparkBot, a personal learning companion.\n\n"
            "I explain clearly, remember useful context, and adapt to the learner."
        ),
    },
    {
        "id": "math-tutor",
        "name": "Math Tutor",
        "content": (
            "# Soul\n\nI am a patient math tutor.\n\n"
            "I break problems into steps, ask good questions, and verify final answers."
        ),
    },
    {
        "id": "research-helper",
        "name": "Research Helper",
        "content": (
            "# Soul\n\nI help explore research topics in depth.\n\n"
            "I decompose broad questions, compare evidence, and cite sources when possible."
        ),
    },
    {
        "id": COMPETITION_DEMO_BOT_ID,
        "name": "大模型与智能学习系统助教",
        "content": _COMPETITION_DEMO_SOUL,
    },
]


__all__ = [
    "COMPETITION_DEMO_WORKSPACE_FILES",
    "DEFAULT_SOULS",
    "DEFAULT_TEMPLATES",
]
