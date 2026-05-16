# SparkWeave 前端素材更新计划

## 目标

把前端从“装饰性小人”调整为更适合教育产品的学习场景视觉。素材要服务学生理解：正在学什么、下一步做什么、助教如何给出证据和反馈。

## 最新结论

Open Peeps / DiceBear 人物素材已在视觉 QA 后淘汰。它们虽然授权清晰，但表情和造型偏玩具化，不适合 SparkWeave 作为高校教育应用参加比赛展示。

新的素材方向：

- 使用本地自制 SVG，不依赖外部 CDN。
- 用课程地图、学习画像、知识笔记、白板讲解、写作批注、题目生成、工具实验台、设置面板替代人物贴纸。
- 保持 Notion 风：白色画布、细边框、低饱和粉彩、克制阴影、小尺寸插画。
- 不再把人物作为页面视觉主角，助教中心继续优先展示真实工作台和证据链。

## 当前落地

- 新增教育场景素材：`web/public/illustrations/education/`
- `PeopleAccent` 保留原 API，同时新增语义化名称：
  `course_map / learner_profile / knowledge_notes / writing_board / vision_tutor / question_lab / playground_lab / settings_panel`
- 页面引用已改为教育场景语义，避免后续再误用夸张小人。

## 后续规则

1. 优先使用产品界面 mockup 和学习场景图，不使用夸张人物头像。
2. 引入第三方素材前必须确认商业使用、再分发、署名和离线打包要求。
3. 比赛包只保留会被页面实际使用的素材，避免无关素材污染观感。
4. 所有新增图都要在 `/guide`、`/memory`、`/vision`、`/co-writer`、`/agents` 等关键页面截图中检查尺寸、遮挡和视觉一致性。

## 在线素材补充方向

详见 `docs/notion-style-frontend-assets.md`。当前优先级：

1. 自制教育场景 SVG，保证风格和授权完全可控。
2. ctrlv.design、Highlights 这类 CC0 素材作为辅助点缀来源。
3. unDraw 只少量使用，不批量打包。
4. Notioly、Overflow Design 适合最像 Notion 的商业素材补强，但必须单独记录 license。
5. 聚合站、需要署名的平台、官方 Notion 品牌资产不进入提交包。
