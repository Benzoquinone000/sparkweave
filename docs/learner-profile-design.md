# 学习画像设计调研与实现方案

学习画像是 SparkWeave 的中枢能力。它不是一个静态“用户资料表”，而是一个由对话、导学、练习、资源使用、笔记沉淀和学习反思共同驱动的证据模型。画像应服务于四件事：

1. 让系统知道用户当前目标、基础、卡点和偏好。
2. 让导学路径、资源生成和智能辅导真正个性化。
3. 让学习效果评估有依据，而不是泛泛总结。
4. 让用户看得懂、能纠正、能信任系统判断。

## 调研结论

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
| 高级记忆 | 原 `SUMMARY.md` / `PROFILE.md` 编辑器 |

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
| `POST` | `/feedback` | 用户确认、修改或驳回画像判断 |
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

- 新增 `LearnerProfileStore`。
- 从 Memory、Guide V2 learner memory、最近 Guide sessions、题目本统计生成只读 `profile.json`。
- 新增 `GET /api/v1/learner-profile`。
- 前端新增“画像中心”只读页面。

### P2：证据账本

- 新增 `evidence.jsonl`。
- Guide V2 任务完成、quiz 提交、Notebook 保存、Chat turn 完成写入证据。
- 前端展示证据时间线和“为什么这样判断”。

### P3：画像校准

- 新增 `/feedback`。
- 用户可以确认/修改/驳回目标、偏好、薄弱点、掌握度判断。
- 校准结果写入 evidence，并提高权重。

### P4：驱动导学和推荐

- Guide V2 创建路线读取统一画像。
- 当前任务和资源推荐基于 weak_points、preferences、mastery。
- 导学完成后把评估结果写回统一画像。

### P5：学习效果评估融合

- 学习报告直接读取统一画像和证据账本。
- 报告能展示掌握度变化、薄弱点变化、资源有效性和下一步调整原因。

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
