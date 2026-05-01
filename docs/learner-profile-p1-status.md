# 学习画像 P1 开发状态

本文记录 P1 实际落地内容，和 `learner-profile-p1-implementation.md` 的设计方案保持同步。

## 已完成

1. 后端新增只读聚合服务 `sparkweave/services/learner_profile.py`。
2. 后端新增画像 API `sparkweave/api/routers/learner_profile.py`，并挂载到 `/api/v1/learner-profile`。
3. 画像聚合已接入现有证据源：
   - Memory：`SUMMARY.md`、`PROFILE.md`
   - Guide V2：`learner_memory.json` 与最近导学会话
   - Question Notebook：题目正确率、题型/分类薄弱点
   - Notebook：最近学习笔记记录
4. 前端 `/memory` 已改造为学习画像中心，包含三个分页：
   - 画像：当前重点、可信度、题目正确率、薄弱点、掌握状态、下一步建议
   - 证据：展示画像判断的来源，不向用户暴露原始 JSON
   - 高级记忆：保留 SUMMARY/PROFILE 手工编辑能力
5. 已补充测试：
   - `tests/services/test_learner_profile.py`
   - `tests/api/test_learner_profile_router.py`

## 当前 API

```text
GET  /api/v1/learner-profile
POST /api/v1/learner-profile/refresh
GET  /api/v1/learner-profile/evidence-preview
```

P1 返回的是画像快照本身，不再包一层 `success/profile`。前端直接消费：

```ts
LearnerProfileSnapshot
```

## 验证记录

```text
pytest tests/services/test_learner_profile.py tests/api/test_learner_profile_router.py -q
npm run build
```

两项均已通过。

## 下一步

1. P2 证据账本底座和首批真实写入链路已接入，详见 [学习画像 P2 证据账本](./learner-profile-p2-evidence-ledger.md)。
2. 下一步把资源生成、Chat 显式目标/卡点、用户校准行为继续接到 `evidence.jsonl`。
3. 增加用户可校准画像：用户可以确认、驳回或修改系统判断，并形成审计记录。
4. 让导学任务生成真正读取统一画像，而不是只读取 Guide V2 自己的 learner memory。
5. 把学习效果评估从“展示正确率”升级为“趋势、稳定性、迁移能力和干预效果”。
