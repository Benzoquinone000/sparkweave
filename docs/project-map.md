# 项目地图

本文档从代码目录角度说明 SparkWeave 的模块分工，适合第一次接手项目时快速定位。

## 顶层目录

| 路径 | 作用 |
| --- | --- |
| `sparkweave/` | 后端核心包，包含运行时、能力图、服务层、API、工具、插件和 SparkBot |
| `sparkweave_cli/` | Typer CLI 入口，复用 `sparkweave.app.SparkWeaveApp` |
| `web/` | Vite + React + TypeScript 前端工作台 |
| `tests/` | 后端、CLI、服务层、运行时和前端契约测试 |
| `scripts/` | 启动、检查、迁移和维护脚本 |
| `requirements/` | 分层 Python 依赖 |
| `assets/` | Logo、架构图等项目素材 |
| `data/` | 本地运行数据、知识库、记忆、Notebook、会话数据库和产物 |
| `docs/` | 详细文档 |

## 后端核心

| 路径 | 说明 |
| --- | --- |
| `sparkweave/app/facade.py` | 应用层 facade，提供 `SparkWeaveApp`、`TurnRequest`、capability manifest |
| `sparkweave/core/contracts.py` | `UnifiedContext`、`StreamEvent`、`StreamBus`，是运行时事件协议核心 |
| `sparkweave/core/state.py` | LangGraph 共享状态 `TutorState`，负责把 `UnifiedContext` 转成图状态 |
| `sparkweave/core/tool_protocol.py` | Tool 协议、参数 schema、返回结构 |
| `sparkweave/core/capability_protocol.py` | Capability 协议和 manifest |
| `sparkweave/runtime/` | 运行时选择、turn 管理、上下文构造、LangGraph runner |
| `sparkweave/graphs/` | `chat`、`deep_solve`、`deep_question`、`deep_research`、`visualize`、`math_animator` 图实现 |
| `sparkweave/tools/` | 内置工具和工具注册表 |
| `sparkweave/services/` | LLM、Embedding、RAG、搜索、会话、记忆、Notebook、SparkBot、OCR、设置等服务 |
| `sparkweave/knowledge/` | 知识库目录管理、初始化、增量导入和进度 |
| `sparkweave/api/` | FastAPI 应用和路由 |
| `sparkweave/plugins/` | 可选 playground 插件 manifest 发现 |
| `sparkweave/sparkbot/` | SparkBot 长期智能体的专用技能、MCP、媒体和工作区工具 |

## 运行时相关文件

| 路径 | 说明 |
| --- | --- |
| `sparkweave/runtime/policy.py` | 根据 capability、显式 runtime 和环境变量选择 `langgraph` 或兼容层 |
| `sparkweave/runtime/routing.py` | `RuntimeRoutingTurnManager`，把 turn 操作路由到 LangGraph 或兼容运行时 |
| `sparkweave/runtime/turn_runtime.py` | `LangGraphTurnRuntimeManager`，负责创建 turn、持久化事件、刷新记忆 |
| `sparkweave/runtime/context_enrichment.py` | 构造 `UnifiedContext`，注入会话历史、记忆、Notebook、附件和配置 |
| `sparkweave/runtime/runner.py` | `LangGraphRunner`，按 capability 调用具体图 |
| `sparkweave/runtime/orchestrator.py` | 兼容 orchestrator，可直接流式执行 capability |
| `sparkweave/runtime/registry/capability_registry.py` | 将 app manifest 包装成可执行 capability |

session、turn、事件 `seq`、SQLite 表和 WebSocket 续流见 [会话、Turn 与事件持久化](./sessions-and-turns.md)。

## 能力图

| Capability | 文件 | 核心阶段 |
| --- | --- | --- |
| `chat` | `sparkweave/graphs/chat.py` | coordinating、thinking、acting、responding |
| `deep_solve` | `sparkweave/graphs/deep_solve.py` | planning、reasoning、writing |
| `deep_question` | `sparkweave/graphs/deep_question.py` | ideation、generation |
| `deep_research` | `sparkweave/graphs/deep_research.py` | rephrasing、decomposing、researching、reporting |
| `visualize` | `sparkweave/graphs/visualize.py` | analyzing、generating、reviewing |
| `math_animator` | `sparkweave/graphs/math_animator.py` | concept_analysis、concept_design、code_generation、code_retry、summary、render_output |

## 内置工具

内置工具定义在 `sparkweave/tools/builtin.py`，由 `sparkweave/tools/registry.py` 注册。协议、别名、prompt hints 和能力图调用方式见 [Tools 工具系统](./tools.md)。

| Tool | 后端服务 | 说明 |
| --- | --- | --- |
| `rag` | `sparkweave/services/rag.py` | 知识库检索与回答 |
| `web_search` | `sparkweave/services/search.py` | 联网搜索与引用 |
| `code_execution` | `sparkweave/services/code_execution.py` | 受限 Python 执行 |
| `reason` | `sparkweave/services/reasoning.py` | 专用推理 LLM 调用 |
| `brainstorm` | `sparkweave/services/reasoning.py` | 广度想法探索 |
| `paper_search` | `sparkweave/services/papers.py` | arXiv 论文搜索 |
| `geogebra_analysis` | `sparkweave/services/vision.py` | 图像几何分析与 GeoGebra 命令 |

## API 路由

FastAPI 应用在 `sparkweave/api/main.py` 中组装。主要路由：

| 前缀 | 文件 | 说明 |
| --- | --- | --- |
| `/api/v1/ws` | `routers/unified_ws.py` | 新运行时统一 WebSocket 入口 |
| `/api/v1/sessions` | `routers/sessions.py` | 会话、turn 和 quiz result 管理 |
| `/api/v1/settings` | `routers/settings.py` | UI 设置、模型 catalog、连接测试 |
| `/api/v1/system` | `routers/system.py` | 系统状态、运行拓扑、连接测试 |
| `/api/v1/knowledge` | `routers/knowledge.py` | 知识库创建、上传、进度、链接文件夹 |
| `/api/v1/notebook` | `routers/notebook.py` | Notebook 和记录管理 |
| `/api/v1/question-notebook` | `routers/question_notebook.py` | 题目记录和分类 |
| `/api/v1/plugins` | `routers/plugins_api.py` | 工具、能力、playground 插件列表与执行 |
| `/api/v1/sparkbot` | `routers/sparkbot.py` | SparkBot 实例、Soul 模板、渠道、文件、历史和聊天 |
| `/api/v1/guide` | `routers/guide.py` | 旧版导学会话和 HTML 页面 |
| `/api/v1/guide/v2` | `routers/guide_v2.py` | Guide V2 学习路径、资源、证据、报告和课程包 |
| `/api/v1/co_writer` | `routers/co_writer.py` | 协作写作与流式编辑 |
| `/api/v1/vision` | `routers/vision_solver.py` | 图像题解析 |

## 前端

| 路径 | 说明 |
| --- | --- |
| `web/src/router.tsx` | TanStack Router 路由和兼容重定向 |
| `web/src/lib/api.ts` | 后端 HTTP、SSE、WebSocket URL 和 API 函数 |
| `web/src/hooks/useChatRuntime.ts` | `/api/v1/ws` 聊天运行时 hook |
| `web/src/lib/capabilities.ts` | 前端 capability、默认工具和默认配置 |
| `web/src/lib/types.ts` | 前后端契约类型 |
| `web/src/pages/` | Chat、Knowledge、Notebook、Settings、Agents 等页面 |
| `web/src/components/chat/` | 聊天工作台组件 |
| `web/src/components/results/` | 可视化、数学动画结果渲染 |

## 数据目录

| 路径 | 说明 |
| --- | --- |
| `data/user/chat_history.db` | SQLite 会话、消息、turn event、题目本数据 |
| `data/user/settings/` | UI 设置和模型 catalog |
| `data/user/workspace/chat/` | chat/deep_solve/deep_question/deep_research/math_animator 产物 |
| `data/user/workspace/guide/` | 旧版导学 session、Guide V2 session、learner memory 和模板 |
| `data/user/workspace/notebook/` | Notebook JSON 文件和索引 |
| `data/memory/` | `SUMMARY.md` 和 `PROFILE.md` |
| `data/memory/SparkBots/` | SparkBot 配置、工作区、session、cron、日志和私有记忆 |
| `data/knowledge_bases/` | 知识库 raw 文件、索引、metadata、配置 |

这些目录保存本地运行状态，通常不应提交到 Git。
