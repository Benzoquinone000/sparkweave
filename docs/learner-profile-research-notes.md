# 学习画像开发前调研笔记

本文档是 `learner-profile-design.md` 的准备材料，记录外部调研、项目内证据源盘点、实现前风险和开发检查清单。画像开发时应同步更新本文档，把新发现、取舍和验证结果留在这里。

## 研究目标

学习画像要成为 SparkWeave 的学习中枢，而不是一个独立展示页。正式开发前需要确认：

- 什么学习行为值得记录。
- 如何把多模块数据统一成可计算证据。
- 如何让画像可解释、可校准、可被用户信任。
- 如何让画像驱动导学、资源生成、答疑和学习效果评估。
- 如何避免把画像做成隐私风险或模型黑箱。

## 外部调研摘要

### xAPI：学习经历应事件化

xAPI 的核心思想是把学习经历表示为 statement，基本结构是 `actor -> verb -> object`，并可携带 `result`、`context`、`timestamp` 等信息。对 SparkWeave 的启发：

- 不要只存最终画像，应先存学习事件。
- 事件要有统一动词，例如 `asked`、`answered`、`completed`、`reflected`、`saved`。
- 分数、正确性、耗时和上下文应放在可追溯的 result/context 字段中。

参考：

- ADL xAPI Data Specification: https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md
- xAPI Statements 101: https://xapi.com/statements-101/

### 1EdTech Caliper：跨工具统一学习活动词表

Caliper 用 events、actions、entities 和 metric profiles 描述 Assessment、Reading、Media 等学习活动。对 SparkWeave 的启发：

- Chat、Guide、Notebook、Question、Resource、Knowledge 不能各记各的，需要统一事件词表。
- 画像服务不必完整实现 Caliper，但应吸收 profile 思维：不同模块产生不同类型事件，统一进入证据账本。
- 事件可以先本地 JSONL 存储，未来再扩展为 LRS/LRW。

参考：

- 1EdTech Caliper Analytics: https://www.1edtech.org/standards/caliper
- Caliper Metric Profiles Common Explanations: https://www.1edtech.org/specs/caliper/caliper-metric-profiles-common-explanations

### Open Learner Model：画像必须开放和可协商

Open Learner Model 强调学习者可以看到系统对自己的理解。对 SparkWeave 的启发：

- 画像中心要展示“系统为什么这样判断”。
- 用户可以确认、修改、驳回画像判断。
- 画像不是最终裁判，而是学习者和系统共同维护的工作模型。
- 面向用户的展示应优先：目标、卡点、下一步，而不是内部 JSON。

参考：

- Open learner model 概念综述: https://edutechwiki.unige.ch/en/Open_learner_model
- AI in Education needs interpretable machine learning: Lessons from Open Learner Modelling: https://arxiv.org/abs/1807.00154

### Knowledge Tracing：掌握度要随证据动态更新

Knowledge Tracing 用学习者连续答题和练习行为更新知识点掌握状态。对 SparkWeave 的启发：

- 每个知识点要有 `score`、`status`、`confidence`、`trend`、`evidence_count`。
- 第一阶段用可解释启发式，不急着引入复杂模型。
- 后续可升级到 BKT 或 IRT-BKT，用题目难度和连续表现修正掌握度。

参考：

- An Introduction to Bayesian Knowledge Tracing with pyBKT: https://www.mdpi.com/2624-8611/5/3/770

### 可信 AI 与教育隐私

教育画像直接涉及学习者数据。NIST AI RMF 强调 valid/reliable、transparent/accountable、explainable/interpretable、privacy-enhanced 等可信特征；UNESCO 的生成式 AI 教育指南也强调以人为本和数据隐私。对 SparkWeave 的启发：

- 不做敏感属性推断。
- 不把单次模型判断当作高置信度事实。
- 画像更新需要审计日志。
- 用户必须能删除、导出、重建画像。
- 默认本地存储，避免把学习画像发送给不必要的第三方。

参考：

- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- UNESCO Guidance for generative AI in education and research: https://www.unesco.org/en/articles/guidance-generative-ai-education-and-research

## SparkWeave 当前证据源盘点

| 来源 | 已有数据 | 可抽取画像信号 | 建议接入阶段 |
| --- | --- | --- | --- |
| Chat / SessionStore | sessions、messages、turns、turn_events | 用户目标、提问主题、能力调用、学习卡点、偏好表达方式 | P2 |
| Memory | `SUMMARY.md`、`PROFILE.md` | 长期目标、学习偏好、人工维护信息 | P1 |
| Guide V2 session | profile、tasks、evidence、mastery、plan_events | 当前目标、前测、任务完成、错因、掌握度、路径调整 | P1/P2 |
| Guide V2 learner memory | `learner_memory.json` | 跨导学 session 的薄弱点、偏好、学习表现 | P1 |
| Question Notebook | notebook_entries、categories | 题型表现、正确率、错题、收藏、分类主题 | P1/P2 |
| Notebook | notebook JSON records | 用户显式沉淀的高价值学习产物 | P1/P2 |
| Resource artifacts | Guide artifact_refs、Chat assets | 生成过什么资源、保存/使用什么资源 | P2 |
| Knowledge/RAG | 默认知识库、引用上下文 | 当前课程资料范围、专业方向 | P3 |
| SparkBot | shared memory、bot history、tools log | 长期助教交互偏好、工具使用偏好 | P3 |

## 当前代码接入点

| 模块 | 文件 | 接入建议 |
| --- | --- | --- |
| 统一画像服务 | `sparkweave/services/learner_profile.py` | 新增，负责 profile/evidence/audit 读写与聚合 |
| 统一画像 API | `sparkweave/api/routers/learner_profile.py` | 新增 `/api/v1/learner-profile` |
| 路由挂载 | `sparkweave/api/main.py` | include 新 router |
| Guide V2 | `sparkweave/services/guide_v2.py`、`sparkweave/api/routers/guide_v2.py` | task complete、diagnostic、profile dialogue、quiz submit 写入证据 |
| SessionStore | `sparkweave/services/session_store.py` | 读取会话、题目本、turn_events；不建议直接改 schema，画像独立存 JSONL |
| Memory | `sparkweave/services/memory.py` | P1 汇总来源，P4 可作为兼容视图 |
| Notebook | `sparkweave/services/notebook.py` | add_record 后写入轻量证据 |
| 前端 API | `web/src/lib/api.ts`、`web/src/hooks/useApiQueries.ts` | 新增 learner profile 查询与 mutation |
| 前端页面 | `web/src/pages/MemoryPage.tsx` 或新 `ProfilePage.tsx` | 建议将 `/memory` 升级为画像中心，高级 Markdown 记忆作为子页 |
| 类型 | `web/src/lib/types.ts` | 新增 UnifiedLearnerProfile、LearnerEvidence 等类型 |

## 事件词表草案

### source

```text
chat
guide_v2
question_notebook
notebook
memory
resource
knowledge
sparkbot
manual
```

### verb

```text
asked
answered
completed
submitted
reflected
generated
viewed
saved
bookmarked
corrected_profile
updated_preference
diagnosed
recommended
```

### object_type

```text
chat_turn
guide_task
diagnostic
quiz
question
resource
notebook_record
memory_file
course_node
knowledge_base
profile_claim
```

### resource_type

```text
text
visual
video
quiz
research
geogebra
code
notebook
```

## 画像判断类型

每个判断都应带来源和置信度。

| 类型 | 示例 | 必须字段 |
| --- | --- | --- |
| stable goal | “想系统学习机器学习基础” | evidence_ids、updated_at |
| current goal | “今天先补梯度下降直观理解” | task_id、session_id、confidence |
| preference | “更偏好图解 + 练习” | source、positive/negative signal |
| weak point | “概念边界不清” | severity、related_nodes、evidence_ids、suggested_action |
| mastery | “梯度下降 needs_support 0.62” | score、confidence、trend、evidence_count |
| behavior pattern | “常保存图解资源，但练习提交少” | window、metric、recommendation |
| system recommendation | “先做判断题校准概念边界” | reason、target_node、expected_effect |

## 画像中心页面准备

建议第一版不要复杂，先做五块：

1. **当前学习目标**
   - 目标、课程、时间预算、下一步。

2. **当前卡点**
   - Top 3 weak points。
   - 每个卡点显示证据来源和一键补基。

3. **知识掌握**
   - 小型知识地图或列表。
   - status、score、trend、confidence。

4. **学习偏好**
   - 资源偏好、讲解风格、节奏。
   - 提供“修改/这不准确”。

5. **证据时间线**
   - 最近答题、任务完成、反思、资源保存。
   - 默认摘要，点击查看来源。

高级入口：

- 原始 Memory Markdown。
- 导出画像 JSON。
- 清空/重建画像。

## 后端开发准备清单

P1 详细施工图见 [学习画像 P1 只读统一画像实施方案](./learner-profile-p1-implementation.md)。

P1 只读画像必须完成：

- `LearnerEvidence`、`UnifiedLearnerProfile`、`ProfileClaim` dataclass/Pydantic model。
- `LearnerProfileStore`：
  - `read_profile()`
  - `write_profile()`
  - `append_evidence()`
  - `list_evidence()`
  - `refresh_from_existing_sources()`
- `ProfileAggregator`：
  - 从 Memory 文本提取目标/偏好。
  - 从 Guide V2 sessions 汇总 mastery/evidence。
  - 从 Question Notebook 汇总正确率和错因。
  - 从 Notebook 汇总显式保存主题。
- API：
  - `GET /api/v1/learner-profile`
  - `GET /api/v1/learner-profile/evidence-preview`
  - `POST /api/v1/learner-profile/refresh`
- 测试：
  - 空数据时返回可用空画像。
  - Guide V2 evidence 能进入 mastery。
  - Question Notebook 正确率能产生 weak point。
  - Memory 中的偏好能进入 preferences。
  - 用户本地数据不存在时不会报错。

## 前端开发准备清单

P1 画像中心必须完成：

- 新增类型和 API hook。
- `/memory` 改成画像中心或新增 `/profile` 并从 `/memory` 跳转。
- 保留高级记忆编辑入口，不再作为默认主体验。
- 所有文案面向学习者：
  - “我现在在学什么”
  - “系统发现的卡点”
  - “为什么这样判断”
  - “下一步建议”
- 不展示原始 JSON。
- 异常/空状态友好：
  - “还没有足够证据，先完成一次导学或练习。”

## 风险清单

| 风险 | 表现 | 规避 |
| --- | --- | --- |
| 画像变成黑箱 | 用户只看到结论，看不到来源 | 每个判断绑定 evidence_ids 和 why |
| 画像过度推断 | 模型从少量对话推断过多 | 低权重、低置信度、用户确认 |
| 旧 Memory 与 Guide memory 冲突 | 两套画像结论不一致 | 统一画像作为主视图，旧数据作为来源 |
| 页面太复杂 | 用户不知道如何使用 | 首页只展示目标、卡点、下一步 |
| 数据污染 | 错误模型输出写入长期画像 | 证据分级，LLM 提取结果低权重 |
| 隐私风险 | 记录不必要个人信息 | 只记录学习相关，支持删除/导出 |
| 推荐闭环断裂 | 画像不影响导学 | Guide V2 创建路线必须读取统一画像 |

## 测试矩阵

| 层级 | 测试 |
| --- | --- |
| Store | 读写 profile/evidence/audit，损坏 JSON 恢复 |
| Aggregator | Memory/Guide/Question/Notebook 聚合 |
| API | get/refresh/evidence/feedback |
| Guide 集成 | task complete、quiz submit 写证据 |
| Frontend | 空画像、已有画像、证据时间线、用户校准 |
| 回归 | 不影响现有 Memory、Guide、Notebook、Question API |

## 建议先做的 Spike

1. 用现有 `data/user/workspace/guide/v2/session_*.json` 和 `learner_memory.json` 生成一个只读画像样例。
2. 用 `notebook_entries` 统计最近题目正确率，映射到 weak points。
3. 做一个不写入数据库的 `/api/v1/learner-profile/evidence-preview`，验证证据摘要结构是否适合前端展示。
4. 设计画像中心低保真页面，只用 mock 数据验证“用户一眼是否知道下一步”。

## 不急着做的事

- 不急着引入 BKT/IRT 数据库模型。
- 不急着把所有历史 turn_events 全量入账。
- 不急着做复杂学习分析图表。
- 不急着让 LLM 自动重写所有画像。
- 不急着把 SparkBot 私有记忆完全并入统一画像。

## 开发前最终检查

正式编码前，确认：

- `learner-profile-design.md` 的模型字段是否冻结。
- P1 是否只做只读聚合，不引入过多自动写入。
- 前端入口到底使用 `/memory` 还是新增 `/profile`。
- Guide V2 的 `learner_memory.json` 是否保留为兼容缓存。
- 用户校准接口是否放到 P3。
- 演示课程的知识点 ID 命名规则是否确定。
