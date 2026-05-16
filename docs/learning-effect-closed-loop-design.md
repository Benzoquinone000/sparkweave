# 学习效果评估闭环设计

> 本文记录 SparkWeave 当前“学习效果评估”模块的设计与代码事实。它不是开发日志，而是用于维护、答辩和简历说明的稳定设计文档。

## 设计目标

学习效果评估不做成一张复杂报表，也不只输出一个分数。它要回答用户最关心的三件事：

1. 现在先做什么；
2. 为什么系统这样判断；
3. 做完以后画像、掌握度和下一步路线会怎样变化。

系统内部的闭环是：

```text
学习行为发生
  -> 写入统一学习证据账本
  -> 更新知识点掌握度、错因、资源使用和投入度
  -> 生成可解释评估
  -> 给出下一步学习动作
  -> 用户完成动作后再次回写证据
```

## 产品原则

- **面向用户**：页面默认只给一个主建议和少量解释，不把底层日志平铺给用户。
- **证据优先**：没有证据时只做轻量诊断，不把低置信度推断说成确定结论。
- **动作闭环**：评估结果必须能落到导学、练习、图解、视频、复测或复习动作。
- **一套画像**：学习效果评估复用学习证据账本和画像体系，不另建一套孤立画像。
- **可解释但不啰嗦**：默认解释“证据、规则、下一步理由”，完整事件仍留在后端。

## 行业启发

当前设计吸收了几类成熟教育产品思路：

- Khan Academy Mastery：掌握度应分层展示，不能只给 0-100 分。
- ALEKS：先诊断，再把知识状态转成可学习路线。
- Duolingo Birdbrain：资源和练习难度要贴近学习者当前边界。
- Coursera LevelSets：评估要有 baseline，才能解释进步。
- Moodle Learning Analytics：模型应包含 indicators、targets、insights、actions。
- Caliper/xAPI：跨模块行为必须事件化，才能形成可信长期画像。

SparkWeave 的落地取向更偏“用户下一步处方”：把指标压缩成一句话、一个主按钮和少量证据。

## 当前代码事实

| 层级 | 代码位置 | 作用 |
| --- | --- | --- |
| 服务内核 | `sparkweave/services/learning_effect.py` | `LearningEffectService` 负责事件写入、报告生成、掌握度聚合、错因闭环、下一步动作和演示摘要 |
| API | `sparkweave/api/routers/learning_effect.py` | 暴露 health、report、concepts、next-actions、events、actions complete、demo-summary |
| 证据账本 | `sparkweave/services/learner_evidence.py` | 统一保存 quiz、resource、guide_task 等学习证据 |
| 导学接入 | `sparkweave/services/guide_v2.py` | 导学 session 内生成 learning-effect 事件，并把报告/下一步动作注入导学结果 |
| 会话答题回写 | `sparkweave/api/routers/sessions.py` | `/quiz-results` 将答题结果写回证据 |
| 题库回写 | `sparkweave/api/routers/question_notebook.py` | 题目提交写入 quiz 证据 |
| 前端画像卡 | `web/src/components/profile/LearningEffectLoopCard.tsx` | 展示学习处方、解释卡、视觉地图、错因闭环和一键动作 |
| 前端 API | `web/src/lib/api.ts`、`web/src/hooks/useApiQueries.ts` | 封装 learning-effect 查询、事件写入和动作完成 mutation |
| 聊天接入 | `web/src/pages/ChatPage.tsx` | 空状态与“继续学习”优先读取 learning-effect 的下一步动作 |
| 导学接入 | `web/src/pages/GuidePage.tsx` | 展示导学 session 的 learning-effect 报告、学习回执和动作 |

## 数据流

### 1. 事件写入

学习行为会被规范化为证据事件。典型来源包括：

- 导学任务完成；
- 交互练习提交；
- 题库答题；
- Notebook 保存；
- 图解、短视频、外部视频等资源反馈；
- 用户校准画像或反思。

关键字段包括：

```json
{
  "source": "learning_effect",
  "type": "quiz",
  "verb": "answered",
  "object_type": "quiz",
  "course_id": "ml_foundations",
  "concepts": ["gradient_descent"],
  "score": 0.75,
  "duration_seconds": 180,
  "metadata": {
    "question_type": "choice",
    "difficulty": "medium",
    "mistake_types": ["concept_boundary"]
  }
}
```

### 2. 报告生成

`LearningEffectService.build_report()` 会汇总证据并输出：

- `overall`：总体状态、分数、趋势和证据数量；
- `dimensions`：掌握度、投入度、资源有效性、错因闭环等维度；
- `concepts`：知识点掌握度、状态和证据；
- `open_mistakes`：仍需处理的错因；
- `next_actions`：可直接执行的下一步动作；
- `remediation_loop`：待补救、待复测、已闭环状态；
- `visualization`：前端可直接消费的闭环节点、维度条和证据时间线；
- `learner_receipt`：面向用户的一段评估回执；
- `study_brief`：今天只做一步的学习安排；
- `explainability`：证据、规则和推荐理由。

### 3. 下一步动作

`next_actions` 不只是文字建议，还包含可执行信息：

- `href`：跳转到导学或聊天；
- `capability`：要触发的能力，例如 `deep_question`、`visualize`；
- `prompt`：动作启动时给模型的提示；
- `config`：动作目的、题型、难度、概念等参数；
- `writes_back`：完成后会写回哪些画像/掌握度字段。

这让“学习效果评估”不止停留在展示，而是能驱动系统继续生成资源、安排复测或调整路径。

## API

基础前缀：

```text
/api/v1/learning-effect
```

主要接口：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/health` | 检查评估服务状态 |
| `GET` | `/report?course_id=&window=14d` | 获取完整学习效果报告 |
| `GET` | `/concepts?course_id=&window=14d&limit=20` | 获取知识点掌握度列表 |
| `GET` | `/next-actions?course_id=&window=14d&limit=3` | 获取下一步动作 |
| `POST` | `/events` | 写入一条学习效果事件 |
| `POST` | `/actions/{action_id}/complete` | 标记动作完成并刷新报告 |
| `GET` | `/demo-summary` | 输出适合 PPT、视频和答辩的一页摘要 |

## 前端呈现

画像页的学习效果模块遵循“先行动，后解释”的顺序：

1. 用户回执：一句话说明当前状态；
2. 今日学习安排：只给一个时间盒和一个主按钮；
3. 为什么这样判断：展示少量证据和规则；
4. 学习效果地图：用节点和维度条解释闭环；
5. 错因闭环：展示补救、复测、已闭环的当前位置；
6. 最近证据：最多展示几条关键证据，避免页面变成日志。

导学页和聊天页只消费最重要的下一步动作，避免让用户在一堆工具里自己选择。

## 错因闭环

错因闭环是当前模块最能体现“评估推动学习”的部分：

```text
答错或低分
  -> 生成最小补救任务
  -> 用户完成补救图解/练习/短视频
  -> 安排复测
  -> 复测通过后标记已闭环
```

`remediation_loop` 会为每个任务提供：

- 当前状态；
- 触发原因；
- 使用的证据；
- 下一步动作；
- 前端按钮需要的 `href`、`capability`、`prompt`、`config`。

## 与画像和导学的关系

学习效果评估与画像不是两套系统：

- 画像负责长期记忆、偏好、薄弱点和证据摘要；
- 学习效果评估负责把最近证据转成掌握度、闭环状态和下一步动作；
- 导学负责执行这些动作，并把完成结果继续写回证据账本。

因此，用户在导学里做题、看图解、保存笔记，都会逐步改变画像和下一步建议。

## 验收方式

后端：

```powershell
pytest tests\services\test_learning_effect.py tests\api\test_learning_effect_router.py -q
pytest tests\services\test_learner_evidence.py tests\api\test_learner_evidence_integration.py -q
```

前端：

```powershell
cd web
npm run check:design
npm run build
```

黑盒路径：

1. 在导学页生成一组练习；
2. 提交答案，制造一个薄弱概念；
3. 回到学习画像页，查看学习效果卡；
4. 确认画像页已显示错因闭环状态：待补救、待复测、已闭环；
5. 点击补救/复测动作；
6. 完成后确认状态从待补救进入待复测或已闭环；
7. 再查看聊天首页“继续学习”是否读取新的 next action。

## 维护原则

- 新增学习行为时，优先写入 learner evidence，再让 learning-effect 聚合。
- 新增报告字段时，同步更新 `web/src/lib/types.ts` 和 `LearningEffectLoopCard`。
- 新增动作类型时，必须明确完成后写回什么证据。
- 新增前端展示时，默认只展示用户需要的一步，不扩大成仪表盘。
- 文档只记录当前代码事实；阶段性开发日志不要继续堆在本文。
