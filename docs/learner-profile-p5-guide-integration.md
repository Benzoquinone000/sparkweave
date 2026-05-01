# 学习画像 P5：Guide V2 导学接入统一画像

## 目标

P1-P4 已经让 SparkWeave 拥有统一画像、证据账本、用户校准和聊天信号采集。P5 的目标是让导学不再只依赖 Guide V2 自己的局部 `learner_memory.json`，而是在创建新导学路线时读取统一学习画像，真正做到“画像驱动导学”。

## 当前实现

- `GuideV2Manager` 新增可选依赖 `learner_profile_service`。
- 创建导学会话时，如果 `use_memory=true`，会读取 `learner_profile_service.read_profile(auto_refresh=True)`。
- 统一画像中的以下信息会被合入本次导学画像：
  - `overview.suggested_level`：补全学习水平。
  - `overview.preferred_time_budget_minutes`：补全单次学习时间。
  - `stable_profile.preferences`：补全资源偏好，例如图解、视频、练习。
  - `learning_state.weak_points`：补全薄弱点。
  - `overview.current_focus`、`stable_profile.goals`、`confidence`：写入 `source_context_summary`，便于解释导学为什么这样规划。
- 用户在创建导学时显式填写的 `level`、`time_budget_minutes` 会优先保留，统一画像只做补全，不强行覆盖。
- API 默认的 `GuideV2Manager` 已接入 `get_learner_profile_service()`，测试或离线调用仍可不传该服务。

## 资源生成个性化

Guide V2 生成图解、短视频、练习和资料时，已经把本次导学画像继续传给资源智能体：

- `UnifiedContext.metadata.learner_profile_hints` 会携带水平、时间预算、资源偏好、薄弱点、常见错因、当前节点掌握状态。
- 资源 prompt 中会加入 `Learner personalization` 段，要求智能体优先回应薄弱点和错因。
- 图解会优先解释概念关系、公式含义和最小例子。
- 短视频会要求脚本分步、公式 LaTeX 友好、避免公式块过大。
- 练习会要求混合题型，包含选择、判断、填空、简答，以及答案、解析、难度和考察点。
- 生成产物会保存 `artifact.personalization`，便于后续调试和前端解释“这个资源为什么这样生成”。

## 前端联动现状

这一阶段前端已经不再只是“把画像参数带到导学页”，而是开始形成真实的画像驱动导学体验：

- 从画像页点击“进入导学”时，会把 `action_title`、`source_label`、`estimated_minutes`、`prompt` 等信息通过 URL 参数传到 `/guide`。
- 导学页创建路线前会自动带入：
  - 时间预算：来自画像的 `estimated_minutes`
  - 当前目标：来自画像的 `suggested_prompt`
  - 薄弱点：当画像动作属于 `weak_point` 时，会自动写入导学表单
- `SourceActionNotice` 已升级为用户可理解的“画像接力卡”，明确告诉用户：
  - 这条建议来自学习画像
  - 系统已经自动带入哪些信息
  - 接下来导学会如何围绕这条建议展开

## 自适应导学策略

导学页主学习区已经开始按统一画像动态调整资源入口，而不是固定展示三颗等权按钮：

- 新增“当前导学策略”卡片。
- 策略卡不只显示“推荐看图解 / 做练习 / 看短视频”，还会额外展示：
  - 当前判断用到的画像信号（如薄弱点、掌握度、近期正确率、画像可信度、学习偏好）
  - “为什么现在先这样安排”的解释块，把推荐动作和具体薄弱点/掌握状态绑定起来
- 系统会综合以下信号判断更适合的资源类型：
  - 统一画像可信度
  - 最近题目正确率
  - 知识点掌握度均值
  - 当前薄弱点数量
  - 用户资源偏好（图解 / 练习 / 视频）
  - 最近一次导学反馈得分
- 三类资源按钮（图解 / 练习 / 短视频）会根据当前策略自动高亮推荐项。

当前启发式策略大致分为：

- 反馈分数偏低：优先图解，先拆错因再复测。
- 掌握度和正确率都较高：优先练习，验证能否迁移。
- 画像可信度偏低：优先补证据，让系统判断更稳。
- 用户偏好视频且基础尚可：优先短视频，加速理解。
- 用户偏好练习且已有一定起点：优先练习，边做边学。

## 已完成的闭环

目前“统一画像 -> 导学 -> 新证据 -> 再回到画像”的链路已经具备以下可见能力：

1. 画像页给出下一步建议。
2. 导学页接住这条建议并预填关键信息。
3. 导学页根据画像状态调整当前资源策略。
4. 用户完成任务、前测、练习或画像对话后，前端主动触发统一画像刷新。
5. 导学反馈卡中明确显示“画像闭环”，并提供“查看画像变化”入口。

## 设计原则

1. 用户当前意图优先：本次输入的目标、水平和时间预算优先级最高。
2. 统一画像做补全：画像用于减少用户填写负担，而不是替用户“拍板”。
3. 只读取，不反写：Guide V2 创建路线时只读取统一画像，避免导学和画像服务互相递归写入。
4. 可解释：导学画像和资源产物中保留画像摘要，后续前端可以展示“为什么系统建议先补这个点”。

## 验证记录

已通过：

```powershell
python -m py_compile sparkweave\services\guide_v2.py sparkweave\api\routers\guide_v2.py
pytest tests\services\test_guide_v2.py -q
pytest tests\api\test_guide_v2_router.py tests\api\test_learner_profile_router.py tests\services\test_learner_profile.py tests\services\test_learner_evidence.py -q
npm run build
```

结果：

- Guide V2 服务层：`21 passed`
- Guide/Profile/Evidence API 与服务联测：`15 passed`

## 下一步

- 继续细化导学策略，让不同评估状态触发不同的补救 / 复测 / 迁移动作。
- 把“为什么当前推荐图解 / 练习 / 视频”与画像中的薄弱点、掌握度更明确地绑定展示。
- 将统一画像进一步接入资源生成 prompt，让图解、短视频、练习题的默认难度和解释层级也随画像变化。
