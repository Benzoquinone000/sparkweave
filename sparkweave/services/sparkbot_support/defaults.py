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

- 课程：深度学习
- 当前目标：梳理 CNN、注意力机制、Transformer 和大模型应用主线
- 当前卡点：CNN 图像检索流程、Q/K/V 关系、BERT 与 GPT 差异
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
- SparkWeave RAG / 星火知识库：用于深度学习课件检索和来源约束答疑。
- 科大讯飞 OCR / 公式识别：用于讲义截图、题目图片和板书内容识别。
- 科大讯飞语音听写：用于学生语音提问、课堂口述笔记和录音转写。
- 科大讯飞 TTS：用于 60 秒语音讲解、短视频旁白和移动端复习。
- deep_question：用于围绕薄弱点生成小测和复测题。
- deep_solve / reason：用于分步讲解复杂概念和模型结构。

回答时不要暴露原始 JSON、密钥或调试日志。需要说明工具时，用“正在查看课程资料”“正在生成练习”“正在写入学习证据”等学习语言。
""",
    "AGENTS.md": """# Agent Notes

演示协作路线：

学习画像智能体 -> 路径规划智能体 -> 课件资料检索智能体 -> 讲解/图解/出题智能体 -> 学习效果评估智能体

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
5. 演示时始终围绕深度学习课程本身讲功能，不把页面讲成技术清单。
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
- 请把 CNN 图像检索流程用图解方式讲清楚。
- 请生成 3 道注意力机制小测，并等我作答后分析错因。
- 请生成一段适合科大讯飞 TTS 合成的 60 秒语音讲解脚本。
- 请复盘我刚才的回答，把错因和下一步写入学习记录。
""",
    "COURSE.md": """# 深度学习

课程标识：`deep_learning_foundations`

## 课程定位

这是一门面向人工智能、计算机和相关专业本科高年级学生的专业课程。学生会从神经网络基础学起，逐步进入 CNN、RNN、注意力机制、Transformer、大模型应用、无监督学习和深度生成模型，并在学习过程中保存资料来源、练习反馈和复盘记录。

## 学习对象

- 具备 Python 或 Web 开发基础。
- 学过线性代数、概率统计和机器学习基础。
- 希望把深度学习主要模型、应用流程和课程项目串成一条清楚路线。

## 课程目标

1. 能说明人工智能、机器学习和深度学习的关系。
2. 能解释前馈神经网络和 CNN 的结构与适用场景。
3. 能把 CNN 特征抽取放入图像检索流程中理解。
4. 能比较 RNN、注意力机制和 Transformer 的序列建模思路。
5. 能解释大模型中的预训练、SFT、RLHF、RAG、Agent 和 CoT。
6. 能区分聚类、PCA、VAE、GAN 等无监督与生成式方法。

## 课程项目

项目名称：深度学习课程学习报告

项目产物：

- 一张 CNN 或 Transformer 模型结构图。
- 一个应用流程案例，例如 CNN 图像检索或大模型学习助手。
- 至少三类学习证据：资料问答来源、练习结果、错因复盘。
- 一份课程项目报告，说明模型主线、应用场景和下一步学习计划。

## 考核结构

| 模块 | 权重 | 说明 |
| --- | ---: | --- |
| 章节小测 | 20% | 神经网络、CNN、注意力、Transformer 等概念检查 |
| 实践练习 | 25% | 图像检索、模型对比或大模型应用链路练习 |
| 资料问答与证据记录 | 15% | 回答要能追溯到课件或资料来源 |
| 课程项目报告 | 30% | 模型路线、案例分析、错因复盘和后续计划 |
| 学习反思 | 10% | 薄弱点、资源使用体验和下一步补救 |
""",
    "LESSONS.md": """# Lessons

## 14 周课程安排

| 周次 | 模块 | 学习目标 | 助教可展示能力 |
| --- | --- | --- | --- |
| 1 | 绪论 | 说明 AI、机器学习和深度学习的关系 | 概念图、目标卡 |
| 2 | 前馈神经网络 | 拆解输入、隐藏层、激活函数和损失函数 | 步骤讲解、小测 |
| 3 | 卷积神经网络 | 说明局部连接、权值共享和池化 | CNN 结构图 |
| 4 | 软硬件基础 | 理解 CPU、GPU、框架和训练流程 | 对比表、环境清单 |
| 5 | CNN 图像检索 | 把 CNN 特征用于图像检索流程 | 应用流程图 |
| 6 | 多模态学习 | 比较文本、图像、语音等模态表示 | 模态对齐表 |
| 7 | 循环神经网络 | 理解序列状态和时间展开 | 动画脚本、小测 |
| 8 | 注意力与外部记忆 | 解释 Q/K/V、外部记忆和 RAG 关系 | 资料证据图 |
| 9 | Transformer | 比较自注意力、位置编码、BERT 和 GPT | 模块图、对比卡 |
| 10 | 大模型应用 | 理解预训练、SFT、RAG、Agent 和 CoT | 应用链路 |
| 11 | 应用案例复盘 | 分析任务目标、资料来源和风险边界 | 报告提纲 |
| 12 | 强化学习 | 比较奖励模型、PPO、DPO 和 GRPO | 判断题、对比表 |
| 13 | 无监督学习 | 理解聚类、K-means、PCA 和降维 | 练习报告 |
| 14 | 深度生成模型 | 比较 VAE、GAN 并完成课程报告 | 项目复盘 |

## 课堂活动样例

1. 让助教生成 CNN 结构图，并检查是否覆盖卷积、池化和分类头。
2. 上传一页深度学习课件截图，使用 OCR 识别后让助教讲解关键概念。
3. 生成 60 秒口语化讲解脚本，用于复述注意力机制。
4. 让练习智能体生成 3 道 Transformer 小测，学生作答后写入错因。
5. 打开学习记录，说明系统如何根据反馈调整下一步。

## 录屏稳定提示词

- 请基于我的学习画像和课程资料，告诉我今天最应该完成的一步。
- 请把 CNN 图像检索流程用图解方式讲清楚。
- 请生成 3 道注意力机制小测，并等我作答后分析错因。
- 请生成一段适合科大讯飞 TTS 合成的 60 秒语音讲解脚本。
- 请复盘我刚才的回答，把错因和下一步写入学习记录。
""",
    "QUESTION_BANK.md": """# Question Bank

## A. 概念理解题

1. CNN 为什么适合图像任务？
   - 参考答案：CNN 通过局部连接和权值共享提取空间邻域特征，参数量比全连接网络更可控，也更容易学习边缘、纹理和局部模式。
2. 注意力机制里的 Query、Key、Value 分别起什么作用？
   - 参考答案：Query 表示当前要寻找的信息，Key 用于匹配相关位置，Value 是被加权汇总的内容。
3. BERT 和 GPT 的主要差异是什么？
   - 参考答案：BERT 更偏双向表示学习，常用于理解任务；GPT 采用自回归方式预测下一个 token，更适合生成任务。

## B. 判断题

1. 卷积层的权值共享可以减少参数量。正确。
2. 图像检索只需要分类标签，不需要特征表示。错误。
3. Transformer 完全不需要位置相关信息。错误。

## C. 实践任务

### 任务 1：CNN 图像检索流程

写出一个基于 CNN 特征的图像检索流程，至少包含查询图像、特征抽取、相似度计算和排序返回。

评分点：

- 流程完整。
- 能解释 CNN 特征和传统手工特征的差异。
- 能说明结果排序依据。

### 任务 2：Transformer 模块说明

用自己的话说明 Transformer 中自注意力、位置编码和前馈层分别解决什么问题。

参考要点：

1. 自注意力用于在序列内部选择相关信息。
2. 位置编码让模型知道 token 的顺序。
3. 前馈层对每个位置做非线性变换。
4. 多头注意力可以从多个关系子空间看上下文。

### 任务 3：大模型应用链路

围绕“课程资料问答助手”，写出预训练模型、SFT、RAG、Agent 和学习评估分别在系统中的位置。

优秀答案应包含：

- 任务目标清楚。
- 能说明资料来源如何进入回答。
- 能指出 Agent 和 RAG 的边界。
- 能把练习反馈写回学习记录。
""",
    "RUBRIC.md": """# Rubric

## 项目评分 Rubric

| 维度 | 优秀 | 合格 | 需改进 |
| --- | --- | --- | --- |
| 模型理解 | 能清楚解释 CNN、RNN、注意力、Transformer 的差异 | 能说明主要结构 | 只会背术语 |
| 应用流程 | 能把 CNN 图像检索或大模型应用链路讲完整 | 能说明部分步骤 | 流程前后断裂 |
| 资料依据 | 回答和报告能引用课件或资料来源 | 有少量来源 | 没有证据 |
| 图解与练习 | 图解、练习和错因复盘能互相呼应 | 有单项资源 | 资源和任务脱节 |
| 学习评估 | 能根据练习反馈调整下一步 | 有简单记录 | 无闭环 |
| 项目报告 | 结构完整，有模型主线、案例、反思和计划 | 基本完整 | 只有零散笔记 |

## 赛题评分映射

- 创新价值与实用性：用真实深度学习课程展示个性化路径、资料证据和学习反馈。
- 功能实现及技术要求：课程模板、RAG、多智能体资源生成、讯飞 OCR/TTS/星火和学习效果评估。
- 配套文档：课程说明、运行说明、AI Coding 说明和提交边界。
- PPT/视频效果：围绕同一门深度学习课程录制 7 分钟学习流程。
""",
    "RESOURCES.md": """# Resources

## 课程资料

- `COURSE.md`：课程定位、目标、项目产物和考核结构。
- `LESSONS.md`：14 周课程安排和录屏稳定提示词。
- `QUESTION_BANK.md`：概念题、判断题、实践任务和参考答案。
- `RUBRIC.md`：课程项目评分标准和赛题映射。
- `NOTES.md`：演示当天的固定目标和提示词。

## SparkWeave 页面入口

- `/agents`：AI 助教中心，演示长期助教、资料与产物、多模态资源动作。
- `/memory`：学习画像与证据账本。
- `/knowledge`：课程资料库和 RAG 检索。
- `/question`：题目生成与练习。
- `/vision`：OCR 与图像题解析。
- `/settings`：讯飞、LLM、Embedding、OCR、公式识别、图片理解、语音和工作流 provider 配置。

## 科大讯飞工具链讲法

- 星火大模型：对话式讲解、资源生成、学习处方。
- Embedding / ONE SEARCH：课程资料索引、私域问答和公开资料补充。
- OCR / 公式识别 / 图片理解：讲义截图、题目图片、板书和实验图先结构化，再进入智能辅导。
- 语音听写 / TTS / 语音评测：口述问题、60 秒语音讲解和口语练习反馈。
- 星辰工作流：把课程资源生成、学习报告或诊断报告封装成可复用流程。
- 星火知识库或 SparkWeave RAG：课程私域资料问答和来源追溯。

## 演示兜底

如果真实服务暂不可用，先展示课程资料包、学习路线、稳定提示词和已生成的产物卡，再说明 provider 可降级且不阻断文字助教闭环。
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
        "name": "深度学习课程助教",
        "content": _COMPETITION_DEMO_SOUL,
    },
]


__all__ = [
    "COMPETITION_DEMO_WORKSPACE_FILES",
    "DEFAULT_SOULS",
    "DEFAULT_TEMPLATES",
]
