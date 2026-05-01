# 服务层与数据流

`sparkweave/services/` 是后端能力的支撑层。运行时和图节点不直接处理所有外部系统细节，而是通过服务层访问模型、搜索、RAG、会话、记忆、Notebook、导学、SparkBot、OCR 和文件路径。

## 服务总览

| 模块 | 关键文件 | 说明 |
| --- | --- | --- |
| 配置解析 | `services/config.py` | `.env`、模型 catalog、provider spec、运行时配置解析 |
| LLM | `services/llm.py`、`sparkweave/llm/factory.py` | 文本生成、流式生成、LangChain chat model 创建 |
| Embedding | `services/embedding.py`、`services/embedding_support/` | 统一 embedding 配置、adapter 和批处理 client |
| RAG | `services/rag.py`、`services/rag_support/` | 知识库检索 facade、pipeline factory、LlamaIndex pipeline |
| 搜索 | `services/search.py`、`services/search_support/` | 联网搜索 provider、引用、答案整合 |
| 知识库 | `sparkweave/knowledge/` | 知识库目录、metadata、初始化、上传、同步 |
| 会话 | `services/session.py`、`services/session_store.py` | runtime manager facade、SQLite 会话和事件持久化 |
| 记忆 | `services/memory.py` | `SUMMARY.md`、`PROFILE.md` 两文件记忆 |
| Notebook | `services/notebook.py`、`services/notebook_summary.py` | Notebook JSON 存储、记录管理、摘要生成 |
| 上下文 | `services/context.py` | 会话历史压缩和 Notebook 引用分析 |
| 导学 | `services/guide_generation.py`、`services/guide_v2.py` | 旧版 HTML 导学、Guide V2 学习路径、证据闭环和资源生成 |
| SparkBot | `services/sparkbot.py`、`sparkweave/sparkbot/` | 长期助教实例、工作区、渠道、工具、heartbeat、cron 和 team |
| OCR | `services/ocr.py` | 讯飞 OCR、扫描版 PDF 文本提取 |
| 视觉 | `services/vision.py`、`services/vision_input.py` | 图像题解析和 GeoGebra pipeline |
| 数学动画 | `services/math_animator.py`、`services/math_animator_support/` | Manim 渲染、重试、视觉复核 |
| 路径 | `services/paths.py` | `data/user` 下的运行目录、产物白名单 |
| 诊断 | `services/diagnostics.py` | 常见 provider 错误的人类可读解释 |

## 配置解析

主配置文件：

```text
sparkweave/services/config.py
```

配置来源：

1. `.env`
2. `data/user/settings/model_catalog.json` 或同类 catalog 文件
3. `data/user/settings/*.yaml`
4. 环境变量
5. provider 默认值

核心对象：

| 对象 | 说明 |
| --- | --- |
| `ProviderSpec` | LLM provider 元数据，如默认地址、默认模型、是否本地、是否 OAuth |
| `EmbeddingProviderSpec` | Embedding provider 元数据和 adapter 类型 |
| `EnvStore` | `.env` 读取、写入和摘要 |
| `ModelCatalogService` | 设置页模型 catalog 的加载、保存和 active profile/model |
| `ResolvedLLMConfig` | 解析后的 LLM 运行配置 |
| `ResolvedEmbeddingConfig` | 解析后的 Embedding 运行配置 |
| `ResolvedSearchConfig` | 解析后的搜索运行配置 |
| `LLMConfig` | 下游 LLM 服务使用的缓存配置 |

关键函数：

| 函数 | 说明 |
| --- | --- |
| `resolve_llm_runtime_config()` | 从 catalog/env/provider spec 解析 LLM |
| `resolve_embedding_runtime_config()` | 解析 Embedding adapter、模型、维度和凭证 |
| `resolve_search_runtime_config()` | 解析搜索 provider、fallback 和凭证状态 |
| `get_llm_config()` | 返回缓存后的 LLM 配置 |
| `clear_llm_config_cache()` | 设置变更后清理缓存 |
| `get_token_limit_kwargs()` | 根据模型决定 `max_tokens` 或 `max_completion_tokens` |

设置页调用 `/api/v1/settings/apply` 后会写入配置并清理相关 runtime cache。
配置解析、catalog、Provider 推断和设置页 API 的完整说明见 [设置与 Provider 配置](./settings-and-providers.md)。

## LLM

LLM 层负责把统一配置转成具体调用。

常见调用方：

- `ChatGraph`、`DeepSolveGraph`、`DeepQuestionGraph` 等图节点。
- `CodeExecutionTool` 的代码生成。
- `MemoryService` 自动刷新记忆。
- `NotebookAnalysisAgent` 上下文分析。

常见入口：

```text
sparkweave/services/llm.py
sparkweave/llm/factory.py
sparkweave/llm/messages.py
```

设计要点：

- provider 选择尽量在 `services/config.py` 统一完成。
- LangGraph 节点通常使用 `create_chat_model()` 得到 LangChain chat model。
- 低层普通文本补全和流式输出由 `services/llm.py` 暴露。

## Embedding

Embedding 配置入口：

```text
sparkweave/services/embedding_support/config.py
sparkweave/services/embedding_support/client.py
```

支持的 adapter：

| Provider | Adapter |
| --- | --- |
| `openai`、`azure_openai`、`custom`、`vllm` | `OpenAICompatibleEmbeddingAdapter` |
| `iflytek_spark` | `IflytekSparkEmbeddingAdapter` |
| `jina` | `JinaEmbeddingAdapter` |
| `cohere` | `CohereEmbeddingAdapter` |
| `ollama` | `OllamaEmbeddingAdapter` |

`EmbeddingClient.embed()` 会按 `batch_size` 分批请求，并可通过 `progress_callback` 上报批处理进度。知识库索引会记录 embedding 模型和维度，模型或维度变更时，`KnowledgeBaseManager` 会标记 `embedding_mismatch` 和 `needs_reindex`。

## RAG 与知识库

RAG facade：

```text
sparkweave/services/rag.py
```

当前默认 provider：

```text
llamaindex
```

关键目录：

```text
data/knowledge_bases/<kb_name>/
  raw/
  images/
  content_list/
  llamaindex_storage/
  metadata.json
```

配置索引：

```text
data/knowledge_bases/kb_config.json
```

关键类：

| 类 | 文件 | 说明 |
| --- | --- | --- |
| `KnowledgeBaseManager` | `knowledge/manager.py` | 知识库列表、默认库、metadata、链接文件夹 |
| `KnowledgeBaseInitializer` | `knowledge/initializer.py` | 创建和初始化知识库 |
| `DocumentAdder` | `knowledge/add_documents.py` | 向现有知识库添加文件 |
| `RAGService` | `services/rag_support/service.py` | 搜索、初始化、删除统一服务 |
| `LlamaIndexPipeline` | `services/rag_support/pipelines/llamaindex.py` | LlamaIndex 索引和检索实现 |

知识库 API 位于 `sparkweave/api/routers/knowledge.py`，支持创建、上传、进度、默认库、配置、链接本地文件夹和同步。
完整生命周期、HTTP API、进度流和 linked folder 说明见 [知识库详解](./knowledge-base.md)。

## 搜索

搜索 facade：

```text
sparkweave/services/search.py
```

Provider 注册：

```text
sparkweave/services/search_support/providers/
```

支持的 provider 在 `services/config.py` 中维护：

```text
brave
tavily
jina
searxng
duckduckgo
perplexity
serper
iflytek_spark
```

搜索结果结构在 `services/search_support/types.py`，答案整合在 `services/search_support/consolidation.py`。

注意事项：

- `brave`、`tavily`、`jina` 缺少 API key 时会回退到 `duckduckgo`。
- `searxng` 缺少 base URL 时会回退到 `duckduckgo`。
- `perplexity`、`serper`、`iflytek_spark` 缺少凭证会标记为 missing credentials。
- `iflytek_spark` 使用科大讯飞 ONE SEARCH，凭证为 Search API 的 `APIPassword`。
- `exa`、`baidu`、`openrouter` 当前标记为 deprecated/unsupported。

## 会话与事件持久化

运行时会话 facade：

```text
sparkweave/services/session.py
```

SQLite store：

```text
sparkweave/services/session_store.py
data/user/chat_history.db
```

主要表：

| 表 | 说明 |
| --- | --- |
| `sessions` | 会话元信息和偏好 |
| `messages` | 用户、assistant、system 消息 |
| `turns` | 单次请求状态 |
| `turn_events` | 流式事件，带 `seq` |
| `notebook_entries` | 题目本记录 |
| `notebook_categories` | 题目分类 |
| `notebook_entry_categories` | 题目与分类关系 |

`append_turn_event()` 会为事件补 `seq`，WebSocket 断线后可以用 `after_seq` 或 `resume_from` 续流。
更完整的 session/turn 生命周期、表结构和恢复机制见 [会话、Turn 与事件持久化](./sessions-and-turns.md)。

## 记忆

记忆服务：

```text
sparkweave/services/memory.py
```

存储文件：

```text
data/memory/SUMMARY.md
data/memory/PROFILE.md
```

职责：

- `PROFILE.md`：稳定身份、偏好、知识水平。
- `SUMMARY.md`：学习旅程、当前关注点、已完成内容、开放问题。
- `build_memory_context()`：把记忆注入 `UnifiedContext.memory_context`。
- `refresh_from_turn()`：每轮 assistant 回复后自动尝试更新记忆。
- `refresh_from_session()`：从最近会话手动刷新。

Memory 的两文件模型、迁移规则、API、自动刷新和 prompt 注入细节见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)。

## Notebook

Notebook 服务：

```text
sparkweave/services/notebook.py
```

存储目录：

```text
data/user/workspace/notebook/
  notebooks_index.json
  <notebook_id>.json
```

记录类型：

```text
solve
question
research
co_writer
chat
guided_learning
```

Notebook 可以被：

- 前端页面直接管理。
- CLI 导入 Markdown。
- Chat turn 通过 `notebook_references` 引用。
- `NotebookAnalysisAgent` 摘要后注入到 prompt。

主 Notebook 与题目本的边界、记录结构、保存入口、引用分析和排查方式见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)。

## 导学

导学服务：

```text
sparkweave/services/guide_generation.py
sparkweave/services/guide_v2.py
```

`guide_generation.py` 维护兼容旧入口的 HTML 导学 session；`guide_v2.py` 维护新的结构化学习路径、课程模板、任务队列、学习证据、掌握度、错因闭环、资源生成和报告/课程包。完整链路见 [导学空间与 Guide V2](./guided-learning.md)。

## SparkBot

SparkBot 服务入口：

```text
sparkweave/services/sparkbot.py
sparkweave/sparkbot/tools.py
sparkweave/sparkbot/mcp.py
sparkweave/sparkbot/media.py
sparkweave/sparkbot/transcription.py
```

它维护的是长期运行的 Bot 实例，而不是主聊天 runtime 的一次 turn。核心职责包括：

- `SparkBotManager`：加载/保存 `config.yaml`、迁移旧目录、启动停止 Bot、读写工作区文件、记录历史。
- `SparkBotAgentLoop`：处理 Web 和外部渠道消息、构造 SparkBot prompt、执行 JSON tool calls、处理 `/new`、`/team`、`/btw`、`/cron` 等命令。
- `SparkBotChannelManager`：按 `ChannelsConfig` 启动 Telegram、Slack、Discord、Email、Feishu、Matrix 等渠道。
- `SparkBotWorkspaceContext`：读取 `SOUL.md`、`USER.md`、`TOOLS.md`、`AGENTS.md`、技能、全局 Memory 和 Bot 私有 Memory。
- `SparkBotHeartbeatService` 与 `SparkBotCronService`：主动提醒、后台 turn 和定时任务。

默认持久化位置是 `data/memory/SparkBots/<bot_id>/`，详情见 [SparkBot 与 Agents 工作台](./sparkbot-agents.md)。

## OCR 与扫描版 PDF

OCR 服务：

```text
sparkweave/services/ocr.py
```

支持科大讯飞 OCR：

- 图片识别：`recognize_image_with_iflytek()`
- PDF OCR：`ocr_pdf_with_iflytek()`
- 配置检查：`is_iflytek_ocr_configured()`

知识库 PDF 解析可以根据 `SPARKWEAVE_PDF_OCR_STRATEGY` 选择 OCR 优先或自动 fallback。
图像输入、VisionSolverAgent、GeoGebra 工具和 OCR fallback 的完整链路见 [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md)。

常见配置：

```env
SPARKWEAVE_OCR_PROVIDER=iflytek
SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first
IFLYTEK_OCR_APPID=
IFLYTEK_OCR_API_KEY=
IFLYTEK_OCR_API_SECRET=
```

## 路径与产物安全

路径服务：

```text
sparkweave/services/paths.py
```

所有运行产物默认写入：

```text
data/user/
```

`SafeOutputStaticFiles` 在 `sparkweave/api/main.py` 挂载 `/api/outputs` 时会调用 `PathService.is_public_output_path()`，只暴露白名单产物，例如：

- Co-Writer 音频。
- Deep Solve artifacts。
- Math Animator artifacts。
- Code execution 公开产物。

私有后缀如 `.json`、`.sqlite`、`.db`、`.md`、`.yaml`、`.py`、`.log` 不会被静态暴露。

## 服务层开发原则

- 新 provider 优先接入 config resolver，再接入对应 adapter/provider。
- 新工具应通过 `sparkweave/tools/builtin.py` 暴露，并在服务层封装外部 API；完整步骤见 [Tools 工具系统](./tools.md)。
- 新数据目录应通过 `PathService` 管理，不要在图节点里硬编码路径。
- 会影响前端配置页的字段，需要同步更新 `web/src/lib/types.ts` 和 API 契约测试。
- 涉及 turn 输出的服务，应通过 `StreamBus` 或 event sink 上报进度。
