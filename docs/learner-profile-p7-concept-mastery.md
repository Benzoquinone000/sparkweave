# 学习画像 P7 知识点掌握度沉淀

P7 的目标是让画像从“记录用户做过什么题”升级为“知道用户在哪些知识点上正在掌握、发展或需要补基”。这一步直接服务导学、交互式练习、学习效果评估和资源推荐。

## 设计动机

仅按题目标题统计会带来三个问题：

- 同一个知识点的多道题会散落成多条 mastery，无法形成稳定判断。
- 错题只能显示“这道题错了”，不能说明“卡在学习率、梯度方向、链式法则”等具体概念。
- 导学报告无法把短期任务结果与长期学习画像合并。

因此题目事件必须携带结构化概念字段，画像聚合也必须优先按概念合并。

## 事件字段

`build_quiz_answer_events()` 现在会从题目 payload 中提取以下字段：

- `concepts`
- `concept`
- `tested_concepts`
- `knowledge_points`
- `learning_points`
- `categories`
- `tags`

提取后写入事件 metadata：

```json
{
  "question_id": "q1",
  "concepts": ["gradient descent", "learning rate"],
  "primary_concept": "gradient descent",
  "concept_id": "gradient_descent"
}
```

如果题目答错，会额外写入 `mistake_types: ["concept:gradient descent"]`，用于兼容旧的错误类型链路，但画像聚合会优先把它还原为知识点，而不是把 `concept:...` 当作普通错误标签展示。

## 聚合规则

统一画像读取 evidence ledger 时：

- 优先读取 `metadata.concepts`、`primary_concept`、`knowledge_points` 等概念字段。
- 有概念字段时，mastery 按概念合并；没有概念字段时，继续按旧逻辑回退到 `object_id`。
- 低分或错误记录优先沉淀为对应知识点 weak point。
- 高分记录优先沉淀为对应知识点 strength。
- evidence preview 保留 `metadata.concepts`，前端可用于解释“为什么系统认为你卡在这里”。

题目本聚合也会优先读取题目中的概念、知识点、分类和标签，再回退到题型/难度。

## 当前落地

- `sparkweave/services/learner_evidence.py`
  - 题目事件生成时提取概念标签。
  - `object_id` 优先使用主知识点 id。
  - metadata 保留题目 id 和概念列表。
- `sparkweave/services/learner_profile.py`
  - evidence ledger 按概念合并 mastery。
  - 错误/低分记录按概念生成 weak point。
  - 题目本 evidence preview 携带概念列表。
- `sparkweave/services/guide_v2.py`
  - 导学练习提交会保留每题的概念字段。
  - quiz evidence metadata 会记录本次练习覆盖的概念列表。
  - 练习提交后生成 `concept_feedback`，按知识点给出正确率、状态、错题和下一步动作。
  - `learning_feedback.resource_actions` 会根据最弱知识点自动生成图解、低门槛复测或迁移挑战入口。
  - deep_question 调用会明确要求生成题带 `concepts` 和 `knowledge_points`。
- `web/src/pages/GuidePage.tsx`
  - 交互式练习提交时会从生成题中提取概念字段并随答案一起提交。
  - 即时反馈卡片会显示知识点级反馈，让用户知道先补哪一个概念。
  - 即时反馈卡片会展示“直接行动”按钮，用户可一键生成针对当前卡点的资源。
  - 页面刷新或切换回来后，会从 session evidence 中恢复与当前任务相关的最近反馈。
- `tests/services/test_learner_evidence.py`
  - 覆盖题目事件的概念字段。
- `tests/services/test_learner_profile.py`
  - 覆盖多道题合并到同一知识点 mastery。
- `tests/services/test_guide_v2.py`
  - 覆盖导学练习提交后的 concept metadata 和 mistake_types。

## 后续约束

后续开发交互式练习、导学提交页、题目生成、资源推荐时，所有题目 payload 都应尽量提供 `concepts` 或 `knowledge_points`。如果 LLM 生成题目时无法给出概念字段，前端/后端也应至少把当前导学任务标题或课程节点标题作为概念回填。
