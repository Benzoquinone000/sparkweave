### 2026-05-04：画像页已显示错因闭环状态

已调整：

- `LearningEffectService.build_report()` 新增 `remediation_loop` 摘要。
- 系统会从导学反馈事件里的 `remediation_task` 识别补救任务，并根据后续完成事件、复测答题事件推断状态：
  - `pending_remediation`：待补救；
  - `ready_for_retest`：补救已做完，等待复测；
  - `closed`：补救后复测通过，错因闭环。
- 学习画像页的学习效果卡新增“错因闭环”状态条，展示待补救、待复测、已闭环数量和当前优先薄弱点。

当前效果：

- 用户不用进入导学详情，也能在画像页看到薄弱点是否真正被处理。
- 闭环链路变成：答错 -> 生成补救任务 -> 完成补救 -> 复测 -> 画像页显示已闭环。
- 页面只显示一个轻量状态条，不增加复杂入口。

已验证：

```powershell
python -m ruff check sparkweave\services\learning_effect.py tests\services\test_learning_effect.py
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py -q
npm run lint
npm run build
```

下一步重点：

1. 将错因闭环状态进一步接入演示脚本和 competition preflight 报告。
2. 给画像页补一个“我为什么被判定为待补救/待复测”的可解释详情。
3. 把补救完成后的复测入口做成更显眼但仍然简约的主按钮。

# SparkWeave 学习效果评估闭环设计稿

> 调研日期：2026-05-04  
> 目标：把 SparkWeave 从“能生成学习资源”推进到“能评估学习是否真的变好，并据此调整画像、导学路线和资源推荐”。

## 1. 设计结论

学习效果评估不应该做成一个孤立报表，也不应该把一堆分数平铺给用户。它应该是一个闭环：

```text
学习行为发生
  -> 写入统一学习事件
  -> 更新知识点掌握度、错因、投入度和证据可信度
  -> 生成一句用户能理解的学习处方
  -> 调整导学下一步、资源类型、练习难度和复测安排
  -> 用户完成下一步后再次回写证据
```

用户最终看到的不是“复杂仪表盘”，而是：

- 现在先做什么；
- 为什么系统这样判断；
- 做完以后系统会如何调整；
- 哪些证据支撑这个判断。

## 2. 市面产品调研摘要

### 2.1 Khan Academy：掌握度分层要简单、可解释

Khan Academy 的 Mastery 系统把技能状态分成 Not Started、Attempted、Familiar、Proficient、Mastered 等层级，并根据练习、混合测验和挑战题动态升降级。它的启发是：SparkWeave 不应该只给 0-100 分，而要把分数转成用户能理解的状态。

可借鉴：

- 每个知识点有清晰状态：未开始、尝试中、熟悉、熟练、掌握。
- 混合测验可以让知识点升降级，而不是只在单点练习里更新。
- “掌握”必须比“做对一次”更严格。

来源：https://support.khanacademy.org/hc/en-us/articles/5548760867853--How-do-Khan-Academy-s-Mastery-levels-work

### 2.2 ALEKS：先诊断，再把知识状态变成下一步

ALEKS 会先做个性化自适应评估，再用知识饼图展示当前知识状态；学习者点击推荐主题进入 Learning Mode，完成掌握后新主题才开放。它的重点不是“展示图表”，而是把评估结果直接变成可学习路径。

可借鉴：

- 初始诊断要尽快建立基线。
- 知识地图不只是展示，要能告诉用户“现在可学什么”。
- 完成掌握后开放下一批任务，形成递进式导学。
- 即时反馈和错题修正是评估闭环的一部分。

来源：https://www.aleks.com/independent/students/tour_print

### 2.3 Duolingo Birdbrain：预测“这道题对这个人是否刚好”

Duolingo 的 Birdbrain 同时学习“学习者知道多少”和“题目/材料有多难”，预测用户答对某个练习的概率，再把结果交给 Session Generator 选择合适难度。它的启发是：资源推荐不能只按主题匹配，还要按“难度是否刚好”匹配。

可借鉴：

- 每道题、每个资源都应有难度估计。
- 推荐的目标不是越难越好，而是接近学习者当前边界。
- 题目正确率、停留时间、重复错误都能反推难度是否合适。

来源：https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain/

### 2.4 Coursera LevelSets：基线评估 + 进步追踪 + 内容匹配

Coursera LevelSets 强调先评估当前能力，再根据技能水平推荐内容，并持续跟踪相对基线的进步。它的启发是：SparkWeave 的学习效果评估要有 baseline，否则很难说明“进步”。

可借鉴：

- 每门课程建立初始水平线。
- 报告要显示相对基线的变化，而不是只显示当前分。
- 个性化推荐要说明对应的技能缺口。

来源：https://www.coursera.org/business/levelsets

### 2.5 Smart Sparrow：自适应反馈触发条件要丰富

Smart Sparrow 的自适应课程会根据回答、屏幕停留时间、尝试次数等触发提示、视频、图表或补充材料。它的启发是：SparkWeave 不应只看答题对错，还要看过程行为。

可借鉴：

- 答错、耗时过长、多次尝试、跳过任务都应是评估信号。
- 反馈可以是文字、图解、短视频、补充练习，不止一种形式。
- 资源效果也要被评估：用户是否看完、保存、继续练习。

来源：https://www.smartsparrow.com/platform/

### 2.6 Moodle Learning Analytics：模型要有指标、目标、洞察和行动

Moodle Learning Analytics 把模型拆成 indicators、targets、insights、notifications/actions。这个结构非常适合 SparkWeave：我们不只是预测，而是要把预测变成用户可执行动作。

可借鉴：

- indicator：可观察指标，例如正确率、完成度、停留时间。
- target：要判断的目标，例如“是否需要补基”“是否可进入下一节”。
- insight：给用户/系统看的结论。
- action：下一步动作，例如复测、生成图解、降低难度。

来源：https://docs.moodle.org/en/Using_analytics

### 2.7 Caliper / xAPI：学习行为需要统一事件格式

Caliper 和 xAPI 的共同启发是：跨模块学习行为必须先事件化。SparkWeave 有 Chat、Guide、Notebook、题库、知识库、视频、TTS、动画等模块，如果每个模块自己记自己的，就无法形成可信画像。

可借鉴：

- 学习事件至少要记录：谁、做了什么、对什么对象、结果如何、发生时间。
- 题目、视频、资源、测验、页面访问都要进入同一个事件账本。
- 事件格式要稳定，后面才能接统计、模型和可视化。

来源：https://www.imsglobal.org/spec/caliper/latest/

### 2.8 BKT：掌握度是随证据更新的概率，不是一锤子买卖

Bayesian Knowledge Tracing 把“是否掌握某技能”看成隐变量，并随着答题表现更新掌握概率。SparkWeave 第一阶段不必上复杂模型，但应采用类似思想：掌握度必须随新证据动态更新，并带有置信度。

可借鉴：

- 每个知识点有 `score` 和 `confidence`。
- 答对、答错、题目难度、错因、复测结果都会更新掌握度。
- 以后可以从规则版升级到 BKT/IRT-BKT。

来源：https://www.mdpi.com/2624-8611/5/3/770

## 3. SparkWeave 当前基础

项目已经具备闭环雏形：

- `LearnerEvidenceService`：已有 append-only `evidence.jsonl` 证据账本。
- `GuideV2Manager.evaluate_session()`：已有导学 session 评分、进度、掌握度、风险和下一步建议。
- `GuideV2Manager._effect_assessment()`：已有任务进度、综合掌握、证据质量、学习参与、错因闭环、长期画像等维度。
- `question_notebook`：题目提交可以写入 learner evidence。
- `learner_profile`：画像已可从证据聚合，并支持用户校准。
- `profile_context`：画像可以进入对话和智能体调度上下文。

现阶段最大问题不是“完全没有评估”，而是：

1. 评估逻辑主要藏在 Guide V2 内，尚未成为全局后端能力。
2. 事件类型还不够统一，跨 Chat / Guide / Notebook / 视频 / 资源的评估口径不够稳定。
3. 掌握度更新偏 session 内，长期知识点层面的演化还不够强。
4. 评估结果还需要更明确地反向驱动推荐、复测、资源生成和画像更新。

## 4. 产品原则

### 4.1 面向用户，不面向报表

默认只给用户一句“学习处方”：

> 你现在主要卡在「梯度下降的方向直觉」，先看 5 分钟图解，再做 3 道判断题复测。

高级详情可以展开，但不能默认塞满页面。

### 4.2 先有证据，再有结论

所有判断都要能回到证据：

- 来自哪次练习；
- 哪个知识点；
- 错在哪里；
- 是否复测过；
- 用户是否校准过。

### 4.3 评分不是终点，动作才是终点

每个评估结论必须产生至少一个动作：

- 继续下一节；
- 复测；
- 补基础；
- 生成图解；
- 生成短视频；
- 做混合练习；
- 回到画像中心确认判断。

### 4.4 一个画像，不做两套画像

导学画像、学习画像、效果评估画像必须是同一个 learner profile 的不同视图。学习效果评估是画像上的动态评估层，不应另起一套“评估画像”。

## 5. 后端目标架构

```text
Chat / Guide / Notebook / Question / Video / RAG / SparkBot
  -> LearningEventCollector
  -> LearningEventLedger
  -> SignalExtractor
  -> ConceptMasteryEngine
  -> LearningEffectEvaluator
  -> InterventionPolicy
  -> ProfileUpdater
  -> Guide / Chat / Resource / Report
```

### 5.1 LearningEventCollector

统一接收所有学习行为，补齐字段，写入事件账本。

### 5.2 LearningEventLedger

基于现有 `LearnerEvidenceService` 扩展，继续保留 JSONL 低成本、易调试优势。后续可以迁移到 SQLite。

### 5.3 SignalExtractor

把原始事件转成可评估信号：

- 正确率；
- 题目难度；
- 错因；
- 耗时；
- 尝试次数；
- 是否跳过；
- 是否保存；
- 是否复测；
- 是否完成反思；
- 用户是否确认/否定画像判断。

### 5.4 ConceptMasteryEngine

维护每个知识点的状态：

```json
{
  "concept_id": "gradient_descent",
  "title": "梯度下降",
  "score": 0.64,
  "status": "needs_support",
  "confidence": 0.72,
  "trend": "up",
  "last_practiced_at": 1760000000,
  "next_review_at": 1760086400,
  "evidence_count": 8,
  "open_mistake_count": 2
}
```

### 5.5 LearningEffectEvaluator

生成全局学习效果报告，而不是只服务 Guide session。

核心维度：

| 维度 | 含义 | 主要信号 |
| --- | --- | --- |
| 掌握度 | 知识点当前水平 | 正确率、难度、复测、错因关闭 |
| 进步度 | 相对 baseline 是否变好 | 初测 vs 最近表现、趋势 |
| 稳定性 | 是否能跨题型/跨时间保持 | 混合题、复测、间隔复习 |
| 证据质量 | 判断是否可信 | 事件数量、来源多样性、评分完整度 |
| 学习投入 | 是否真的参与 | 完成任务、看资源、保存、反思 |
| 错因闭环 | 错误是否被处理 | 错因聚类、补救、复测通过 |
| 资源有效性 | 推荐资源是否有用 | 查看、保存、后续正确率变化 |

### 5.6 InterventionPolicy

把评估结果转成下一步动作。

示例：

| 条件 | 动作 |
| --- | --- |
| 掌握度低 + 证据少 | 做 5 题诊断 |
| 掌握度低 + 错因集中 | 生成图解 + 3 道判断题 |
| 掌握度中等 + 复测缺失 | 安排混合复测 |
| 掌握度高 + 稳定性高 | 进入下一节或项目任务 |
| 视频看过但练习没变好 | 换成例题讲解或交互练习 |
| 用户否定画像判断 | 降低该结论置信度并触发重新诊断 |

## 6. 数据模型草案

### 6.1 LearningEffectEvent

第一阶段可以复用 `LearnerEvidenceEvent`，但语义上要收敛成下面结构：

```json
{
  "id": "ev_xxx",
  "learner_id": "local-user",
  "source": "guide_v2",
  "verb": "answered",
  "object_type": "quiz_item",
  "object_id": "q_001",
  "course_id": "ml_foundations",
  "concept_ids": ["gradient_descent", "loss_function"],
  "task_id": "task_ml4",
  "resource_id": "",
  "result": {
    "score": 0.8,
    "is_correct": true,
    "duration_seconds": 42,
    "attempt_count": 1,
    "difficulty": 0.55,
    "question_type": "choice"
  },
  "signals": {
    "mistake_types": [],
    "self_report_confidence": 0.7,
    "help_used": false
  },
  "created_at": 1760000000
}
```

### 6.2 LearningEffectReport

```json
{
  "learner_id": "local-user",
  "course_id": "ml_foundations",
  "window": "last_14_days",
  "baseline": {
    "score": 42,
    "created_at": 1760000000
  },
  "overall": {
    "score": 73,
    "label": "正在进步",
    "summary": "最近练习正确率提升，但梯度方向和学习率仍需复测。"
  },
  "dimensions": [],
  "concepts": [],
  "open_mistakes": [],
  "next_actions": [],
  "evidence_refs": []
}
```

### 6.3 NextBestAction

```json
{
  "id": "nba_001",
  "type": "generate_practice",
  "title": "做 3 道梯度下降判断题",
  "reason": "你在两个任务中都把负梯度方向和函数上升方向混淆了。",
  "target_concepts": ["gradient_descent"],
  "estimated_minutes": 8,
  "priority": 0.92,
  "href": "/guide?...",
  "writes_back": ["mastery", "mistake_review", "profile"]
}
```

## 7. 掌握度更新策略

第一阶段使用透明规则，避免一上来就黑盒化。

### 7.1 事件分数

```text
event_score =
  correctness_part * 0.55
  + difficulty_part * 0.15
  + reflection_part * 0.10
  + completion_part * 0.10
  + retest_part * 0.10
```

### 7.2 知识点更新

```text
new_score = old_score * decay + event_score * (1 - decay)
confidence += evidence_weight * source_reliability
```

建议：

- 普通练习：`decay = 0.72`
- 诊断/复测：`decay = 0.60`
- 用户校准：不直接改分，但改置信度和解释。

### 7.3 状态分层

```text
0.00 - 0.35  未建立基础
0.35 - 0.55  需要补基
0.55 - 0.75  正在练习
0.75 - 0.88  基本熟练
0.88 - 1.00  稳定掌握
```

### 7.4 复测与遗忘

每个概念维护 `next_review_at`：

- 新学概念：1 天后复测；
- 正在练习：3 天后复测；
- 基本熟练：7 天后复测；
- 稳定掌握：14-30 天后抽查。

如果超过复测时间，状态不必直接降级，但 `stability` 降低，并优先推荐混合复测。

## 8. API 设计

建议新增独立路由：

```text
/api/v1/learning-effect
```

### 8.1 查询总报告

```text
GET /api/v1/learning-effect/report?course_id=ml_foundations&window=14d
```

返回 `LearningEffectReport`。

### 8.2 查询知识点状态

```text
GET /api/v1/learning-effect/concepts?course_id=ml_foundations
```

返回知识点掌握度、趋势、复测时间、开放错因。

### 8.3 写入事件

```text
POST /api/v1/learning-effect/events
```

内部可直接代理到 `LearnerEvidenceService`，但字段采用更标准的 learning event 结构。

### 8.4 查询下一步动作

```text
GET /api/v1/learning-effect/next-actions?course_id=ml_foundations
```

给 Chat、Guide、Memory 首页和工作台空状态使用。

### 8.5 完成干预动作

```text
POST /api/v1/learning-effect/actions/{action_id}/complete
```

用于记录用户完成了系统推荐的补基、复测、图解、视频或练习。

## 9. 与现有模块的接入方式

### 9.1 Guide V2

Guide 仍然是主闭环入口，但评估逻辑逐步下沉到 `LearningEffectEvaluator`。

接入点：

- 创建 session：写 baseline event。
- 提交诊断：更新 concept mastery。
- 生成资源：记录 resource generated。
- 查看资源：记录 resource viewed。
- 提交练习：记录 answered / quiz_attempt。
- 完成任务：记录 completed。
- 学习报告：读取全局 effect report。

### 9.2 Chat

Chat 不直接做复杂评估，但需要把以下内容写入事件：

- 用户主动提问的主题；
- 智能体能力调用；
- 用户点击保存、生成练习、生成图解、找视频；
- 回答后的反馈。

Chat 协调智能体读取 `next_action_prompt`，让“继续学习”真正按评估结果执行。

### 9.3 Question Notebook

题目本是效果评估最强证据之一。

需要加强：

- 每题必须带 `concept_ids`；
- 每题有 `difficulty`；
- 每次提交记录 `attempt_count` 和 `duration_seconds`；
- 错题进入 mistake cluster；
- 复测通过后关闭错因。

### 9.4 Notebook

Notebook 保存不能当作掌握，只能当作学习投入和偏好证据。

规则：

- 保存图解/视频/笔记：增加 resource preference 轻证据。
- 用户写反思：增加 evidence quality。
- 从 Notebook 发起复习：增加 engagement。

### 9.5 多模态资源

OCR、图解、Manim、TTS、外部视频都要进入资源效果评估。

最低事件：

- generated
- viewed / played
- saved
- used_in_practice
- marked_helpful / marked_not_helpful

## 10. 前端呈现原则

虽然本设计主要是后端，但接口要服务前端的“懒人式”体验。

默认页面只展示：

1. 当前学习处方；
2. 一个主按钮；
3. 两个备用动作；
4. 证据摘要。

不默认展示：

- 原始 JSON；
- 事件流水；
- 复杂雷达图；
- 一屏十几个指标；
- 开发者调试日志。

## 11. 分阶段实施计划

### P1：全局评估服务骨架

目标：把评估从 Guide V2 中抽出来，成为独立服务。

任务：

- 新增 `sparkweave/services/learning_effect.py`
- 新增 `sparkweave/api/routers/learning_effect.py`
- 复用 `LearnerEvidenceService`
- 实现 report / concepts / next-actions 基础接口
- 给现有 Guide V2 report 改为读取新服务结果

验收：

- 不跑 Guide 也能基于 evidence 生成效果报告。
- 报告能返回当前处方和下一步动作。

### P2：知识点掌握度引擎

目标：让每个知识点有长期状态。

任务：

- 从 evidence 中抽取 concept ids。
- 建立 `ConceptMasteryState`。
- 实现掌握度 EWMA 更新。
- 实现 status / confidence / trend。
- 把 question notebook 和 guide quiz 的证据纳入更新。

验收：

- 用户连续答题后，知识点状态会变化。
- 答错后出现开放错因。
- 复测通过后错因可以关闭。

### P3：学习处方和干预策略

目标：让评估结果影响下一步。

任务：

- 新增 `InterventionPolicy`
- 生成 next best actions。
- 接入 Chat 的 profile/context prompt。
- 接入 Guide 首页当前任务推荐。
- 支持复测、补基、图解、短视频、练习、项目任务几类动作。

验收：

- 用户说“继续学习”，系统能按评估结果唤醒正确能力。
- Guide 首页主任务来自学习效果评估，而不是固定模板。

### P4：资源有效性评估

目标：证明多模态资源不是摆设，而是真的影响学习。

任务：

- 记录资源查看、保存、反馈。
- 关联资源后的练习表现变化。
- 给资源打 helpful score。
- 推荐时优先选择对当前用户有效的资源类型。

验收：

- 如果用户看视频后仍答错，下一步会换成练习或图解。
- 如果用户反复保存图解，画像会提高 visual preference 置信度。

### P5：比赛演示闭环

目标：形成可录屏、可解释、可答辩的完整故事。

脚本：

```text
对话建立目标
  -> 系统生成画像
  -> 前测发现薄弱点
  -> 生成图解/短视频/练习
  -> 用户提交答案
  -> 效果报告更新
  -> 路线自动调整
  -> 画像中心显示证据变化
```

验收：

- 7 分钟视频能清楚展示赛题第五项。
- 报告能解释“为什么推荐下一步”。
- 画像能显示“这次学习如何改变了我”。

## 12. 测试计划

### 单元测试

- event normalization
- concept mastery update
- effect report scoring
- next action policy
- mistake cluster close/reopen

### API 测试

- `/api/v1/learning-effect/report`
- `/api/v1/learning-effect/concepts`
- `/api/v1/learning-effect/next-actions`
- event append and refresh

### 集成测试

- Guide quiz submit -> evidence -> mastery -> report -> next action
- Question notebook answer -> evidence -> concept state
- External video viewed -> preference update -> resource recommendation
- Profile calibration -> confidence update -> report explanation

### 黑盒演示测试

- 新用户第一次进入：报告提示先做诊断。
- 答错若干题：报告提示补基和复测。
- 完成补救：报告状态改善。
- 保存图解/视频：画像偏好变化。

## 13. 风险与边界

### 风险

- LLM 生成题目未标注知识点，导致掌握度更新不准。
- 用户只看资源不做练习，系统不能误判为掌握。
- 少量证据下评分波动大。
- 复杂指标会让前端重新变乱。

### 约束

- 第一阶段宁可透明规则，也不要黑盒模型。
- LLM judge 只能辅助错因归类，不能作为唯一评分来源。
- 用户手动校准优先级高，但不能直接覆盖全部客观练习证据。
- 评估结果必须给用户看得懂的理由。

## 14. 第一轮开发建议

我建议下一步先做 P1 + P2 的最小闭环：

1. 新建 `LearningEffectService`。
2. 从现有 evidence 聚合报告。
3. 建立 `ConceptMasteryState`。
4. 给 Guide / Question Notebook 的答题证据补齐 concept/difficulty 字段。
5. 暴露 report、concepts、next-actions 三个 API。
6. 写测试覆盖“答题 -> 掌握度变化 -> 学习处方变化”。

做到这一步后，SparkWeave 的学习效果评估就会从“导学里的一个报告”升级为“整个系统的学习大脑”。

## 15. 实现状态

### 2026-05-04：P1/P2 最小内核已落地

已新增：

- `sparkweave/services/learning_effect.py`
- `sparkweave/api/routers/learning_effect.py`
- `/api/v1/learning-effect/health`
- `/api/v1/learning-effect/report`
- `/api/v1/learning-effect/concepts`
- `/api/v1/learning-effect/next-actions`
- `/api/v1/learning-effect/events`
- `/api/v1/learning-effect/actions/{action_id}/complete`

当前实现特点：

- 复用现有 `LearnerEvidenceService`，不引入新数据库迁移。
- 基于 `evidence.jsonl` 实时聚合全局学习效果。
- 已能从题目、导学、Notebook、资源等证据中抽取知识点信号。
- 已能生成知识点掌握度、置信度、趋势、复测时间、错因信号和下一步动作。
- 已能在无证据时推荐诊断，在薄弱知识点出现时推荐图解、练习、复测或错因闭环。

已验证：

```powershell
python -m py_compile sparkweave\services\learning_effect.py sparkweave\api\routers\learning_effect.py
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py -q
pytest tests\services\test_learner_evidence.py tests\api\test_learner_profile_router.py tests\api\test_api_main.py -q
```

下一步应继续做三件事：

1. 将 Guide V2 的 `build_learning_report()` 逐步改为读取 `LearningEffectService` 的全局报告，而不是只用 session 内部评估。
2. 给题目生成、导学练习和外部视频反馈补齐 `concept_ids`、`difficulty`、`duration_seconds`、`attempt_count` 等字段。
3. 前端画像中心和导学首页读取 `/api/v1/learning-effect/next-actions`，让“继续学习”真正由学习效果评估驱动。

### 2026-05-04：Guide V2 学习报告已接入全局评估

已新增：

- `GuideV2Manager._build_learning_effect_report()`
- `GuideV2Manager._session_learning_effect_events()`
- `GuideV2Manager._merge_learning_effect_assessment()`

当前效果：

- Guide V2 的 `build_learning_report()` 会基于当前导学 session 生成标准 learning-effect 事件。
- 报告新增 `learning_effect_report`，包含全局评估格式的 `overall`、`dimensions`、`concepts`、`open_mistakes` 和 `next_actions`。
- 原有 `effect_assessment` 保持兼容，同时新增：
  - `learning_effect_report`
  - `learning_effect_next_actions`
- `next_plan` 优先使用全局 learning-effect 下一步动作，让导学报告开始由同一个评估内核驱动。

已验证：

```powershell
python -m py_compile sparkweave\services\guide_v2.py sparkweave\services\learning_effect.py
pytest tests\services\test_guide_v2.py::test_guide_v2_builds_learning_report tests\services\test_learning_effect.py -q
pytest tests\services\test_guide_v2.py tests\api\test_guide_v2_router.py tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py -q
python -m ruff check sparkweave\services\guide_v2.py sparkweave\services\learning_effect.py sparkweave\api\routers\learning_effect.py tests\services\test_guide_v2.py tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py
```

下一步重点：

1. 把题目生成和导学练习里的每道题都稳定标注 `concept_ids`、`difficulty`、`question_type`。
2. 把精选视频、图解、Manim 动画的查看/保存/有帮助反馈写入 learning-effect 事件。
3. 前端导学页优先展示 `learning_effect_report.next_actions[0]`，让用户只看到“现在先做这一步”。

### 2026-05-04：前端画像中心已显示学习效果闭环

已新增：

- `web/src/components/profile/LearningEffectLoopCard.tsx`
- `web/src/lib/api.ts` 的 learning-effect API 封装
- `web/src/hooks/useApiQueries.ts` 的 learning-effect 查询和完成动作 mutation
- `web/src/pages/MemoryPage.tsx` 画像页闭环卡片
- `web/src/pages/GuidePage.tsx` 导学报告中的全局学习效果卡片

当前效果：

- 画像页会直接展示全局效果分、证据数、首要下一步动作和最多 3 个薄弱概念。
- 用户可以点击“去执行”进入系统推荐动作，也可以点击“完成并记录”写回学习证据。
- 导学报告会显示 `learning_effect_report`，让 session 内报告和全局学习效果使用同一个评估内核。

已验证：

```powershell
npm run build
python -m ruff check sparkweave\services\learning_effect.py sparkweave\api\routers\learning_effect.py sparkweave\services\guide_v2.py tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py tests\services\test_guide_v2.py
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py tests\services\test_guide_v2.py::test_guide_v2_builds_learning_report -q
```

下一步重点：

1. 在图解、Manim 动画、语音讲解、精选视频组件里记录“查看/保存/有帮助/没帮助”事件。
2. 让聊天页的“继续学习”优先读取 learning-effect 的 next action。
3. 为题目提交补齐概念、难度、题型和耗时字段，让掌握度更准。

### 2026-05-04：多模态资源反馈已写入 learning-effect 事件

已新增/调整：

- `ResourceEvidenceButton` 改为调用 `/api/v1/learning-effect/events`，不再只写画像证据。
- 新增 `appendLearningEffectEvent()` 前端 API 封装。
- 新增 `invalidateLearningQueries()`，统一刷新画像、证据账本、学习效果报告、概念状态和下一步动作。
- `ExternalVideoViewer` 打开公开视频后会写入 external_video 学习事件。
- `AudioNarrationViewer` 新增“有帮助，记入画像”反馈按钮，并写入 audio 学习事件。

当前效果：

- 图解、Manim 动画、语音讲解、精选视频这些多模态资源都会进入学习效果闭环。
- 资源反馈会影响后续画像、资源偏好、概念掌握评估和 next action。
- 避免了重复写两套事件：learning-effect API 底层仍复用 learner evidence 账本。

已验证：

```powershell
npm run lint
npm run build
```

下一步重点：

1. 让聊天页“继续学习”读取 learning-effect 的首个 next action。
2. 保存到 Notebook 时同步写入 resource saved 事件。
3. 给题目提交事件补齐 `concept_ids`、`difficulty`、`question_type`、`duration_seconds`。

### 2026-05-04：聊天页继续学习已由 learning-effect 驱动

已调整：

- `ChatPage` 新增 `useLearningEffectNextActions({ limit: 1 })`。
- 空状态里的“今天先做这一小步”优先展示 learning-effect 的首个 next action。
- “进入导学”优先使用 learning-effect action 的 `href`。
- “按画像继续”会从 learning-effect action 中提取 prompt；若没有 prompt，再回退到原画像逻辑。

当前效果：

- 用户在聊天首页看到的下一步，不再只来自画像摘要，而是来自学习效果评估闭环。
- 画像、导学报告、聊天入口三处的“继续学习”开始共用同一个 next action 来源。

已验证：

```powershell
npm run lint
npm run build
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py -q
```

下一步重点：

1. 保存到 Notebook 时同步写入 resource saved 事件。
2. 给题目提交事件补齐 `concept_ids`、`difficulty`、`question_type`、`duration_seconds`。
3. 在导学任务完成页展示“本次行为如何改变了画像/掌握度”。

### 2026-05-04：Notebook 保存已升级为 resource saved 事件

已调整：

- `build_notebook_record_event()` 现在将保存行为写成 `verb=saved`、`object_type=resource`。
- 原来的 Notebook 记录语义保留在 `metadata.record_object_type=notebook_record` 和 `metadata.record_type` 中。
- 保存精选视频、图解、Manim 动画、语音讲解、练习、普通笔记时，会推断出更稳定的 `resource_type`：`external_video`、`visual`、`video`、`audio`、`quiz`、`research`、`solution`、`writing`、`guide_report`、`note`。

当前效果：

- 用户点击“保存到笔记本”不再只是内容管理行为，也会成为学习效果评估的投入证据。
- learning-effect 的 `resource_count`、`saved_count`、`engagement` 和 `resource_effectiveness` 能识别用户真正沉淀过哪些资源。
- Notebook 仍然可以按原记录类型展示和追踪，不影响旧的记录管理逻辑。

已验证：

```powershell
python -m ruff check sparkweave\services\learner_evidence.py tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\services\test_learning_effect.py
pytest tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\services\test_learning_effect.py -q
```

下一步重点：

1. 给题目提交事件补齐 `concept_ids`、`difficulty`、`question_type`、`duration_seconds`。
2. 在导学任务完成页展示“本次行为如何改变画像/掌握度”。
3. 把 learning-effect 的 next action 与资源生成按钮进一步联动，让用户少选工具、直接做下一步。

### 2026-05-04：题目提交事件已补齐题型、难度、概念和耗时

已调整：

- `build_quiz_answer_events()` 会把 `duration_seconds` 写入事件顶层，并在 metadata 中保留 `duration_seconds`、`attempt_count`、`question_type`、`difficulty`、`concepts`。
- `/api/v1/sessions/{session_id}/quiz-results` 支持 `concepts`、`knowledge_points`、`duration_seconds`、`attempt_count`。
- `/api/v1/guide/v2/.../quiz-results` 支持 `duration_seconds`、`attempt_count`。
- `/api/v1/question-notebook/entries/upsert` 支持同样的补充字段。
- 聊天里的交互题组件会按每题提交记录耗时和尝试次数。
- 导学里的交互题组件会按每题开始作答和提交时间估算耗时。

当前效果：

- 学习效果评估可以区分“同一知识点不同题型”的表现。
- 后续可以把“耗时长但答对”“反复尝试才答对”“简单题答错”等信号用于更细的处方策略。
- 题目证据不再只是对错，而是更接近一条完整学习行为事件。

已验证：

```powershell
python -m ruff check sparkweave\services\learner_evidence.py sparkweave\api\routers\sessions.py sparkweave\api\routers\guide_v2.py sparkweave\api\routers\question_notebook.py tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\services\test_learning_effect.py
pytest tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\services\test_learning_effect.py tests\api\test_notebook_router.py -q
npm run lint
npm run build
```

下一步重点：

1. 在导学任务完成页展示“本次行为如何改变画像/掌握度”。
2. 把 learning-effect 的 next action 与资源生成按钮进一步联动，让用户少选工具、直接做下一步。
3. 继续强化错因闭环：答错后生成一个最小补救任务，完成后回写同一个概念。

### 2026-05-04：导学提交页已显示画像影响摘要

已调整：

- `GuidePage` 新增 `LearningImpactSummary`。
- 任务提交后会展示“这次提交改变了什么”，拆成三块：
  - 证据：本次学习证据质量和是否已写入画像；
  - 概念：涉及哪些知识点、掌握度如何变化；
  - 路线：系统接下来如何调整下一步。
- 同一摘要也嵌入学习反馈卡，避免用户只看到“下一步建议”，却不知道建议来自哪里。

当前效果：

- 导学反馈更面向用户：用户提交后能立即理解系统为什么改变路线。
- 画像闭环更可解释：从“做了题/写了反思”到“画像与掌握度更新”之间有可见桥梁。
- 对比赛演示更友好：可以直接展示“行为 -> 证据 -> 画像 -> 下一步”的闭环。

已验证：

```powershell
npm run lint
npm run build
```

下一步重点：

1. 把 learning-effect 的 next action 与资源生成按钮进一步联动，让用户少选工具、直接做下一步。
2. 继续强化错因闭环：答错后生成一个最小补救任务，完成后回写同一个概念。
3. 给学习效果评估报告增加更清晰的演示用 API/CLI 输出。
### 2026-05-04：导学反馈已生成最小补救任务

已调整：

- `GuideV2Manager._learning_feedback()` 现在会在低分、薄弱概念或错因存在时返回 `remediation_task`。
- `remediation_task` 包含标题、原因、概念、目标任务、建议资源类型、预计时间和 3 个极简步骤。
- 前端导学反馈卡新增“10 分钟补救”块，用户可以直接点击“开始补救”，生成绑定到补救任务节点的图解或练习。

当前效果：

- 答错后不再只是提示“建议补弱”，而是明确告诉用户“先补哪一个小块、做哪三步、点哪里开始”。
- 补救动作绑定到导学插入的 remediation task，后续提交可以回写同一个任务与概念，形成更清楚的错因闭环。
- 页面保持懒人式：只在需要补救时显示，不额外平铺一堆工具。

已验证：

```powershell
python -m ruff check sparkweave\services\learning_effect.py sparkweave\services\guide_v2.py tests\services\test_learning_effect.py tests\services\test_guide_v2.py
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\api\test_notebook_router.py tests\services\test_guide_v2.py::test_guide_v2_quiz_attempt_updates_learning_evidence tests\api\test_guide_v2_router.py -q
npm run lint
npm run build
```

下一步重点：

1. 给学习效果报告增加演示友好的 CLI/API 摘要，方便比赛 PPT 和视频讲解。
2. 把 `remediation_task` 的完成状态接入画像页，让“待补救/已补救/待复测”更直观。
3. 继续减少前端解释性文字，把闭环状态做成一句话和一个主按钮。

### 2026-05-04：next action 已升级为可执行动作蓝图

已调整：

- `LearningEffectService` 返回的每个 `next_actions` 现在不只包含 `title`、`reason`、`href`，还包含：
  - `capability`：建议调用的能力，例如 `deep_question`、`visualize`、`chat`；
  - `prompt`：可直接发送给能力集群的用户任务；
  - `config`：题量、题型、诊断/复测/错因复盘等执行参数。
- `/chat?new=1&capability=...&prompt=...` 现在会自动按 URL 中的能力与 prompt 启动一次任务。
- 聊天首页的“按画像继续”会优先使用 learning-effect action 的 `capability`、`prompt` 和 `config`，不再只是把建议文字塞进普通聊天。
- learning-effect 的链接参数改为标准 URL 编码，中文 prompt 不再依赖浏览器容错。

当前效果：

- 学习效果评估从“给建议”推进到“给可执行处方”：用户点击一次即可进入图解、练习、诊断或错因复盘。
- 画像、导学、聊天入口共用同一个 next action 来源，闭环链路更清楚：证据 -> 评估 -> 处方 -> 执行 -> 新证据。
- 后续可以继续把 `config.purpose` 用于更细的前端展示，例如“诊断题”“复测题”“错因复盘题”单独呈现。

已验证：

```powershell
python -m ruff check sparkweave\services\learning_effect.py tests\services\test_learning_effect.py
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py tests\api\test_notebook_router.py -q
npm run lint
npm run build
```

下一步重点：

1. 继续强化错因闭环：答错后自动生成“最小补救任务”，完成后回写同一个概念。
2. 给学习效果报告增加更清晰的演示用 API/CLI 输出。
3. 在前端把不同 `purpose` 的练习反馈做成更直观的用户语言，而不是只显示通用练习。
### 2026-05-04：错因闭环新增可解释详情

- `LearningEffectService._remediation_loop()` 现在会为每个补救任务返回 `reason`、`evidence_summary`、`next_step`、`progress_label`。
- 画像页的学习效果卡新增 `learning-effect-remediation-explanation` 详情块，用户能看到为什么被判定为待补救、待复测或已闭环。
- 赛前检查同步增加对解释层的检测，确保比赛包能证明“学习效果评估”不是静态分数，而是可解释、可执行、可闭环的学习调整机制。

### 2026-05-04：错因闭环新增一键动作

- 每个 `remediation_loop.items[]` 新增 `action_label`、`action_href`、`action_capability`、`action_prompt`、`action_config`。
- 待补救状态会直接进入补救图解或补救练习；待复测状态会直接生成 3 题复测；已闭环状态会安排一次 5 分钟间隔复习。
- 画像页的解释块新增 `learning-effect-remediation-action` 按钮，让用户不需要自己找入口。

### 2026-05-04：画像页新增三步闭环状态条

- 画像页错因解释块新增 `learning-effect-remediation-stepper`，用“补救 -> 复测 -> 闭环”三步展示当前位置。
- 这是一层轻量视觉提示，不增加新的表单或抽屉，目标是让用户一眼知道现在该先补、该测，还是已经进入复习。

### 2026-05-04：画像页新增学习效果可视化

- 学习效果卡新增 `LearningEffectVisualMap` 和 `learning-effect-visual-map`。
- 可视化主线为“证据流 -> 效果评估 -> 动态调度 -> 闭环进度”，同时展示关键评估维度的进度条。
- 目标是给用户和评委一个一眼能讲清楚的闭环图，而不是只看分数和文字诊断。

### 2026-05-04：学习效果报告新增可视化快照

- `LearningEffectService.build_report()` 新增 `visualization` 字段，由后端直接输出闭环节点、节点连线、维度条、最近证据时间线和薄弱点摘要。
- 前端 `LearningEffectVisualMap` 优先消费这份后端快照，而不是只在浏览器里临时拼装展示数据。
- 画像页新增 `learning-effect-evidence-timeline`，用 3 条最近证据解释“为什么系统会给出这个评估”，同时保持页面简洁。
- 这一步让学习效果评估更适合答辩演示：评委可以看到“证据 -> 评估 -> 调度 -> 闭环”的结构化数据，而不是单纯 UI 装饰。

### 2026-05-04：学习效果地图升级为三段式用户视图

- 画像页将原来的统计卡升级为“学习效果地图”：左侧看最近证据，中间看画像评估，右侧看下一步处方和闭环进度。
- 新增 `learning-effect-prescription-panel` 和 `learning-effect-map-primary-action`，用户可以从地图直接进入补救、复测或复习动作。
- 保留简约原则：地图只显示当前判断必需的信息，完整解释仍放在错因闭环详情里，避免把画像页再次做成调试面板。

### 2026-05-04：导学反馈新增学习闭环回执

- 导学任务或练习提交后，反馈卡新增 `GuideLearningLoopReceipt` 和 `guide-learning-loop-receipt`。
- 回执只讲三件事：证据已经写回、画像判断已经更新、下一步处方已经生成。
- 用户可以直接从回执进入画像页，或按 `guide-learning-loop-receipt-action` 继续执行学习处方，避免提交后不知道下一步去哪。

### 2026-05-04：学习效果报告新增用户回执

- `LearningEffectService` 在全局报告中新增 `learner_receipt`，把算法字段整理成用户能直接理解的一段闭环说明。
- `learner_receipt` 统一输出当前状态、证据摘要、画像更新、下一步动作、推荐原因和写回目标，避免前端各处重复拼装解释。
- 画像页新增 `LearningEffectLearnerReceipt` 和 `learning-effect-learner-receipt`，默认先展示“现在先做什么”和“为什么”，再把学习效果地图作为透明解释放在后面。

### 2026-05-04：学习效果动作可直接接入导学

- 导学页新增 `buildGuideEffectActionSeed`，识别 `/guide?new=1&effect_action=...` 形式的学习效果动作。
- `practice:概念`、`retest:概念`、`mistake_review`、`diagnostic`、`advance` 会自动转成导学目标、时间预算、薄弱点和 `source_action`。
- 这样画像页或学习效果报告给出的下一步不再只是跳转，而是进入导学时已经填好“现在先做什么”。

### 2026-05-04：学习效果评估新增演示摘要

- `LearningEffectService.demo_summary()` 会把完整报告压缩成一页“证据链、画像更新、下一步处方、错因闭环、赛题要求对齐、答辩讲法”。
- API 新增 `GET /api/v1/learning-effect/demo-summary`，方便前端、PPT 生成脚本或外部演示工具复用同一份摘要。
- CLI 新增 `sparkweave learning-effect summary`，可直接输出 Markdown 或 JSON，并支持 `--output dist/learning-effect-summary.md` 形成赛前材料。
- 这一步的目标是避免第五项只停留在页面展示：即使不打开前端，也能用命令行证明系统如何根据证据评估学习效果并调整下一步。
