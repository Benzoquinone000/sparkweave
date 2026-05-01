# Capabilities 详解

SparkWeave 的 Level 2 能力由 `sparkweave/graphs/` 下的 LangGraph 图实现。每个能力接收同一种 `UnifiedContext`，通过 `StreamBus` 输出阶段、进度、工具调用、正文、来源和最终结果。

公共入口会先经过 `sparkweave/services/validation.py` 校验配置，再由 `sparkweave/runtime/runner.py` 分派到对应图。能力清单和 CLI alias 由 `sparkweave/app/facade.py` 暴露给 CLI、Web 前端和 Python facade。

## 能力总览

| Capability | CLI alias | 主要文件 | 阶段 | 常用工具 |
| --- | --- | --- | --- | --- |
| `chat` | `chat` | `graphs/chat.py` | `coordinating`、`thinking`、`acting`、`responding` | `rag`、`web_search`、`paper_search`、`code_execution`、`reason`、`brainstorm` |
| `deep_solve` | `solve` | `graphs/deep_solve.py` | `planning`、`reasoning`、`writing` | `rag`、`web_search`、`code_execution`、`reason` |
| `deep_question` | `quiz` | `graphs/deep_question.py` | `ideation`、`generation` | `rag` |
| `deep_research` | `research` | `graphs/deep_research.py` | `rephrasing`、`decomposing`、`researching`、`reporting` | `rag`、`web_search`、`paper_search`、`code_execution` |
| `visualize` | `visualize`、`viz` | `graphs/visualize.py` | `analyzing`、`generating`、`reviewing` | 无 |
| `math_animator` | `animate` | `graphs/math_animator.py` | `concept_analysis`、`concept_design`、`code_generation`、`code_retry`、`summary`、`render_output` | 无 |

## 公共请求形状

WebSocket 主入口是 `/api/v1/ws`。一次 turn 的核心字段来自 `TurnRequest`：

```json
{
  "type": "start_turn",
  "content": "解释傅里叶变换",
  "capability": "chat",
  "session_id": "optional-session",
  "tools": ["rag", "web_search"],
  "knowledge_bases": ["math-kb"],
  "language": "zh",
  "config": {},
  "attachments": []
}
```

`tools` 决定图可以调用哪些 Level 1 工具，`knowledge_bases` 决定 RAG 默认检索哪个库。运行时会把它们写入 `UnifiedContext.enabled_tools` 和 `UnifiedContext.knowledge_bases`。

工具协议、注册表、内置工具行为和各能力如何补参、过滤、执行工具，见 [Tools 工具系统](./tools.md)。

Guide V2 不是主 WebSocket 的独立 capability，但它会把学习任务映射到 `visualize`、`math_animator`、`deep_question`、`deep_research` 等能力来生成图解、视频、练习和资料；也会通过 `external_video_search` 复用联网搜索筛选公开视频。普通对话中，当学习者明确说“找视频 / 推荐视频 / 公开课”时，对话协调智能体也会直接唤醒 `external_video_search`，返回精选视频卡片而不是原始搜索列表。编排链路见 [导学空间与 Guide V2](./guided-learning.md)。

SparkBot 也不是 Level 2 capability。它是长期运行的 Bot 实例系统，有自己的 WebSocket、工作区 prompt、渠道、工具循环和后台任务；边界见 [SparkBot 与 Agents 工作台](./sparkbot-agents.md)。

## Chat

`chat` 是默认能力，适合短问答、资料追问和轻量工具调用。

运行流程：

1. `coordinating`：对用户请求做轻量路由判断。
2. 如果需要专门能力，构造新的 `UnifiedContext` 并委托给 specialist。
3. 否则进入 `thinking`，让模型决定是否调用工具。
4. `acting` 执行工具调用并收集结果。
5. `responding` 写最终回复并输出 `result`。

配置：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `auto_delegate` | bool | `true` | 是否允许自动委托给 specialist |
| `delegate_capability` | string | 空 | 强制委托到某个能力 |
| `coordinator_capability` | string | 空 | `delegate_capability` 的兼容别名 |

可委托能力：

| 触发意图 | 目标 |
| --- | --- |
| 动画、视频式解释、分镜 | `math_animator` |
| 生成练习题、测验、选择题 | `deep_question` |
| 图解、流程图、图表、可视化 | `visualize` |
| 调研、学习路径、资料整理 | `deep_research` |
| 求解、推导、证明、计算题 | `deep_solve` |

强制留在普通聊天：

```json
{
  "capability": "chat",
  "config": {
    "auto_delegate": false
  }
}
```

强制委托：

```json
{
  "capability": "chat",
  "config": {
    "delegate_capability": "deep_research"
  }
}
```

结果结构：

```json
{
  "response": "最终回答",
  "tool_traces": [],
  "runtime": "langgraph"
}
```

## Deep Solve

`deep_solve` 适合数学题、证明、推理题和需要工具辅助验证的问题。

运行流程：

1. `planning`：生成解题计划。
2. `reasoning`：选择最多 3 个工具调用。
3. `reasoning`：执行工具调用，RAG 会自动补 `kb_name`。
4. `reasoning`：基于计划和工具观察写草稿。
5. `reasoning`：验证草稿中的计算、缺漏和 unsupported claims。
6. `writing`：写面向学习者的最终答案。

配置：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `detailed_answer` | bool | `true` | 公共契约字段，当前图主要用于保持请求兼容 |

工具行为：

- 如果启用 `rag` 但没有绑定知识库，会跳过 RAG 并输出 warning progress。
- 模型支持 tool calling 时，图会让模型选择工具；否则使用 fallback 规则。
- 工具结果会被写入 `tool_traces`，来源会通过 `sources` 事件单独输出。

结果结构：

```json
{
  "response": "最终解答",
  "plan": {},
  "verification": "验证笔记",
  "tool_traces": [],
  "runtime": "langgraph"
}
```

## Deep Question

`deep_question` 负责题目生成。它既支持按知识点生成，也支持从试卷中抽取参考题后仿题。

配置：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `mode` | `custom` 或 `mimic` | `custom` | 生成模式 |
| `topic` | string | 用户输入 | 题目主题 |
| `num_questions` | int | `1` | 自定义模式题数，范围 1 到 50 |
| `difficulty` | string | 空 | 难度偏好 |
| `question_type` | string | 空 | `choice`、`true_false`、`fill_blank`、`written`、`coding`，空值表示自动 |
| `preference` | string | 空 | 额外出题偏好 |
| `paper_path` | string | 空 | mimic 模式的 PDF、解析目录或 JSON 文件 |
| `max_questions` | int | `10` | mimic 模式最多参考题数，范围 1 到 100 |

自定义模式流程：

1. `ideation`：如果启用 `rag` 且绑定知识库，先用主题检索知识上下文。
2. `ideation`：生成题目模板，每个模板包含考点、题型、难度和理由。
3. `generation`：逐题生成题干、选项、答案和解析。
4. `generation`：校验题型结构。
5. `generation`：对结构不合法的题目进行一次 repair。
6. `generation`：输出 Markdown 摘要和结构化 summary。

mimic 模式输入：

| 输入 | 说明 |
| --- | --- |
| `paper_path` 指向 JSON | 读取 `questions` 数组或根数组 |
| `paper_path` 指向目录 | 查找 `*_questions.json` 或 `questions.json`，没有则尝试从解析目录抽题 |
| `paper_path` 指向 PDF | 需要本地 MinerU 解析依赖 |
| WebSocket attachment PDF | 运行时会临时写入 PDF 并走同一加载逻辑 |

结果 summary：

```json
{
  "success": true,
  "source": "custom",
  "requested": 5,
  "template_count": 5,
  "completed": 5,
  "failed": 0,
  "templates": [],
  "results": [],
  "errors": [],
  "mode": "custom",
  "runtime": "langgraph"
}
```

每个 `results` item 通常包含：

```json
{
  "template": {},
  "qa_pair": {
    "question_id": "q_1",
    "question_type": "choice",
    "question": "...",
    "options": { "A": "...", "B": "..." },
    "correct_answer": "A",
    "explanation": "...",
    "difficulty": "medium",
    "validation": {}
  },
  "success": true
}
```

旧题目 WebSocket 路由见 [题目工作流](./question-workflows.md)。

## Deep Research

`deep_research` 负责调研、资料整合、对比和学习路径生成。公共请求应显式传入 config，避免依赖图内部默认值。

配置：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `mode` | `notes`、`report`、`comparison`、`learning_path` | 输出风格 |
| `depth` | `quick`、`standard`、`deep`、`manual` | 调研深度 |
| `sources` | `kb`、`web`、`papers` 数组 | 检索来源 |
| `manual_subtopics` | int | manual 深度下主题数，范围 1 到 10 |
| `manual_max_iterations` | int | 手动迭代提示，范围 1 到 10 |
| `confirmed_outline` | array | 用户确认后的大纲 |
| `outline_preview` | bool | 是否先只返回大纲预览 |
| `checkpoint_id` | string | checkpoint 续跑 ID |
| `checkpoint_thread_id` | string | `checkpoint_id` 兼容别名 |
| `use_code` | bool | 是否允许额外代码验证 |

深度含义：

| depth | 子主题数量 | 每个子主题查询数 |
| --- | --- | --- |
| `quick` | 2 | 1 |
| `standard` | 3 | 2 |
| `deep` | 5 | 3 |
| `manual` | `manual_subtopics` 限定后数量 | 3 |

来源映射：

| source | Tool | 额外条件 |
| --- | --- | --- |
| `kb` | `rag` | 必须绑定知识库 |
| `web` | `web_search` | 必须启用工具 |
| `papers` | `paper_search` | 必须启用工具 |

运行流程：

1. `rephrasing`：把用户输入整理成 research topic。
2. `decomposing`：拆成子主题和查询。
3. 如果需要确认大纲，返回 outline preview。
4. `researching`：按子主题和来源执行工具检索。
5. 当 `use_code=true`，或 `mode=comparison` 且 `depth=deep`，并启用 `code_execution` 时，执行一次定量验证。
6. `reporting`：收集来源，写最终报告。

大纲预览：

只要请求了 `outline_preview=true`，或 config 中出现 `mode`、`depth`、`sources`、`manual_subtopics`、`manual_max_iterations` 且没有 `confirmed_outline`，图会先输出大纲预览。结果结构类似：

```json
{
  "outline_preview": true,
  "sub_topics": [],
  "topic": "研究主题",
  "research_config": {
    "mode": "report",
    "depth": "standard",
    "sources": ["web"]
  },
  "checkpoint_id": "deep_research:session:turn",
  "checkpoint": {
    "id": "deep_research:session:turn",
    "thread_id": "deep_research:session:turn",
    "resume_config_key": "checkpoint_id",
    "next": "researching"
  },
  "runtime": "langgraph"
}
```

确认后续跑：

```json
{
  "capability": "deep_research",
  "content": "原始研究主题",
  "config": {
    "mode": "report",
    "depth": "standard",
    "sources": ["web"],
    "checkpoint_id": "deep_research:session:turn",
    "confirmed_outline": [
      { "title": "主题一", "overview": "..." }
    ]
  }
}
```

最终结果：

```json
{
  "response": "Markdown 报告",
  "report": "Markdown 报告",
  "metadata": {
    "topic": "...",
    "mode": "report",
    "depth": "standard",
    "sources": ["web"],
    "subtopics": [],
    "evidence": [],
    "outline_preview": false,
    "runtime": "langgraph"
  },
  "runtime": "langgraph"
}
```

## Visualize

`visualize` 把自然语言需求转成可渲染代码。它不直接调用外部工具。

配置：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `render_mode` | `auto`、`svg`、`chartjs`、`mermaid` | `auto` | 指定或自动推断渲染类型 |

类型选择：

| 类型 | 输出 |
| --- | --- |
| `svg` | 完整 raw SVG，禁止脚本和外部资产 |
| `chartjs` | Chart.js 配置对象，不创建 DOM |
| `mermaid` | Mermaid DSL |

流程：

1. `analyzing`：分析请求并选择 render type。
2. `generating`：生成对应代码。
3. `reviewing`：检查可渲染性、语法、安全性和需求匹配。
4. `reviewing`：输出 fenced code 和结构化 result。

结果结构：

```json
{
  "response": "可视化摘要",
  "render_type": "svg",
  "code": {
    "language": "svg",
    "content": "<svg ...></svg>"
  },
  "analysis": {},
  "review": {},
  "runtime": "langgraph"
}
```

## Math Animator

`math_animator` 生成 Manim 代码，并在后端安装 Manim 时渲染视频或图片产物。

配置：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `output_mode` | `video`、`image` | `video` | 产物类型 |
| `quality` | `low`、`medium`、`high` | `medium` | Manim 质量，对应 `-ql`、`-qm`、`-qh` |
| `style_hint` | string | 空 | 风格提示，最多 500 字符 |
| `max_retries` | int | `4` | 渲染失败修复次数，validator 允许 0 到 10，图内部限制到 8 |
| `enable_visual_review` | bool | 空 | 是否启用渲染帧视觉复核 |
| `visual_review` | bool | 空 | `enable_visual_review` 兼容别名 |

运行流程：

1. `concept_analysis`：分析学习目标、数学重点和视觉目标。
2. `concept_design`：生成 storyboard 和代码约束。
3. `code_generation`：生成 Manim Python 代码。
4. `code_retry`：调用 Manim 渲染，失败时让 LLM 修复代码并重试。
5. `render_output`：输出 Manim 原始进度和视觉复核进度。
6. `summary`：总结生成内容。
7. `render_output`：整理 artifacts 并输出 result。

运行环境：

- 默认使用当前 Python 解释器，只要能 `import manim`。
- 可用 `SPARKWEAVE_MANIM_PYTHON` 指向另一个安装了 Manim 的 Python。
- 如果 Manim 不可用，图仍返回代码，但 `artifacts` 为空，`render.render_skipped=true`。

图片模式要求：

`output_mode=image` 时，生成代码必须只包含一个或多个锚点代码块：

```python
### YON_IMAGE_1_START ###
from manim import *

class ImageScene(Scene):
    def construct(self):
        self.add(Text("Example"))
### YON_IMAGE_1_END ###
```

产物位置：

```text
data/user/workspace/chat/math_animator/<turn_id>/
  source/
  artifacts/
  media/
  meta/
```

公开 URL 通过 `/api/outputs/...` 暴露，只允许访问 artifacts 下的公开文件。

结果结构：

```json
{
  "response": "生成摘要",
  "summary": {},
  "code": {
    "language": "python",
    "content": "from manim import *"
  },
  "output_mode": "video",
  "artifacts": [
    {
      "type": "video",
      "url": "/api/outputs/workspace/chat/math_animator/...",
      "filename": "animation.mp4",
      "content_type": "video/mp4",
      "label": "Animation video"
    }
  ],
  "timings": {},
  "render": {
    "quality": "medium",
    "retry_attempts": 0,
    "retry_history": [],
    "source_code_path": "...",
    "visual_review": null,
    "render_skipped": false,
    "skip_reason": ""
  },
  "analysis": {},
  "design": {},
  "runtime": "langgraph"
}
```

## Answer Now

多个能力支持 `answer_now_context`。这是运行时中断或用户要求“现在直接给答案”时的快速完成机制。

共同特点：

- 跳过部分前置阶段。
- 不再调用外部工具。
- 从已有 partial trace 中综合结果。
- `result.metadata.answer_now=true`。

支持情况：

| Capability | 跳过阶段 | 最终阶段 |
| --- | --- | --- |
| `chat` | 工具和继续思考 | `responding` |
| `deep_solve` | `planning`、`reasoning` | `writing` |
| `deep_question` | `ideation` | `generation` |
| `deep_research` | `rephrasing`、`decomposing`、`researching` | `reporting` |
| `visualize` | `analyzing`、`reviewing` | `generating` |
| `math_animator` | `concept_analysis`、`concept_design`、`summary` | `code_generation`、`code_retry`、`render_output` |

## 配置校验

公共 runtime 会拒绝未知 config 字段，运行时内部字段除外。内部字段包括：

```text
_runtime
_persist_user_message
answer_now_context
followup_question_context
```

新增能力时需要同步更新：

- `sparkweave/runtime/runner.py` 的 capability 分派。
- `sparkweave/app/facade.py` 的 manifest。
- `sparkweave/services/validation.py` 的 config schema。
- `web/src/lib/capabilities.ts` 的前端默认配置。
