# 学习画像 P4 对话信号接入

P4 的目标是让画像真正具备“对话式自主构建”的味道：学生在聊天里自然说出的学习目标、卡点和资源偏好，会被系统转成低置信度证据，进入统一画像账本。

## 已完成能力

1. 新增聊天证据构造器：

```python
build_chat_statement_events(
    message,
    session_id="chat_xxx",
    turn_id="turn_xxx",
    capability="chat",
    language="zh",
)
```

2. 当前识别三类信号：

| 信号 | 事件 object_type | 示例 |
| --- | --- | --- |
| 学习目标 | `learning_goal` | “我想掌握梯度下降” |
| 学习卡点 | `learning_blocker` | “我不理解公式含义” |
| 资源偏好 | `learning_preference` | “我更喜欢图解和短视频” |

3. LangGraph turn runtime 在持久化用户消息时，会把聊天信号写入 evidence service。

4. 画像聚合器已读取这些事件：

- `learning_goal` -> `stable_profile.goals`
- `learning_blocker` -> `learning_state.weak_points`
- `learning_preference` -> `stable_profile.preferences`

## 权重策略

聊天信号默认置信度较低：

- 目标：`confidence=0.42`
- 卡点：`confidence=0.50`
- 偏好：`confidence=0.46`

原因是聊天中的表达可能只是临时语境，不能直接压倒题目正确率、导学任务结果和用户手动校准。后续如果学生确认画像，P3 校准事件会以更高优先级覆盖它。

## 运行链路

```text
用户发送聊天消息
  -> LangGraphTurnRuntimeManager
  -> build_turn_context 持久化 user message
  -> build_chat_statement_events 抽取目标/卡点/偏好
  -> evidence.jsonl
  -> LearnerProfileService 聚合画像
  -> /memory 画像页展示
```

## 设计边界

- 当前是启发式识别，不调用大模型，保证稳定、快速、可测试。
- 只抽取学习相关信号，不推断人格、情绪病理或敏感属性。
- 只在消息持久化时写入；`_persist_user_message=false` 的内部转发不会写入画像。
- 通过依赖注入支持测试，避免单测写入真实 `data/user/learner_profile/evidence.jsonl`。

## 验证记录

```powershell
python -m py_compile sparkweave\services\learner_evidence.py sparkweave\services\learner_profile.py sparkweave\runtime\context_enrichment.py sparkweave\runtime\turn_runtime.py sparkweave\runtime\routing.py sparkweave\services\session.py
pytest tests\services\test_learner_evidence.py tests\services\test_learner_profile.py tests\api\test_unified_ws_turn_runtime.py -q
cd web
npm run build
```

已通过。

## 下一步

1. 将 Guide V2 的路径规划读取统一画像，而不是只读 Guide 自己的 learner memory。
2. 在导学任务生成前，将已确认的画像弱点和资源偏好注入规划上下文。
3. 前端画像页增加“这条画像来自哪几次聊天”的用户友好解释。
