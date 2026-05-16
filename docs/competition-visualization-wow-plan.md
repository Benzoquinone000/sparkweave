# 比赛可视化抓眼计划书

本文档用于沉淀 SparkWeave 比赛可视化专项的调研依据、设计路线、实施记录和最终验收口径。前端展示、录屏路线、PPT 截图和答辩讲法均已按本文收口，避免把创意与证据散落在聊天记录里。

## 1. 目标

SparkWeave 现有能力已经覆盖学习画像、导学路线、多智能体资源生成、智能辅导、学习效果评估和讯飞工具链。本次可视化层的目标不是继续堆功能，而是让评委在短时间内看懂三件事：

1. 这不是普通聊天机器人，而是完整学习闭环。
2. 多智能体协作不是后台概念，而是用户可见的接力过程。
3. 科大讯飞相关能力不是文档里提一句，而是嵌入到了真实学习资源与证据链。

核心表达：

```text
学生目标
  -> 学习画像
  -> 个性化路线
  -> 多智能体资源生成
  -> 多模态辅导
  -> 练习与反馈
  -> 学习效果评估
  -> 下一步动态调整
```

## 2. 落地参考

以下参考都来自已经落地的教育产品或开发者平台，可作为设计背书，但 SparkWeave 不直接照抄界面。调研结论已经转化为 `/demo`、课程产出包、资源卡、知识掌握图、学习效果报告和证据链组件中的可见设计。

| 参考 | 可借鉴点 | SparkWeave 转化方向 |
| --- | --- | --- |
| NotebookLM Mind Maps / Audio Overview | 资料、问题、摘要和音频围绕同一知识任务展开 | 当前任务下聚合文字、图解、TTS、视频、练习和引用证据 |
| Google Learn About | 学习卡片、图片、视频、测验和延伸问题组合呈现 | 做成学习资源 Studio，而不是单个生成结果 |
| Duolingo Path / Birdbrain | 学习路径和难度贴近学习者状态 | 用路径节点显示当前推荐、薄弱点和下一步 |
| ALEKS Knowledge State / Pie | 知识掌握状态可视化，区分已会、可学、未掌握 | 做知识掌握星图或地铁图，显示待补救与待复测 |
| Carnegie MATHia LiveLab | 实时学习状态、风险提示和干预建议 | 学习效果报告中显示证据、风险、补救、复测闭环 |
| LangGraph Studio / LangSmith / Arize Phoenix | Agent trace、工具调用、检索和输出可视化 | 多智能体接力剧场，显示角色分工和证据流 |
| 讯飞星火、Embedding、ONE SEARCH、OCR、TTS | 模型、检索、识别、搜索和语音合成能力完整 | 在每个资源卡中显式标注讯飞能力参与位置 |

可在答辩材料中引用的官方方向：

- NotebookLM Mind Maps: https://support.google.com/notebooklm/answer/16212283
- NotebookLM Audio Overview: https://support.google.com/notebooklm/answer/16212820
- Google Learn About: https://support.google.com/websearch/answer/15662709
- Duolingo Birdbrain: https://blog.duolingo.com/learning-how-to-help-you-learn-introducing-birdbrain/
- ALEKS: https://www.aleks.com/about_aleks/
- Carnegie Learning LiveLab: https://support.carnegielearning.com/help-center/math/livelab/article/livelab-overview/
- LangGraph Studio: https://docs.langchain.com/oss/python/langgraph/studio
- LangSmith tracing: https://docs.smith.langchain.com/
- Arize Phoenix: https://arize.com/docs/phoenix/
- 讯飞星火大模型: https://www.xfyun.cn/doc/spark/X1http.html
- 讯飞 ONE SEARCH: https://www.xfyun.cn/doc/spark/Search_API/search_API.html
- 讯飞超拟人 TTS: https://www.xfyun.cn/doc/spark/super%20smart-tts.html
- 讯飞 OCR: https://www.xfyun.cn/doc/words/universal_character_recognition/API.html
- 讯飞 Embedding: https://www.xfyun.cn/doc/spark/embedding_api.html

## 3. 设计原则

1. 评委模式优先  
   新增可视化要服务 7 分钟演示和答辩，不做成复杂管理后台。

2. 先证据，后细节  
   默认展示一条结论、一组真实证据和一个下一步动作；原始日志、JSON、内部 ID 继续隐藏。

3. 动态但克制  
   可以有路线点亮、节点流动、进度推进和状态切换，但不要做无意义的大屏动画。

4. 每个视觉都要绑定赛题要求  
   如果一个组件不能对应画像、资源生成、路径规划、智能辅导或学习评估之一，就不进入主演示路线。

5. 讯飞能力显性化  
   资源卡、演示驾驶舱和设置状态中都要能看到星火、Embedding、ONE SEARCH、OCR、TTS 分别服务哪个环节。

6. 可复现优先  
   关键视觉使用稳定课程模板、历史产物或 deterministic seed，避免现场模型波动影响录屏。

## 4. 优先级路线

### P0. 比赛演示驾驶舱

定位：给评委看的首页级证明面板，已落地为 `/demo` 独立演示台，并在 `/guide` 课程产出包中保留证明入口。

核心内容：

- 赛题五项对齐卡：画像、资源生成、路径规划、智能辅导、学习评估。
- 每项显示状态：已就绪、可排练、已纳入提交包。
- 每项绑定真实证据：页面入口、最近产物、最近学习证据或课程模板。
- 顶部给出一句话项目价值：先理解学生，再安排学习，再生成资源，再根据反馈持续调整。

视觉形态：

- 5 张横向评分点卡片。
- 中间一条学习闭环轨道。
- 右侧或底部显示讯飞工具链状态条。

验收标准：

- 评委不看代码也能知道项目覆盖赛题五项。
- 每张卡都有可点击入口，不只是静态宣传。
- 录屏时能在 30 秒内讲完项目主线。

### P0. 学习闭环轨道图

定位：把 SparkWeave 的核心故事压缩成一张图。

节点：

```text
目标输入 -> 学习画像 -> 当前任务 -> 资源生成 -> 练习反馈 -> 学习报告 -> 下一步调整
```

每个节点展示：

- 当前状态。
- 一条真实证据。
- 进入对应页面的动作。

视觉形态：

- 横向轨道或轻量环形路线。
- 当前所在步骤点亮。
- 已完成节点显示对勾，待复测节点显示观察状态。

验收标准：

- 能解释学习数据如何回写画像。
- 能解释评估如何改变下一步。
- 移动端不拥挤，至少能横向滚动或分段折行。

### P0. 讯飞能力证明条

定位：让赛题要求中的“需选用科大讯飞相关工具”在前端可见。

能力映射：

| 讯飞能力 | 显示位置 | 用户可见表达 |
| --- | --- | --- |
| 星火大模型 | 对话、导学、资源生成、评估 | 星火生成讲解与学习处方 |
| Embedding | 知识库、RAG 证据链 | 课程资料已完成智能索引 |
| ONE SEARCH | 精选公开视频、外部资料 | 公开视频由讯飞搜索辅助筛选 |
| OCR | 图像解题、扫描 PDF 资料导入 | 扫描资料由 OCR 识别 |
| TTS | 语音讲解、短视频旁白 | 讲解可合成为语音资源 |

视觉形态：

- 小型状态条，不做大面积营销 banner。
- 产物卡角标显示参与能力，例如“星火生成”“TTS 讲解”“OCR 识别”。
- 设置页保留连通性检测，演示页只展示用户能懂的状态。

验收标准：

- 评委能在演示画面中看到讯飞工具链。
- 不暴露 API Key、APPID、底层错误。
- 讯飞服务不可用时显示“可配置 / 有回退”，不让演示断线。

### P1. 多智能体接力剧场

定位：升级现有 `AgentCollaborationPanel` 的视觉表达，让多智能体协作更抓眼。

角色：

- 画像智能体：读取目标、薄弱点、偏好和时间预算。
- 协调智能体：把用户请求改写成具体学习任务。
- 路径规划智能体：决定当前任务和备选路径。
- 知识检索智能体：从知识库或外部资料找证据。
- 资源智能体：生成图解、动画、TTS、练习或视频建议。
- 评估智能体：根据反馈更新画像和下一步。

视觉形态：

- 横向泳道或接力路线。
- 一个“学习任务包”从左到右流动。
- 每个角色只显示一句用户可懂的职责。
- 可展开查看协作明细，但默认不展示协议事件。

验收标准：

- Chat 和 Guide 都能复用。
- 完成态只显示关键路径，不显示尾部 progress 噪声。
- 资源卡能说明“由哪些智能体共同生成”。

### P1. 多模态资源 Studio

定位：让“智能辅导”和“多模态学习资源”在一个任务里集中爆发。

同一当前任务下展示：

- 文字讲解。
- 图解或流程图。
- TTS 音频讲解。
- Manim 短视频或视频脚本。
- 精选公开视频。
- 交互练习。
- RAG 引用证据。

视觉形态：

- Bento 网格，但避免花哨大卡堆叠。
- 主资源大区 + 右侧小资源队列。
- 每张资源卡显示：生成依据、使用画像信号、下一步动作。

验收标准：

- 一眼能看出多模态。
- 每个资源都服务当前任务，不像随机生成合集。
- 练习提交后能回写学习效果。

### P1. 知识掌握星图 / 地铁图

定位：把课程模板和学习路径变成强视觉记忆点。

节点状态：

- 已掌握。
- 正在学。
- 可开始。
- 需补救。
- 待复测。

视觉形态：

- 对项目式课程用地铁图。
- 对概念型课程用星图或知识网络。
- 当前推荐节点发光或强调。

验收标准：

- 能展示完整高校课程，而不只是单次对话。
- 能解释为什么当前节点被推荐。
- 能从节点进入任务、资源或复测。

### P2. Before / After 学习路径变形

定位：证明学习效果评估真的会动态调整路线。

交互流程：

1. 展示提交反馈前的路线。
2. 用户提交练习结果和反思。
3. 展示系统写入证据。
4. 路线中某个节点状态发生变化。
5. 下一步处方更新。

视觉形态：

- 左右对比。
- 或单图状态切换动画。
- 明确显示“依据了哪些新证据”。

验收标准：

- 能在录屏中 40 秒内讲清楚。
- 不需要真实复杂模型也能用稳定 seed 演示。
- 学习报告和画像页状态一致。

### P2. RAG 证据瀑布

定位：让“有依据的智能辅导”比普通大模型回答更可信。

视觉流程：

```text
用户问题
  -> 问题拆解
  -> 检索分支
  -> 证据片段
  -> 质量判断
  -> 最终回答
```

视觉形态：

- 轻量瀑布流或分支合流图。
- 展示命中的文档、片段、相关性和是否回退。
- 最终回答引用来源。

验收标准：

- 不暴露 chunk、Milvus、embedding mismatch 等底层词。
- 弱证据时不能包装成强结论。
- 能跳到知识库检索测试或资料来源。

## 5. 实施顺序与完成状态

以下为本专项采用的实施顺序，已按轮次完成；保留该结构用于复盘、答辩解释和维护定位。

第一轮：比赛演示驾驶舱

1. 已新增可复用组件：评分点对齐卡、闭环轨道、讯飞能力条。
2. 已挂到 Guide 课程产出包和 `/demo` 稳定演示入口。
3. 已使用现有 course package、demo seed、learning effect 和 guide session 数据。
4. 已使用明确标注的稳定课程模板兜底，保证录屏可复现。

第二轮：多智能体接力剧场

1. 已基于现有 `AgentCollaborationPanel` 升级视觉。
2. 已沉淀多智能体接力剧场表达。
3. Chat 与 Guide 资源卡已共用同一套角色命名。
4. 已接入 `collaboration_route`、`agent_chain` 或资源生成元数据。

第三轮：多模态资源 Studio

1. 已在当前任务页聚合已有资源。
2. 资源卡已补充讯飞能力角标和画像依据。
3. TTS 已纳入脚本、配置状态和服务状态说明。
4. 精选公开视频已保留观看计划和画像回写入口。

第四轮：知识掌握地图和路径变形

1. 已使用课程模板节点和 learning effect concepts。
2. 已完成状态视觉，不引入复杂图算法风险。
3. 已保证录屏可讲，并完成桌面/移动端截图验证。

第五轮：RAG 证据瀑布

1. 已复用已有 RAG evidence chain 和 agentic explanation。
2. 已在 Chat 回答和知识库测试页中展示轻量证据流。
3. 弱证据、回退和下一步动作已按用户可理解语言表达。

## 6. 前端落点

| 模块 | 优先落点 | 可能涉及文件 |
| --- | --- | --- |
| 比赛演示驾驶舱 | `/guide` 课程产出包、稳定演示入口 | `web/src/pages/guide/GuideCoursePackagePanel.tsx`、新增 demo 组件 |
| 学习闭环轨道图 | `/guide`、`/memory` | `GuideHero.tsx`、`LearningEffectLoopCard.tsx`、新增 LoopRail 组件 |
| 讯飞能力证明条 | 资源卡、设置页、演示驾驶舱 | `GuideResourceArtifactPager.tsx`、`SettingsPage.tsx`、新增 IflytekCapabilityStrip |
| 多智能体接力剧场 | Chat、Guide 资源卡 | `AgentCollaborationPanel.tsx`、新增 AgentRelayRoute |
| 多模态资源 Studio | 当前任务页 | `GuideCurrentTaskPanel.tsx`、`GuideResourceArtifactPager.tsx` |
| 知识掌握星图 / 地铁图 | 导学路线页 | `GuideKnowledgeMapPanel.tsx`、`GuideStudyPlanPanel.tsx` |
| Before / After 路径变形 | 学习报告、反馈页 | `GuideLearningReportPanel.tsx`、`GuideLearningFeedbackPanel.tsx` |
| RAG 证据瀑布 | Chat 回答、知识库检索测试 | `RagEvidenceChain.tsx`、`KnowledgeWorkspaceContent.tsx` |

## 7. 验收清单

每完成一个可视化模块，都至少检查：

- 是否直接对应赛题五项之一。
- 是否能在 7 分钟视频里用一句话讲清楚。
- 是否有真实数据或明确兜底数据。
- 是否隐藏内部 ID、原始 JSON 和调试事件。
- 是否在桌面和移动端都不重叠、不溢出。
- 是否能通过 `npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`。
- 若改动 API 字段，追加 `npm.cmd run check:api-contract`。

## 8. 录屏讲法模板

比赛演示驾驶舱：

> 这里不是功能菜单，而是赛题证明面板。五个评分点都能直接跳到真实功能和产物证据。

学习闭环轨道：

> 学生目标进入系统后，先形成学习画像，再生成当前任务和资源，练习反馈会回写画像，最终调整下一步路线。

多智能体接力剧场：

> 这条路线展示了本次请求由哪些智能体接力完成：画像先判断卡点，规划压缩成任务，检索补充证据，资源智能体生成图解或练习，评估智能体再把结果写回学习闭环。

讯飞能力证明条：

> SparkWeave 把讯飞能力放在学习闭环的不同节点：星火负责理解和生成，Embedding 支撑课程资料检索，ONE SEARCH 找外部资源，OCR 处理扫描资料，TTS 生成可听讲解。

学习效果 Before / After：

> 这里可以看到评估不是一个分数。提交练习后，系统识别错因，生成补救任务，并调整下一步推荐。

## 9. 不做清单

- 不做泛泛的数据大屏。
- 不把工具调用日志直接展示给评委。
- 不在首屏堆满所有资源类型。
- 不为了动画牺牲稳定性和移动端布局。
- 不把讯飞能力做成只会出现一次的宣传标语。
- 不用无法离线打包或授权不清的第三方素材。

## 10. 2026-05-15 实施完成记录

本轮已按计划完成首批可视化落地，覆盖 P0、P1、P2 的主演示链路：

| 计划项 | 当前状态 | 前端落点 |
| --- | --- | --- |
| 比赛演示驾驶舱 | 已完成 | `/demo`、`GuideCoursePackagePanel.tsx`、`CompetitionDemoDashboard.tsx` |
| 学习闭环轨道图 | 已完成 | `CompetitionDemoDashboard.tsx` |
| 讯飞能力证明条 | 已完成 | `CompetitionDemoDashboard.tsx`、`GuideResourceArtifactPager.tsx` |
| 多智能体接力剧场 | 已完成 | `AgentCollaborationPanel.tsx`、资源卡接力链 |
| 多模态资源 Studio | 已完成 | `GuideResourceArtifactPager.tsx` |
| 知识掌握地铁图 | 已完成 | `GuideKnowledgeMapPanel.tsx` |
| Before / After 路径变形 | 已完成 | `GuideLearningReportPanel.tsx` |
| RAG 证据瀑布 | 已完成 | `RagEvidenceChain.tsx` |

验证命令已通过：

```powershell
npm.cmd run lint
npm.cmd run build
npm.cmd run check:design
npm.cmd run check:api-contract
npm.cmd run check:replacement
npm.cmd run test:e2e -- --grep "competition demo route"
$env:SCREENSHOT_ONLY="/demo"; npm.cmd run screenshots
python scripts/check_competition_visuals.py
python scripts/export_competition_package.py --output dist/competition_package --archive dist/sparkweave_competition_package.zip
python scripts/verify_competition_package.py dist/competition_package
python scripts/verify_competition_package.py dist/sparkweave_competition_package.zip
python scripts/check_competition_readiness.py --output dist/competition_readiness_latest.json
```

## 11. 已完成打磨记录

本轮已继续完成以下打磨项，计划书对应的视觉层工作已收口到可提交状态：

1. 新增 `/demo` 独立评委演示台，使用稳定课程包兜底，不依赖现场生成。
2. 新增稳定演示数据 `web/src/pages/demo/demoCoursePackage.ts`，覆盖画像、路线、资源、评估、PPT、录屏脚本和提交清单。
3. 新增 `docs/competition-demo-visual-runbook.md`，沉淀 7 分钟录屏路线、PPT 截图位、答辩锚点和兜底策略。
4. 截图脚本已加入 `/demo` 桌面与移动端截图目标。
5. Playwright 已加入 `/demo` 黑盒可见性检查，覆盖五项证明、闭环轨道、讯飞能力条、录屏路线和截图清单。
6. `/demo` 右侧服务状态区已接入 `system/status`，展示 LLM、Embedding/RAG、搜索、OCR、TTS 的可用/待检查状态。
7. 已重新生成 `/demo` 桌面和移动端截图，并纳入正式提交包。
8. 已导出正式提交包 `dist/competition_package` 和 `dist/sparkweave_competition_package.zip`，目录包与 zip 包均通过校验。
9. `scripts/check_competition_readiness.py` 已确认所有必需参赛材料就绪。

已完成的非阻塞优化（原赛前人工项）：

1. 已启动真实后端服务并完成 `/api/v1/system/status` 连通性检查；状态记录见 `docs/competition-demo-connectivity-check.md`。
2. 已采用“SparkWeave 参赛团队”作为默认提交品牌，并写入提交包首页、`START_HERE.md` 与 `submission_manifest.md`；如赛前确定学校或队伍名，可只做名称替换，不影响当前提交完整性。

## 12. 最终完成判定

截至 2026-05-15，本计划书覆盖的可视化专项已完成：

- 调研参考已沉淀为可执行设计原则。
- P0/P1/P2 可视化模块均已落到前端页面或可复用组件。
- `/demo` 评委演示台、录屏 runbook、桌面/移动截图、E2E 测试和提交包均已生成。
- 后端真实连通性已复核，讯飞搜索、OCR、TTS 等能力在状态接口中显示为 `configured`。
- 正式提交包目录与 zip 包均通过校验，总 readiness 结果为 `All required competition materials are ready.`。
