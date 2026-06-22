# API 开发规范

本篇面向评委说明 SparkWeave 的接口边界。前端页面看到的学习路线、资料问答、画像更新、讯飞工具配置和多智能体过程，都通过这些 API 与后端服务连接。

## 接口分层

SparkWeave 后端使用 FastAPI。所有业务接口集中在 `/api/v1` 下，按学习场景拆分路由：

| 路由前缀 | 对应页面或能力 | 说明 |
| --- | --- | --- |
| `/api/v1/ws` | 问问题、多智能体对话 | 统一 WebSocket 入口，返回可持续展示的执行过程 |
| `/api/v1/guide/v2` | 学习页 | 课程模板、学习路线、任务推进、资源生成、评估报告 |
| `/api/v1/knowledge` | 资料页 | 知识库创建、资料上传、索引、RAG 测试、来源检查 |
| `/api/v1/learner-profile` | 记录 / 画像页 | 学习证据、画像刷新、画像校准 |
| `/api/v1/learning-effect` | 学习效果评估 | 概念掌握度、下一步建议和行动完成状态 |
| `/api/v1/notebook` | 笔记 | 保存学习笔记和问答记录 |
| `/api/v1/settings` | 设置页 | 本地配置、模型目录、界面偏好和连接测试 |
| `/api/v1/system` | 系统状态 | 后端状态、模型状态、OCR、语音、讯飞工具检测 |
| `/api/v1/speech` | 语音能力 | 语音转写和口语评测 |
| `/api/v1/plugins` | 扩展工具 | 工具和能力的列表、调用和流式执行 |
| `/api/v1/sparkbot` | 课程助教 | 长期助教、资料同步、提醒任务、工作区文件和 QQ 等消息通道配置 |

路由注册集中在 `sparkweave/api/router_registry.py`，应用创建入口是 `sparkweave/api/app_factory.py`。这样做的好处是评委可以从一个位置看到后端暴露了哪些能力，也方便用自动检查确认前端没有调用不存在的接口。

## 普通请求与长过程

SparkWeave 不是所有功能都用同一种请求方式。

普通读写使用 REST，例如课程模板列表、系统状态、知识库列表、画像读取和设置保存。这类接口返回 JSON，适合页面快速刷新。

长过程使用 WebSocket 或 SSE，例如多智能体对话、资料索引进度、资源生成进度和工具流式结果。这类接口会持续返回阶段、内容、来源和最终结果，前端可以把“正在检索资料”“正在生成讲解”“已经得到来源”等过程展示出来。

主要长过程入口：

| 入口 | 用途 |
| --- | --- |
| `/api/v1/ws` | 统一对话和能力执行入口 |
| `/api/v1/knowledge/tasks/{task_id}/stream` | 资料入库和索引任务进度 |
| `/api/v1/knowledge/{kb_name}/progress/ws` | 指定知识库进度 |
| `/api/v1/guide/v2/resource-jobs/{job_id}/events` | 学习资源生成进度 |
| `/api/v1/plugins/tools/{tool_name}/execute-stream` | 工具流式调用 |
| `/api/v1/plugins/capabilities/{capability_name}/execute-stream` | 扩展能力流式调用 |
| `/api/v1/sparkbot/{bot_id}/ws` | 课程助教 WebSocket 试问和消息回传 |

## 统一 WebSocket

`/api/v1/ws` 是问问题页面和多智能体执行的核心入口。前端发起一次对话后，后端会创建执行记录，并把过程事件按顺序推回前端。

这套设计让问答不只是“等一个最终回答”。评委可以看到检索、工具调用、专业能力处理、来源返回和最终答案的过程；如果页面刷新或网络短暂中断，也可以继续接收后续事件。

## 学习页接口

学习页主要使用 `/api/v1/guide/v2`：

| 接口 | 用途 |
| --- | --- |
| `GET /templates` | 读取课程模板 |
| `POST /sessions` | 创建学习路线 |
| `GET /sessions/{session_id}` | 读取学习会话详情 |
| `GET /sessions/{session_id}/study-plan` | 读取学习计划 |
| `GET /sessions/{session_id}/diagnostic` | 读取诊断题 |
| `POST /sessions/{session_id}/diagnostic` | 提交诊断答案 |
| `POST /sessions/{session_id}/tasks/{task_id}/complete` | 完成任务并写入学习证据 |
| `POST /sessions/{session_id}/tasks/{task_id}/resources` | 生成某个任务的学习资源 |
| `GET /sessions/{session_id}/resource-recommendations` | 读取个性化资源推荐 |
| `GET /sessions/{session_id}/report` | 读取学习报告 |

这些接口对应赛题中的个性化学习路径、资源生成和学习效果评估。完成任务后，学习证据会进入画像服务，下一步建议也会随之变化。

## 资料页接口

资料页主要使用 `/api/v1/knowledge`：

| 接口 | 用途 |
| --- | --- |
| `POST /create` | 创建知识库并上传资料 |
| `POST /{kb_name}/upload` | 向已有知识库追加资料 |
| `GET /{kb_name}/documents` | 查看资料清单 |
| `GET /{kb_name}/vectors` | 查看向量片段 |
| `GET /{kb_name}/diagnostics` | 检查知识库检索状态 |
| `POST /{kb_name}/rag-test` | 进行资料检索问答测试 |
| `POST /{kb_name}/rag-eval` | 运行 RAG 评估 |
| `POST /{kb_name}/reindex` | 重新建立索引 |
| `DELETE /{kb_name}` | 删除知识库 |

资料问答必须能给出来源。接口返回的来源会进入前端展示，避免回答只是一段自然语言结论。

当请求启用 Agentic RAG 时，`POST /api/v1/knowledge/{kb_name}/rag-test` 不只返回 `answer` 和 `sources`，还会返回一组可解释字段：`query_plan`、`subquery_results`、`agentic_evidence_groups`、`agentic_context_pack`、`agentic_quality`、`agentic_repair`、`agentic_fallback` 和 `agentic_fallback_reason`。前端资料页用这些字段展示多路检索、质量判断、弱分支修复和保守回退，方便评委核验资料问答不是普通“拼片段”。

## 画像与学习效果接口

画像接口负责把学习过程沉淀成可读结果：

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/learner-profile` | 读取当前画像 |
| `POST /api/v1/learner-profile/refresh` | 刷新画像 |
| `GET /api/v1/learner-profile/evidence-preview` | 预览学习证据 |
| `GET /api/v1/learner-profile/evidence` | 查看标准化学习证据账本 |
| `POST /api/v1/learner-profile/evidence` | 写入一条学习证据 |
| `POST /api/v1/learner-profile/evidence/batch` | 批量写入学习证据，导学和资源生成流程会用到 |
| `POST /api/v1/learner-profile/evidence/rebuild` | 从当前画像预览重建正式证据账本 |
| `POST /api/v1/learner-profile/calibrations` | 通过对话校准画像 |

学习效果接口继续把画像和任务表现转成建议：

| 接口 | 用途 |
| --- | --- |
| `/api/v1/learning-effect/concepts` | 查看概念掌握状态 |
| `/api/v1/learning-effect/next-actions` | 查看下一步行动建议 |
| `/api/v1/learning-effect/report` | 查看学习效果报告 |

这两类接口共同支撑记录页：评委能看到证据、画像、薄弱点和建议之间的关系。

## 课程助教接口

课程助教使用 `/api/v1/sparkbot`。它不是普通聊天接口，而是长期助教管理入口：可以创建助教、保存课程文件、查看历史、管理技能、设置提醒任务，并通过通道配置接入外部消息入口。

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/sparkbot` | 查看课程助教列表 |
| `POST /api/v1/sparkbot` | 创建并启动课程助教 |
| `GET /api/v1/sparkbot/channels/schema` | 查看 Web、QQ、飞书、钉钉等通道的配置 schema |
| `GET /api/v1/sparkbot/{bot_id}` | 查看单个助教配置和运行状态 |
| `PUT /api/v1/sparkbot/{bot_id}` | 更新助教人格、模型、工具和通道配置 |
| `GET /api/v1/sparkbot/{bot_id}/files` | 查看助教工作区文件 |
| `GET /api/v1/sparkbot/{bot_id}/history` | 查看助教历史消息 |
| `POST /api/v1/sparkbot/{bot_id}/cron` | 创建提醒任务，可指定发送通道和对象 |
| `WS /api/v1/sparkbot/{bot_id}/ws` | 在网页中试问助教并接收回复 |

如果配置了 QQ 平台凭据和 `qq-botpy` 依赖，`qq` 通道可以接收私聊、群聊消息，也可以作为提醒任务的发送目标。没有真实凭据时，Web 端仍能展示助教管理、工作区和提醒配置，不把未配置状态说成真实 QQ 调用。

## 设置与讯飞能力接口

设置页使用 `/api/v1/settings` 和 `/api/v1/system`。其中 `/api/v1/system/status` 会返回后端、LLM、Embedding、搜索、RAG、OCR、语音、公式识别、图片理解和讯飞工作流的状态。

单项检测接口包括：

| 接口 | 用途 |
| --- | --- |
| `POST /api/v1/system/test/llm` | 检测大模型配置 |
| `POST /api/v1/system/test/embeddings` | 检测 Embedding 配置 |
| `POST /api/v1/system/test/search` | 检测搜索配置 |
| `POST /api/v1/system/test/ocr` | 检测 OCR 配置 |
| `POST /api/v1/system/test/tts` | 检测语音合成配置 |
| `POST /api/v1/system/test/asr` | 检测语音识别配置 |
| `POST /api/v1/system/test/speech_eval` | 检测口语评测配置 |
| `POST /api/v1/system/test/iflytek_workflow` | 检测讯飞工作流配置 |
| `POST /api/v1/system/test/formula_ocr` | 检测公式识别配置 |
| `POST /api/v1/system/test/image_understanding` | 检测图片理解配置 |

如果未配置真实密钥，接口应当明确返回未配置或带标记的替代结果，不能把未配置状态包装成真实服务调用成功。

## 前端调用边界

前端 API 调用集中在 `web/src/lib/api.ts` 和 `web/src/lib/api/`。页面组件不直接散落拼接后端地址，而是通过统一客户端调用。

`web/src/lib/http.ts` 负责：

- 解析后端地址，默认端口为 `8001`。
- 为 REST 请求补齐认证头。
- 为 WebSocket 和 SSE 地址追加必要参数。
- 把非 2xx 响应转换成页面可以展示的错误。
- 统一处理 JSON 和流式响应。

这种方式让接口变更更容易被检查，也避免页面之间出现不同的错误处理方式。

## 接口核验

项目提供静态合同检查：

```bash
python scripts/check_web_api_contract.py
```

它会读取后端 FastAPI 路由和前端 API 客户端，检查前端调用的 `/api/v1` 路径是否真实存在。发布前也可以运行：

```bash
python scripts/verify_project.py --profile quick
```

这会连同项目结构、文档索引、课程模板、发布边界和 Python 编译一起检查。

## 边界说明

API 文档说明的是系统边界，不替代可运行系统。评委在验收时应重点看三件事：前端页面是否能完成学习流程，接口是否能返回真实数据，长过程是否能展示来源和进度。只要这三件事能对上，SparkWeave 的多智能体能力就不是停留在架构图里，而是进入了可操作的学习场景。
