# SparkWeave 文档中心

这里放置 SparkWeave 的详细文档。根目录 `README.md` 更适合作为项目首页和快速介绍，`docs/` 则用于沉淀安装、配置、架构、接口、插件开发和维护流程。

## 推荐阅读顺序

1. [快速开始](./getting-started.md)
2. [项目地图](./project-map.md)
3. [系统架构](./architecture.md)
4. [运行时链路](./runtime-flow.md)
5. [会话、Turn 与事件持久化](./sessions-and-turns.md)
6. [Notebook、Memory 与上下文引用](./notebook-memory-context.md)
7. [学习画像设计调研与实现方案](./learner-profile-design.md)
8. [学习画像开发前调研笔记](./learner-profile-research-notes.md)
9. [学习画像 P1 只读统一画像实施方案](./learner-profile-p1-implementation.md)
10. [学习画像 P1 开发状态](./learner-profile-p1-status.md)
11. [学习画像 P2 证据账本](./learner-profile-p2-evidence-ledger.md)
12. [学习画像 P3 用户校准](./learner-profile-p3-calibration.md)
13. [学习画像 P4 对话信号接入](./learner-profile-p4-chat-signals.md)
14. [学习画像 P5 Guide V2 导学接入统一画像](./learner-profile-p5-guide-integration.md)
15. [学习画像 P6 学习效果评估融合](./learner-profile-p6-effect-assessment.md)
16. [学习画像 P7 知识点掌握度沉淀](./learner-profile-p7-concept-mastery.md)
17. [学习画像 P8 一步行动建议](./learner-profile-p8-next-action.md)
18. [学习画像 P9 模型上下文注入](./learner-profile-p9-context-injection.md)
19. [导学空间与 Guide V2](./guided-learning.md)
20. [稳定课程 Demo 模板](./demo-course-templates.md)
21. [演示者 5 分钟入口](./demo-quickstart.md)
22. [比赛 7 分钟演示 Runbook](./competition-demo-runbook.md)
23. [SparkBot 与 Agents 工作台](./sparkbot-agents.md)
24. [Capabilities 详解](./capabilities.md)
25. [Tools 工具系统](./tools.md)
26. [CLI 与 API 使用](./cli-and-api.md)
27. [知识库详解](./knowledge-base.md)
28. [题目工作流](./question-workflows.md)
29. [试卷解析与仿题素材链路](./question-parsing-and-mimic.md)
30. [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md)
31. [前端工作台](./frontend.md)
32. [服务层与数据流](./services.md)
33. [设置与 Provider 配置](./settings-and-providers.md)
34. [系统诊断与 Provider 健康检查](./system-diagnostics.md)
35. [环境变量配置](./configuration.md)
36. [插件开发](./plugin-development.md)
37. [赛题对齐与后续开发路线](./competition-roadmap.md)
38. [AI Coding 工具使用说明](./ai-coding-statement.md)
39. [开发与维护](./development.md)

## 文档定位

| 文档 | 适合读者 | 内容 |
| --- | --- | --- |
| [快速开始](./getting-started.md) | 初次运行项目的人 | 本地环境、依赖安装、启动命令、常见入口 |
| [项目地图](./project-map.md) | 新加入的开发者 | 后端、CLI、前端、测试和数据目录的代码索引 |
| [系统架构](./architecture.md) | 维护者、架构设计者 | Entry Points、运行时、Tools、Capabilities、插件层 |
| [运行时链路](./runtime-flow.md) | 后端开发者、集成方 | 一次 turn 从请求到事件流、持久化、记忆更新的完整过程 |
| [会话、Turn 与事件持久化](./sessions-and-turns.md) | 后端开发者、前端集成方 | SQLite 会话模型、turn 生命周期、事件 seq、WebSocket 续流、消息汇总 |
| [Notebook、Memory 与上下文引用](./notebook-memory-context.md) | 后端开发者、前端集成方、上下文能力维护者 | 主 Notebook JSON、题目本边界、两文件 Memory、引用分析、prompt 注入、前端/CLI 保存和排查 |
| [学习画像设计调研与实现方案](./learner-profile-design.md) | 画像功能维护者、导学/评估开发者、比赛材料整理者 | 画像调研、统一数据模型、证据账本、前端画像中心、API 和分阶段实现计划 |
| [学习画像开发前调研笔记](./learner-profile-research-notes.md) | 画像功能维护者、架构设计者、测试规划者 | 外部调研摘要、项目证据源盘点、事件词表、风险清单、测试矩阵和开发前检查 |
| [学习画像 P1 只读统一画像实施方案](./learner-profile-p1-implementation.md) | 画像功能开发者、前端开发者、测试维护者 | P1 边界、数据结构、API 合约、聚合规则、前端页面结构、测试计划和开发顺序 |
| [学习画像 P1 开发状态](./learner-profile-p1-status.md) | 画像功能开发者、联调者、验收者 | P1 已完成内容、当前 API、验证记录和下一步计划 |
| [学习画像 P2 证据账本](./learner-profile-p2-evidence-ledger.md) | 画像功能开发者、导学/评估开发者、联调者 | 统一学习事件格式、证据账本 API、画像接入规则和后续模块接入点 |
| [学习画像 P3 用户校准](./learner-profile-p3-calibration.md) | 画像功能开发者、前端开发者、导学/推荐开发者 | 画像确认、驳回、修正的 API、事件格式、前端入口和验证记录 |
| [学习画像 P4 对话信号接入](./learner-profile-p4-chat-signals.md) | 画像功能开发者、运行时维护者、导学/推荐开发者 | 聊天中的目标、卡点、资源偏好如何低置信度写入统一画像证据账本 |
| [学习画像 P5 Guide V2 导学接入统一画像](./learner-profile-p5-guide-integration.md) | 画像功能开发者、导学功能维护者、推荐策略开发者 | Guide V2 创建路线时如何读取统一画像、保留用户显式输入并补全导学画像 |
| [学习画像 P6 学习效果评估融合](./learner-profile-p6-effect-assessment.md) | 画像功能开发者、导学评估维护者、比赛演示材料整理者 | 学习效果评估如何纳入统一画像、长期薄弱点、证据账本和前端解释 |
| [学习画像 P7 知识点掌握度沉淀](./learner-profile-p7-concept-mastery.md) | 画像功能开发者、题目/导学/评估开发者 | 题目事件如何携带知识点、画像如何按概念合并 mastery 与 weak point |
| [学习画像 P8 一步行动建议](./learner-profile-p8-next-action.md) | 画像功能开发者、导学功能维护者、前端开发者 | 画像中心如何给出“现在只做这一步”，并把行动来源带入导学创建 |
| [学习画像 P9 模型上下文注入](./learner-profile-p9-context-injection.md) | 运行时维护者、能力开发者、画像功能开发者 | 画像如何被压缩成模型上下文，注入 LangGraph 回合并覆盖 Chat/解题/出题/图解/动画 |
| [导学空间与 Guide V2](./guided-learning.md) | 导学功能维护者、前后端集成方 | 旧版导学、Guide V2 学习画像、课程模板、任务证据闭环、资源生成、报告和 Notebook/题目本保存 |
| [稳定课程 Demo 模板](./demo-course-templates.md) | 比赛材料整理者、录屏负责人、导学功能维护者 | 机器学习、ROS、高等数学三条可复现课程演示路线、任务链、兜底材料和扩展模板格式 |
| [演示者 5 分钟入口](./demo-quickstart.md) | 录屏者、答辩者、现场演示者 | 最短演示路径、赛题五项映射、现场兜底和赛后材料整理 |
| [比赛 7 分钟演示 Runbook](./competition-demo-runbook.md) | 录屏负责人、答辩负责人、项目负责人 | 正式录制前检查、7 分钟分段讲法、页面动作、兜底策略和答辩优先回答 |
| [SparkBot 与 Agents 工作台](./sparkbot-agents.md) | 长期智能体维护者、前端集成方、渠道开发者 | SparkBot 生命周期、工作区文件、渠道 schema、WebSocket 聊天、工具、heartbeat、cron、team 和排查路径 |
| [Capabilities 详解](./capabilities.md) | 能力开发者、前后端集成方 | Chat、Deep Solve、Deep Question、Deep Research、Visualize、Math Animator 的配置、阶段和结果 |
| [Tools 工具系统](./tools.md) | 工具开发者、能力维护者 | Tool 协议、注册表、内置工具、能力图调用方式、SparkBot 工具边界 |
| [CLI 与 API 使用](./cli-and-api.md) | 使用者、集成方 | 命令行、WebSocket API、HTTP API、Python facade |
| [知识库详解](./knowledge-base.md) | RAG 维护者、部署者 | 知识库目录、创建、上传、检索、进度、linked folder、embedding 指纹 |
| [题目工作流](./question-workflows.md) | 题目功能维护者、前端开发者 | `deep_question`、兼容题目 WebSocket、仿题、题目本 API |
| [试卷解析与仿题素材链路](./question-parsing-and-mimic.md) | 题目解析维护者、QuestionLab 开发者 | PDF 上传、MinerU 解析目录、题目 JSON、仿题模板、前端预览和排错 |
| [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md) | 视觉能力维护者、OCR/知识库维护者、前端开发者 | 图像输入契约、讯飞 OCR、VisionSolverAgent、GeoGebra 工具、VisionPage 和排错 |
| [前端工作台](./frontend.md) | 前端开发者 | 路由、API 客户端、聊天运行时、页面与后端契约 |
| [服务层与数据流](./services.md) | 后端开发者、部署者 | 配置、LLM、Embedding、RAG、搜索、会话、记忆、Notebook、SparkBot、OCR |
| [设置与 Provider 配置](./settings-and-providers.md) | 部署者、Provider 适配开发者 | 设置页 catalog、`.env`、LLM/Embedding/Search resolver、连接测试和新增 provider 步骤 |
| [系统诊断与 Provider 健康检查](./system-diagnostics.md) | 运维者、Provider 适配开发者、设置页维护者 | `/api/v1/system/*`、设置页流式测试、Embedding adapter、讯飞向量签名和排错 |
| [环境变量配置](./configuration.md) | 部署者、后端开发者 | LLM、Embedding、搜索、OCR、Docker、端口配置 |
| [插件开发](./plugin-development.md) | 能力扩展开发者 | `sparkweave/plugins/` 目录约定、manifest、Capability 实现 |
| [赛题对齐与后续开发路线](./competition-roadmap.md) | 项目负责人、功能规划者、比赛材料整理者 | 五项赛题要求的实现现状、学习闭环目标、后续阶段计划和验收标准 |
| [AI Coding 工具使用说明](./ai-coding-statement.md) | 比赛评委、项目负责人、提交材料整理者 | AI Coding 工具参与范围、人工审查方式、密钥边界和可追溯材料 |
| [开发与维护](./development.md) | 项目贡献者 | 测试、检查、目录结构、提交前检查 |

## 文档维护原则

- README 只保留项目亮点、快速入口和最常见命令。
- 详细步骤、排错说明、配置矩阵放在 `docs/`。
- 新增功能时，同步补充对应文档，尤其是环境变量、CLI 参数、API 合约和插件 manifest。
- 文档中的命令默认从项目根目录执行，除非特别说明。
- 架构图、流程图和截图统一放在 `docs/assets/`，再通过相对路径嵌入文档。
