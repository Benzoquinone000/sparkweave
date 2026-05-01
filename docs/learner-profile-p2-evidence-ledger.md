# 学习画像 P2 证据账本

P2 的目标是把画像从“临时聚合结论”推进到“证据优先”。系统不再只展示画像结果，而是为每一次学习活动沉淀统一事件，后续导学、推荐和效果评估都可以回看这些事件。

## 已完成的底座

1. 新增服务：`sparkweave/services/learner_evidence.py`
2. 默认存储：`data/user/learner_profile/evidence.jsonl`
3. 新增 API：

```text
GET  /api/v1/learner-profile/evidence
POST /api/v1/learner-profile/evidence
POST /api/v1/learner-profile/evidence/batch
POST /api/v1/learner-profile/evidence/rebuild
```

4. 画像聚合服务已读取正式证据账本：
   - 低分/错误事件会进入薄弱点
   - 有分数事件会进入掌握度
   - 资源类型事件会进入偏好
   - 事件本身会进入画像证据预览
5. 已接入真实写入链路：
   - Guide V2：任务完成、练习提交、资源/报告/课程包保存
   - Sessions：聊天中的题目结果提交
   - Question Notebook：单题 upsert
   - Notebook：普通笔记保存与流式摘要保存

## 事件格式

```json
{
  "id": "ev_...",
  "source": "question_notebook",
  "source_id": "question.12",
  "actor": "learner",
  "verb": "answered",
  "object_type": "quiz",
  "object_id": "gradient_descent",
  "title": "学习率过大可能发生什么？",
  "summary": "回答错误；解析：学习率过大会越过最优点。",
  "course_id": "ml_foundations",
  "node_id": "gradient_descent",
  "task_id": "task_...",
  "resource_type": "quiz",
  "score": 0.0,
  "is_correct": false,
  "duration_seconds": 90,
  "confidence": 0.8,
  "reflection": "学习率和震荡关系还不清楚。",
  "mistake_types": ["学习率判断错误"],
  "created_at": 1777000000.0,
  "weight": 1.0,
  "metadata": {}
}
```

## 设计原则

- 只追加，不原地改写，保证可追溯。
- 不记录敏感人格推断，只记录学习行为和学习结果。
- 每条事件要有 `source`、`verb`、`object_type`，方便跨模块统计。
- 事件可以从真实行为实时写入，也可以通过 `/evidence/rebuild` 从当前画像证据预览补种。

## 下一步接入点

1. Resource artifacts：资源生成成功时写入 `generated resource`，并记录图解/视频/练习偏好。
2. Chat：用户主动暴露目标、卡点、偏好时写入低置信度 `stated` 事件。
3. 用户校准：画像确认、驳回、修改时写入 `corrected_profile`。当前已落地，详见 [学习画像 P3 用户校准](./learner-profile-p3-calibration.md)。
4. 前端：画像证据页增加“证据账本”分页，面向开发验收和调试。
5. 评估：基于证据账本计算趋势、稳定性、迁移能力和干预效果。

## 验证记录

```text
pytest tests/api/test_learner_evidence_integration.py tests/services/test_learner_evidence.py tests/services/test_learner_profile.py tests/api/test_learner_profile_router.py -q
```

已通过。
