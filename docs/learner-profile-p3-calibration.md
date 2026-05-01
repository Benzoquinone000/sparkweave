# 学习画像 P3 用户校准

P3 的目标是让学习画像从“系统生成的结论”升级为“学生可协商、可纠偏、可审计的开放画像”。这一步对应赛题里的“对话式学习画像自主构建”：系统不仅自动归纳学生状态，也允许学生确认、驳回或修正画像判断，并把这些操作写回证据账本。

## 已完成能力

1. 后端新增校准事件构造器：

```python
build_profile_calibration_event(
    action="confirm | reject | correct",
    claim_type="weak_point | mastery | preference | goal | strength",
    value="原画像判断",
    corrected_value="修正后的判断",
    note="用户说明",
)
```

2. 后端新增接口：

```text
POST /api/v1/learner-profile/calibrations
```

请求示例：

```json
{
  "action": "correct",
  "claim_type": "weak_point",
  "value": "概念边界不清",
  "corrected_value": "梯度方向和下降方向混淆",
  "note": "我不是完全不懂概念，而是方向关系不稳",
  "source_id": "evidence.guide"
}
```

返回内容包含写入的 `event` 和刷新后的 `profile`。

3. 画像聚合器已应用校准结果：

- `confirm`：把用户确认的画像判断以高置信度写入对应画像桶。
- `reject`：把被驳回的画像判断加入过滤表，后续画像快照不再展示该判断。
- `correct`：先驳回原判断，再加入修正后的判断。

4. 前端 `/memory` 画像页已加入轻量校准入口：

- 弱点卡片：确认、修改、不准。
- 掌握度卡片：确认、修改、不准。
- 修改时使用轻量输入，不要求学生填写复杂表单。

## 事件设计

校准事件统一写入 `data/user/learner_profile/evidence.jsonl`，事件核心字段如下：

```json
{
  "source": "profile_calibration",
  "actor": "learner",
  "verb": "corrected_profile",
  "object_type": "profile_claim",
  "title": "梯度方向和下降方向混淆",
  "confidence": 1.0,
  "metadata": {
    "action": "correct",
    "claim_type": "weak_point",
    "value": "概念边界不清",
    "corrected_value": "梯度方向和下降方向混淆"
  }
}
```

## 设计原则

- 尊重学生自我判断：用户校准优先级高于普通行为证据。
- 保持可审计：校准不是直接覆盖画像文件，而是以事件方式追加。
- 降低操作负担：前端只提供少量动作，不做复杂画像编辑后台。
- 不推断敏感人格：校准对象限定在学习目标、偏好、掌握度、弱点、优势等学习相关字段。

## 验证记录

```powershell
python -m py_compile sparkweave\services\learner_evidence.py sparkweave\services\learner_profile.py sparkweave\api\routers\learner_profile.py
pytest tests\services\test_learner_evidence.py tests\services\test_learner_profile.py tests\api\test_learner_profile_router.py -q
cd web
npm run build
```

已通过。

## 下一步

1. Chat 中显式表达的“目标、卡点、偏好”已自动写入画像证据账本，详见 [学习画像 P4 对话信号接入](./learner-profile-p4-chat-signals.md)。
2. 让 Guide V2 读取统一画像，而不是只读取自己的 learner memory。
3. 做画像驱动推荐：根据被确认/修正的弱点，动态改变下一步任务和资源类型。
4. 增加校准历史页：学生能看到自己何时修改过画像，以及这些修改如何影响后续导学。
