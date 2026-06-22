# SparkWeave 文档中心

本页面面向评委阅读，按赛题验收顺序整理 SparkWeave 的核心文档和功能入口。建议先看交付清单，再按学习画像、资源生成、路径规划、智能辅导、学习效果评估和讯飞工具链逐项核对。

项目运行方式、页面入口和提交说明见根目录 [README.md](../../README.md)；本目录负责展开关键功能和工程实现。

## 核心创新点

评审时建议先抓住一个主张：SparkWeave 不是把 Agent、RAG、画像、多模态能力分开展示，而是把它们织进同一条学习线。这里的创新点都可以沿着代码核验：RAG 有 query plan、并发分支、质量门和修复回退；画像有追加式证据账本和上下文注入；调度器会把自然语言学习任务转给专业能力或工具；课程助教通道层还能把同一套能力接到 QQ。

| 创新点 | 代码里的落点 | 评委可核验的位置 |
| --- | --- | --- |
| Agentic RAG 质量门 | `rag_support/service.py` 规划并发检索，`agentic_quality.py` 判断覆盖度和相关性，`agentic_repair.py` 做弱分支修复或回退 | [RAG 系统设计](./rag-system-design.md)、资料页 |
| 证据化画像 | `learner_evidence.py` 写入 `evidence.jsonl`，`learner_profile.py` 聚合画像，`profile_context.py` 注入精简提示 | [学习画像与记忆设计](./learner-profile-memory-design.md)、记录 / 画像页 |
| 自动调度的多智能体 | `LearningCapabilityRouter` 结合规则、约束和可选 LLM intent coordinator，把任务转给 `deep_solve`、`deep_question`、`visualize`、`math_animator` 等能力 | [智能体编排设计](./agent-orchestration-design.md)、问问题页 |
| 课程和资料库联动 | 课程模板的 `source_materials` 由 `sync_course_materials_to_kb.py` 同步到课程 RAG 资料库 | [完整课程样例说明](./course-template-guide.md)、资料页 |
| 可接 QQ 的课程助教 | `QQChannel` 支持私聊、群聊和提醒发送，`/sparkbot/channels/schema` 暴露通道配置 | [智能体编排设计](./agent-orchestration-design.md)、课程助教页 |
| 讯飞能力进入学习环节 | 星火模型、Embedding、ONE SEARCH、OCR、公式、图片理解、语音和工作流在工具层与设置页都有落点 | [科大讯飞工具链说明](./iflytek-toolchain-guide.md)、设置页 |
| 学习闭环优先 | 前端把 Agent、RAG、画像等工程能力后台化，一级入口保留学习、资料、记录、设置 | [前端设计规范](./frontend-design-guide.md)、学习页 |

## 先看哪几篇

| 评审关注点 | 建议阅读 |
| --- | --- |
| 想快速浏览一页版项目说明 | [SparkWeave HTML 项目说明](../html/sparkweave-overview.html) |
| 作品如何对应赛题要求 | [软件杯交付检查清单](./software-cup-delivery-checklist.md) |
| 源码、课程、数据和部署文件是否完整 | [项目结构说明](./project-structure.md) |
| 每块功能如何追到代码 | [功能代码链路说明](./feature-code-walkthrough.md) |
| 完整高校课程样例如何组织 | [完整课程样例说明](./course-template-guide.md) |
| 最终提交包应当如何整理 | [提交包整理说明](./submission-package-guide.md) |
| 多智能体如何分工生成学习资源 | [智能体编排设计](./agent-orchestration-design.md) |
| 对话式学习画像如何形成 | [学习画像与记忆设计](./learner-profile-memory-design.md) |
| 资料问答如何给出可追溯依据 | [RAG 系统设计](./rag-system-design.md) |
| 科大讯飞相关工具如何接入 | [科大讯飞工具链说明](./iflytek-toolchain-guide.md)、[配置指南](./configuration-guide.md) |
| 前端为什么把“学习、资料、记录、设置”作为主入口 | [前端设计规范](./frontend-design-guide.md) |
| 可运行性、API、测试和数据边界如何核验 | [API 开发规范](./api-development-guide.md)、[测试规范](./testing-guide.md)、[数据存储规范](./data-storage-guide.md) |
| PPT 和 7 分钟视频如何组织 | [PPT 与 7 分钟演示视频建议](./presentation-video-guide.md) |
| AI Coding 使用情况如何说明 | [AI Coding 使用说明](./ai-coding-disclosure.md) |

## 界面预览

下表对应视频中的主要入口。截图用于帮助评委快速定位页面，具体流程以可运行系统和视频为准。

| 入口 | 对应赛题能力 | 截图 |
| --- | --- | --- |
| 学习 | 个性化学习路径规划、任务推进、学习反馈 | [学习页](../../web/screenshots-guide.png) |
| 资料 | 课程资料入库、资料问答、证据引用 | [资料页](../../web/screenshots-knowledge.png) |
| 问问题 | 智能辅导、多模态资源生成入口 | [问问题页](../../web/screenshots-chat.png) |
| 记录 / 画像 | 学习记录、薄弱点、下一步建议 | [记录与画像页](../../web/screenshots-memory.png) |
| 设置 | 模型、搜索、OCR、语音和讯飞工具配置 | [设置页](../../web/screenshots-settings.png) |
| 课程助教 | 长期课程助教、资料同步、提醒任务和 QQ 等消息通道 | [课程助教页](../../web/screenshots-agents.png) |

## 文档地图

| 文档 | 主要内容 |
| --- | --- |
| [SparkWeave HTML 项目说明](../html/sparkweave-overview.html) | 一页版项目说明，整合定位、赛题对应、界面、课程、讯飞工具和运行方式 |
| [软件杯交付检查清单](./software-cup-delivery-checklist.md) | 赛题要求、提交物、7 分钟演示、AI Coding 说明和最终复核 |
| [提交包整理说明](./submission-package-guide.md) | 源码、课程、配置样例、截图、PPT、视频和不可提交内容 |
| [完整课程样例说明](./course-template-guide.md) | 主课程的 14 周安排、学习节点、任务、考核和核验路线 |
| [PPT 与 7 分钟演示视频建议](./presentation-video-guide.md) | PPT 页结构、7 分钟视频讲稿、截图和讲解重点 |
| [AI Coding 使用说明](./ai-coding-disclosure.md) | AI 编程助手使用范围、人工复核、密钥和隐私边界 |
| [科大讯飞工具链说明](./iflytek-toolchain-guide.md) | 星火、Embedding、ONE SEARCH、OCR、公式、图片、语音和工作流在学习流程中的落点 |
| [项目结构说明](./project-structure.md) | 后端、前端、数据、课程模板、验证文件和部署文件的目录边界 |
| [功能代码链路说明](./feature-code-walkthrough.md) | 按学习、资料、问问题、练习、画像、评估、课程助教和讯飞工具逐项追到代码 |
| [智能体编排设计](./agent-orchestration-design.md) | 一次学习请求如何经过对话协调、专业能力、工具调用和前端展示 |
| [RAG 系统设计](./rag-system-design.md) | 资料如何入库、检索、打包证据，并进入回答 |
| [学习画像与记忆设计](./learner-profile-memory-design.md) | 目标、薄弱点、偏好和学习记录如何沉淀成下一步建议 |
| [配置指南](./configuration-guide.md) | 模型、Embedding、搜索、OCR、公式识别、图片理解、语音和讯飞工具链配置 |
| [API 开发规范](./api-development-guide.md) | FastAPI、WebSocket、前端 API 客户端和契约边界 |
| [数据存储规范](./data-storage-guide.md) | `data/` 下的课程模板、知识库、用户记录和不可提交数据 |
| [测试规范](./testing-guide.md) | 后端、前端、课程模板、API 合约和发布前验证 |
| [前端设计规范](./frontend-design-guide.md) | 学习、资料、记录、设置这条主路径，以及页面和视觉约束 |
| [开发指南](./development-guide.md) | 本地开发、后端服务、前端页面和质量检查流程 |
| [软件工程规范](./engineering-standards.md) | 目录职责、文档治理、自动化门禁和提交边界 |
