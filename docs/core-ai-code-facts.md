# 智能体、RAG 与学习画像代码事实说明

本文只记录已经能在当前代码中追溯到的事实，适合用于保研简历、面试准备、答辩讲稿和后续技术文档校准。若后续代码继续演进，应优先更新本文，避免项目介绍和真实实现脱节。

## 核心结论

SparkWeave 当前已经形成三条核心 AI 链路：

1. **LangGraph 多能力运行时**：用户的一次 turn 会进入统一运行时，构造上下文、注入记忆/画像、分派到 `chat`、`deep_solve`、`deep_question`、`deep_research`、`visualize`、`math_animator` 等能力图，并把事件流持久化。
2. **Milvus 优先的 Evidence RAG**：知识库以 `raw/` 原始文件为源，索引到 Milvus collection；检索时可经过自适应策略、HyDE 查询改写、受控 Agentic RAG 子查询规划、二阶段轻量重排和 Context Pack 证据打包。
3. **两层学习画像/记忆系统**：`MemoryService` 维护面向对话的 `PROFILE.md` 与 `SUMMARY.md`，`LearnerProfileService` 则基于证据账本、导学、题目本、Notebook 和 Memory 生成统一学习画像，并由 `ProfileContextInjector` 压缩后进入模型上下文。

这三条链路不是三个孤立模块。实际 turn 链路中，`context_enrichment` 会把会话历史、Notebook 引用、长期 Memory 和统一学习画像合并为 `UnifiedContext`，再交给 LangGraph 能力运行。

三条主线的进一步设计说明见：

- [Agent 运行时与多智能体调度设计](./agent-runtime-design.md)
- [RAG 系统设计与代码事实](./rag-system-design.md)
- [学习画像与长期记忆设计](./learner-profile-memory-design.md)

```text
Web / CLI / Python facade
  -> LangGraphTurnRuntimeManager
  -> build_turn_context
     -> conversation history
     -> MemoryService PROFILE/SUMMARY
     -> ProfileContextInjector learner profile hints
     -> Notebook/history references
  -> LangGraphRunner
     -> ChatGraph / DeepSolveGraph / DeepQuestionGraph / DeepResearchGraph / VisualizeGraph / MathAnimatorGraph
  -> StreamBus events
  -> SQLite turn_events + assistant message
  -> best-effort memory refresh
```

## 代码地图

| 领域 | 关键文件 | 代码事实 |
| --- | --- | --- |
| capability manifest | `sparkweave/app/facade.py` | 注册内置 capability、阶段、工具和 CLI alias |
| runtime 分派 | `sparkweave/runtime/runner.py` | `LangGraphRunner.supported_capabilities` 明确列出已迁移的 LangGraph 能力 |
| turn 生命周期 | `sparkweave/runtime/turn_runtime.py` | 创建 turn、订阅事件、运行图、持久化事件、写 assistant message、刷新 Memory |
| 上下文注入 | `sparkweave/runtime/context_enrichment.py` | 合并历史、Memory、学习画像、Notebook/历史引用和附件 |
| 对话协调 | `sparkweave/graphs/chat.py` | 对用户意图做规则/配置驱动的 specialist 委派 |
| RAG 统一入口 | `sparkweave/services/rag_support/service.py` | 组织 retrieval policy、HyDE、Agentic RAG、pipeline search、证据合并 |
| RAG 策略 | `sparkweave/services/rag_support/retrieval_policy.py` | 按问题类型生成 fast/concept/exact/code/formula/guide/broad profile |
| Agentic RAG 规划 | `sparkweave/services/rag_support/query_planner.py` | `off/auto/force` 三态门控、LLM JSON 子查询规划、规则 fallback |
| 查询改写 | `sparkweave/services/rag_support/query_transform.py` | 可选 HyDE，失败时退回原查询 |
| 重排 | `sparkweave/services/rag_support/rerank.py` | 当前实现无额外依赖的 `keyword` reranker |
| 证据包 | `sparkweave/services/rag_support/context_pack.py` | 阈值过滤、去重、上下文预算、来源解释 |
| Milvus pipeline | `sparkweave/services/rag_support/pipelines/milvus.py` | 每个知识库对应 Milvus collection，本地 marker 记录 provider、collection、embedding 和 hybrid 信息 |
| RAG 诊断 | `sparkweave/services/rag_support/diagnostics.py` | 检查 provider、marker、collection、embedding 配置和连接状态 |
| RAG 评测 | `sparkweave/services/rag_support/evaluation.py` | 多策略 retrieval 评测，包含 keyword/source/ranking/context/latency 指标 |
| 两文件 Memory | `sparkweave/services/memory.py` | `PROFILE.md`、`SUMMARY.md` 读写、迁移、上下文构造和 turn 后刷新 |
| 证据账本 | `sparkweave/services/learner_evidence.py` | 统一学习事件 JSONL，支持对话、导学、题目、资源、Notebook 等事件 |
| 统一画像 | `sparkweave/services/learner_profile.py` | 从多个来源聚合只读画像快照 |
| 画像上下文 | `sparkweave/services/profile_context.py` | 把画像压缩为模型可用 prompt block 和策略 hints |

## 多智能体与能力调度

### 已实现的能力图

`sparkweave/runtime/runner.py` 当前明确支持以下 LangGraph capability：

| Capability | 主要用途 | 主要文件 |
| --- | --- | --- |
| `chat` | 默认对话、工具调用、协调 specialist | `sparkweave/graphs/chat.py` |
| `deep_solve` | 解题、推导、证明、验证 | `sparkweave/graphs/deep_solve.py` |
| `deep_question` | 题目生成、仿题、自定义题型 | `sparkweave/graphs/deep_question.py` |
| `deep_research` | 调研、学习路径、报告和资料整合 | `sparkweave/graphs/deep_research.py` |
| `visualize` | SVG、Mermaid、Chart.js 等可视化生成 | `sparkweave/graphs/visualize.py` |
| `math_animator` | Manim 数学动画代码与产物渲染 | `sparkweave/graphs/math_animator.py` |

如果请求未迁移的 capability，`LangGraphRunner` 会返回类似 `LangGraph runtime has not migrated capability ...` 的错误。因此文档和简历中不应声称“任意能力都已迁移到 LangGraph”。

### Chat 协调器的真实边界

`ChatGraph` 内置协调逻辑，会根据配置和关键词把请求委派到 specialist。当前可委派目标来自：

```python
DELEGABLE_CAPABILITIES = {
    "deep_question",
    "deep_research",
    "deep_solve",
    "math_animator",
    "visualize",
}
```

实际策略：

- `auto_delegate=false` 时不自动委派。
- `delegate_capability` / `coordinator_capability` 可强制委派或强制留在普通聊天。
- 已经由 coordinator 委派过的上下文会带有 `delegated_by_coordinator`，避免重复递归委派。
- `external_video_search` 不是 LangGraph specialist capability，而是普通聊天内的工具路径。
- 视频、图解、动画、出题、研究、解题等意图由关键词/配置触发，不是开放式无限 agent loop。

因此更准确的表述是：

> 项目实现了一个受控的对话协调智能体，可根据学习任务意图把请求单跳委派给解题、出题、研究、图解和动画等 specialist graph，并通过事件流展示 handoff 与结果。

不建议表述为：

> 系统实现了完全自主、多轮无限规划的 agent swarm。

这句话目前不符合代码事实。

## RAG 系统代码事实

### 入库与存储

知识库以 `data/knowledge_bases/<kb_name>/raw/` 为原始资料源。上传或重建索引时，RAG provider 会读取原始资料并创建索引。当前 Milvus pipeline 的关键事实：

- 默认 provider 已转向 `milvus`，同时保留 `llamaindex` 兼容。
- 每个知识库会有 `milvus_storage/metadata.json` 作为 ready marker。
- marker 记录 `provider`、`collection_name`、`uri`、`embedding_model`、`embedding_dim`、`document_count`、`retrieval_mode` 等字段。
- 默认 chunk 参数来自环境变量：`RAG_CHUNK_SIZE` 默认 `512`，`RAG_CHUNK_OVERLAP` 默认 `50`。
- Windows 原生环境默认连接 `http://localhost:19530`；非 Windows 可使用 Milvus Lite 文件模式 `./data/milvus/sparkweave.db`。

### 检索链路

`RAGService.search()` 当前按以下顺序组织检索：

```text
用户查询
  -> build_retrieval_policy()
  -> plan_rag_queries()
     -> off: 单路检索
     -> auto/force: 子查询规划
  -> transform_rag_query()
     -> none 或 HyDE
  -> pipeline.search()
     -> Milvus / LlamaIndex
  -> rerank_nodes()
     -> none 或 keyword
  -> build_context_pack()
     -> score threshold
     -> 去重
     -> 上下文预算
     -> matched_keywords / evidence_reason
  -> content + sources + trace
```

其中 `retrieval_policy` 会按问题类型自动补默认参数：

| Profile | 典型问题 | 默认倾向 |
| --- | --- | --- |
| `fast` | 简短事实问答 | dense、小 top_k、不重排 |
| `concept` | 概念解释 | hybrid、balanced dense/sparse、keyword rerank |
| `exact` | 原文、章节、术语定位 | hybrid、提高 sparse 权重 |
| `code` | 代码、报错、函数/API | hybrid、提高 sparse 权重 |
| `formula` | 公式、推导、证明 | hybrid、提高 sparse 权重 |
| `guide` | 导学、薄弱点、学习路线 | hybrid + HyDE + gated agentic |
| `broad` | 多意图、综合比较 | hybrid + HyDE + gated agentic |

显式传入的参数优先，policy 只补默认值。

### Agentic RAG 的真实实现

当前项目已经实现的是 **Gated Agentic RAG**，不是开放式 agent loop。它的核心在 `query_planner.py` 和 `service.py`：

1. `RAG_AGENTIC_MODE=off|auto|force` 控制是否启用。
2. `auto` 模式只在长问题、多问号、多意图词、枚举式问题或综合型问题下触发。
3. 触发后先尝试用 LLM 输出 JSON 子查询计划。
4. LLM 失败或超时时，使用规则拆分 fallback。
5. 子查询会并发执行 `_single_search()`，并受 `RAG_AGENTIC_MAX_CONCURRENCY` 限制。
6. 多路结果会合并来源、证据组、子查询结果和 `agentic_activity_plan`。
7. 如果多路检索无结果且 `RAG_AGENTIC_FALLBACK_TO_SINGLE=true`，会自动回退单路检索。

适合写进简历的准确表述：

> 设计并实现受控 Agentic RAG：通过规则门控与 LLM JSON planner 对复杂学习问题拆解为少量 focused subqueries，并发检索后合并证据链；简单问题仍走 Fast RAG，以控制延迟和成本。

当前不能夸大的部分：

- 没有实现开放式自主反思/循环检索。
- 没有让 RAG agent 自主选择任意外部工具。
- `keyword` reranker 是轻量词面重排，不是 cross-encoder reranker。
- hybrid 检索只有在 collection 建索引时启用了 sparse/BM25 字段才是真 hybrid；旧 dense-only collection 会安全降级。

### 评测与可解释性

`evaluation.py` 已经把 RAG 调优变成可观测流程。当前支持的评测信号包括：

- success
- latency
- keyword recall
- source hit
- avg source score
- source count
- context chars
- source MRR / nDCG / first rank
- matched keyword count
- evidence reason count
- skipped duplicate / threshold / budget

它更偏向 retrieval evaluation，不是完整答案 faithfulness judge。文档中如果提到“RAG 质量评估”，应说明当前重点在检索质量、证据排序和上下文打包指标，尚未接入大规模 LLM-as-judge 或 Ragas 全量评测。

## 学习画像与记忆代码事实

### 两层设计

SparkWeave 当前有两层长期上下文：

1. **两文件 Memory**：`data/memory/PROFILE.md` 和 `data/memory/SUMMARY.md`。这层偏向对话连续性和长期背景。
2. **统一学习画像**：`data/user/learner_profile/profile.json` 是从证据源聚合出的只读画像快照；`data/user/learner_profile/evidence.jsonl` 是 append-only 证据账本。

两者都可以进入模型上下文，但职责不同：

| 层 | 代码 | 作用 |
| --- | --- | --- |
| Memory | `sparkweave/services/memory.py` | 对话后 best-effort 刷新长期学习摘要和偏好 |
| Evidence ledger | `sparkweave/services/learner_evidence.py` | 记录学习行为、答题、导学、资源、Notebook 等事件 |
| Learner profile | `sparkweave/services/learner_profile.py` | 从多个来源聚合画像、薄弱点、掌握度、证据预览 |
| Profile context | `sparkweave/services/profile_context.py` | 将画像压缩为模型可用 hints 和 prompt block |

### 画像来源

`LearnerProfileService.refresh()` 当前会从以下来源聚合：

- Memory 中的目标、偏好、长期摘要。
- Guide V2 的 learner memory、session profile、course map、mastery、evidence。
- Question Notebook 的答题记录、标签、概念、正确率。
- 主 Notebook 的近期记录。
- `learner_evidence` 证据账本中的学习事件。

这些来源会被转换为：

- `claims`
- `mastery`
- `weak_points`
- `strengths`
- `evidence_previews`
- `next_action`
- `recommended_level`
- `time_budget_minutes`

### 画像如何进入模型

`context_enrichment.build_turn_context()` 会调用 `ProfileContextInjector.build_context()`。如果画像可用，运行时会把画像摘要合并进 `UnifiedContext.memory_context`，并把完整的压缩 payload 放到：

```text
UnifiedContext.metadata["learner_profile_context"]
```

因此 Chat、Deep Solve、Deep Question、Deep Research、Visualize、Math Animator 等读取 `context.memory_context` 的能力都能收到画像摘要。它不是前端页面里的装饰，而是进入了模型运行时上下文。

准确表述：

> 统一学习画像通过运行时上下文注入进入 LangGraph 能力图，作为模型调整解释粒度、资源形态和下一步建议的依据；原始证据留在画像服务中，模型只接收压缩摘要和策略 hints。

当前边界：

- 画像是规则聚合和 LLM 辅助记忆刷新，不是训练出来的学生模型。
- 画像快照是 read-only projection，底层事实仍来自证据账本、Guide、题目本、Notebook 和 Memory。
- 对话信号属于低置信度证据，是否可靠取决于事件抽取质量和后续用户校准。

## 可用于简历的技术表述

下面这些说法与当前代码事实基本一致，可以按简历篇幅压缩：

- 设计并实现 SparkWeave 多能力 LangGraph 运行时，统一管理 turn 生命周期、事件流持久化、上下文构造、记忆刷新和 capability 分派，支持对话、解题、出题、研究、图解和 Manim 动画等学习智能体。
- 实现受控的对话协调智能体，可根据任务意图将普通对话单跳委派到解题、出题、研究、可视化和动画 specialist graph，并通过 `agent_handoff` / `coordinator_decision` 事件暴露协作轨迹。
- 将知识库检索升级为 Milvus 优先的 Evidence RAG：支持原始资料重建索引、collection marker、dense/hybrid 检索、轻量 keyword rerank、Context Pack 证据打包和诊断接口。
- 实现 Gated Agentic RAG：对复杂学习问题进行 LLM JSON 子查询规划、并发多路检索、证据合并和单路 fallback；简单问题保留 Fast RAG 路径以控制延迟。
- 建立 RAG 评测闭环，基于 JSONL 样本对比 baseline、adaptive policy、hybrid rerank、HyDE 和 agentic 策略，统计关键词召回、来源命中、MRR/nDCG、上下文预算和延迟。
- 构建统一学习画像系统：通过证据账本汇聚对话、导学、题目、Notebook 和资源使用行为，生成掌握度、薄弱点、学习偏好和下一步行动建议，并将压缩画像注入模型上下文。

应避免或谨慎使用的说法：

- “完整自主 agent swarm”：当前是受控单跳委派和受控 Agentic RAG，不是无限循环智能体集群。
- “全量 Agentic RAG 已落地”：当前落地的是 gated query planning + 多路检索 + 合并，不是开放式工具规划代理。
- “RAG 已有完整事实性评测”：当前主要是 retrieval 指标；答案 faithfulness / hallucination judge 仍可继续补。
- “画像完全准确刻画学生”：当前画像来自多源证据聚合和低置信度推断，需要用户校准和长期数据积累。

## 维护建议

基于当前代码，后续文档维护优先关注：

1. **RAG 入库调试手册**：从 OCR/PDF 解析、分块、embedding、Milvus collection 到检索命中的逐步排查。
2. **Agentic RAG 对比实验报告模板**：固定 408 教材样本集，展示 baseline、hybrid、HyDE、agentic 的真实指标。
3. **学习画像字段字典**：把 `profile.json`、`evidence.jsonl`、前端画像卡片和模型注入 hints 对齐。
4. **多智能体事件流说明**：把 `coordinator_decision`、`agent_handoff`、`tool_call`、`sources`、`result` 映射到前端可视化。

## 验证索引

本文基于代码阅读整理。与本文相关的测试文件包括：

| 领域 | 测试 |
| --- | --- |
| turn runtime / WebSocket | `tests/ng/test_turn_runtime.py`、`tests/ng/test_turn_runtime_parity.py`、`tests/api/test_unified_ws_turn_runtime.py` |
| Chat 协调 | `tests/ng/test_chat_graph.py` |
| RAG 工具与服务 | `tests/tools/test_rag_tool.py`、`tests/ng/test_rag_services.py`、`tests/capabilities/test_rag_consistency.py` |
| RAG pipeline | `tests/services/rag/test_rag_pipelines.py`、`tests/services/rag/test_milvus_pipeline_config.py`、`tests/services/rag/test_pipeline_integration.py` |
| RAG 策略 | `tests/services/rag/test_retrieval_policy.py`、`tests/services/rag/test_query_planner.py`、`tests/services/rag/test_query_transform.py`、`tests/services/rag/test_rerank.py`、`tests/services/rag/test_context_pack.py` |
| RAG 诊断与评测 | `tests/services/rag/test_rag_diagnostics.py`、`tests/scripts/test_rag_eval_experiment.py` |
| 学习画像 | `tests/services/test_learner_profile.py`、`tests/api/test_learner_profile_router.py` |
| 画像上下文注入 | `tests/services/test_profile_context.py` |

后续如果这些测试和本文发生不一致，应优先以代码和测试为准，再更新文档。
