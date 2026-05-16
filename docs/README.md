# SparkWeave 文档中心

根目录 `README.md` 用于项目首页和快速介绍；`docs/` 用于沉淀可维护的技术文档、接口说明、部署配置、比赛材料和后续开发计划。

如果你只想快速了解项目，按下面顺序读：

1. [快速开始](./getting-started.md)
2. [项目地图](./project-map.md)
3. [系统架构](./architecture.md)
4. [智能体、RAG 与学习画像代码事实说明](./core-ai-code-facts.md)
5. [功能级代码地图](./feature-code-map.md)

如果你要准备简历、面试或答辩，优先读三条核心技术主线：

- [Agent 运行时与多智能体调度设计](./agent-runtime-design.md)
- [RAG 系统设计与代码事实](./rag-system-design.md)
- [学习画像与长期记忆设计](./learner-profile-memory-design.md)

## 核心架构

| 文档 | 用途 |
| --- | --- |
| [系统架构](./architecture.md) | Entry Points、运行时、Tools、Capabilities、插件层 |
| [运行时链路](./runtime-flow.md) | 一次 turn 从请求到事件流、持久化、记忆更新的完整过程 |
| [会话、Turn 与事件持久化](./sessions-and-turns.md) | SQLite 会话模型、turn 生命周期、事件 seq、WebSocket 续流 |
| [服务层与数据流](./services.md) | 配置、LLM、Embedding、RAG、搜索、会话、记忆、Notebook、SparkBot、OCR |
| [功能级代码地图](./feature-code-map.md) | 从用户功能反查前端页面、API 路由、CLI、服务层和数据落点 |

## 三条 AI 主线

| 文档 | 用途 |
| --- | --- |
| [智能体、RAG 与学习画像代码事实说明](./core-ai-code-facts.md) | 对齐代码事实，区分已实现能力和不能夸大的边界 |
| [Agent 运行时与多智能体调度设计](./agent-runtime-design.md) | 统一 turn runtime、Chat 协调器、specialist 委派、工具调用、协作事件 |
| [RAG 系统设计与代码事实](./rag-system-design.md) | Milvus 优先架构、检索策略、HyDE、Gated Agentic RAG、rerank、Context Pack、RAG 评测 |
| [学习画像与长期记忆设计](./learner-profile-memory-design.md) | Memory 与统一学习画像分层、证据账本、画像聚合、上下文注入和用户校准 |

## 用户功能

| 文档 | 用途 |
| --- | --- |
| [前端工作台](./frontend.md) | 路由、API 客户端、聊天运行时、页面与后端契约 |
| [Capabilities 详解](./capabilities.md) | Chat、Deep Solve、Deep Question、Deep Research、Visualize、Math Animator 的配置、阶段和结果 |
| [Tools 工具系统](./tools.md) | Tool 协议、注册表、内置工具、能力图调用方式、SparkBot 工具边界 |
| [Notebook、Memory 与上下文引用](./notebook-memory-context.md) | Notebook、题目本、两文件 Memory、引用分析和 prompt 注入 |
| [导学空间与 Guide V2](./guided-learning.md) | Guide V2 学习画像、任务证据闭环、资源生成、报告和保存 |
| [学习画像设计调研与实现方案](./learner-profile-design.md) | 画像数据模型、事件词表、前端信息架构和隐私边界 |
| [学习效果评估闭环设计稿](./learning-effect-closed-loop-design.md) | 学习事件模型、掌握度引擎、效果报告、干预策略和落地计划 |
| [题目工作流](./question-workflows.md) | 题目生成、仿题、交互式练习和题目本 API |
| [试卷解析与仿题素材链路](./question-parsing-and-mimic.md) | PDF 上传、MinerU 解析、题目 JSON、仿题模板和排错 |
| [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md) | 图像输入、OCR、图像题解析、GeoGebra 工具和前端入口 |
| [SparkBot 与 Agents 工作台](./sparkbot-agents.md) | SparkBot 生命周期、工作区文件、渠道 schema、工具、heartbeat、cron、team |

## RAG 与知识库

| 文档 | 用途 |
| --- | --- |
| [知识库详解](./knowledge-base.md) | 知识库目录、创建、上传、检索、进度、linked folder、文档和向量块管理 |
| [Milvus RAG 设计说明](./milvus-rag.md) | Milvus 默认向量库、本地/Standalone 模式、collection 元数据、兼容回退和验证命令 |
| [RAG 升级设计与对比实验](./rag-improvement-design.md) | Evidence RAG Pipeline、hybrid/rerank/HyDE/Agentic RAG 调研与可复现实验 |
| [示例 RAG 评测集](./examples/rag_eval_dataset.sample.jsonl) | 最小 JSONL 评测样例 |
| [机器学习课程 RAG 评测集](./examples/rag_eval_dataset.ml_course.sample.jsonl) | 课程场景评测样例 |

## 配置、部署与运维

| 文档 | 用途 |
| --- | --- |
| [快速开始](./getting-started.md) | 本地环境、依赖安装、启动命令和常见入口 |
| [CLI 与 API 使用](./cli-and-api.md) | 命令行、WebSocket API、HTTP API、Python facade |
| [环境变量配置](./configuration.md) | LLM、Embedding、搜索、OCR、TTS、Docker、端口配置 |
| [设置与 Provider 配置](./settings-and-providers.md) | 设置页 catalog、`.env`、Provider resolver、连接测试和新增 provider 步骤 |
| [系统诊断与 Provider 健康检查](./system-diagnostics.md) | `/api/v1/system/*`、流式测试、Embedding adapter、搜索 fallback 和排错 |
| [科大讯飞能力接入说明](./iflytek-integration.md) | 讯飞星火、Embedding、ONE SEARCH、OCR、TTS 在学习闭环中的使用位置和失败回退 |
| [开发与维护](./development.md) | 测试、检查、目录结构、提交前检查和文档维护规则 |
| [下一阶段执行计划](./next-iteration-plan.md) | 产品化收敛、真实 RAG 验收、知识库体验、Agentic RAG 解释和质量基准的默认推进路线 |
| [SparkWeave 后续开发计划书](./sparkweave-execution-plan.md) | 后续开发阶段、质量门、执行记录和可视化专项最终完成状态 |

## 比赛与展示

| 文档 | 用途 |
| --- | --- |
| [赛题对齐与后续开发路线](./competition-roadmap.md) | 五项赛题要求的实现现状、学习闭环目标、后续阶段计划和验收标准 |
| [比赛 7 分钟演示 Runbook](./competition-demo-runbook.md) | 正式录制前检查、7 分钟分段讲法、页面动作和兜底策略 |
| [比赛可视化抓眼计划书](./competition-visualization-wow-plan.md) | 面向评委观感的演示驾驶舱、闭环轨道、多智能体接力和讯飞能力可视化专项路线 |
| [比赛可视化专项完成证据](./competition-visualization-completion-report.md) | 可视化专项的完成结论、完成矩阵、前端落点、提交包证据和最终验证命令 |
| [比赛可视化录屏与截图 Runbook](./competition-demo-visual-runbook.md) | `/demo` 评委演示台的 7 分钟录屏路线、PPT 截图位、答辩锚点和兜底策略 |
| [比赛演示连通性检查记录](./competition-demo-connectivity-check.md) | 当前 `/demo`、前端服务和后端 API 的录屏前连通性状态与兜底建议 |
| [AI 助教中心 SparkBot 演示 Runbook](./sparkbot-demo-runbook.md) | `/agents` 助教中心的一键 seed、7 分钟录屏路线和讯飞工具链讲法 |
| [演示者 5 分钟入口](./demo-quickstart.md) | 最短演示路径、赛题五项映射和现场兜底 |
| [稳定课程 Demo 模板](./demo-course-templates.md) | 可复现课程演示路线、任务链、兜底材料和扩展模板格式 |
| [演示脚本：画像驱动导学闭环](./demo-script-profile-guide-loop.md) | 画像、导学、资源、评估闭环的录屏讲稿 |
| [AI Coding 工具使用说明](./ai-coding-statement.md) | AI Coding 工具参与范围、人工审查方式、密钥边界和可追溯材料 |

## 扩展开发

| 文档 | 用途 |
| --- | --- |
| [插件开发](./plugin-development.md) | `sparkweave/plugins/` 目录约定、manifest、Capability 实现 |

## 文档维护原则

- 首页 `README.md` 只保留项目亮点、快速入口和最常见命令。
- `docs/README.md` 只做索引，不塞长篇方案。
- 功能文档必须尽量绑定代码路径、API 路由和数据落点，避免宣传化描述。
- 过期阶段日志、一次性开发计划和已被主文档吸收的小文档应及时删除。
- 新增截图、流程图、架构图统一放在 `docs/assets/`，再通过相对路径嵌入。
