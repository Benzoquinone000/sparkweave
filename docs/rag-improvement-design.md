# SparkWeave RAG 升级设计稿

> 目标：把 SparkWeave 的 RAG 从“能检索资料”升级成“可解释、可评测、可对比、可面试讲清楚”的课程知识引擎。

## 1. 调研结论

RAG 的核心价值不是简单把向量数据库接上大模型，而是让模型在回答时访问可更新的外部知识，并给出来源。Lewis 等人在 RAG 论文中强调，参数化知识模型在知识密集任务上存在精确访问、来源追踪和知识更新问题，RAG 通过“生成模型 + 非参数化向量索引”补齐这一点。

对 SparkWeave 来说，RAG 不能只服务“聊天”，还要服务：

- 导学：按画像和当前任务找资料。
- 题目生成：从课程材料抽取考点。
- 智能辅导：把解答绑定到证据片段。
- 学习效果评估：根据错因回到相关资料。
- 面试表达：能说明召回、重排、评估、观测和实验设计。

从调研看，成熟 RAG 系统通常分成五层：

| 层 | 作用 | SparkWeave 当前状态 | 下一步 |
| --- | --- | --- | --- |
| 数据入库 | 文档解析、OCR、切块、metadata | 已支持 PDF/文本/代码，Milvus 优先 | 增强 chunk 策略和结构化 metadata |
| 召回 | dense、sparse、hybrid、多查询 | 当前以 Milvus dense 检索为主 | 加 hybrid sparse + dense 和 HyDE |
| 重排 | 相似度过滤、cross-encoder/LLM rerank | 已加 score threshold 和上下文上限 | 增加可选 reranker |
| 上下文压缩 | 去重、排序、上下文预算 | 已加 `RAG_MAX_CONTEXT_CHARS` | 增加引用分组和首尾强化 |
| 评估观测 | hit rate、MRR、nDCG、faithfulness、latency | 已有 doctor/diagnostics | 增加标准对比实验报告 |

## 2. 参考依据

- RAG 原始论文：RAG 把 seq2seq 参数知识和 dense vector index 外部知识结合，用于知识密集任务，并改善事实性与来源问题。  
  https://arxiv.org/abs/2005.11401
- HyDE：先让大模型生成“假想答案文档”，再用该文档做 dense retrieval，可在没有标注数据时提升零样本检索。  
  https://arxiv.org/abs/2212.10496
- Lost in the Middle：长上下文模型对中间位置证据利用不稳定，说明 RAG 不能盲目塞超长上下文，必须做排序和预算控制。  
  https://arxiv.org/abs/2307.03172
- Milvus Hybrid Search：Milvus 官方支持 dense search、sparse search，以及 dense+sparse hybrid search，并可用 weighted reranker 融合。  
  https://milvus.io/docs/hybrid_search_with_milvus.md
- LlamaIndex Node Postprocessor：官方把后处理放在 retrieval 和 response synthesis 之间，支持 similarity cutoff、rerank 等。  
  https://developers.llamaindex.ai/python/framework/module_guides/querying/node_postprocessors/
- LlamaIndex Retrieval Evaluation：官方示例使用 hit_rate、MRR、precision、recall、AP、nDCG 等指标评估 retriever。  
  https://developers.llamaindex.ai/python/examples/evaluation/retrieval/retriever_eval/
- Ragas：官方提供 context precision、context recall、response relevancy、faithfulness 等 RAG/agent 评估指标。  
  https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/

### 2.1 生产落地实践调研

为了避免只参考论文，SparkWeave 的 RAG 路线更应该对齐已经产品化的检索增强系统。调研后的共同结论是：成熟 RAG 很少停留在“向量召回 + prompt 拼接”，而是普遍采用 **hybrid retrieval + metadata filter + rerank + query planning + observability** 的组合。

| 产品/框架 | 已落地策略 | 对 SparkWeave 的启发 |
| --- | --- | --- |
| Azure AI Search | hybrid search 同时跑全文和向量查询，用 RRF 合并；可叠加 semantic ranker。官方说明 real-world 和 benchmark 数据上 hybrid + semantic ranker 能显著提升 relevance。 | Milvus dense 不能作为终点，必须补 sparse/BM25 与 RRF/Weighted fusion。 |
| Azure Agentic Retrieval | 用 LLM 基于对话历史拆解复杂问题为多个 focused subqueries，并行执行、merge、semantic rerank，返回 grounding data、reference data 和 activity plan；官方也明确它会增加延迟和成本。 | Agentic RAG 适合复杂问题和导学任务，但必须有路由门控，不能所有查询都走 agent。 |
| Amazon Bedrock Knowledge Bases | `RetrieveAndGenerate` 内部串联 query generation、retrieve、model invoke；也允许单独调用 `Retrieve` 以自定义 RAG 步骤，并支持 reranker。 | SparkWeave 应保留低层 `Retrieve` 能力，不做黑盒 RAG，方便实验和面试展示。 |
| Google Vertex AI RAG Engine | 把 corpus、file import、ANN index rebuild、retrieval query 做成云产品能力，并强调外部知识源接入。 | 知识库生命周期、reindex、diagnostics 是 RAG 产品能力的一部分，不是边角功能。 |
| Pinecone | 官方 relevance 指南把 rerank、metadata filter、full-text keyword、hybrid search、chunking strategy 列为提升搜索质量的核心技术；two-stage rerank 被称为改进 RAG 质量的简单有效方法。 | 下一步优先实现 rerank interface 和 metadata-aware retrieval，而不是急着堆更多智能体。 |
| Weaviate | hybrid search 融合 vector 和 BM25F，fusion method 与 relative weights 可配置，并可返回 explainScore。 | SparkWeave 前端可以展示“命中来源为什么被选中”，增强用户信任和面试可解释性。 |
| Qdrant | hybrid queries 支持 dense/sparse 融合和多阶段 query/rerank pipeline。 | 对课程代码、公式、专业词汇，应将 sparse precision 与 dense semantic 组合。 |
| Milvus/LlamaIndex | Milvus hybrid search 支持 BM25 sparse、RRF 和 WeightedRanker，权重可控制 dense/sparse 重要性。 | 当前 Milvus 路线正确；下一步应把 collection schema 升级到 dense+sparse，并把权重纳入策略实验。 |
| OpenAI Retrieval/File Search | 官方提供 `score_threshold`、ranker、hybrid_search embedding/text 权重等调优项。 | SparkWeave 已有 threshold；应继续加入 ranker 与 text/vector 权重控制。 |

因此，SparkWeave 的工程目标应从“RAG 接入”升级为：

```text
可维护的数据入库
  + 可解释的 hybrid 检索
  + 可替换 reranker
  + 可路由 agentic query planning
  + 可复现实验报告
  + 面向用户的证据卡片
```

## 3. 当前 SparkWeave RAG 基线

已完成：

- 默认 provider 切到 `milvus`。
- Docker Compose 内置 Milvus Standalone、etcd、MinIO。
- Windows 原生环境默认连接 `http://localhost:19530`，Linux/macOS/WSL 可用 Milvus Lite。
- 每个知识库拥有 `milvus_storage/metadata.json`，记录 collection、embedding 模型、维度和文档数。
- 支持旧 `llamaindex` 本地索引作为兼容回退。
- 支持从 `raw/` 原始资料重建索引。
- 支持 `kb doctor`、`/knowledge/diagnostics` 和前端“检查连接”。
- 支持 `RAG_TOP_K`、`RAG_SCORE_THRESHOLD`、`RAG_MAX_CONTEXT_CHARS`。

当前短板：

- 召回主要依赖 dense vector，对“专有名词、代码符号、公式编号、章节标题”不够稳。
- 没有标准评测集，难以证明改进幅度。
- 没有 reranker，top-k 里可能混入低相关片段。
- 没有 HyDE 或多查询扩展，对模糊学习问题的召回不够强。
- 前端引用来源可以展示，但还没形成“为什么推荐这段资料”的解释层。

## 4. 目标架构

推荐架构命名为 **Evidence RAG Pipeline**：

```text
用户问题
  -> 查询理解 Query Planner
  -> 查询扩展 Query Expansion
     - raw query
     - HyDE hypothetical document
     - course concept aliases
  -> 多路召回 Retrieval
     - dense vector
     - sparse keyword/BM25
     - metadata filter
  -> 候选融合 Fusion
     - weighted dense/sparse
     - reciprocal rank fusion fallback
  -> 重排 Rerank
     - similarity cutoff
     - optional cross-encoder/LLM rerank
  -> 上下文压缩 Context Pack
     - 去重
     - 按章节/文件聚合
     - 控制上下文预算
     - 优先首部和尾部放关键证据
  -> Grounded Answer
     - 带引用回答
     - 明确证据不足
  -> Observability
     - latency
     - source_count
     - source score
     - hit/mrr/faithfulness
```

### 4.1 Agentic RAG 的定位

我建议 SparkWeave 使用 **Gated Agentic RAG**，不要使用“全量 Agentic RAG”。

原因：

- Agentic RAG 的核心不是让智能体随便循环，而是 **query planning**：看懂用户问题、拆成子问题、选择检索工具、并行召回、合并证据。
- 它非常适合教育场景里的复杂问题：例如“我线性代数和概率论都薄弱，为什么 PCA 推导看不懂，先补什么？”这种问题同时涉及画像、课程知识库、导学目标和资源推荐。
- 它不适合简单事实查询：例如“梯度下降公式是什么？”这类问题直接 hybrid retrieve + rerank 更快、更稳、更便宜。
- 它会引入额外延迟、成本和不确定性，所以必须有门控、最大步数、超时和可观测日志。

SparkWeave 的 Agentic RAG 应设计成三档：

| 档位 | 触发条件 | 流程 | 用户体验 |
| --- | --- | --- | --- |
| Fast RAG | 单一概念、短问题、明确知识库 | dense/sparse hybrid -> rerank -> answer | 秒级回答 |
| Guided RAG | 问题带学习目标、薄弱点、当前导学任务 | 画像 hints + metadata filter + hybrid -> answer | 个性化解释 |
| Agentic RAG | 多意图、多课程、跨资料、证据不足、需要规划 | planner 拆子问题 -> 多路检索 -> 合并证据 -> answer/activity plan | “系统帮我拆清楚了” |

实现上不建议一开始做开放式 agent loop，而是做一个受控的 `RagQueryPlanner`：

```json
{
  "mode": "agentic",
  "reason": "问题包含多个学习目标和薄弱点",
  "subqueries": [
    {"query": "PCA 与协方差矩阵的关系", "kb": "linear-algebra", "weight": 0.5},
    {"query": "最大方差投影的直观解释", "kb": "machine-learning", "weight": 0.3},
    {"query": "特征值特征向量基础", "kb": "linear-algebra", "weight": 0.2}
  ],
  "constraints": {
    "max_subqueries": 3,
    "max_latency_ms": 2500,
    "require_citations": true
  }
}
```

这样既有 agentic 的智能性，也保留工程可控性。

## 5. 分阶段实现

### P0：稳定生产基线

已基本完成。

- Milvus default provider
- reindex
- diagnostics
- context length / score threshold
- Docker Compose

### P1：对比实验框架

目标：先让改进可衡量。

实验数据格式：

```json
{"id":"gd-01","kb_name":"ml-course","question":"为什么梯度下降沿负梯度方向？","expected_keywords":["负梯度","损失函数","最陡下降"],"expected_sources":["gradient"]}
```

指标：

| 指标 | 含义 | 面试表达 |
| --- | --- | --- |
| keyword recall | 答案或上下文命中人工关键词比例 | 判断是否召回核心概念 |
| source hit rate | 是否命中人工标注来源 | 判断检索是否找到了正确资料 |
| avg source score | 平均召回分数 | 判断召回置信度 |
| context chars | 上下文长度 | 控制成本与 lost-in-the-middle 风险 |
| latency p50/p95 | 延迟 | 面向用户体验 |

### P2：Hybrid Retrieval

目标：补 dense retrieval 对精确词的弱点。

当前进展：已完成 hybrid-ready 基础层。Milvus provider 支持 `RAG_RETRIEVAL_MODE=dense|hybrid`、RRF/WeightedRanker 参数、marker 记录 `enable_sparse`，并在旧 dense-only 知识库请求 hybrid 时自动安全降级。下一步需要用真实 Milvus collection 重建 hybrid 索引，并跑对比实验验证收益。

方案：

- 保留 Milvus dense vector 字段。
- 增加 sparse/BM25 字段。
- 对代码、公式、术语类问题提高 sparse 权重。
- 对概念解释类问题提高 dense 权重。
- 默认策略：
  - `dense_weight=1.0`
  - `sparse_weight=0.6`
  - 专名/代码/公式触发 `sparse_weight=1.0`

对比：

| 实验组 | 描述 |
| --- | --- |
| A | Milvus dense top_k=5 |
| B | Milvus dense top_k=20 + cutoff |
| C | Milvus hybrid dense+sparse |
| D | Milvus hybrid + rerank |

### P3：Rerank 与 Context Pack

目标：减少低相关片段进入大模型。

当前进展：已完成轻量 reranker 接口和 `keyword` reranker。默认关闭；开启后可以通过 `RAG_CANDIDATE_TOP_K=20` 先扩大候选，再用 `RAG_RERANK_TOP_N=5` 截断。该实现无额外模型依赖，适合作为二阶段重排链路的稳定基线，后续可以替换为 cross-encoder/API reranker。

Context Pack 也已完成基础层：检索结果会经过阈值过滤、去重、上下文预算控制，并为每个来源生成 `matched_keywords` 和 `evidence_reason`，为前端证据卡片和评测报告做准备。

方案：

- 第一阶段用 similarity cutoff。
- 第二阶段接入可选 reranker：
  - 本地 sentence-transformer rerank
  - Jina/Cohere/其他 API rerank
  - LLM pairwise rerank fallback
- 上下文打包策略：
  - 同一文件连续片段合并。
  - 去掉重复 chunk。
  - 高分证据放前面。
  - 补充证据放末尾。
  - 总长度受 `RAG_MAX_CONTEXT_CHARS` 控制。

### P4：HyDE 与学习画像融合

目标：让“学生模糊提问”也能找到资料。

示例：

```text
用户：我还是不懂反向传播为什么要链式法则
HyDE：生成一段关于反向传播、链式法则、梯度传递的假想讲义
检索：用假想讲义 embedding 找真实课程材料
回答：用真实材料生成解释，而不是相信假想讲义
```

画像融合：

- 画像中的薄弱概念加入 query hints。
- 当前导学任务加入 metadata filter。
- 学生偏好“图解/代码/公式”影响资源类型排序。

### P5：Grounded Answer 与前端可解释

目标：用户知道“答案为什么这么说”。

前端展示：

- 引用资料卡片：文件名、章节、相似度、命中关键词。
- “为什么引用”：一句人话解释。
- “证据不足”：当 source hit 或 score 太低时提醒继续上传资料或联网查找。

这对大厂面试很有价值，因为它体现了：

- 不盲信模型。
- 有证据链。
- 有降级策略。
- 关注用户信任。

## 6. 对比实验设计

### 数据集

建议构造三类课程数据：

| 数据集 | 样例 | 目的 |
| --- | --- | --- |
| 概念问答 | 梯度下降、DPO、过拟合 | 测 dense semantic |
| 精确术语 | `std::move`、公式编号、章节名 | 测 sparse/hybrid |
| 导学错因 | “概念边界不清”“公式不会用” | 测画像 + query expansion |

每条样本人工标注：

- `question`
- `expected_keywords`
- `expected_sources`
- `difficulty`
- `topic`
- `query_type`: `concept | exact | code | formula | guide`

### 实验组

| 组 | 策略 | 预期收益 |
| --- | --- | --- |
| Baseline | dense top_k=5 | 当前基线 |
| DenseWide | dense top_k=20 + max_context | 提升 recall |
| DenseStrict | top_k=12 + score_threshold | 降低噪声 |
| Hybrid | dense+sparse weighted | 提升术语/代码/公式问题 |
| HybridRerank | hybrid + reranker top_n=5 | 提升 precision |
| HyDEHybrid | HyDE + hybrid + rerank | 提升模糊问题 |
| GatedAgentic | query planner + subqueries + hybrid rerank | 提升多意图/跨资料问题 |

### 报告模板

```text
Strategy        keyword_recall  source_hit  p50_latency  p95_latency  avg_context
Baseline        0.62            0.55        220ms        480ms        4200
DenseStrict     0.68            0.61        260ms        530ms        3600
Hybrid          0.77            0.72        310ms        650ms        4500
HybridRerank    0.83            0.80        680ms        1200ms       3900
```

面试表达：

> 我没有只接一个向量库，而是把 RAG 做成可评测管线。先用 dense Milvus 作为基线，再逐步加入阈值过滤、hybrid sparse+dense、rerank 和 HyDE。每次改动都用同一套课程问答集比较 hit rate、MRR、source hit、faithfulness 和 latency，最后选择收益/延迟最平衡的策略作为默认。

## 7. 风险与取舍

| 风险 | 处理 |
| --- | --- |
| Hybrid 会增加索引复杂度 | 先保留 dense 稳定基线，再做可选 provider |
| Rerank 增加延迟 | 默认只对 top-20 rerank 到 top-5，并记录 p95 |
| HyDE 可能生成虚假信息 | HyDE 只参与检索，不直接进入答案 |
| Agentic RAG 不稳定 | 只用于复杂查询，限制 subquery 数、最大步数、超时和工具范围 |
| Agentic RAG 成本变高 | 默认 Fast RAG，只有复杂问题启用 query planning，并记录 token/latency |
| LLM judge 成本高 | 先做 retrieval 指标，再按需做 Ragas |
| Windows LlamaIndex/Numpy import 不稳定 | 继续保留子进程预检，避免服务启动硬崩 |

## 8. 下一步开发清单

1. 已完成 `sparkweave/services/rag_support/evaluation.py`，脚本、CLI、API 和资料库前端共享同一套 JSONL 多策略对比逻辑。
2. 已完成机器学习课程 30 条人工标注样本模板。
3. 已完成 optional reranker interface 与 `keyword` 轻量重排基线。
4. 已完成 Milvus hybrid sparse+dense collection 的工程基础和 dense-only 安全降级。
5. 已完成资料库页最近一次评测摘要展示。
6. 已完成受控 HyDE query transform：默认关闭，可在策略中通过 `query_transform=hyde` 开启，并记录原查询/检索查询/超时回退。
7. 已完成 `RagQueryPlanner` 基础版：`off/auto/force` 三态门控，LLM 规划失败后自动规则拆分，返回 `query_plan` 和 `subquery_results`。
8. 已完成 Chat 结果中的“知识库证据链”可视化：回答下方会显示 Fast RAG / Agentic RAG、分路检索计划、来源片段、命中关键词和证据理由。
9. 已完成 Chat/DeepSolve 的 RAG 策略透传：前端可选择快速检索、自动分解、强制多路和 HyDE 查询改写，后端会传入 `rag` 工具执行。
10. 已完成资料库页一键小样本评测：用户可直接选择“快速体检”“标准体检”或“完整对比”。`quick_check` 只跑基础检索和自适应策略，适合上传/重建索引后的连通性确认；报告会显示样本标注覆盖度，避免把无标注小样本误读成正式质量门。正式实验仍建议使用标注 JSONL 数据集。
11. 已完成题目级失败诊断：评测报告新增 `case_diagnostics`，把无来源、关键词弱覆盖、期望来源未命中、上下文预算截断和检索错误翻译成可执行优化建议；资料库页只展示最需要优先检查的样本。

## 9. 评测脚本用法

样例数据集在 `docs/examples/rag_eval_dataset.sample.jsonl`。更完整的机器学习课程评测模板在 `docs/examples/rag_eval_dataset.ml_course.sample.jsonl`，包含 concept、exact、formula、guide、code 五类问题共 30 条。正式实验时建议复制一份并把 `kb_name`、`expected_sources` 改成真实课程知识库和真实文件名。

```powershell
python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.sample.jsonl `
  --kb ml-course `
  --provider milvus `
  --preset rag_upgrade `
  --baseline-strategy baseline `
  --output dist/rag-eval-report.md `
  --json-output dist/rag-eval-report.json
```

上传资料或刚重建索引后，可以先用更轻的体检预设确认检索链路：

```powershell
python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.sample.jsonl `
  --kb ml-course `
  --provider milvus `
  --preset quick_check
```

自定义策略示例：

```powershell
python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.sample.jsonl `
  --strategy baseline:top_k=5,max_context_chars=8000 `
  --strategy dense_wide:top_k=20,max_context_chars=12000 `
  --strategy dense_strict:top_k=12,score_threshold=0.35,max_context_chars=6000 `
  --strategy keyword_rerank:candidate_top_k=20,reranker=keyword,rerank_top_n=5
```

报告会输出每个策略的成功率、关键词召回、来源命中、证据解释数量、命中关键词数量、上下文长度和延迟，并按 `query_type` 拆分。`dataset_profile` 会说明样本是 `smoke_check`、`partial` 还是 `release_ready`：无期望关键词/来源的小样本只适合检查链路，不能直接作为发布质量门。`case_diagnostics` 会列出题目级问题和下一步修复建议。`--preset quick_check` 用于快速确认基础链路；`--preset rag_upgrade` 会一次跑 baseline、自适应策略、宽召回、hybrid+keyword rerank、HyDE+hybrid+rerank、Agentic+HyDE 六组，适合作为面试和比赛答辩里的对比实验。

同一套能力也可以通过 CLI 和 API 调用：

```powershell
python -m sparkweave_cli kb eval ml-course docs/examples/rag_eval_dataset.ml_course.sample.jsonl `
  --provider milvus `
  --preset rag_upgrade
```

```http
POST /api/v1/knowledge/ml-course/rag-eval
```

请求体可以直接使用 preset：

```json
{
  "preset": "rag_upgrade",
  "cases": [
    {
      "id": "case-1",
      "question": "什么是梯度下降？",
      "query_type": "concept",
      "expected_keywords": ["梯度", "损失函数"]
    }
  ]
}
```

面试时建议重点展示：

- 总体表：说明整体质量和延迟变化。
- 按问题类型表：说明 hybrid/rerank 对 exact、code、formula 类型的收益。
- 相对 Baseline 表：说明改进幅度，而不是只展示绝对值。
## P1.3 实验结论自动化

RAG 对比实验不只输出表格，还要自动给出一段可以直接放进答辩、README 或面试讲解里的结论：

- `experiment_summary.quality_leader`：当前综合质量最好的策略。
- `experiment_summary.fastest_strategy`：P95 延迟最低的策略。
- `experiment_summary.quality_delta`：领先策略相对 baseline 的收益与延迟代价。
- `experiment_summary.headline`：一句话说明命中率、关键词召回和延迟。
- `experiment_summary.recommendation`：给出默认策略/可选策略的产品建议。

这样评测报告可以回答三个实际问题：哪种策略更好、好多少、是否值得牺牲延迟。

## P2.3 自适应检索策略

新增 `retrieval_policy` 层，把用户问题先路由到可解释 profile，再填充默认检索参数：

| Profile | 典型问题 | 默认策略 |
| --- | --- | --- |
| `fast` | 简短事实问答 | dense / small top_k / no rerank |
| `concept` | 概念解释 | hybrid / balanced dense+sparse / keyword rerank |
| `exact` | 原文、标题、章节定位 | hybrid / sparse 权重更高 |
| `code` | 代码、报错、函数/API | hybrid / sparse 权重最高 / keyword rerank |
| `formula` | 公式、推导、证明 | hybrid / sparse 权重更高 / keyword rerank |
| `guide` | 导学、薄弱点、学习路线 | hybrid + HyDE + gated Agentic RAG |
| `broad` | 多意图、比较、综合题 | hybrid + HyDE + gated Agentic RAG |

显式传入的参数永远优先，policy 只补默认值，避免黑箱覆盖调用者决策。

## P3.2 可控 Agentic RAG 编排

Agentic RAG 当前采用 gated 设计：

1. 简单问题保持 fast path。
2. 复杂问题或导学问题触发 planner。
3. planner 拆成少量 focused subqueries。
4. 子问题并行检索。
5. 合并证据、去重来源，并返回 `agentic_activity_plan`。

前端后续可以用 `agentic_activity_plan.steps` 展示“系统如何拆题、每步找到多少证据、哪一步失败”，让 Agentic RAG 不只是技术词，而是用户能看懂的学习路径解释。
## P1.4 Mature Evaluation Decision

RAG 评测报告现在不只给表格，还会给可执行决策：

- `experiment_summary.decision`：`promote_default`、`use_for_complex_queries`、`keep_baseline`、`needs_more_data`。
- `experiment_summary.quality_score`：综合成功率、来源命中、关键词召回和证据解释数量。
- `experiment_summary.latency_tradeoff_ms`：领先策略相对 baseline 的 P95 延迟代价。

成熟标准：报告必须能回答“是否切默认、是否只用于复杂问题、是否需要扩充评测集”。

## P3.3 Mature Agentic Guardrails

Agentic RAG 增加了两个稳定性控制：

- `RAG_AGENTIC_MAX_CONCURRENCY`：子问题并发上限，默认 3。
- `RAG_AGENTIC_FALLBACK_TO_SINGLE`：分解检索无证据时自动回退到单次检索，默认开启。

返回 `agentic_fallback=true` 时，前端会标记“已回退”，用户不会直接看到空的复杂链路。

## P1.5 Adaptive Policy Evaluation

`rag_upgrade` 评测预设现在加入 `adaptive_policy`。它不再固定使用一组 `top_k` / `reranker` 参数，而是把问题交给 `retrieval_policy` 自动路由到 `concept`、`exact`、`code`、`formula`、`guide`、`broad` 等 profile。

这一步的价值是让评测更贴近真实产品：真实用户不会手动选择“混合检索”或“HyDE”，系统需要根据问题自动决定检索方式。报告中可以直接比较：

- `baseline`：最小成本的普通检索。
- `adaptive_policy`：产品默认候选策略，适合作为上线前候选。
- `hybrid_keyword_rerank` / `hyde_hybrid_rerank`：强检索增强策略。
- `agentic_hyde`：复杂问题和导学路径的多步检索策略。

评测报告同时新增 `summary_by_difficulty` 与 `summary_by_chapter`。后续做面试展示时，可以说明系统不是只追求总分，而是能解释“基础题、进阶题、某一章内容”分别是否变好，从而指导下一轮切分、重排和数据补充。

## P1.6 Ranking-Aware Metrics

RAG 评测不能只看“有没有命中来源”，还要看“正确证据排在第几位”。如果正确证据在第 8 条，模型仍然可能因为上下文预算、lost-in-the-middle 或重排不足而使用弱证据。

新增排名指标：

- `first_source_rank`：第一个期望来源出现的位置，越小越好。
- `source_mrr`：Mean Reciprocal Rank，首个命中越靠前得分越高。
- `source_ndcg`：归一化折损累积增益，衡量多个期望来源在列表中的整体排序质量。
- `avg_source_mrr` / `avg_source_ndcg`：策略级平均值，可与 baseline 做对比。

产品侧展示成“证据排序质量”，避免把普通用户暴露在过多指标里；研发和面试侧保留完整 JSON/Markdown 指标，用来证明 rerank、hybrid、adaptive policy 是否真的把关键证据推到了前面。
