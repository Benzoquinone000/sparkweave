# 学习画像设计调研与实现方案

学习画像是 SparkWeave 的中枢能力。它不是一个静态“用户资料表”，而是一个由对话、导学、练习、资源使用、笔记沉淀和学习反思共同驱动的证据模型。画像应服务于四件事：

1. 让系统知道用户当前目标、基础、卡点和偏好。
2. 让导学路径、资源生成和智能辅导真正个性化。
3. 让学习效果评估有依据，而不是泛泛总结。
4. 让用户看得懂、能纠正、能信任系统判断。

## 调研结论

更完整的调研记录、项目内证据源盘点、风险清单和测试矩阵见 [学习画像开发前调研笔记](./learner-profile-research-notes.md)。

### 1. 学习行为要按“事件”沉淀

xAPI 将学习经历抽象为 statement，核心结构是 `actor`、`verb`、`object`，并可携带 `result`、`context`、`timestamp` 等信息。SparkWeave 不需要完整实现 xAPI/LRS，但应该借鉴这种事件化思想：每次答题、看视频、生成图解、提交反思、保存笔记，都可以成为画像的证据。

参考：

- ADL xAPI Spec: https://github.com/adlnet/xAPI-Spec/blob/master/xAPI-Data.md
- xAPI Statements 101: https://xapi.com/statements-101/

### 2. 事件要有统一词表，便于跨模块汇总

1EdTech Caliper 强调用统一的 learning activity vocabulary 来描述阅读、测验、视频、评分、工具使用等学习活动，并把来自多个系统的数据汇总成可分析视图。SparkWeave 当前已有 Chat、Guide、Notebook、Question Notebook、Knowledge、Math Animator 等多个模块，必须先统一事件类型，否则画像会继续割裂。

参考：

- 1EdTech Caliper Analytics: https://www.1edtech.org/standards/caliper
- Caliper Metric Profiles: https://www.1edtech.org/specs/caliper/caliper-metric-profiles-common-explanations

### 3. 画像必须开放、可解释、可协商

Open Learner Model 的核心价值是让学习者能看到系统如何理解自己。更进一步，Negotiable / Editable OLM 支持学习者通过对话、校准和编辑参与画像构建。SparkWeave 的画像不能只显示一个“系统说你薄弱”的结论，而要显示依据，并允许用户纠正。

参考：

- Open learner models and pedagogical strategies in higher education: https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1760183/full

### 4. 掌握度需要随证据动态更新

Knowledge Tracing 用学习者连续答题/练习数据更新知识状态，用于预测未来表现、发现薄弱点并提供干预。SparkWeave 第一阶段不需要上复杂模型，但应先把每个知识点的 `score`、`confidence`、`evidence_count`、`trend` 建起来，后续可以升级为 BKT/IRT-BKT。

参考：

- An Introduction to Bayesian Knowledge Tracing with pyBKT: https://www.mdpi.com/2624-8611/5/3/770

## 当前项目基础

SparkWeave 已经有很多画像素材，但还没有统一中枢。

| 来源 | 当前能力 | 可转化画像信号 |
| --- | --- | --- |
| Chat 会话 | 用户问题、能力调用、回答结果、会话历史 | 学习目标、关注主题、表达习惯、频繁卡点 |
| Memory | `SUMMARY.md`、`PROFILE.md` 两文件长期记忆 | 稳定偏好、长期目标、近期学习摘要 |
| Guide V2 | `LearnerProfile`、`LearningEvidence`、`MasteryState`、`learner_memory.json` | 路径目标、前测结果、任务完成、掌握度、薄弱点 |
| Question Notebook | 题目、答案、正确性、分类、收藏 | 正确率、题型薄弱点、知识点薄弱点 |
| Notebook | 用户显式保存的学习产物 | 高价值材料、复盘主题、长期学习资产 |
| Resource artifacts | 图解、视频、练习、资料、保存行为 | 资源偏好、资源有效性、学习投入 |
| Knowledge/RAG | 当前使用的知识库和检索上下文 | 课程范围、知识来源、专业方向 |

当前断点：

- 全局 Memory 与 Guide V2 learner memory 是两套画像。
- 画像更多是 Markdown 或 session 内字段，不够结构化。
- 证据来源没有统一 event ledger。
- 前端 MemoryPage 偏开发者式编辑，不像面向学习者的画像中心。
- 画像对导学和推荐有影响，但影响过程不够可见。

## 设计原则

1. **证据优先**：任何画像判断都应能追溯来源。
2. **用户可见**：默认展示用户能理解的结论，不展示原始 JSON。
3. **用户可纠正**：用户可以确认、修改或驳回系统推断。
4. **分层建模**：稳定信息、短期状态、知识掌握、学习偏好和行为证据分开存。
5. **谨慎推断**：只推断学习相关内容，不做人格、心理、敏感属性判断。
6. **可被下游使用**：画像必须能驱动 Guide、Chat、Question、Resource 推荐，而不是只做展示。
7. **渐进落地**：先统一结构和只读汇总，再逐步接入自动更新和推荐策略。

## 统一画像模型

建议新增统一画像服务：`sparkweave/services/learner_profile.py`。

默认存储：

```text
data/user/learner_profile/
  profile.json
  evidence.jsonl
  audit.jsonl
```

### LearnerEvidence

每条证据是一条规范化学习事件。

```json
{
  "id": "ev_...",
  "source": "guide_v2 | chat | question_notebook | notebook | resource | memory",
  "source_id": "session/task/record id",
  "actor": "learner",
  "verb": "asked | answered | completed | reflected | viewed | saved | generated | corrected_profile",
  "object_type": "concept | task | quiz | resource | notebook_record | chat_turn",
  "object_id": "node/task/question/resource id",
  "course_id": "ml_foundations",
  "node_id": "gradient_descent",
  "task_id": "task_...",
  "resource_type": "text | visual | video | quiz | research",
  "score": 0.82,
  "is_correct": true,
  "duration_seconds": 420,
  "confidence": 0.7,
  "reflection": "我能理解方向，但公式推导还不稳。",
  "mistake_types": ["概念边界不清", "公式意义不清"],
  "created_at": 1760000000.0,
  "weight": 1.0,
  "metadata": {}
}
```

### UnifiedLearnerProfile

画像是证据聚合后的当前状态。

```json
{
  "learner_id": "local-user",
  "version": 1,
  "updated_at": 1760000000.0,
  "stable": {
    "display_name": "",
    "major": "",
    "course_focus": [],
    "long_term_goals": [],
    "constraints": []
  },
  "current": {
    "active_goal": "",
    "active_course_id": "",
    "readiness": "beginner | intermediate | advanced | unknown",
    "time_budget_minutes": 30,
    "next_best_action": ""
  },
  "preferences": {
    "resource_types": ["visual", "practice"],
    "explanation_style": ["step_by_step", "example_first"],
    "language": "zh",
    "pace": "normal"
  },
  "mastery": {
    "gradient_descent": {
      "title": "梯度下降",
      "score": 0.62,
      "status": "needs_support",
      "confidence": 0.74,
      "trend": "up",
      "evidence_count": 5,
      "last_evidence_ids": ["ev_1", "ev_2"],
      "why": "最近练习正确率偏低，并在反思中多次提到公式意义不清。"
    }
  },
  "weak_points": [
    {
      "label": "概念边界不清",
      "severity": "high",
      "related_nodes": ["gradient_descent"],
      "evidence_ids": ["ev_1"],
      "suggested_action": "先看图解，再做 3 道判断题。"
    }
  ],
  "strengths": [],
  "recommendations": [],
  "evidence_summary": {
    "total": 0,
    "last_7_days": 0,
    "latest_at": null
  }
}
```

## 画像更新流水线

```text
学习行为发生
  -> 各模块写入 LearnerEvidence
  -> EvidenceNormalizer 规范字段和类型
  -> SignalExtractor 抽取目标、偏好、错因、知识点
  -> ProfileAggregator 更新画像
  -> ExplanationBuilder 生成 why
  -> ProfileStore 保存 profile.json / evidence.jsonl
  -> Guide / Chat / Recommendation 读取画像
```

### 证据权重建议

| 证据类型 | 默认权重 | 原因 |
| --- | --- | --- |
| 前测/诊断题 | 1.2 | 对初始路径影响大 |
| 交互练习结果 | 1.0 | 直接反映掌握度 |
| 任务完成提交 | 0.9 | 有反思和自评价值 |
| Notebook 保存 | 0.6 | 表示用户认为内容重要 |
| 资源查看 | 0.4 | 只能说明接触过资源 |
| 普通聊天问题 | 0.3 | 可提示兴趣和卡点，但噪声较多 |
| 用户手动纠正画像 | 1.5 | 应优先尊重用户自我校准 |

### 掌握度更新建议

第一阶段使用透明启发式：

```text
new_score = old_score * 0.75 + evidence_score * 0.25
confidence = min(1.0, confidence + evidence_weight * 0.08)
```

状态阈值：

```text
score < 0.45       -> needs_foundation
0.45 <= score < .7 -> needs_support
0.70 <= score < .85 -> practicing
score >= 0.85      -> mastered
```

后续可升级：

- BKT：用连续答题更新知识点掌握概率。
- IRT-BKT：加入题目难度，避免“做简单题全对”导致掌握度虚高。
- LLM judge：只作为解释和错因归类辅助，不直接作为唯一评分来源。

## 前端画像中心设计

建议将当前 `/memory` 从“Markdown 编辑器”升级为“学习画像中心”，Markdown Memory 作为高级入口保留。

### 首页只保留三件事

1. **我现在在学什么**
   - 当前目标
   - 当前课程/知识模块
   - 推荐下一步

2. **系统认为我卡在哪里**
   - Top 3 薄弱点
   - 每个薄弱点的证据来源
   - 一键进入补基任务

3. **我适合怎样学**
   - 偏好资源：图解、练习、视频、文字
   - 解释风格：例子优先、公式优先、步骤拆解
   - 时间预算和学习节奏

### 子页

| 子页 | 内容 |
| --- | --- |
| 能力地图 | 按课程/知识点展示 mastery、trend、confidence |
| 薄弱点 | 错因聚类、相关任务、推荐补救 |
| 证据时间线 | 最近答题、任务、反思、资源、保存记录 |
| 画像校准 | 用户确认/修改系统推断 |
| 手动补充 | 原 `SUMMARY.md` / `PROFILE.md` 编辑器，仅作为长期信息的可选入口 |

### 交互原则

- 每条画像判断旁边有“为什么这样判断”。
- 用户可以点击“这不准确”进行修正。
- 不展示原始 JSON。
- 不让用户一次填写大量表单，而是通过对话、练习和反思慢慢构建。
- 修改画像后，导学页面应提示“已据此调整下一步”。

## API 设计建议

新增路由前缀：

```text
/api/v1/learner-profile
```

建议端点：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 当前统一画像 |
| `GET` | `/evidence` | 证据时间线，支持 source/course/node/filter |
| `POST` | `/evidence` | 写入一条或多条规范化证据 |
| `POST` | `/refresh` | 从现有 Memory、Guide V2、Notebook、题目本重建画像 |
| `POST` | `/calibrations` | 用户确认、修改或驳回画像判断 |
| `GET` | `/recommendations` | 基于画像的下一步建议 |
| `POST` | `/export` | 导出画像和证据，便于演示或调试 |

## 与现有模块的集成

### Chat

- 每轮会话结束后，抽取目标、偏好、卡点、请求类型。
- 只写学习相关证据。
- Chat prompt 注入统一画像摘要，而不是直接拼长 Markdown。

### Guide V2

- 创建路线时优先读取统一画像。
- 前测、任务完成、quiz 结果、反思提交全部写入 evidence。
- `LearnerProfile` 可以继续保留为 session-local snapshot，但来源应来自统一画像。
- `learner_memory.json` 后续可降级为兼容缓存或迁移到统一画像。

### Question Notebook

- 题目提交结果写入 evidence。
- 题型、知识点、错因、难度进入 mastery/weak_points。
- 错题本不只是收藏，也要成为画像更新的重要来源。

### Notebook

- 保存记录时写入轻量证据：保存了什么主题、来自哪个能力、用户认为它重要。
- Notebook 内容不应全部进入画像，只抽取摘要和标签。

### Resource artifacts

- 资源生成只说明系统提供过什么。
- 资源查看、练习提交、保存或反馈才说明资源是否有效。
- 视频/图解/练习偏好应由使用行为和用户反馈共同决定。

## 隐私与安全边界

- 默认本地存储，不上传第三方学习画像。
- 不推断敏感属性，例如心理状态、家庭背景、政治宗教等。
- 所有画像判断应可删除、可编辑、可重新生成。
- 用户手动修改优先级高于模型推断。
- 画像用于学习建议，不用于排名或惩罚。

## 开发路线

### P0：设计冻结

- 确认本文档的数据模型、事件词表、前端信息架构。
- 明确哪些旧数据参与迁移，哪些只做兼容。

### P1：只读统一画像

详细施工图见 [学习画像 P1 只读统一画像实施方案](./learner-profile-p1-implementation.md)。

- 新增 `LearnerProfileStore`。
- 从 Memory、Guide V2 learner memory、最近 Guide sessions、题目本统计生成只读 `profile.json`。
- 新增 `GET /api/v1/learner-profile`。
- 前端新增“画像中心”只读页面。

### P2：证据账本

- 新增 `evidence.jsonl`。
- Guide V2 任务完成、quiz 提交、Notebook 保存、Chat turn 完成写入证据。
- 前端展示证据时间线和“为什么这样判断”。

### P3：画像校准

- 新增 `/calibrations`，详见 [学习画像 P3 用户校准](./learner-profile-p3-calibration.md)。
- 用户可以确认/修改/驳回目标、偏好、薄弱点、掌握度判断。
- 校准结果写入 evidence，并提高权重。

### P4：对话信号接入

- LangGraph 运行时在持久化用户消息时抽取学习目标、卡点和资源偏好。
- 对话信号以低置信度写入 evidence，详见 [学习画像 P4 对话信号接入](./learner-profile-p4-chat-signals.md)。
- 用户后续校准事件优先级高于聊天启发式信号。

### P5：驱动导学和推荐

- Guide V2 创建路线读取统一画像，详见 [学习画像 P5 Guide V2 导学接入统一画像](./learner-profile-p5-guide-integration.md)。
- 当前任务和资源推荐基于 weak_points、preferences、mastery。
- 导学完成后把评估结果写回统一画像。

### P6：学习效果评估融合

- 学习报告直接读取统一画像和证据账本，详见 [学习画像 P6 学习效果评估融合](./learner-profile-p6-effect-assessment.md)。
- 报告能展示掌握度变化、薄弱点变化、资源有效性和下一步调整原因。

### P7：知识点掌握度沉淀

- 题目/练习事件提取 `concepts`、`knowledge_points`、`categories` 等字段，详见 [学习画像 P7 知识点掌握度沉淀](./learner-profile-p7-concept-mastery.md)。
- 画像聚合优先按知识点合并 mastery、weak point 和 strength。
- 交互式练习、导学提交页和学习报告都应优先展示概念级反馈，而不是只展示题目级结果。

### P8：一步行动建议

- 统一画像输出 `next_action`，详见 [学习画像 P8 一步行动建议](./learner-profile-p8-next-action.md)。
- 画像页首屏优先展示“现在只做这一步”，降低用户理解成本。
- 行动建议默认跳到导学页，后续形成“建议 -> 行动 -> 反馈 -> 画像更新”的闭环。

### P9：模型上下文注入

- 新增 `ProfileContextInjector`，详见 [学习画像 P9 模型上下文注入](./learner-profile-p9-context-injection.md)。
- LangGraph 回合创建 `UnifiedContext` 时，把画像压缩摘要注入 `memory_context`，让 Chat、解题、出题、图解、动画和研究能力都能静默使用画像。
- 只注入短摘要和策略提示，不把原始画像 JSON 交给模型；完整证据仍由画像中心和 evidence ledger 负责解释。
- 画像不可用时不阻断普通会话，只在 `metadata.learner_profile_context` 中记录状态。

### P10：用户侧极简呈现

- 画像页默认只回答四个问题：系统现在怎么理解我、下一步做什么、最需要补什么、掌握情况如何。
- 画像页首屏采用“一个主行动 + 三条原因 + 轻量可信度”的仪表盘，不再把下一步、依据、统计拆成多张并列卡片。
- 薄弱点和掌握情况必须写成用户能直接行动的话：先补什么、是否能继续、是否需要短练习验证；证据数和进度条只做辅助，不抢主信息。
- 薄弱点、掌握项和下一步建议都应能一键进入导学，并自动带入学习目标，避免用户重新描述同一个问题。
- 聊天页只用一枚轻量提示说明“画像已启用”，详细画像放在资料与工具抽屉里，避免打扰主对话。
- 导学页只在当前任务旁用一句“画像依据”解释资源推荐原因，不再展示策略面板或长列表。
- 高级证据、长期记忆、路线地图、课程产出包都放到二级页面，主流程保持单任务、少下拉、多跳转。
- 用户可以在画像首页用一句话修正系统判断，失败时给明确反馈，修正事件进入 `/calibrations` 并优先影响画像概览。
- 从画像建议进入导学时，导学页自动填好目标；路线创建、任务完成、前测、练习和画像对话后都要刷新画像，形成“画像建议 -> 导学行动 -> 证据沉淀 -> 画像更新”的闭环。
- 从画像建议进入导学时默认落在主创建流程，不进入学习偏好页；偏好、Notebook 引用和课程模板只作为用户主动进入的二级设置。
- 导学页的侧边抽屉只承担路线切换、新建路线、查看画像和少量管理动作；不要再放资源生成、推荐列表或长表单，避免用户从主任务分心。
- 导学主页面默认就是专注单任务，不再提供“普通/专注模式”切换；用户只需要看到当前一步和一个主要行动。
- 导学主流程不再插入画像对话入口；画像修正放回画像页，导学阶段只通过前测、练习、反思自然沉淀证据。
- 完整路线、课程产出包等二级内容只作为轻量链接出现，不使用全宽卡片抢占当前任务注意力。
- 资源结果区不是“结果列表”，而是学习顺序：先看图解/短视频建立直觉，再做练习验证，最后回到提交页沉淀反馈。
- 当前任务区的资源入口只突出画像推荐的一个主行动；图解、短视频、练习等其他资源只能作为轻量备选，避免用户在资源类型之间反复纠结。
- 当前任务提交页不让用户填写系统格式分数，默认使用“还没懂 / 有点懂 / 掌握了”这类自然反馈，再由前端映射为评分证据。
- 学习反馈页只展示反馈摘要和一个主下一步，不在导学主流程里铺开知识点反馈、证据质量、资源按钮矩阵；细节回到画像页或报告页查看。
- 导学主流程不保留隐藏旧侧栏、策略面板或备用工具箱代码；被移出用户路径的复杂信息必须迁移到二级页面或直接删除，避免后续回流。
- 画像页和导学抽屉里的页面切换、路线管理、重新整理、删除等动作必须降级为轻量分页或小按钮；首屏视觉重心只留给学习行动。

## 验收标准

画像中心必须达到以下效果：

- 用户一眼知道系统认为自己“目标是什么、会什么、卡在哪里、下一步做什么”。
- 每个判断都能看到证据来源。
- 用户可以纠正画像。
- 导学、答疑、资源生成和学习报告都会使用画像。
- 画像随着练习、反思、会话和笔记持续变化。
- 演示时可以清楚对应赛题第一条“对话式学习画像自主构建”。

## 不做事项

- 不做复杂人格画像。
- 不把原始日志直接暴露给用户。
- 不用单次 LLM 判断覆盖长期证据。
- 不强迫用户填写长表单。
- 不把画像做成只读黑箱。
