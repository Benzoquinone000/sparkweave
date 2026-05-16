# 学习画像与长期记忆设计

本文记录 SparkWeave 当前学习画像和 Memory 的真实设计。重点区分两层：面向对话连续性的长期 Memory，以及面向学习闭环的统一学习画像。

## 一句话定位

SparkWeave 的画像系统不是一个静态表单，而是一个**证据驱动的学习状态聚合层**：

```text
chat / guide / quiz / notebook / resource / calibration
  -> learner evidence ledger
  -> LearnerProfileService aggregation
  -> profile snapshot
  -> ProfileContextInjector compressed hints
  -> LangGraph turn context
  -> personalized answer / guide / resource generation
```

同时系统保留 `MemoryService` 作为更轻量的长期对话记忆：

```text
turn user+assistant
  -> best-effort rewrite
  -> PROFILE.md / SUMMARY.md
  -> memory_context
  -> model prompt
```

## 代码地图

| 层级 | 关键文件 | 已实现事实 |
| --- | --- | --- |
| 长期 Memory | `sparkweave/services/memory.py` | 维护 `PROFILE.md` 与 `SUMMARY.md`，支持旧 `memory.md` 迁移、上下文构造和 turn 后刷新 |
| 画像证据账本 | `sparkweave/services/learner_evidence.py` | 统一 JSONL 学习事件，支持导学、题目、Notebook、资源、对话、用户校准等事件 |
| 统一画像聚合 | `sparkweave/services/learner_profile.py` | 聚合 Memory、Guide、题目本、Notebook、证据账本，生成只读画像快照 |
| 画像上下文注入 | `sparkweave/services/profile_context.py` | 把画像压缩成 prompt block 和 strategy hints |
| Turn 上下文 | `sparkweave/runtime/context_enrichment.py` | 合并 memory_context 与 learner_profile_context |
| Turn 后刷新 | `sparkweave/runtime/turn_runtime.py` | assistant message 写入后 best-effort 调用 Memory refresh |
| 画像 API | `sparkweave/api/routers/learner_profile.py` | 画像读取、刷新、证据预览、证据写入、证据重建、用户校准 |
| 前端画像页 | `web/src/pages/MemoryPage.tsx` | 展示画像、证据、长期记忆、校准入口 |
| 前端导学页 | `web/src/pages/GuidePage.tsx` | 导学事件写入证据账本，并在导学后刷新画像 |

## 两层模型：Memory 与 Learner Profile

### MemoryService

`MemoryService` 面向“对话连续性”，文件落点：

```text
data/memory/PROFILE.md
data/memory/SUMMARY.md
```

它的职责：

- 保存用户长期偏好、身份、目标等稳定信息。
- 保存近期学习旅程摘要。
- turn 结束后用 LLM 进行 best-effort rewrite。
- 构造 `## Background Memory` prompt block。
- 提醒模型“Use this memory sparingly — only when directly relevant.”，避免过度套用旧记忆。

### LearnerProfileService

`LearnerProfileService` 面向“学习画像与个性化决策”，文件落点：

```text
data/user/learner_profile/profile.json
data/user/learner_profile/evidence.jsonl
```

它的职责：

- 聚合多个来源的证据。
- 生成 goals、preferences、strengths、weak_points、mastery、recommendations、next_action。
- 记录 data_quality，例如 evidence_count、source_count、confidence。
- 给前端展示“为什么系统这样判断”。
- 给模型提供压缩后的学习状态提示。

两者关系：Memory 是画像来源之一，但画像不等于 Memory。画像更强调可解释证据、学习状态和下一步行动。

## 证据账本

`LearnerEvidenceEvent` 是画像系统的底层事件模型。核心字段包括：

| 字段 | 作用 |
| --- | --- |
| `source` / `source_id` | 事件来源和来源 ID |
| `actor` | 事件主体 |
| `verb` | 行为，例如 observed、completed、answered、preferred |
| `object_type` / `object_id` | 对象类型和对象 ID |
| `title` / `summary` | 用户可读的事件标题和摘要 |
| `course_id` / `node_id` / `task_id` | 导学/课程/知识点关联 |
| `resource_type` | 资源偏好，例如 video、practice、visual |
| `score` / `is_correct` | 练习和评估结果 |
| `duration_seconds` | 学习行为时长 |
| `confidence` | 事件置信度 |
| `reflection` | 用户反思 |
| `mistake_types` | 错误类型 |
| `weight` | 事件权重 |
| `metadata` | 扩展字段 |

账本是 append-only JSONL，`append_events(dedupe=True)` 会用事件 ID 去重，避免同一行为重复写入。

## 证据来源

当前 `LearnerProfileService.refresh()` 会聚合：

| 来源 | 采集方法 | 典型贡献 |
| --- | --- | --- |
| Memory | `_collect_memory()` | goals、preferences、weak lines、长期摘要 |
| Guide memory | `_collect_guide_memory()` | 导学长期目标、偏好、弱点、下一步建议 |
| Guide sessions | `_collect_guide_sessions()` | 导学路线、任务进度、掌握度、练习证据 |
| Question notebook | `_collect_question_notebook()` | 题目本、错题、收藏、答题结果 |
| Notebook | `_collect_notebooks()` | 保存的学习记录和资源 |
| Evidence ledger | `_collect_evidence_ledger()` | 标准化行为事件、测验分数、资源偏好、错误类型 |
| User calibration | `apply_calibration()` / calibration event | 用户显式确认、修正或驳回画像判断 |

## 画像聚合逻辑

画像构造器 `_ProfileBuilder` 会将来源转成统一结构：

| 画像字段 | 聚合方式 |
| --- | --- |
| goals | 多来源 claim 去重，保留 evidence_count 和 confidence |
| preferences | 用户偏好和资源偏好聚合 |
| strengths | 高分、正向反馈、导学记录沉淀 |
| weak_points | 低分、错误类型、导学弱点、长期记忆中的卡点沉淀 |
| mastery | 按 concept/node 聚合分数，生成 status |
| recommendations | 基于弱点、导学下一步、证据质量生成 |
| next_action | 优先弱点，其次 mastery needs support，再其次导学建议 |
| evidence_preview | 最近证据摘要，供前端解释 |
| data_quality | source_count、evidence_count、confidence 等 |

画像置信度不是“模型自信地说了算”，而是与 source_count、evidence_count、用户校准等信号有关。当前实现会把整体 confidence 控制在 0.05 到 0.92 之间，避免虚假的 100% 确定。

## 模型上下文注入

`ProfileContextInjector.build_context()` 会读取 `LearnerProfileService.read_profile()`，并把画像压缩成：

1. `text`：给模型看的 prompt block。
2. `hints`：给运行时和 coordinator 用的结构化提示。

Prompt block 以 `[Learner Profile Context]` 开头，并明确要求：

- quietly use hints。
- 不要向用户暴露这段系统块。
- 不要编造没有证据的画像判断。

注入内容包括：

- current_focus
- summary
- level
- time_budget_minutes
- goals
- preferences
- preferred_resource
- strengths
- weak_points
- mastery_needs_attention
- progress_style
- next_action

`build_turn_context()` 会把 `MemoryService.build_memory_context()` 和 `ProfileContextInjector` 输出合并到 `UnifiedContext.memory_context`，同时把完整 `learner_profile_context` 放进 metadata。

## 对 Agent 的影响

画像会影响三个层面：

1. **默认回答**：模型能看到弱点、目标、偏好和下一步行动，回答更贴近学习者。
2. **对话协调**：`ChatGraph` 的协作路线可以先显示“学习画像智能体”，并在 metadata 中标记 `profile_hints_applied`。
3. **导学闭环**：Guide V2 完成任务、提交答案、生成资源后，会写证据并刷新画像，再影响下一轮导学。

这使画像从“页面展示”进入“模型决策上下文”，是项目区别于静态用户档案的关键点。

## 前端用户体验原则

画像页应面向用户，而不是展示原始 JSON：

- 告诉用户“系统认为你现在卡在哪里”。
- 告诉用户“依据是什么”。
- 给出一个下一步行动，而不是一堆指标。
- 允许用户校准：对、错、补充说明。
- 证据不足时要明说“证据偏少”，不要装作很确定。

当前前端已有 `MemoryPage.tsx` 展示画像、证据、长期记忆和校准入口；后续仍应继续做减法，让用户一眼知道“现在该做什么”。

## 可以写进简历的准确表述

可以写：

- 设计并实现证据驱动学习画像系统，以 append-only JSONL 学习事件账本聚合导学、练习、Notebook、对话和用户校准信号。
- 实现双层长期个性化：`PROFILE.md`/`SUMMARY.md` 长期对话记忆 + `LearnerProfileService` 统一学习画像快照。
- 将学习画像压缩为模型可读 prompt block 和结构化 hints，注入 LangGraph turn context，用于个性化回答、导学推荐和多智能体调度。
- 为画像增加用户校准和证据预览，避免黑箱画像判断。

不要写：

- “画像已经完全准确评估学生能力。”当前是证据驱动的近似聚合。
- “画像由实时行为全量自动采集。”当前采集的是项目内事件，不是浏览器级全量行为追踪。
- “画像直接训练了模型。”当前是上下文注入，不是模型微调。
- “Memory 和画像是同一个东西。”当前是两层系统，职责不同。

## 后续优化方向

1. 将 408 知识点体系接入 `mastery.concept_id`，让画像从“文本标签”升级到“课程知识图谱节点”。
2. 给 evidence ledger 增加更严格 schema version 和迁移脚本。
3. 建立画像评测集：给定一组学习事件，验证 weak_points、next_action、preferred_resource 是否符合预期。
4. 在前端把证据解释做成用户友好的“依据卡片”，减少技术字段。
5. 将用户校准反馈用于调整 claim confidence，而不只是新增事件。
