# 功能级代码地图

本文从“用户能看到的功能”出发，反向标注前端页面、API 路由、后端服务、数据落点和已有文档。它不是宣传稿，而是后续逐功能补文档时的索引底稿。

> 维护原则：新增功能时先把入口补到本文，再补专题文档；删除或合并入口时也要同步删掉本文中的旧描述。

## 总览

SparkWeave 当前前端主页面集中在 `web/src/pages/`，后端 HTTP/WebSocket API 由 `sparkweave/api/main.py` 统一挂载，CLI 由 `sparkweave_cli/main.py` 组装。

```text
web/src/router.tsx
  -> web/src/pages/*
  -> web/src/lib/api.ts / web/src/hooks/useApiQueries.ts
  -> sparkweave/api/routers/*
  -> sparkweave/services/* / sparkweave/graphs/*
  -> data/*
```

## 前端页面与功能归属

| 页面 | 路由 | 主要代码 | 后端能力 |
| --- | --- | --- | --- |
| 对话工作台 | `/chat`、`/chat/$sessionId` | `web/src/pages/ChatPage.tsx`、`web/src/hooks/useChatRuntime.ts`、`web/src/components/chat/*` | `/api/v1/ws`、`chat` capability、sessions、RAG、Notebook 引用 |
| 题目实验室 | `/question` | `web/src/pages/QuestionLabPage.tsx`、`web/src/components/quiz/QuizViewer.tsx` | `/api/v1/question/generate`、`/api/v1/question/mimic`、`question-notebook` |
| 图像解题 | `/vision`、兼容 `/vision-solver`、`/geogebra` | `web/src/pages/VisionPage.tsx` | `/api/v1/vision/analyze`、`/api/v1/vision/solve`、OCR、GeoGebra 分析 |
| 资料库 | `/knowledge` | `web/src/pages/KnowledgePage.tsx` | `/api/v1/knowledge/*`、RAG、Milvus、文档管理 |
| 笔记本 | `/notebook` | `web/src/pages/NotebookPage.tsx` | `/api/v1/notebook/*`、`/api/v1/question-notebook/*` |
| 学习画像 | `/memory` | `web/src/pages/MemoryPage.tsx`、`web/src/components/profile/LearningEffectLoopCard.tsx` | `/api/v1/memory`、`/api/v1/learner-profile`、`/api/v1/learning-effect` |
| 导学路线 | `/guide` | `web/src/pages/GuidePage.tsx` | `/api/v1/guide/*`、`/api/v1/guide/v2/*` |
| 协作写作 | `/co-writer`、兼容 `/co_writer`、`/cowriter` | `web/src/pages/CoWriterPage.tsx` | `/api/v1/co_writer/*` |
| SparkBot / Agents | `/agents`、`/agents/$botId/chat`、兼容 `/sparkbot` | `web/src/pages/AgentsPage.tsx` | `/api/v1/sparkbot/*` |
| 插件实验室 | `/playground` | `web/src/pages/PlaygroundPage.tsx` | `/api/v1/plugins/*` |
| 设置 | `/settings` | `web/src/pages/SettingsPage.tsx` | `/api/v1/settings/*`、`/api/v1/system/*` |

兼容路由仍保留在 `web/src/router.tsx`，例如 `/solver`、`/research`、`/visualize`、`/math_animator` 会跳转或复用对话页能力，而不是独立页面。

## 后端 API 功能索引

后端路由由 `sparkweave/api/main.py` 挂载。当前主路由如下：

| API 前缀 | 路由文件 | 功能事实 |
| --- | --- | --- |
| `/api/v1/ws` | `sparkweave/api/routers/unified_ws.py` | 新运行时统一 WebSocket 入口，启动 turn、订阅事件、取消 turn |
| `/api/v1/chat` | `sparkweave/api/routers/chat.py` | 兼容旧聊天 WebSocket 和会话查询 |
| `/api/v1/solve` | `sparkweave/api/routers/solve.py` | 兼容旧解题 WebSocket 和会话查询 |
| `/api/v1/question` | `sparkweave/api/routers/question.py` | 题目生成与仿题 WebSocket |
| `/api/v1/knowledge` | `sparkweave/api/routers/knowledge.py` | 知识库创建、上传、重建、诊断、文档预览、向量块、评测、linked folder |
| `/api/v1/dashboard` | `sparkweave/api/routers/dashboard.py` | 最近活动与活动详情 |
| `/api/v1/co_writer` | `sparkweave/api/routers/co_writer.py` | 协作写作、React 式编辑、流式编辑、自动批注、历史和导出 |
| `/api/v1/notebook` | `sparkweave/api/routers/notebook.py` | 主 Notebook 的列表、创建、记录保存、流式摘要和 CRUD |
| `/api/v1/question-notebook` | `sparkweave/api/routers/question_notebook.py` | 题目本 entries、分类、收藏、追问 session 绑定 |
| `/api/v1/guide` | `sparkweave/api/routers/guide.py` | 旧版导学 HTML session、导航、重试、修复和 WebSocket |
| `/api/v1/guide/v2` | `sparkweave/api/routers/guide_v2.py` | Guide V2 session、模板、画像对话、诊断、学习计划、资源生成、报告、课程包 |
| `/api/v1/learning-effect` | `sparkweave/api/routers/learning_effect.py` | 学习效果报告、知识点、下一步行动、学习事件、行动完成 |
| `/api/v1/learner-profile` | `sparkweave/api/routers/learner_profile.py` | 统一学习画像、证据预览、证据账本、画像校准 |
| `/api/v1/memory` | `sparkweave/api/routers/memory.py` | `PROFILE.md` / `SUMMARY.md` 读取、写入、刷新和清空 |
| `/api/v1/sessions` | `sparkweave/api/routers/sessions.py` | 会话列表、详情、重命名、删除和 quiz result 写入 |
| `/api/v1/settings` | `sparkweave/api/routers/settings.py` | UI 设置、模型 catalog、侧边栏设置、Provider 检测任务和 setup tour |
| `/api/v1/system` | `sparkweave/api/routers/system.py` | 运行拓扑、系统状态、LLM/Embedding/Search/OCR/TTS 快速检测、TTS preview |
| `/api/v1/plugins` | `sparkweave/api/routers/plugins_api.py` | 插件列表、工具执行、工具流式执行和 capability 流式执行 |
| `/api/v1/agent-config` | `sparkweave/api/routers/agent_config.py` | 智能体配置和 agent 类型详情 |
| `/api/v1/vision` | `sparkweave/api/routers/vision_solver.py` | 图像分析和图像题 WebSocket 解答 |
| `/api/v1/sparkbot` | `sparkweave/api/routers/sparkbot.py` | SparkBot soul、实例、渠道 schema、文件、历史和 WebSocket |

## CLI 功能索引

CLI 入口在 `sparkweave_cli/main.py`，子命令分散在 `sparkweave_cli/*.py`。

| 命令组 | 代码 | 说明 |
| --- | --- | --- |
| `run` | `sparkweave_cli/main.py` | 直接运行指定 capability |
| `serve` | `sparkweave_cli/main.py` | 启动 FastAPI 服务 |
| `chat` | `sparkweave_cli/chat.py` | 单轮或交互式对话，复用 turn runtime |
| `kb` | `sparkweave_cli/kb.py` | 知识库 list/info/doctor/create/add/reindex/delete/search/eval |
| `memory` | `sparkweave_cli/memory.py` | 查看和清空 Memory |
| `notebook` | `sparkweave_cli/notebook.py` | Notebook list/create/show/add-md/replace-md/remove-record |
| `bot` | `sparkweave_cli/bot.py` | SparkBot list/start/stop/create |
| `plugin` | `sparkweave_cli/plugin.py` | 插件 list/info |
| `config` | `sparkweave_cli/config_cmd.py` | 查看当前配置 |
| `provider` | `sparkweave_cli/provider_cmd.py` | provider login |
| `session` | `sparkweave_cli/session_cmd.py` | session list/show/open/delete/rename |
| `learning-effect` | `sparkweave_cli/learning_effect.py` | 学习效果 summary |
| `competition-*` | `sparkweave_cli/main.py` | 比赛检查、模板、演示、打包、验证和 preflight |

## 功能细分

### 1. 对话工作台与统一运行时

| 项 | 事实 |
| --- | --- |
| 前端 | `ChatPage.tsx`、`Composer.tsx`、`MessageBubble.tsx`、`AgentCollaborationPanel.tsx`、`TaskSnapshot.tsx` |
| API | `/api/v1/ws`、`/api/v1/sessions` |
| 后端 | `runtime/turn_runtime.py`、`runtime/context_enrichment.py`、`runtime/runner.py`、`graphs/chat.py` |
| 数据 | `data/user/chat_history.db` 中 sessions、messages、turns、turn_events |
| 重点 | 一次 turn 会构造 `UnifiedContext`、注入记忆/画像/引用、运行 LangGraph capability、持久化事件并写 assistant message |
| 文档 | `docs/runtime-flow.md`、`docs/sessions-and-turns.md`、`docs/core-ai-code-facts.md`、`docs/agent-runtime-design.md` |

### 2. 多能力智能体

| Capability | 后端图 | 前端入口 | 说明 |
| --- | --- | --- | --- |
| `chat` | `graphs/chat.py` | 对话页默认 | 可调用工具，可受控委派 specialist |
| `deep_solve` | `graphs/deep_solve.py` | 对话能力切换/兼容入口 | 解题、推导、验证 |
| `deep_question` | `graphs/deep_question.py` | 题目实验室/对话委派 | 自定义题目和仿题 |
| `deep_research` | `graphs/deep_research.py` | 对话能力切换/导学 | 调研、报告、学习路径 |
| `visualize` | `graphs/visualize.py` | 对话委派/结果渲染 | SVG、Chart.js、Mermaid |
| `math_animator` | `graphs/math_animator.py` | 对话委派/导学资源 | Manim 代码和视频/图片产物 |

能力清单由 `sparkweave/app/facade.py` 暴露，运行时分派由 `sparkweave/runtime/runner.py` 负责。能力配置 schema 在 `sparkweave/services/validation.py`。多智能体协调、specialist 委派、协作事件和边界见 `docs/agent-runtime-design.md`。

### 3. 知识库与 RAG

| 项 | 事实 |
| --- | --- |
| 前端 | `KnowledgePage.tsx`、`RagEvidenceChain.tsx` |
| API | `/api/v1/knowledge/*` |
| 服务 | `services/rag.py`、`services/rag_support/*`、`knowledge/manager.py`、`knowledge/add_documents.py`、`knowledge/reindex.py`、`knowledge/document_inventory.py` |
| 存储 | `data/knowledge_bases/<kb>/raw/`、`milvus_storage/metadata.json`、Milvus collection |
| 重点 | 支持上传、预览、文档删除、向量块管理、重建索引、诊断、RAG 评测、linked folder |
| 文档 | `docs/knowledge-base.md`、`docs/milvus-rag.md`、`docs/rag-improvement-design.md`、`docs/rag-system-design.md`、`docs/core-ai-code-facts.md` |

当前 RAG 由 `RAGService` 串联自适应检索策略、可选 HyDE、受控 Agentic RAG、Milvus/LlamaIndex pipeline、keyword rerank 和 Context Pack。

### 4. 学习画像、Memory 与学习效果评估

| 项 | 事实 |
| --- | --- |
| 前端 | `MemoryPage.tsx`、`LearningEffectLoopCard.tsx` |
| API | `/api/v1/memory`、`/api/v1/learner-profile`、`/api/v1/learning-effect` |
| 服务 | `memory.py`、`learner_evidence.py`、`learner_profile.py`、`profile_context.py`、`learning_effect.py` |
| 存储 | `data/memory/PROFILE.md`、`data/memory/SUMMARY.md`、`data/user/learner_profile/evidence.jsonl`、`profile.json` |
| 重点 | Memory 是长期对话背景；Learner Profile 是多源证据聚合画像；Learning Effect 基于证据生成可解释评估与下一步行动 |
| 文档 | `docs/learner-profile-design.md`、`docs/learning-effect-closed-loop-design.md`、`docs/notebook-memory-context.md`、`docs/learner-profile-memory-design.md` |

画像会通过 `ProfileContextInjector` 被压缩进模型上下文，不只是前端展示。

### 5. 导学路线 Guide / Guide V2

| 项 | 事实 |
| --- | --- |
| 前端 | `GuidePage.tsx` |
| API | `/api/v1/guide/*`、`/api/v1/guide/v2/*` |
| 服务 | `guide_generation.py`、`guide_v2.py` |
| 存储 | `data/user/workspace/guide/` |
| 重点 | 旧版 Guide 以 HTML 页面导学为主；Guide V2 以 session、诊断、画像对话、任务、资源、报告、课程包为主 |
| 文档 | `docs/guided-learning.md`、`docs/demo-course-templates.md`、`docs/competition-demo-runbook.md` |

Guide V2 会和学习画像、题目、资源生成、Notebook 保存形成闭环。

### 6. 题目生成与题目本

| 项 | 事实 |
| --- | --- |
| 前端 | `QuestionLabPage.tsx`、`QuizViewer.tsx` |
| API | `/api/v1/question/generate`、`/api/v1/question/mimic`、`/api/v1/question-notebook/*` |
| 图/服务 | `graphs/deep_question.py`、`services/question.py`、`services/question_generation.py` |
| 数据 | 题目本在 `data/user/chat_history.db`，不是主 Notebook JSON |
| 重点 | 支持 custom/mimic；题目类型包括 choice、true_false、fill_blank、written、coding 等；答题结果可回写题目本和画像证据 |
| 文档 | `docs/question-workflows.md`、`docs/question-parsing-and-mimic.md` |

### 7. Notebook

| 项 | 事实 |
| --- | --- |
| 前端 | `NotebookPage.tsx`、`ContextReferencesPanel.tsx` |
| API | `/api/v1/notebook/*` |
| 服务 | `notebook.py`、`notebook_summary.py` |
| 存储 | `data/user/workspace/notebook/notebooks_index.json`、`<notebook_id>.json` |
| 重点 | 主 Notebook 使用短 UUID 字符串；题目本分类 ID 是整数，二者不能混用 |
| 文档 | `docs/notebook-memory-context.md` |

### 8. 视觉输入、OCR 与 GeoGebra

| 项 | 事实 |
| --- | --- |
| 前端 | `VisionPage.tsx` |
| API | `/api/v1/vision/analyze`、`/api/v1/vision/solve` |
| 服务 | `vision.py`、`vision_input.py`、`ocr.py` |
| 工具 | `geogebra_analysis` |
| 文档 | `docs/vision-ocr-geogebra.md`、`docs/iflytek-integration.md` |

图像解题会涉及 OCR、视觉模型、GeoGebra 命令和 tutor 式讲解。OCR provider 配置在设置页和 `services/config.py` 中管理。

### 9. 数学动画、可视化、音频讲解

| 项 | 事实 |
| --- | --- |
| 前端 | `MathAnimatorViewer.tsx`、`VisualizationViewer.tsx`、`AudioNarrationViewer.tsx` |
| 后端 | `graphs/math_animator.py`、`graphs/visualize.py`、`services/math_animator_support/*`、`services/tts.py` |
| 数据 | `data/user/workspace/chat/math_animator/<turn_id>/` |
| 重点 | Math Animator 生成 Manim 代码并尝试渲染视频/图片；TTS 可为讲解生成音频；Visualize 生成 SVG/Chart.js/Mermaid |
| 文档 | `docs/capabilities.md`、`docs/vision-ocr-geogebra.md`、`docs/configuration.md` |

### 10. 联网搜索、公开视频与论文搜索

| 项 | 事实 |
| --- | --- |
| 工具 | `web_search`、`external_video_search`、`paper_search` |
| 服务 | `search.py`、`search_support/providers/*`、`video_search.py`、`papers.py` |
| 前端渲染 | `ExternalVideoViewer.tsx`、`ResourceEvidenceButton.tsx` |
| 重点 | 普通搜索 provider 包括 Brave、Serper、Tavily、Jina、Exa、Perplexity、OpenRouter、SearXNG、DuckDuckGo、Baidu、iFlytek Spark 等；公开视频搜索当前作为工具链路，不是 LangGraph capability |
| 文档 | `docs/tools.md`、`docs/settings-and-providers.md`、`docs/iflytek-integration.md` |

### 11. 协作写作

| 项 | 事实 |
| --- | --- |
| 前端 | `CoWriterPage.tsx` |
| API | `/api/v1/co_writer/*` |
| 服务 | `co_writer.py` |
| 功能 | edit、edit_react、stream、automark、history、tool_calls、export markdown |
| 文档 | `docs/services.md`、`docs/cli-and-api.md` |

### 12. SparkBot / Agents

| 项 | 事实 |
| --- | --- |
| 前端 | `AgentsPage.tsx` |
| API | `/api/v1/sparkbot/*` |
| 服务 | `sparkbot.py` |
| 数据 | `data/memory/SparkBots/` |
| 重点 | SparkBot 是长期 bot 实例系统，有 soul、渠道、文件、历史、WebSocket、heartbeat、cron、team 等逻辑，不走普通 `UnifiedContext` turn runtime |
| 文档 | `docs/sparkbot-agents.md` |

### 13. 设置、Provider 与系统诊断

| 项 | 事实 |
| --- | --- |
| 前端 | `SettingsPage.tsx` |
| API | `/api/v1/settings/*`、`/api/v1/system/*` |
| 服务 | `config.py`、`settings.py`、`config_test_runner.py`、`diagnostics.py`、`embedding_support/*` |
| 存储 | `.env`、`data/user/settings/main.yaml`、`agents.yaml`、模型 catalog |
| 重点 | 管理 LLM、Embedding、Search、OCR、TTS、UI、侧边栏、setup tour 和连接检测 |
| 文档 | `docs/settings-and-providers.md`、`docs/system-diagnostics.md`、`docs/configuration.md` |

### 14. 插件实验室

| 项 | 事实 |
| --- | --- |
| 前端 | `PlaygroundPage.tsx` |
| API | `/api/v1/plugins/*` |
| 后端 | `plugins/loader.py`、`api/routers/plugins_api.py` |
| 重点 | 当前主要负责 manifest 发现、工具执行、流式工具执行和 capability 流式执行 playground |
| 文档 | `docs/plugin-development.md` |

### 15. 比赛打包与交付检查

| 项 | 事实 |
| --- | --- |
| CLI | `competition-check`、`competition-templates`、`competition-demo`、`competition-package`、`competition-verify`、`competition-preflight` |
| 脚本 | `scripts/check_competition_readiness.py`、`scripts/export_competition_package.py`、`scripts/verify_competition_package.py` |
| 文档 | `docs/competition-roadmap.md`、`docs/competition-demo-runbook.md`、`docs/demo-quickstart.md`、`docs/ai-coding-statement.md` |

## 维护清单

本文只保留“功能到代码”的索引。新增或调整用户入口时，同步检查：

1. 前端路由、页面和 API client 是否已列入“前端页面与功能归属”。
2. 后端 router 是否已列入“后端 API 功能索引”。
3. CLI 命令是否已列入“CLI 功能索引”。
4. 功能细分中的数据落点是否仍准确。
5. 专题文档是否已经存在，若没有，应补到对应功能的“文档”行，而不是在本文展开长篇说明。

## 验证方式

本文根据以下代码入口核对：

- `sparkweave/api/main.py`
- `sparkweave/api/routers/*.py`
- `sparkweave_cli/*.py`
- `web/src/router.tsx`
- `web/src/lib/api.ts`
- `web/src/hooks/useApiQueries.ts`
- `sparkweave/services/*`
- `sparkweave/graphs/*`

如果某个专题已经有独立文档，本文只保留链接和一句代码事实，避免重新变成大而散的总文档。
