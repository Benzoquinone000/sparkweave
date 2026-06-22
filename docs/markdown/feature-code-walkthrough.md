# 功能代码链路说明

这篇文档按功能块写，不按目录树写。评委如果问“这个功能是不是只做了页面”，可以顺着每一节看：前端入口在哪里，API 从哪里进，服务层做了什么，数据落在哪里，最后怎样验证。

## 代码入口总览

| 功能块 | 前端入口 | API 入口 | 服务层 | 数据落点 |
| --- | --- | --- | --- | --- |
| 学习路线 | `web/src/pages/GuidePage.tsx`、`web/src/pages/guide/` | `sparkweave/api/routers/guide_v2.py` | `sparkweave/services/guide_v2.py` | `data/user/workspace/guide/`、`data/user/learner_profile/` |
| 课程模板 | `GuideSetupPage`、课程选择组件 | `GET /api/v1/guide/v2/templates` | `GuideV2Manager.list_course_templates()` | `data/course_templates/` |
| 资料库与 RAG | `web/src/pages/KnowledgePage.tsx`、`web/src/pages/knowledge/` | `sparkweave/api/routers/knowledge.py` | `sparkweave/knowledge/manager.py`、`sparkweave/services/rag_support/` | `data/knowledge_bases/`、Milvus |
| 问问题与多智能体 | `web/src/pages/ChatPage.tsx`、`useChatRuntime.ts` | `sparkweave/api/routers/unified_ws.py` | `runtime/context_enrichment.py`、`runtime/capability_router.py`、`graphs/` | 会话库、Notebook、各能力 workspace |
| 练习生成 | `web/src/pages/QuestionLabPage.tsx` | `sparkweave/api/routers/question.py` | `graphs/deep_question.py`、`agents/question/` | 题目本、学习证据 |
| 记录 / 画像 | `web/src/pages/MemoryPage.tsx`、`web/src/pages/memory/` | `sparkweave/api/routers/learner_profile.py`、`memory.py` | `learner_evidence.py`、`learner_profile.py`、`profile_context.py` | `data/user/learner_profile/` |
| 学习效果评估 | 学习页报告、记录页建议 | `sparkweave/api/routers/learning_effect.py` | `sparkweave/services/learning_effect.py` | 证据账本、学习报告响应 |
| 课程助教 | `web/src/pages/AgentsPage.tsx`、`web/src/pages/agents/` | `sparkweave/api/routers/sparkbot.py` | `sparkweave/services/sparkbot.py`、`sparkbot_support/` | `data/memory/SparkBots/`、助教 workspace |
| 设置与讯飞工具 | `web/src/pages/SettingsPage.tsx`、`web/src/pages/settings/` | `settings.py`、`system.py`、`speech.py` | `config.py`、讯飞相关 service | `.env`、`data/user/settings/` |
| 笔记和题目本 | `NotebookPage.tsx`、`QuestionNotebookWorkspace.tsx` | `notebook.py`、`question_notebook.py` | `NotebookManager`、SQLite session store | `data/user/workspace/notebook/`、会话库 |

## 学习路线

学习页不是一个静态课程展示页。前端的 `GuidePage.tsx` 只是壳，真正的状态被拆在 `useGuidePageState.ts`、`useGuideRuntimeData.ts`、`useGuideActions.ts` 和 `GuideWorkspaceRouter.tsx`。页面会保存学习目标、课程模板、时间预算、偏好、薄弱点、当前 session、资源生成 job 和反馈输入。

后端入口集中在 `sparkweave/api/routers/guide_v2.py`：

| 接口 | 后端动作 |
| --- | --- |
| `GET /templates` | 调 `GuideV2Manager.list_course_templates()` 读取课程模板 |
| `POST /sessions` | 调 `create_session()`，把目标、画像、课程模板和笔记上下文转成学习路线 |
| `GET /sessions/{session_id}` | 读取学习会话、任务、掌握状态和资源产物 |
| `POST /tasks/{task_id}/complete` | 完成任务，写入学习证据 |
| `POST /tasks/{task_id}/resources` | 同步生成图解、练习、视频等资源 |
| `POST /tasks/{task_id}/resources/jobs` | 后台生成资源，用 SSE 返回进度 |
| `GET /sessions/{session_id}/report`、`/study-plan`、`/resource-recommendations` | 基于当前证据生成报告、计划和推荐 |

核心服务在 `sparkweave/services/guide_v2.py`。关键函数包括：

| 函数 | 作用 |
| --- | --- |
| `create_session()` | 读取课程模板、统一画像提示，生成课程地图、任务列表和初始建议 |
| `complete_task()` | 更新任务状态、掌握度和证据，并触发后续建议变化 |
| `generate_resource()` | 根据任务和资源类型调动图解、题目、视频、语音等能力 |
| `_resource_profile_hints()` | 把当前任务、节点、薄弱点和偏好整理给资源生成器 |
| `_update_profile_from_evidence()` | 根据低分、错因、反思和高分表现更新导学画像 |
| `_save_session()` | 把学习会话写回用户 workspace |

这块的关键判断有三类：一是课程模板是否完整，二是任务完成后是否形成证据，三是资源生成是否绑定当前任务。验证时不只看页面上有没有卡片，要看完成任务后记录页和学习报告是否发生变化。

运行目录也能直接核验。`PathService.get_guide_dir()` 把导学文件放在 `data/user/workspace/guide/`，`GuideV2Manager` 默认再进入 `v2/` 子目录，单个学习会话由 `_save_session()` 写成 `session_<id>.json`。如果评委现场追问“学习进度是不是只存在前端状态里”，可以打开这个目录，看任务状态、证据、掌握度和资源引用是否已经落盘。

## 课程模板和课件同步

课程模板放在 `data/course_templates/`。当前主课程是 `deep_learning/deep_learning_foundations.json`，第二门课程是 `intelligent_robot_systems/intelligent_robot_systems.json`。模板里不只写标题，还包含课程目标、知识节点、任务、评价方式和 `source_materials`。

课件进入 RAG 的脚本是 `scripts/sync_course_materials_to_kb.py`：

| 命令 | 作用 |
| --- | --- |
| `--stage-only` | 把课程模板引用的课件复制到 `data/knowledge_bases/<课程名>/raw/` |
| `--index` | 在 Milvus 和 Embedding 可用时重建索引 |

验证入口是 `python scripts/check_course_templates.py`。它能检查课程模板结构、课程目录和必要字段，避免演示时选到一门只有标题的“空课程”。

## 资料库与 Agentic RAG

资料页前端在 `KnowledgePage.tsx`，具体面板在 `web/src/pages/knowledge/`。创建、上传、重建索引、查看文档、跑 RAG 测试都通过 `web/src/lib/api.ts` 和 `useKnowledgeMutations()` 调后端。

后端路由在 `sparkweave/api/routers/knowledge.py`，RAG 返回格式整理在 `knowledge_rag_ops.py`：

| 阶段 | 代码 |
| --- | --- |
| 创建资料库 | `create_knowledge_base()` |
| 上传文件 | `upload_files()` |
| 重建索引 | `reindex_knowledge_base()` |
| RAG 测试 | `POST /{kb_name}/rag-test`，先由 `build_rag_search_kwargs()` 整理参数 |
| 返回前端 | `format_rag_search_result()` 保留 sources、query plan、质量报告和修复记录 |

服务层分两块：`sparkweave/knowledge/manager.py` 管资料库目录、配置和文档清单；`sparkweave/services/rag_support/service.py` 管检索。普通检索走 `_single_search()`，复杂问题走 `_agentic_search()`。

RAG 服务不是前端临时拼参数。`build_rag_search_kwargs()` 会把 `top_k`、`retrieval_profile`、`retrieval_mode`、`query_transform`、`agentic_rag` 和质量阈值整理成统一参数；`RagSearchService.search()` 再根据知识库绑定的 provider 选择 Milvus 或 LlamaIndex pipeline。检索结果最终由 `format_rag_search_result()` 变成前端稳定结构，里面保留 `sources`、`query_plan`、`agentic_quality`、`agentic_repair`、`context_pack` 等字段。

Agentic RAG 的关键路径是：

1. `retrieval_policy.py` 根据请求和环境变量构建检索策略。
2. `query_planner.py` 的 `plan_rag_queries()` 生成多个 focused query。
3. `_agentic_search()` 用并发限制执行多个 `_single_search()`。
4. `agentic_merge.py` 合并来源，生成 `agentic_evidence_groups` 和 `agentic_context_pack`。
5. `agentic_quality.py` 计算来源数、覆盖率、相关覆盖率、上下文长度和分数。
6. `agentic_repair.py` 对弱分支补检；仍不够时回退到单路检索。
7. 前端 `RagAgenticTrace.tsx` 展示质量指标、阈值、子查询、修复和回退原因。

这块的验证方式很直接：用同一个知识库问一个单点问题，再问一个包含“解释原因、举例、比较”的复合问题。复合问题应能看到 query plan、子查询结果和质量状态，而不是只有最终回答。

## 问问题与自动调度

问问题页的前端入口是 `ChatPage.tsx`。流式运行逻辑在 `web/src/hooks/useChatRuntime.ts`：它连接 `unifiedRuntimeSocketUrl()`，发送 `start_turn`，携带用户问题、能力、工具列表、知识库、附件、画布上下文、笔记引用和语言。后端事件回来后，前端把 `content`、`result`、`stage_end`、`error` 等事件挂到同一条 assistant message 上。

后端 WebSocket 入口是 `sparkweave/api/routers/unified_ws.py`。真正构造上下文的是 `sparkweave/runtime/context_enrichment.py`：

| 上下文 | 来源 |
| --- | --- |
| 会话历史 | session store 和 `ContextBuilder` |
| 长期记忆 | `MemoryService.build_memory_context()` |
| 学习画像 | `ProfileContextInjector.build_context()` |
| 笔记引用 | `NotebookAnalysisAgent` |
| 附件和画布 | 前端 payload |

自动调度在 `sparkweave/runtime/capability_router.py`。它先检查 `auto_delegate`、强制能力、是否已委派、是否明确“不联网 / 不用工具 / 不开画布”。然后判断是否进入 `deep_solve`、`deep_question`、`deep_research`、`visualize`、`math_animator`，或在 chat 里直接调用 `external_video_search`、`external_image_search`、`canvas`、`rag` 等工具。置信度不足时可以使用 LLM intent coordinator，但它只返回 JSON 路由决策，不直接回答学生。

前端的 `AgentCollaborationPanel.tsx` 会读取协作 metadata。后端的 `collaboration_route()` 会把画像、协调器和专业智能体步骤整理成可展示路线，所以评委看到的不是硬编码的“智能体列表”，而是本轮请求实际经过的协作链。

这块还有一个实用边界：`unified_ws.py` 只负责 WebSocket 协议和 turn 订阅，真正执行在 `LangGraphTurnRuntimeManager`。`start_turn` 创建 turn 后，前端收到的是可重放事件流；断线后还能用 `subscribe_turn` 或 `resume_from` 继续读事件。会话和题目本共享的 SQLite 存在 `data/user/chat_history.db`，由 `SQLiteSessionStore` 管理，不靠浏览器本地缓存保存核心结果。

## 练习生成和题目本

练习有两条入口：一条在学习页任务资源里生成，一条在 `QuestionLabPage.tsx` 里单独生成。单独生成使用 `questionGenerateSocketUrl()` 或 `questionMimicSocketUrl()`，后端是 `sparkweave/api/routers/question.py` 的 WebSocket `/generate` 和 `/mimic`。

智能体实现主要在 `graphs/deep_question.py` 和 `agents/question/`。练习结果前端会整理成题目列表、答案、解析和知识点；保存时调用 `upsertQuestionEntry()`，进入 `sparkweave/api/routers/question_notebook.py`。题目本数据进入 SQLite/session store，画像服务会从 question notebook 读取正确率、题型、难度和概念标签，进一步形成掌握度和薄弱点。

学习页里生成的 quiz 还会走 `guide_v2.py` 的资源产物链路。学生提交 quiz 结果后，`/artifacts/{artifact_id}/quiz-results` 会把每道题变成学习证据，后续学习效果报告能看到这些作答。

核验时建议走两条线：先在题目工坊生成一组题并保存，确认 `question_notebook.py` 能查到 entry；再从学习页生成任务 quiz 并提交结果，确认 `guide_v2.py` 返回的学习报告里出现 quiz attempt。这样能证明练习不是一次性文本输出，而是进入了题目本和学习评估。

## 记录、画像和上下文注入

记录页前端是 `MemoryPage.tsx`，分为概览、记录来源、补充三块。概览页负责展示当前重点、薄弱点、下一步行动和稳定度；记录来源页展开证据；补充页走长期记忆。

后端画像接口在 `learner_profile.py`：

| 接口 | 作用 |
| --- | --- |
| `GET /api/v1/learner-profile` | 读取当前画像快照 |
| `POST /refresh` | 从所有来源重新聚合画像 |
| `GET /evidence` | 查看标准化证据账本 |
| `POST /evidence`、`/evidence/batch` | 写入学习证据 |
| `POST /calibrations` | 学生确认、否定或修正画像判断 |

证据写入服务是 `LearnerEvidenceService`。它把事件标准化为追加式 JSONL，路径是 `data/user/learner_profile/evidence.jsonl`。画像聚合是 `LearnerProfileService`，读取长期记忆、导学会话、题目本、笔记和正式证据账本，生成 `profile.json`。

关键点在于它没有把 `profile.json` 原样塞进模型。`ProfileContextInjector` 会抽取 `current_focus`、`goals`、`preferences`、`weak_points`、`mastery_needs_attention`、`next_action` 和 `decision_scores`，格式化成短提示，由 `context_enrichment.py` 放进 `UnifiedContext.metadata["learner_profile_context"]`。这样既能个性化，又保留来源解释。

画像更新的证据来源比较散，所以代码里专门做了聚合边界：`LearnerProfileService.refresh()` 会按来源采集长期记忆、导学任务、题目本、笔记和校准记录；`POST /calibrations` 写的是学生对画像判断的确认或修正，不是直接让模型重写个人档案。评委如果看记录页，重点看“证据来源”和“下一步建议”是否能对上，而不是只看几个标签是否漂亮。

## 学习效果评估

学习效果接口在 `sparkweave/api/routers/learning_effect.py`。服务层是 `LearningEffectService`，它明确写着从 learner evidence ledger 生成报告，规则透明，方便解释。

核心函数是：

| 函数 | 作用 |
| --- | --- |
| `append_event()` | 把外部学习事件整理成标准证据 |
| `complete_action()` | 学生完成一个补救动作后写入证据，并刷新报告 |
| `build_report()` | 生成综合学习效果报告 |
| `_build_concepts()` | 按概念聚合作答、分数、错因和资源行为 |
| `_build_next_actions()` | 根据薄弱点、错因闭环和课程上下文生成下一步行动 |
| `_dimensions()` | 计算证据质量、参与度、掌握度等维度 |
| `_remediation_loop()` | 判断错因是否已补救、待复测或已闭环 |

评估不是正式教育测量模型，而是项目内可解释的学习处方。它的价值在于把练习、资源使用、反思和错因串成下一步建议。验证时看三件事：证据数是否增长，薄弱概念是否出现，下一步 action 是否能跳回学习页继续执行。

## 课程助教和 QQ 通道

课程助教前端在 `AgentsPage.tsx` 和 `web/src/pages/agents/`，API 客户端拆在 `web/src/lib/api/sparkbot.ts` 与 `web/src/hooks/api/sparkbot.ts`。后端入口是 `sparkweave/api/routers/sparkbot.py`。

主要能力和代码关系如下：

| 能力 | 代码 |
| --- | --- |
| 创建、更新、删除助教 | `SparkBotManager`、`SparkBotInstance` |
| 助教人格和默认配置 | `sparkbot_support/defaults.py`、`config_models.py` |
| 工作区文件 | `SparkBotWorkspaceContext` 和 `/files` 接口 |
| 技能上传和编辑 | `/skills` 接口、`SparkBotSkillsLoader` |
| 定时提醒 | `sparkbot_support/cron.py`、`SparkBotCronService` |
| 消息总线 | `sparkbot_support/messages.py` |
| 通道管理 | `sparkbot_support/channel_manager.py` |
| QQ 通道 | `sparkbot_support/channels.py` 的 `QQChannel` |

`QQConfig` 定义 `enabled`、`app_id`、`secret`、`allow_from` 和 `msg_format`。`QQChannel` 启动时加载 `botpy`，监听私聊、直接消息和群 at 消息，把它们统一转成 `SparkBotInboundMessage`；发送时根据 group/c2c 目标调用 QQ 发送接口。没有真实凭据或依赖时会退回内存通道，所以 Web 管理、工作区、技能和 cron 仍能演示，但不能说成真实 QQ 调用。

助教运行文件由 `SparkBotManager._base_dir()` 放在 `data/memory/SparkBots/`。每个助教有自己的 `config.yaml`、`workspace/`、`cron/jobs.json` 和 `history.jsonl`；`SparkBotWorkspaceContext` 读取工作区资料、技能和共享记忆，`SparkBotSkillsLoader` 负责加载技能文件。评委如果要核验 QQ 接入，先看 `/sparkbot/channels/schema` 是否暴露 `qq` 通道字段，再看当前助教配置里 `channels.qq.enabled` 和凭据状态。

## 讯飞工具链

讯飞能力分散在具体学习链路里，不是一个独立 demo 菜单。

| 能力 | 代码位置 | 进入哪里 |
| --- | --- | --- |
| 星火大模型 | `services/iflytek_spark_ws.py`、`services/llm.py` | 对话、导学、资源生成 |
| MaaS Coding | `services/llm.py` provider 配置 | 代码类讲解和工具编排 |
| Spark Embedding | `embedding_support/adapters/iflytek_spark.py` | 课程资料向量化 |
| ONE SEARCH | `search_support/providers/iflytek_spark.py` | 外部资料、公开视频、公开资源 |
| OCR | `services/ocr.py` | 扫描课件、图片讲义入库 |
| 公式识别 | `services/iflytek_formula.py`、`IflytekFormulaTool` | 图片题和公式题 |
| 图片理解 | `services/iflytek_vision.py`、`IflytekImageUnderstandingTool` | 板书、示意图、截图辅导 |
| TTS | `services/tts.py` | 语音讲解、视频旁白 |
| ASR / 语音评测 | `services/speech.py`、`api/routers/speech.py` | 口述提问、口语类证据 |
| 星辰工作流 | `services/iflytek_workflow.py`、`IflytekWorkflowTool` | 课程资源或诊断报告 |

设置页读取 `settings.py` 的 provider catalog，系统检测走 `system.py` 的 `/test/*` 接口。正式演示时要区分三种状态：真实配置成功、未配置、使用离线 fallback。文档和视频不要把 fallback 包装成真实云端调用。

## 设置、配置和系统检测

设置页前端是 `SettingsPage.tsx` 和 `web/src/pages/settings/`。配置 API 在 `sparkweave/api/routers/settings.py`，系统状态和连接检测在 `sparkweave/api/routers/system.py`。

配置服务主要在 `sparkweave/services/config.py`，Embedding 运行时还有一层 `sparkweave/services/embedding_support/config.py`：

| 代码 | 作用 |
| --- | --- |
| `ModelCatalogService.load()` | 读取模型、Embedding、搜索、OCR、语音等配置目录 |
| `ModelCatalogService.save()` | 保存设置页修改到 `data/user/settings/model_catalog.json` |
| `ModelCatalogService.apply()` | 把当前 catalog 渲染成兼容运行时的 `.env` 键 |
| `get_llm_config()` | 把 catalog 和环境变量解析成 LLM 运行时配置 |
| `embedding_support/config.py:get_embedding_config()` | 给 `EmbeddingClient` 解析实际向量服务配置 |
| `_inject_runtime_paths()` | 把 workspace、guide、question、research 等运行目录注入配置 |

前端调用集中在 `web/src/lib/api.ts` 的 settings/system 函数和 `useSettingsMutations()`。`settings.py` 返回 catalog 时会经过 `_redact_secret_values()` 遮罩敏感字段，保存时用 `_restore_redacted_secret_values()` 保留用户没有重新填写的旧密钥。连接检测有两层：`system.py` 提供 `/test/llm`、`/test/embeddings`、`/test/search`、`/test/ocr`、`/test/tts`、`/test/asr`、`/test/speech_eval`、`/test/iflytek_workflow`、`/test/formula_ocr`、`/test/image_understanding`；设置页的 `/tests/{service}/start` 和 `/events` 用 SSE 展示更细的测试过程。敏感字段只应该出现在本地 `.env` 或被遮罩的设置页中，不应写入文档和截图。

## 笔记、保存和复用

Notebook 不是主赛题能力，但它支撑“学习资源可沉淀”。前端在 `NotebookPage.tsx`，普通笔记 API 是 `sparkweave/api/routers/notebook.py`，题目本 API 是 `question_notebook.py`。

`NotebookManager` 管 notebook 和 record。资源保存入口常出现在学习页和问问题页：图解、练习、视频推荐、资料问答都可以保存成 record。`learner_profile.py` 会读取 notebook 里的记录，把资源类型、保存行为和题目概念作为画像的补充证据。

## 前后端契约如何保证

前端所有 REST、SSE、WebSocket 地址集中在 `web/src/lib/api.ts`、`web/src/lib/api/` 和 `web/src/lib/http.ts`。后端路由统一由 `sparkweave/api/router_registry.py` 注册。项目用下面命令检查前端引用的 `/api/v1` 路径是否真实存在：

```powershell
python scripts/check_web_api_contract.py
```

更完整的快速验证是：

```powershell
python scripts/verify_project.py --profile quick
```

这会连同项目结构、发布安全、课程模板、API 合同、替换守卫和 Python 编译一起跑。评委如果只想确认“文档说的代码是不是存在”，这两条命令是最省时间的入口。
