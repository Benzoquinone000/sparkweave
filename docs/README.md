# SparkWeave 文档中心

这里放置 SparkWeave 的详细文档。根目录 `README.md` 更适合作为项目首页和快速介绍，`docs/` 则用于沉淀安装、配置、架构、接口、插件开发和维护流程。

## 推荐阅读顺序

1. [快速开始](./getting-started.md)
2. [项目地图](./project-map.md)
3. [系统架构](./architecture.md)
4. [运行时链路](./runtime-flow.md)
5. [会话、Turn 与事件持久化](./sessions-and-turns.md)
6. [Capabilities 详解](./capabilities.md)
7. [Tools 工具系统](./tools.md)
8. [CLI 与 API 使用](./cli-and-api.md)
9. [知识库详解](./knowledge-base.md)
10. [题目工作流](./question-workflows.md)
11. [试卷解析与仿题素材链路](./question-parsing-and-mimic.md)
12. [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md)
13. [前端工作台](./frontend.md)
14. [服务层与数据流](./services.md)
15. [设置与 Provider 配置](./settings-and-providers.md)
16. [系统诊断与 Provider 健康检查](./system-diagnostics.md)
17. [环境变量配置](./configuration.md)
18. [插件开发](./plugin-development.md)
19. [开发与维护](./development.md)

## 文档定位

| 文档 | 适合读者 | 内容 |
| --- | --- | --- |
| [快速开始](./getting-started.md) | 初次运行项目的人 | 本地环境、依赖安装、启动命令、常见入口 |
| [项目地图](./project-map.md) | 新加入的开发者 | 后端、CLI、前端、测试和数据目录的代码索引 |
| [系统架构](./architecture.md) | 维护者、架构设计者 | Entry Points、运行时、Tools、Capabilities、插件层 |
| [运行时链路](./runtime-flow.md) | 后端开发者、集成方 | 一次 turn 从请求到事件流、持久化、记忆更新的完整过程 |
| [会话、Turn 与事件持久化](./sessions-and-turns.md) | 后端开发者、前端集成方 | SQLite 会话模型、turn 生命周期、事件 seq、WebSocket 续流、消息汇总 |
| [Capabilities 详解](./capabilities.md) | 能力开发者、前后端集成方 | Chat、Deep Solve、Deep Question、Deep Research、Visualize、Math Animator 的配置、阶段和结果 |
| [Tools 工具系统](./tools.md) | 工具开发者、能力维护者 | Tool 协议、注册表、内置工具、能力图调用方式、SparkBot 工具边界 |
| [CLI 与 API 使用](./cli-and-api.md) | 使用者、集成方 | 命令行、WebSocket API、HTTP API、Python facade |
| [知识库详解](./knowledge-base.md) | RAG 维护者、部署者 | 知识库目录、创建、上传、检索、进度、linked folder、embedding 指纹 |
| [题目工作流](./question-workflows.md) | 题目功能维护者、前端开发者 | `deep_question`、兼容题目 WebSocket、仿题、题目本 API |
| [试卷解析与仿题素材链路](./question-parsing-and-mimic.md) | 题目解析维护者、QuestionLab 开发者 | PDF 上传、MinerU 解析目录、题目 JSON、仿题模板、前端预览和排错 |
| [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md) | 视觉能力维护者、OCR/知识库维护者、前端开发者 | 图像输入契约、讯飞 OCR、VisionSolverAgent、GeoGebra 工具、VisionPage 和排错 |
| [前端工作台](./frontend.md) | 前端开发者 | 路由、API 客户端、聊天运行时、页面与后端契约 |
| [服务层与数据流](./services.md) | 后端开发者、部署者 | 配置、LLM、Embedding、RAG、搜索、会话、记忆、Notebook、OCR |
| [设置与 Provider 配置](./settings-and-providers.md) | 部署者、Provider 适配开发者 | 设置页 catalog、`.env`、LLM/Embedding/Search resolver、连接测试和新增 provider 步骤 |
| [系统诊断与 Provider 健康检查](./system-diagnostics.md) | 运维者、Provider 适配开发者、设置页维护者 | `/api/v1/system/*`、设置页流式测试、Embedding adapter、讯飞向量签名和排错 |
| [环境变量配置](./configuration.md) | 部署者、后端开发者 | LLM、Embedding、搜索、OCR、Docker、端口配置 |
| [插件开发](./plugin-development.md) | 能力扩展开发者 | `sparkweave/plugins/` 目录约定、manifest、Capability 实现 |
| [开发与维护](./development.md) | 项目贡献者 | 测试、检查、目录结构、提交前检查 |

## 文档维护原则

- README 只保留项目亮点、快速入口和最常见命令。
- 详细步骤、排错说明、配置矩阵放在 `docs/`。
- 新增功能时，同步补充对应文档，尤其是环境变量、CLI 参数、API 合约和插件 manifest。
- 文档中的命令默认从项目根目录执行，除非特别说明。
- 架构图、流程图和截图统一放在 `docs/assets/`，再通过相对路径嵌入文档。
