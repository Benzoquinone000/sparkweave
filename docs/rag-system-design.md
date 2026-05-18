# SparkWeave RAG 设计

本文档只记录当前项目里 RAG 的关键实现，不展开成完整方案书。

## 1. 定位

SparkWeave RAG 是学习资料问答的证据层：

```text
用户问题
  -> Agent 判断是否调用 rag 工具，并选择 retrieval_profile
  -> RAGService 生成检索策略
  -> Milvus 召回 + rerank
  -> 质量门检查 + 证据打包
  -> Chat / Deep Capability 基于证据生成回答
```

RAG 不直接负责最终教学表达，它返回 `content`、`sources` 和 `metadata`，由上层 agent 合成回答。

核心目标：

- 从用户资料中取可追溯证据。
- 简单问题保持低延迟。
- 复杂问题启用 HyDE / Agentic 多路检索。
- 检索过程、证据质量、来源片段可解释。

## 2. 代码落点

| 模块 | 职责 |
| --- | --- |
| `sparkweave/tools/builtin.py` | `rag` 工具定义；提示 agent 根据意图选择 `retrieval_profile` |
| `sparkweave/services/rag_support/service.py` | RAGService，总控 HyDE、Agentic、质量门、fallback |
| `sparkweave/services/rag_support/retrieval_policy.py` | 根据 profile 补默认检索参数 |
| `sparkweave/services/rag_support/pipelines/milvus.py` | 文档入库、chunk、Milvus 检索 |
| `sparkweave/services/rag_support/rerank.py` | keyword rerank / 外部 reranker |
| `sparkweave/services/rag_support/context_pack.py` | 证据打包 |
| `web/src/lib/ragLiveStatus.ts` | 前端解析 RAG 调用中状态 |
| `web/src/components/results/RagEvidenceChain.tsx` | 前端展示最终证据链 |

## 3. 入库链路

```text
上传 / 重建知识库
  -> 保存 raw 原始文件
  -> 解析 PDF / 图片 / DOCX / 文本
  -> 递归 chunk
  -> embedding(search_document)
  -> 写入 Milvus
  -> 写 metadata marker
```

文档处理：

| 类型 | 当前策略 |
| --- | --- |
| PDF | 优先文本层，必要时 OCR |
| 图片 | OCR；未配置 OCR 时不入可检索文本 |
| DOCX | 解析 `word/document.xml` 提取段落 |
| 文本 / 代码 | 多编码读取 |
| 旧 `.doc` | 暂不支持 |

Chunk 策略：

- 默认 `RAG_CHUNK_SIZE=512`，`RAG_CHUNK_OVERLAP=50`。
- 先保留页码 marker、Markdown/章节/编号标题等结构线索。
- 再递归按分隔符切分：`\n\n` -> `\n` -> 中英文句末标点 -> 逗号/顿号 -> 空格 -> 字符 fallback。
- 每个 chunk 保留 `document_id`、文件名、路径、页码、章节标题、`chunk_index`、文本预览等 metadata。

这版已经不是纯字符切分；但它仍不是完整版面解析，复杂表格、公式、多栏 PDF 仍可能丢结构。

## 4. 索引与 Embedding

Embedding 策略：

- 入库使用 `input_type="search_document"`。
- 查询使用 `input_type="search_query"`。
- 入库前校验 embedding API 和向量维度。
- 向量维度或 chunk/schema 变更后需要 reindex。

Milvus provider：

| 模式 | 行为 |
| --- | --- |
| `dense` | dense vector 召回 |
| `hybrid` | dense vector + Milvus BM25 sparse，用 ranker 融合 |

重要边界：

- 只有按 hybrid schema 建过的 collection 才是真 hybrid。
- 旧 dense-only 知识库请求 hybrid 时会 fallback 到 dense recall + keyword rerank，并提示需要 reindex。
- `milvus_storage/metadata.json` 是索引 marker；缺失 marker 时不认为索引可用。

## 5. 自适应检索

自适应检索分两层：

1. Agent 层：`rag` 工具说明要求模型根据用户意图选择 `retrieval_profile`，例如 `fast`、`concept`、`exact`、`broad`。
2. Backend 层：`build_retrieval_policy()` 根据 profile 补默认参数；如果 agent 传 `auto`，后端用规则兜底推断。

Profile 只表达“问题意图”，不要求 agent 猜底层索引类型。dense / hybrid / fallback 由 RAG 后端处理。

| Profile | 适用问题 | 默认倾向 |
| --- | --- | --- |
| `fast` | 短词、缩写、直接查找 | dense、小候选、无 rerank |
| `concept` | 普通概念解释 | hybrid + keyword rerank |
| `exact` | 原文、章节、定义、引用 | 提高 lexical 权重 |
| `code` | API、函数、报错、identifier | 保护代码关键词 |
| `formula` | 公式、证明、推导 | 保护符号和术语 |
| `guide` | 学习路线、薄弱点 | HyDE + Agentic auto |
| `broad` | 对比、总结、多跳问题 | HyDE + Agentic auto，更宽召回 |

## 6. HyDE 与 Agentic RAG

HyDE：

- 通过 `query_transform=hyde` 启用。
- LLM 先生成 hypothetical answer，再与原问题组成 retrieval query。
- 只影响检索，不作为事实来源。
- 默认只在 `guide` / `broad` 等复杂 profile 中启用。

Agentic 多路召回：

```text
original query
  -> query planner 拆成 focused subqueries
  -> 并发执行 single_search
  -> 合并 sources / context
  -> quality gate
  -> repair weak branches
  -> 必要时 fallback 到原问题单路检索
```

质量门检查：

| 指标 | 作用 |
| --- | --- |
| `source_count` | 是否有来源 |
| `coverage_ratio` | 子问题覆盖率 |
| `relevant_coverage_ratio` | 相关证据覆盖率 |
| `content_chars` | 上下文是否过薄 |
| `min_score` | 可选分数阈值 |

质量门的作用不是“打分好看”，而是阻止弱证据直接进入答案生成：先修复，修复失败再回退。

## 7. 重排与证据打包

默认 rerank 是轻量 keyword rerank，不是默认 cross-encoder：

```text
combined = vector_weight * vector_rank_score + lexical_weight * lexical_score
```

外部 reranker 可通过 `RAG_RERANKER_BASE_URL`、`RAG_RERANKER_API_KEY`、`RAG_RERANKER_MODEL` 配置；未配置时回到 keyword。

证据打包由 `build_context_pack()` 完成：

1. 低分过滤。
2. source 去重。
3. 按 `max_context_chars` 截断。
4. 生成 `content` 和结构化 `sources`。
5. 记录 skipped duplicate / threshold / budget 等 trace。

每条 source 包含文件名、路径、chunk id、分数、片段预览、命中关键词、`evidence_reason`。

这就是 Evidence RAG 的主要体现：返回的不只是上下文，还有来源、质量、筛选和多路检索轨迹。

## 8. 前端呈现

学习用户默认不需要手动选择检索策略。前端只展示必要状态：

- 调用中：`RagRetrievalStatus` 显示“正在查资料 / 多路检索 / 检查证据 / 补强证据 / 已找到依据”。
- 回答后：`RagEvidenceChain` 展示证据链、质量状态、来源片段、子查询结果。
- 高级参数仍放在知识库测试 / 诊断入口，不放在日常聊天主流程。

## 9. 运行时集成

使用路径：

| 路径 | 说明 |
| --- | --- |
| Tool 调用 | Agent 显式调用 `rag`，runtime 注入当前 KB |
| Prefetch | `prefetch_rag=true` 时先检索，再注入上下文 |
| RAG Test | 知识库页面直接测试检索、质量和来源 |
| RAG Eval | 用轻量指标做回归和 smoke check |

常用 API：

| API | 用途 |
| --- | --- |
| `POST /knowledge/{kb_name}/rag-test` | 单次检索测试 |
| `POST /knowledge/{kb_name}/rag-eval` | 检索评估 |
| `POST /knowledge/{kb_name}/upload` | 增量上传 |
| `POST /knowledge/{kb_name}/reindex` | 重建索引 |
| `GET /knowledge/{kb_name}/documents` | 文档统计 |
| `GET /knowledge/{kb_name}/vectors` | chunk 列表 |

## 10. 当前边界

- hybrid 需要 hybrid schema 重建；旧 dense-only 索引只能兼容 fallback。
- DOCX 已支持；旧 `.doc` 未支持。
- chunk 已是递归分隔符切分，但不是专业版面解析。
- 默认 rerank 是 keyword，不是 cross-encoder。
- OCR 质量决定扫描件和图片资料的可用性。
- Agentic RAG 依赖 LLM planning，有额外延迟；失败时会走 fallback。

## 11. 维护约定

- 改 chunk、embedding 维度、Milvus schema 后必须提示 reindex。
- 新增 RAG 参数要同步 tool schema、`rag_overrides.py`、API schema、测试。
- 普通聊天入口保持简洁；不要把 HyDE、Agentic、ranker 参数暴露给默认用户。
- 重要检索策略变更至少跑单元测试、RAG smoke test 和一组端到端检索检查。
