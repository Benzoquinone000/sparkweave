# SparkWeave 学习画像与记忆系统设计

范围：记录当前实现。少讲意图，多讲数据、链路、规则。本文档只描述代码中已经存在的行为；未落地能力统一放到“限制与待实现”，不写成当前能力。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| Memory | `sparkweave/services/memory.py`, `sparkweave/api/routers/memory.py`, `sparkweave_cli/memory.py` |
| Evidence Ledger | `sparkweave/services/learner_evidence.py`, `sparkweave/api/routers/learner_profile.py` |
| Learner Profile | `sparkweave/services/learner_profile.py`, `sparkweave/services/profile_context.py` |
| Runtime 注入 | `sparkweave/runtime/context_enrichment.py`, `sparkweave/runtime/turn_runtime.py` |
| Chat/Router 消费 | `sparkweave/graphs/chat.py`, `sparkweave/runtime/capability_router.py` |
| 前端展示 | `web/src/pages/MemoryPage.tsx`, `web/src/pages/memory/` |

## 1. 核心链路

```text
学习行为 -> Evidence Ledger -> Learner Profile -> Prompt/Hints -> Chat/Guide/资源/评估
Markdown Memory --------------------^              ^
Guide Learner Memory ------------------------------|
```

系统分两层：

| 层 | 定位 | 是否可重建 |
| --- | --- | --- |
| Markdown Memory | 可编辑长期文本记忆 | 不完全可重建 |
| Learner Profile | 证据聚合后的学习画像快照 | 可由证据重建 |

一句话定义：

```text
学习者长期状态建模 = 把目标、薄弱点、偏好、历史上下文转化为智能体可用的个性化决策依据。
```

![学习画像与记忆系统逻辑总图](assets/learner-profile-memory-overview.png)

## 2. 组件与数据落点

| 组件 | 代码 | 数据 |
| --- | --- | --- |
| Memory | `sparkweave/services/memory.py` | `data/memory/PROFILE.md`, `data/memory/SUMMARY.md` |
| Evidence Ledger | `sparkweave/services/learner_evidence.py` | `data/user/learner_profile/evidence.jsonl` |
| Learner Profile | `sparkweave/services/learner_profile.py` | `data/user/learner_profile/profile.json` |
| Profile Context | `sparkweave/services/profile_context.py` | 运行时 `text` + `hints` |
| Runtime 注入 | `sparkweave/runtime/context_enrichment.py` | `UnifiedContext.memory_context`, metadata |
| Guide 记忆 | `sparkweave/services/guide_v2.py` | `data/user/workspace/guide/v2/learner_memory.json` |

边界：

- Memory：人工可读、可编辑，服务对话连续性。
- Evidence Ledger：append-only 原始证据，不直接给模型全量注入。
- Learner Profile：从证据聚合出的结构化快照。
- Guide Learner Memory：导学域缓存，不等于统一画像。

![学习画像与记忆系统模块职责与边界](assets/learner-profile-memory-boundaries.png)

## 3. 存储结构

```text
data/
  memory/
    PROFILE.md
    SUMMARY.md
  user/
    learner_profile/
      evidence.jsonl
      profile.json
    workspace/
      guide/
        v2/
          learner_memory.json
          session_<id>.json
```

| 格式 | 用途 |
| --- | --- |
| Markdown | 长期记忆，便于查看、编辑、清空 |
| JSONL | 证据账本，便于追加和去重 |
| JSON snapshot | 画像快照，便于前端和 runtime 读取 |

## 4. Markdown Memory

`MemoryService` 维护两个文件：

| 文件 | 内容 |
| --- | --- |
| `PROFILE.md` | 稳定信息：身份、目标、偏好、学习风格、知识水平 |
| `SUMMARY.md` | 学习旅程：当前重点、进展、待解决问题 |

核心方法：

| 方法 | 处理 |
| --- | --- |
| `read_snapshot()` | 读两个文件和更新时间 |
| `write_file()` | 手动写 `summary` 或 `profile` |
| `clear_file()` | 清空指定文件 |
| `clear_memory()` | 清空全部 Memory |
| `build_memory_context()` | 生成 `## Background Memory` prompt block |
| `refresh_from_turn()` | turn 后用 LLM 改写两份 Markdown |
| `refresh_from_session()` | 从最近会话或指定会话刷新 |

刷新规则：

- 用户消息或助手消息为空：跳过。
- `PROFILE.md` 和 `SUMMARY.md` 分开重写。
- LLM 返回 `NO_CHANGE`：不写文件。
- 新旧内容相同：不写文件。
- `TurnRuntime._refresh_memory()` 会捕获刷新异常，主对话不因 Memory 刷新失败而失败。
- `POST /api/v1/memory/refresh` 直接调用 `refresh_from_session()`；接口层没有额外吞异常，失败会按 FastAPI 错误返回。

## 5. Evidence Ledger

`LearnerEvidenceEvent` 是画像的原始事件模型。

| 字段 | 含义 |
| --- | --- |
| `id` | 去重键 |
| `source`, `source_id` | 来源和来源内部 ID |
| `actor` | 行为主体，默认 `learner` |
| `verb` | 行为，如 `stated`, `completed`, `answered`, `saved`, `viewed`, `corrected_profile` |
| `object_type`, `object_id` | 对象类型和对象 ID |
| `title`, `summary` | 展示和解释文本 |
| `course_id`, `node_id`, `task_id` | 课程/知识点/任务关联 |
| `resource_type` | 资源类型，如 `visual`, `video`, `external_video`, `quiz` |
| `score`, `is_correct` | 评分证据 |
| `duration_seconds` | 学习时长 |
| `confidence` | 证据置信度，限制在 0 到 1 |
| `reflection` | 用户反思 |
| `mistake_types` | 错因 |
| `weight` | 事件权重 |
| `metadata` | 扩展信息 |

写入处理：

- `append_event()` 写单条。
- `append_events(dedupe=True)` 批量写入并按 `id` 去重。
- 字符串清洗空白并限制长度。
- `score`、`is_correct`、`created_at` 做类型归一。

当前事件写入来源：

| 来源 | 代码入口 | 构造或写入 |
| --- | --- | --- |
| 聊天陈述 | `sparkweave/runtime/context_enrichment.py` | `build_chat_statement_events()` |
| Guide 路线 | `sparkweave/api/routers/guide_v2.py` | `build_guide_session_event()` |
| Guide 任务 | `sparkweave/api/routers/guide_v2.py` | `build_guide_task_event()` |
| Guide 资源 | `sparkweave/api/routers/guide_v2.py` | `build_guide_resource_event()` |
| 会话题目/测验 | `sparkweave/api/routers/sessions.py`, `sparkweave/api/routers/question_notebook.py`, `sparkweave/api/routers/guide_v2.py` | `build_quiz_answer_events()` |
| Notebook | `sparkweave/api/routers/notebook.py`, `sparkweave/api/routers/guide_v2.py` | `build_notebook_record_event()` |
| 用户校准 | `sparkweave/api/routers/learner_profile.py` | `build_profile_calibration_event()` |
| 学习效果 | `sparkweave/api/routers/learning_effect.py`, `sparkweave/services/learning_effect.py` | `LearningEffectService.append_event()` |
| 语音评测 | `sparkweave/api/routers/speech.py` | `LearnerEvidenceService.append_event()` |

## 6. Learner Profile

`LearnerProfileService.refresh()` 聚合证据，输出 `profile.json`。

| 字段 | 内容 |
| --- | --- |
| `overview` | 当前重点、建议水平、时间预算、正确率、摘要 |
| `stable_profile` | `goals`, `preferences`, `strengths`, `constraints` |
| `learning_state` | `weak_points`, `mastery` |
| `next_action` | 下一步主动作 |
| `recommendations` | 辅助建议 |
| `sources` | 本次使用的数据来源 |
| `evidence_preview` | 前端解释用证据摘要 |
| `data_quality` | 来源数、证据数、证据权重、警告、校准数 |
| `quantification` | `profile_scoring_v2` 量化结果：轴分数、偏好分、薄弱点分、掌握度分、下一步优先级 |

读取策略：

- `read_profile(auto_refresh=True)` 优先读缓存。
- `profile.json` 超过 60 秒视为 stale。
- stale 时自动刷新。
- `include_sources` 可限制刷新来源。

## 7. 长期状态建模机制

建模对象：

| 维度 | 落点 | 用途 |
| --- | --- | --- |
| 目标 | `stable_profile.goals`, `overview.current_focus` | 判断当前学习方向，决定继续学什么 |
| 薄弱点 | `learning_state.weak_points`, `mastery[status=needs_support]` | 决定补基、练习、解释深度 |
| 偏好 | `stable_profile.preferences`, `preferred_resource` | 决定讲解风格和资源类型 |
| 历史上下文 | `PROFILE.md`, `SUMMARY.md`, `evidence_preview`, `sources` | 保持连续性，解释画像依据 |

处理流程映射到当前代码：

```text
collect -> normalize -> score -> merge -> calibrate -> decide -> inject
```

| 阶段 | 处理 |
| --- | --- |
| `collect` | `LearnerProfileService.refresh()` 调用 `_collect_memory()`、`_collect_guide_memory()`、`_collect_guide_sessions()`、`_collect_question_notebook()`、`_collect_notebooks()`、`_collect_evidence_ledger()` |
| `normalize` | `_normalize_label()`、`_slug()`、`_event_concept_labels()` 等函数把文本、概念和事件字段规整为 claim、weak point、mastery、preference |
| `score` | `_ProfileBuilder.add_weighted_evidence()` 和 `_evidence_signal_weight()` 计算证据权重，`_build_quantification()` 生成 `profile_scoring_v2` |
| `merge` | `_ProfileBuilder._add_claim()`、`add_weak_point()`、`add_mastery()` 合并同名标签、来源、证据数和分数 |
| `calibrate` | `_ProfileBuilder.apply_calibration()` 应用 `confirm`、`reject`、`correct` 事件 |
| `decide` | `_ProfileBuilder._next_action()` 生成 `next_action`、`priority` 和 `suggested_prompt` |
| `inject` | `ProfileContextInjector.build_context()` 生成 `text`、`hints`，`build_turn_context()` 写入 `UnifiedContext.memory_context` 和 metadata |

给智能体的个性化决策依据：

| 输出 | 消费方 | 作用 |
| --- | --- | --- |
| `next_action` | Chat、Guide、前端 | 决定下一步主动作 |
| `hints.preferences` | Chat、资源工具 | 控制讲解形式和资源类型 |
| `hints.weak_points` | Chat、Guide、评估 | 决定补哪里、练什么、解释到多细 |
| `hints.goals` | Chat、Guide | 保持回答和路线贴合目标 |
| `hints.decision_scores` | ChatGraph、Capability Router | 给协调器读取画像可信度、证据覆盖、弱点强度、掌握度、下一步优先级 |
| `memory_context` | LLM prompt | 提供压缩历史上下文 |
| `metadata.learner_profile_context` | graph/tool | 给非 LLM 节点读取结构化画像 |

约束：

- 智能体使用压缩后的状态，不读取完整历史账本。
- 没有足够证据时，`ProfileContextInjector.build_context()` 返回 `available=false` 且不注入画像文本；`LearnerProfile` 的 `next_action` 会退到 `kind=calibrate`。
- 用户校准优先于系统推断。

![学习画像与记忆系统数据流与时序](assets/learner-profile-memory-timeline.png)

## 8. 来源处理

| 来源 | 方法 | 处理 |
| --- | --- | --- |
| Markdown Memory | `_collect_memory()` | 读 `PROFILE.md`/`SUMMARY.md`，抽取目标、偏好、弱点；置信度低 |
| Guide memory | `_collect_guide_memory()` | 读 `recent_goals`, `top_preferences`, `persistent_weak_points`, `common_mistakes`, `strengths`, `next_guidance` |
| Guide sessions | `_collect_guide_sessions()` | 读路线目标、session profile、mastery、任务分数、session evidence |
| Question notebook | `_collect_question_notebook()` | 按概念分组算正确率，写 mastery 和 weak point |
| Notebook | `_collect_notebooks()` | 读最近记录，主要生成 evidence preview，不强推 mastery |
| Evidence ledger | `_collect_evidence_ledger()` | 读最近最多 300 条事件，聚合目标、偏好、弱点、掌握度、校准 |

关键规则：

- 正确率 `>=0.82`：`mastered`。
- 正确率 `<0.65`：`needs_support`；题目本至少需要 2 条评分证据才写 weak point。
- 低分或错误事件：进入 weak_points。
- 高分事件：进入 strengths。
- 有 `score` 的事件：按概念聚合 mastery。
- `mistake_types`：进入 weak_points。
- `resource_type` 只有在 `verb in {viewed, saved, answered, completed}` 时才进入 preferences。
- `generated` 不算偏好，避免把“系统生成了视频”误判为“用户喜欢视频”。

## 9. 合并与校准

量化公式对应当前实现：

```text
evidence_weight = clamp(weight, 0, 2.5)
                * source_reliability
                * clamp(event.confidence, 0, 1)
                * verb_weight
                * object_weight
                * resource_bonus
                * max(0.18, recency)
claim_score = 1 - Π(1 - claim_evidence_weight)
weakness_score = clamp(0.16 + 0.42*confidence + 0.18*evidence_count/4 + 0.24*evidence_weight/2.4)
mastery_score = 按 evidence_weight 加权平均 score
overall_confidence = 0.06 + evidence_coverage + source_diversity + assessment_strength + recency + calibration_strength
next_action.priority = 当前最高风险/收益项的可执行优先级
```

量化输出：

| 字段 | 含义 |
| --- | --- |
| `quantification.axes.goal` | 目标明确度 |
| `quantification.axes.weakness` | 薄弱点定位强度 |
| `quantification.axes.preference` | 偏好稳定度 |
| `quantification.axes.evidence` | 证据覆盖度 |
| `quantification.axes.mastery` | 掌握稳定度 |
| `quantification.preference_scores` | 各偏好的分数、置信度、来源 |
| `quantification.weakness_scores` | 各薄弱点的分数、置信度、严重度 |
| `quantification.mastery_scores` | 各知识点的掌握分、置信度、证据权重 |

规则：

- 用户校准来源可靠性最高。
- `answered`、`completed` 的 verb weight 高于 `viewed`、`saved`。
- `generated` 的 verb weight 低；偏好只从 `viewed`、`saved`、`answered`、`completed` 的 `resource_type` 或显式 `learning_preference` 写入。
- 近期证据权重大于旧证据。
- 评分证据进入 `scored_evidence_weight`，影响掌握度和整体可信度。

Claim 合并：

- `goals`、`preferences`、`strengths` 使用统一 claim bucket。
- 相同 label 去重。
- 合并 `source_ids`。
- 累加 `evidence_count`。
- 合并 `evidence_weight`，用 `claim_score` 排序。

Weak point 合并：

- 以规范化 label 为 key。
- 累加证据数，合并来源，保存原因。
- 根据 `score`、置信度和证据数生成 `severity`。

Mastery 合并：

- 以 `concept_id` 为 key。
- 同概念多个 score 按证据权重求平均。
- 平均分 `>=0.82` 为 `mastered`。
- 平均分 `<0.65` 为 `needs_support`。
- 其他为 `developing`。

用户校准 API：`POST /api/v1/learner-profile/calibrations`

| action | 处理 |
| --- | --- |
| `confirm` | 提升对应 claim 可信度 |
| `reject` | 加入 rejected set，输出时过滤 |
| `correct` | 拒绝原值，加入修正值 |

校准规则：

- 不直接改 `profile.json`。
- 写入 Evidence Ledger。
- 写入后刷新画像。
- `data_quality.read_only` 当前表示“尚未用户校准”，不是文件不可写。

## 10. next_action

画像只给一个主动作。

优先级：

1. 有 weak point：`kind=remediate`，去 `/guide` 补基。
2. 有 `needs_support` mastery：`kind=practice`，做低门槛练习。
3. 有 goal：`kind=continue`，继续导学。
4. 证据不足：`kind=calibrate`，补充目标、卡点、偏好。

资源提示：

| 偏好 | 推荐 |
| --- | --- |
| `external_video` | 精选公开视频 |
| `video` | 短视频讲解 |
| `practice` / `quiz` | 入门练习 |
| `visual` | 图解 |
| 无明确偏好 | 图解 |

## 11. Prompt 注入

Memory 注入：

- `MemoryService.build_memory_context()` 生成 `## Background Memory`。
- 包含 `User Profile` 和 `Learning Context`。
- 提示模型只在直接相关时使用。

Profile 注入：

- `ProfileContextInjector.build_context()` 生成 `[Learner Profile Context]`。
- 输出 `text` 给 prompt。
- 输出 `hints` 给 graph/tool。
- 包含 `current_focus`, `level`, `preferences`, `weak_points`, `next_action`, `decision_scores` 等。

Runtime 合并：

- `build_turn_context()` 读取 Memory context。
- 读取 Profile context。
- 合并到 `UnifiedContext.memory_context`。
- 把完整 `learner_profile_context` 放入 metadata。
- 持久化用户消息时提取聊天陈述证据。

失败策略：

- 画像服务异常：`available=false`, `text=""`, `hints={}`。
- 证据不足：不注入画像文本。
- 主对话不因画像失败而失败。

## 12. 对业务能力的影响

| 能力 | 使用 |
| --- | --- |
| Chat | 按目标、偏好、弱点调整回答 |
| ChatGraph 协调 | metadata 标记 `profile_hints_applied`, `profile_guided` |
| External Video | 用 `preferred_resource` 和 weak_points 选视频 |
| Guide V2 | 创建路线、任务、资源、报告时读画像和 Guide memory |
| Learning Effect | 复用 Evidence Ledger 生成学习效果报告 |

## 13. API 与 CLI

Memory：

```text
GET  /api/v1/memory
PUT  /api/v1/memory
POST /api/v1/memory/refresh
POST /api/v1/memory/clear
```

Learner Profile：

```text
GET  /api/v1/learner-profile
POST /api/v1/learner-profile/refresh
GET  /api/v1/learner-profile/evidence-preview
GET  /api/v1/learner-profile/evidence
POST /api/v1/learner-profile/evidence
POST /api/v1/learner-profile/evidence/batch
POST /api/v1/learner-profile/evidence/rebuild
POST /api/v1/learner-profile/calibrations
```

CLI：

```bash
sparkweave memory show [summary|profile|all]
sparkweave memory clear [summary|profile|all]
```

## 14. 前端

入口：`web/src/pages/MemoryPage.tsx`

| Tab | 用户含义 | 数据 |
| --- | --- | --- |
| 概览 | 现在该做什么 | Learner Profile |
| 依据 | 为什么这么判断 | evidence preview |
| 补充 | 手动修正画像 | Markdown Memory |

要求：

- 默认展示下一步，不展示原始 JSON。
- 证据不足时直接给行动入口。
- 校准入口用“确认/否定/修正”。
- Agent、RAG、诊断等工程能力不作为默认入口。

## 15. 典型处理

| 场景 | 处理 |
| --- | --- |
| 用户说“我想学机器学习，先看图解” | 抽取 goal + visual preference |
| 用户连续答错学习率题 | quiz event 写低分，画像生成 weak point 和 needs_support |
| 用户保存视频资源 | `saved` + `resource_type` 成为偏好证据 |
| 系统生成视频但用户未看 | `generated` 只展示为证据，不进入偏好 |
| 用户否定薄弱点 | calibration reject 写账本，画像刷新时过滤 |
| 没有证据 | `next_action=calibrate`，不注入画像 prompt |

## 16. 隐私与边界

- 当前默认本地单用户数据目录。
- 不做全量行为追踪。
- 不把完整 evidence ledger 注入模型。
- 用户校准以事件保存，保留可追溯性。
- 当前没有加密存储；多用户部署前需要用户隔离和权限控制。
- `data/memory/`、`data/user/learner_profile/` 和 `data/user/workspace/guide/` 均属于本地运行时数据，不进入公开提交包。
- 文档不承诺“画像不会被任何外部模型看到”；当前实现会把压缩后的 `memory_context` 和 `[Learner Profile Context]` 放入 LLM prompt，用于个性化回答。

## 17. 测试覆盖

| 测试 | 覆盖 |
| --- | --- |
| `tests/services/memory/test_memory_service.py` | Memory 读取、刷新、`NO_CHANGE` |
| `tests/services/test_learner_evidence.py` | Evidence 追加、汇总、校准事件、聊天陈述和资源事件构造 |
| `tests/services/test_learner_profile.py` | 多来源聚合、偏好、mastery、校准、聊天事件 |
| `tests/services/test_profile_context.py` | prompt 压缩、decision_scores、无证据不注入、失败关闭 |
| `tests/api/test_learner_profile_router.py` | Profile API、Evidence API、Calibration API |
| `tests/api/test_learner_evidence_integration.py` | 题目本、Notebook 写证据 |
| `tests/api/test_unified_ws_turn_runtime.py` | WebSocket turn 写入聊天陈述证据、刷新 Memory |
| `tests/ng/test_turn_runtime.py` | Runtime 合并 profile context |
| `tests/services/test_guide_v2.py` | Guide memory 和画像闭环 |

聚焦命令：

```powershell
pytest tests/services/test_learner_evidence.py tests/services/test_learner_profile.py tests/services/test_profile_context.py tests/services/memory/test_memory_service.py tests/api/test_learner_profile_router.py tests/api/test_learner_evidence_integration.py tests/api/test_unified_ws_turn_runtime.py tests/ng/test_turn_runtime.py -q
```

## 18. 限制与待实现

本节不是当前实现说明，只记录基于代码事实能看到的限制。

- `mastery.concept_id` 仍依赖文本标签或 slug，知识点 ID 不够稳定。
- `profile_scoring_v2` 是显式量化层，但仍不是 IRT/BKT 这类严格测量模型。
- `data_quality.read_only` 命名容易误解。
- Markdown Memory 和 Learner Profile 的前端解释需要继续区分。
- 当前适合本地单用户，多用户部署需要数据隔离。

待实现项：

1. 接入稳定知识点 ID。
2. 给 Evidence Ledger 增加 schema version。
3. 增加画像评测集：事件输入 -> 画像输出断言。
4. 前端细化“这条判断来自哪些证据”。
5. 让用户校准按 claim 类型精细调整分数，而不只是过滤/添加。
