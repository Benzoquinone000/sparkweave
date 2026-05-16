# RAG 系统设计与代码事实

本文记录 SparkWeave 当前 RAG 系统的真实设计：数据如何进入知识库，如何进入 Milvus，检索时如何经过自适应策略、HyDE、Gated Agentic RAG、轻量 rerank 和 Context Pack，最后如何被工具和前端展示。

## 一句话定位

SparkWeave 的 RAG 不是“简单向量召回后拼接 prompt”，而是一个**Milvus 优先的 Evidence RAG 管线**：

```text
raw documents
  -> ingestion / chunking / embedding
  -> Milvus collection
  -> retrieval policy
  -> optional HyDE query transform
  -> optional gated Agentic RAG subqueries
  -> dense / hybrid retrieval
  -> keyword rerank
  -> context pack with evidence reasons
  -> model / frontend evidence chain
```

## 代码地图

| 层级 | 关键文件 | 已实现事实 |
| --- | --- | --- |
| RAG 服务入口 | `sparkweave/services/rag_support/service.py` | 统一组织 retrieval policy、HyDE、Agentic RAG、pipeline search 和结果合并 |
| Provider 工厂 | `sparkweave/services/rag_support/factory.py` | 默认 provider 是 `milvus`，旧 provider 会被归一到 Milvus 路径 |
| Milvus pipeline | `sparkweave/services/rag_support/pipelines/milvus.py` | 负责 Milvus collection、索引、检索、rerank、Context Pack |
| 旧 pipeline | `sparkweave/services/rag_support/pipelines/llamaindex.py` | 提供 LlamaIndex 文档加载、embedding wrapper 等基础能力 |
| 检索策略 | `sparkweave/services/rag_support/retrieval_policy.py` | 根据 query 和 profile 选择 fast/concept/exact/code/formula/guide/broad 等策略 |
| 查询改写 | `sparkweave/services/rag_support/query_transform.py` | 支持 HyDE，失败时退回原 query |
| Agentic RAG | `sparkweave/services/rag_support/query_planner.py` | `off/auto/force` 三态门控，LLM JSON 子查询规划和规则 fallback |
| 重排 | `sparkweave/services/rag_support/rerank.py` | 当前实现轻量 `keyword` reranker，无额外重排模型依赖 |
| 证据包 | `sparkweave/services/rag_support/context_pack.py` | 阈值过滤、重复过滤、上下文预算、来源解释 |
| 诊断 | `sparkweave/services/rag_support/diagnostics.py` | 检查 Milvus marker、collection、provider、embedding 配置和连接 |
| 文档/向量管理 | `sparkweave/knowledge/document_inventory.py` | 查看 OCR/Markdown 文档和 Milvus 向量 chunk，支持删除 chunk |
| 重建索引 | `sparkweave/knowledge/reindex.py` | 以 raw 文件为源重建 Milvus 索引 |
| 质量评估 | `sparkweave/services/rag_support/evaluation.py` | 多策略 retrieval evaluation，输出 source/ranking/context/latency 指标 |

## 数据与存储模型

知识库目录仍保留本地数据结构，Milvus 负责向量检索：

```text
data/knowledge_bases/<kb>/
  raw/                         原始上传文件，索引重建的 source of truth
  markdown_pages/ 或 preview    OCR/Markdown 预览缓存，供前端查看
  milvus_storage/metadata.json  Milvus collection marker
```

Milvus 中每个知识库对应一个 collection。`MilvusPipeline._collection_name()` 使用：

- `MILVUS_COLLECTION_PREFIX`，默认 `sparkweave`
- 知识库名清洗后的安全标识
- 知识库名 SHA1 digest 前缀

这样可以避免中文/特殊字符导致 collection 名不合法，也避免不同知识库重名冲突。

## Milvus 默认行为

`MilvusPipeline` 的默认连接策略：

| 平台/配置 | 默认行为 |
| --- | --- |
| `MILVUS_URI` 显式配置 | 使用该 URI |
| Windows 原生 Python | 默认 `http://localhost:19530` |
| 非 Windows 且未配置 URI | 默认本地文件 `./data/milvus/sparkweave.db` |
| `MILVUS_TOKEN` | 可选，用于 Zilliz Cloud 或带 token 的 Milvus |

注意：原生 Windows 下 Milvus Lite 文件模式不可用，项目诊断会建议使用 Docker、Standalone Milvus 或 WSL。

## 索引配置

Milvus pipeline 在 `_configure_settings()` 中设置 LlamaIndex 全局配置：

| 参数 | 默认/来源 |
| --- | --- |
| embedding | `sparkweave.services.embedding_support.get_embedding_config()` |
| chunk size | `RAG_CHUNK_SIZE`，默认 `512` |
| chunk overlap | `RAG_CHUNK_OVERLAP`，默认 `50` |

索引时会写入 marker，记录 collection、embedding、维度、provider、retrieval mode、hybrid sparse 信息等。检索时如果找不到 marker，会返回明确错误：

- 旧 LlamaIndex storage 存在：提示执行重建索引。
- 没有任何 Milvus metadata：提示先上传资料并等待索引完成。

## 检索策略层

`build_retrieval_policy()` 会根据 query 自动选择 profile；显式传入的参数不会被覆盖。

当前 profile 大致含义：

| Profile | 典型场景 | 主要策略 |
| --- | --- | --- |
| `fast` | 简单问答 | dense，小候选集 |
| `concept` | 概念解释 | hybrid + keyword rerank |
| `exact` | 原文、定义、页码、术语 | hybrid，更重 keyword |
| `code` | 代码、函数、报错、配置 | hybrid，偏 sparse |
| `formula` | 公式、推导、数学符号 | hybrid，偏 sparse |
| `guide` | 导学路线、补基任务 | hybrid + HyDE + Agentic auto |
| `broad` | 多点综合、对比、规划 | hybrid + HyDE + Agentic auto |

这层的价值是：用户不需要理解 dense/hybrid/top_k，系统先按任务类型给出可解释默认值。

## 单路检索流程

`RAGService._single_search()` 的流程：

1. 调用 `transform_rag_query()`，按策略决定是否 HyDE。
2. 向事件流输出原始 query、retrieval query、transform trace。
3. 调用当前 pipeline 的 `search()`。
4. 把 `retrieval_policy`、`query_transform`、`original_query`、`source_count` 等 trace 合并到结果。

`MilvusPipeline.search()` 的核心步骤：

1. 读取 `milvus_storage/metadata.json`。
2. 解析 `top_k`、`candidate_top_k`、`max_context_chars`、`score_threshold`。
3. 根据 indexed mode 和 requested mode 决定实际 `dense` / `hybrid`。
4. 创建 Milvus vector store。
5. LlamaIndex retriever 取 `candidate_top_k` 个候选。
6. 调用 `rerank_nodes()`。
7. 调用 `build_context_pack()` 生成最终上下文和 evidence sources。

## Hybrid 与 fallback

如果请求 `hybrid`，但该知识库索引时没有 sparse vectors，则实际会 fallback 到 dense，并返回：

```text
hybrid_fallback_reason = knowledge_base_was_indexed_without_sparse_vectors
```

这能避免“用户以为开了 hybrid 但底层没有 sparse”的静默失败。

Hybrid ranker 支持：

| Ranker | 配置 |
| --- | --- |
| `RRFRanker` | `MILVUS_HYBRID_RRF_K`，默认 `60` |
| `WeightedRanker` | `MILVUS_DENSE_WEIGHT`、`MILVUS_SPARSE_WEIGHT` |

## Gated Agentic RAG

Agentic RAG 当前是**受控门控**，不是默认每次都启动。

`plan_rag_queries()` 支持三种模式：

| 模式 | 行为 |
| --- | --- |
| `off` | 默认关闭 |
| `auto` / `gated` | 根据 query 复杂度判断 |
| `force` | 强制规划子查询，常用于评测对比 |

`should_use_agentic_rag()` 的触发信号包括：

- 多个问号或多个问题。
- query 长度超过 `RAG_AGENTIC_MIN_QUERY_CHARS`，默认 80。
- 出现多个多意图词，例如“比较、总结、路线、优缺点、区别”等。
- 编号式或组合式问题。

开启后流程：

1. LLM 输出 JSON 子查询计划：`{"subqueries":[{"query":"...","purpose":"..."}]}`。
2. 失败时规则 fallback 拆分。
3. 并发执行 `_single_search()`，并发数来自 `RAG_AGENTIC_MAX_CONCURRENCY`，默认 3。
4. 合并去重后的 sources。
5. 输出 `agentic_activity_plan`、`agentic_evidence_groups` 和 `subquery_results`。
6. 若无有效 sources 且 `RAG_AGENTIC_FALLBACK_TO_SINGLE=true`，自动退回单路检索。

## Context Pack

`build_context_pack()` 是 RAG 可解释性的关键层：

| 机制 | 作用 |
| --- | --- |
| score threshold | 过滤低分候选 |
| duplicate filter | 避免重复 chunk 占满上下文 |
| max context budget | 控制进入模型的总字符数 |
| matched keywords | 记录 query 与 chunk 的关键词命中 |
| evidence reason | 给每个 source 生成“为什么引用它”的解释 |
| skipped trace | 记录被阈值、重复、预算过滤掉的数量 |

前端的证据链可以基于 `sources[].evidence_reason`、`context_pack.trace`、`agentic_evidence_groups` 展示可解释检索过程。

## RAG 质量评估

`sparkweave/services/rag_support/evaluation.py` 提供轻量可复现实验，不依赖 LLM judge。

当前策略包括：

- `baseline`
- `adaptive_policy`
- `wide_context`
- `hybrid_keyword_rerank`
- `hyde_hybrid_rerank`
- `agentic_hyde`

指标包括：

| 指标 | 含义 |
| --- | --- |
| `success` | 检索是否执行成功 |
| `keyword_recall` | 期望关键词命中比例 |
| `source_hit` | 是否命中期望来源 |
| `source_mrr` / `source_ndcg` | 期望来源排序质量 |
| `avg_source_score` | 来源分数均值 |
| `context_chars` | 上下文长度 |
| `avg_evidence_reasons` | source 是否带解释 |
| `p95_latency_ms` | 延迟 |
| diagnostics | 无来源、低关键词召回、来源过晚、上下文过短、阈值过滤等问题诊断 |

这部分适合写进简历中的“可复现实验与可解释评估”，但需要配合真实数据集跑出报告后再写具体提升百分比。

## 可以写进简历的准确表述

可以写：

- 将知识库检索从本地 LlamaIndex 文件索引升级为 Milvus 优先架构，按知识库隔离 collection，并保留 raw 文件作为可重建 source of truth。
- 设计 Evidence RAG pipeline：自适应检索策略、可选 HyDE、Gated Agentic RAG 子查询规划、轻量 keyword rerank、Context Pack 证据打包与可解释来源。
- 实现 RAG 诊断和多策略检索评测，支持从 source hit、MRR/nDCG、keyword recall、context budget 和 latency 维度比较策略。

不要写：

- “已经实现跨模态知识图谱级 RAG。”当前主要是文本/OCR/Markdown 到向量检索。
- “Agentic RAG 每次都自动启用。”当前默认 off，部分 profile 会设 auto。
- “使用了商业 rerank 模型。”当前 rerank 是轻量 keyword reranker。
- “RAG 质量已经有固定百分比提升。”除非基于项目数据集跑出报告。

## 后续优化方向

1. 针对 408 教材数据增加结构化切分：章/节/知识点/例题/答案分离，并把题目与答案建立显式关系。
2. 增加 OCR 后 Markdown 清洗、页眉页脚去除、公式块规范化和题号识别。
3. 在 Milvus metadata 中强化 `course`、`chapter`、`section`、`page`、`item_type`、`question_id`、`answer_ref`。
4. 增加 reranker adapter，支持硅基流动/讯飞/本地 bge-reranker 等可选模型。
5. 建立 408 RAG eval set：概念题、原文定位题、跨章节综合题、题目答案配对题、错题解释题。
