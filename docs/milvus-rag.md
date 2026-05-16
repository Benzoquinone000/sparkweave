# Milvus RAG 设计说明

SparkWeave 的知识库检索已经升级为 Milvus 优先的向量数据库方案。对普通用户来说，使用方式不变：上传资料、等待索引完成、在对话或导学中选择知识库即可。对开发和部署来说，RAG 的向量数据从本地 LlamaIndex JSON 存储迁移到了 Milvus collection。

如果需要从代码事实角度解释 RAG 与智能体、画像的关系，参见 [智能体、RAG 与学习画像代码事实说明](./core-ai-code-facts.md)。

## 默认模式

SparkWeave 默认使用 Milvus provider。Windows 原生 Python 环境推荐启动 Milvus Standalone，并通过本地端口连接：

```env
RAG_PROVIDER=milvus
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_PREFIX=sparkweave
```

如果使用项目自带 Docker Compose，`docker compose up -d` 会同时启动 SparkWeave、Milvus Standalone、etcd 和 MinIO。此时 SparkWeave 容器内部不应该连接 `localhost`，而是使用服务名：

```env
DOCKER_MILVUS_URI=http://milvus:19530
```

Compose 文件会自动把 `MILVUS_URI` 覆盖为 `DOCKER_MILVUS_URI`，因此即使本机 `.env` 里保留 `MILVUS_URI=http://localhost:19530`，容器模式也能连接到正确的 Milvus 服务。

Linux、macOS 或 WSL 可以使用 Milvus Lite 文件模式：

```env
MILVUS_URI=./data/milvus/sparkweave.db
```

这种模式不需要额外启动 Milvus 服务，适合本地开发和轻量演示。`data/milvus/` 已加入 `.gitignore`，不会上传到 GitHub。注意：`milvus-lite` 当前不支持 Windows 原生 Python；Windows 请使用 Docker/Standalone 或 WSL。

如果需要连接独立 Milvus 或 Zilliz Cloud，只需要修改：

```env
MILVUS_URI=http://your-milvus-host:19530
DOCKER_MILVUS_URI=http://your-milvus-host:19530
MILVUS_TOKEN=
```

## Docker Compose 部署

项目的 `docker-compose.yml` 内置了 Milvus Standalone 依赖栈：

- `milvus-etcd`: Milvus 元数据服务
- `milvus-minio`: Milvus 对象存储服务
- `milvus`: Milvus Standalone，向宿主机暴露 `19530` 和 `9091`
- `sparkweave`: 后端与前端一体服务，默认连接 `http://milvus:19530`

数据会持久化到：

```text
data/milvus/
  etcd/
  minio/
  standalone/
```

启动：

```powershell
python scripts/start_docker.py --milvus-only
```

查看状态：

```powershell
python scripts/start_docker.py --milvus-only --status
```

Milvus WebUI 默认地址：

```text
http://localhost:9091/webui/
```

如果本机已经占用了 `19530` 或 `9091`，可以在 `.env` 中改端口：

```env
MILVUS_PORT=19531
MILVUS_WEBUI_PORT=9092
```

## 数据结构

每个知识库仍保留本地目录：

```text
data/knowledge_bases/<kb_name>/
  raw/
  milvus_storage/
    metadata.json
  metadata.json
  .progress.json
```

本地目录只保存原始文件、进度和 Milvus collection 元数据。真正用于相似度检索的向量存储在 Milvus 中。

`milvus_storage/metadata.json` 记录：

- `provider`: 固定为 `milvus`
- `collection_name`: 该知识库对应的 Milvus collection
- `uri`: 当前 Milvus 连接地址
- `embedding_model`: 建库时使用的向量模型
- `embedding_dim`: 建库时使用的向量维度
- `document_count`: 已写入文档数

## 索引流程

1. 上传文件进入 `raw/`。
2. PDF 使用 PyMuPDF 读取文本层；扫描版 PDF 可走讯飞 OCR fallback。
3. 文本、代码、Markdown、JSON、CSV 等文件直接读取。
4. LlamaIndex 负责切块，默认 `chunk_size=512`、`chunk_overlap=50`。
5. 当前 Embedding provider 生成向量。
6. `MilvusVectorStore` 写入 Milvus collection。
7. 本地写入 `milvus_storage/metadata.json` 作为 ready marker。

## 检索流程

1. `rag` 工具调用 `sparkweave.services.rag.rag_search()`。
2. `RAGService` 根据 `RAG_PROVIDER` 选择 Milvus pipeline。
3. Pipeline 根据知识库名定位 collection。
4. LlamaIndex retriever 从 Milvus 取回 top-k 片段。
5. 返回 `answer/content/sources/provider/collection_name`。
6. 上层 Chat、DeepSolve、DeepQuestion、DeepResearch、Guide 再组织成用户可读回答。

可调检索参数：

| 环境变量 / 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `RAG_TOP_K` / `top_k` | `5` | 单次检索最多召回的片段数 |
| `RAG_CANDIDATE_TOP_K` / `candidate_top_k` | `RAG_TOP_K` | rerank 前候选召回数；开启 rerank 时建议大于 `RAG_TOP_K` |
| `RAG_SCORE_THRESHOLD` / `score_threshold` | 空 | 可选相关性阈值；低于阈值的片段不会进入上下文 |
| `RAG_MAX_CONTEXT_CHARS` / `max_context_chars` | `8000` | 返回给上层智能体的最大上下文长度 |
| `RAG_RERANKER` / `reranker` | `none` | 二阶段重排器。当前支持 `none`、`keyword` |
| `RAG_RERANK_TOP_N` / `rerank_top_n` | `RAG_TOP_K` | 重排后保留的候选数 |
| `RAG_RERANK_VECTOR_WEIGHT` / `rerank_vector_weight` | `0.65` | `keyword` reranker 中原始向量排序权重 |
| `RAG_RERANK_LEXICAL_WEIGHT` / `rerank_lexical_weight` | `0.35` | `keyword` reranker 中词面命中权重 |
| `RAG_RETRIEVAL_MODE` / `retrieval_mode` | `dense` | 检索模式。可选 `dense` 或 `hybrid` |
| `MILVUS_HYBRID_RANKER` | `RRFRanker` | hybrid 模式的融合策略。可选 `RRFRanker` 或 `WeightedRanker` |
| `MILVUS_HYBRID_RRF_K` | `60` | RRF 融合参数 |
| `MILVUS_DENSE_WEIGHT` | `1.0` | WeightedRanker 下 dense 召回权重 |
| `MILVUS_SPARSE_WEIGHT` | `0.6` | WeightedRanker 下 sparse/BM25 召回权重 |

## Hybrid 检索

SparkWeave 的 Milvus provider 已经支持 hybrid-ready 配置。默认仍使用稳定的 dense vector 检索；当你希望增强代码符号、公式编号、章节标题、专有术语等精确匹配场景时，可以开启 hybrid：

```env
RAG_RETRIEVAL_MODE=hybrid
MILVUS_HYBRID_RANKER=RRFRanker
MILVUS_HYBRID_RRF_K=60
```

或使用 weighted fusion：

```env
RAG_RETRIEVAL_MODE=hybrid
MILVUS_HYBRID_RANKER=WeightedRanker
MILVUS_DENSE_WEIGHT=1.0
MILVUS_SPARSE_WEIGHT=0.6
```

注意：hybrid 模式需要在 Milvus collection 中创建 sparse/BM25 字段，所以必须在开启 `RAG_RETRIEVAL_MODE=hybrid` 后重建索引：

```powershell
python -m sparkweave_cli kb reindex demo --provider milvus
```

如果一个知识库原本是 dense-only，但查询时请求 `retrieval_mode=hybrid`，系统会自动安全降级到 dense，并在返回结果中带上：

```json
{
  "requested_retrieval_mode": "hybrid",
  "indexed_retrieval_mode": "dense",
  "retrieval_mode": "dense",
  "hybrid_fallback_reason": "knowledge_base_was_indexed_without_sparse_vectors"
}
```

这样做是为了避免旧 collection 因 schema 不匹配而检索失败。

## 二阶段重排

SparkWeave 支持 retrieval 后的轻量 rerank。默认关闭，保持最低延迟；开启后建议先扩大候选数，再重排截断：

```env
RAG_CANDIDATE_TOP_K=20
RAG_RERANKER=keyword
RAG_RERANK_TOP_N=5
RAG_RERANK_VECTOR_WEIGHT=0.65
RAG_RERANK_LEXICAL_WEIGHT=0.35
```

当前 `keyword` reranker 是无额外依赖的基础实现，主要用于增强课程术语、代码符号、公式关键词等词面命中。它不是最终的重型 cross-encoder reranker，但能先把二阶段检索链路跑通，并作为后续接入 Jina/Cohere、本地 cross-encoder 或 LLM pairwise rerank 的统一接口。

返回结果会带上：

```json
{
  "candidate_top_k": 20,
  "reranker": "keyword",
  "rerank_applied": true,
  "rerank_input_count": 20,
  "rerank_output_count": 5
}
```

## 证据包与可解释来源

检索结果不再只是拼接原始 chunk，而是经过 Context Pack：

1. 根据 score threshold 过滤低相关片段。
2. 按 chunk id 或文本指纹去重。
3. 根据 `RAG_MAX_CONTEXT_CHARS` 控制上下文预算。
4. 给每个来源生成 `matched_keywords` 和 `evidence_reason`。

返回示例：

```json
{
  "content": "用于回答的上下文...",
  "context_pack": {
    "context_chars": 4200,
    "source_count": 5,
    "skipped_duplicate": 2,
    "skipped_threshold": 1,
    "skipped_budget": 0
  },
  "sources": [
    {
      "title": "gradient.md",
      "source": "/kb/ml/gradient.md",
      "page": 3,
      "score": 0.91,
      "matched_keywords": ["梯度", "负梯度", "损失函数"],
      "evidence_reason": "命中问题关键词：梯度、负梯度、损失函数。"
    }
  ]
}
```

这部分是后续前端“为什么引用这段资料”的基础，也能用于 RAG 对比实验中的可解释报告。

## 兼容策略

旧的本地 LlamaIndex 索引仍可显式使用：

```env
RAG_PROVIDER=llamaindex
```

已有 `llamaindex_storage/` 且核心文件完整的知识库会继续被识别为可用。未知或废弃 provider 会被规范为 `milvus`，并在必要时标记 `needs_reindex=true`，提示用户重建索引。

## 重建索引

从旧索引迁移到 Milvus、切换 Embedding 模型或向量维度后，可以直接从 `raw/` 原始资料重建索引。前端资料库页面提供“重建索引”按钮；CLI 可以运行：

```powershell
python -m sparkweave_cli kb reindex demo --provider milvus
```

HTTP API：

```http
POST /api/v1/knowledge/demo/reindex
Content-Type: application/json

{
  "rag_provider": "milvus",
  "backup": true
}
```

重建时系统会：

1. 读取 `raw/` 中的原始资料。
2. 备份并清理本地索引标记。
3. 删除旧 Milvus collection（如果 marker 中记录了 collection）。
4. 使用当前 Embedding 配置重新写入 Milvus。
5. 将 `needs_reindex` 更新为 `false`。

## 诊断与排障

Milvus 升级后，资料库页面的状态条会显示当前检索引擎。当前资料库卡片里提供“检查连接”按钮，用户点击后只看到面向使用者的摘要和少量检查项，不直接暴露原始 JSON。需要更细的排障信息时，可以使用 CLI 或 API 查看 provider、连接地址、collection marker、embedding 配置和连接检查结果。

CLI：

```powershell
python -m sparkweave_cli kb doctor
python -m sparkweave_cli kb doctor demo --no-connect
python -m sparkweave_cli kb doctor demo --format json
python -m sparkweave_cli kb preflight demo --no-docker
```

HTTP API：

```http
GET /api/v1/knowledge/diagnostics?check_connection=false
GET /api/v1/knowledge/demo/diagnostics?check_connection=true
GET /api/v1/knowledge/preflight?check_connection=true&check_docker=false
GET /api/v1/knowledge/demo/preflight?check_connection=true&check_docker=false
```

常见结果含义：

| 状态 | 含义 | 建议 |
| --- | --- | --- |
| `ok` | 已连接 Milvus，且目标 collection 可见 | 可以直接检索 |
| `configured` | 配置可读取，连接检查被跳过 | 前端健康状态使用该轻量模式 |
| `warning` | marker 缺失、collection 缺失或 Windows 使用了 Milvus Lite 文件模式 | 优先执行“重建索引”或改用 Docker/Standalone |
| `error` | 依赖缺失或 Milvus 连接失败 | 检查 `pymilvus`、`MILVUS_URI`、Docker 服务状态和网络 |

`preflight` 是比 `doctor` 更接近真实验收的入口。它会把 readiness 摘要、连接错误类型、URI mismatch、代理策略和推荐命令合并到一个结果里，供前端“连接检查”页和 E2E 验收脚本使用。典型修复顺序是：

```powershell
python scripts/start_docker.py --milvus-only
python -m sparkweave_cli kb preflight ml-course --no-docker
python -m sparkweave_cli kb reindex ml-course --provider milvus
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --chat-check --cleanup
```

在本机开发模式下推荐 `MILVUS_URI=http://localhost:19530`；在 Compose 容器内推荐 `DOCKER_MILVUS_URI=http://milvus:19530`。如果知识库 marker 记录的是 `http://milvus:19530`，但当前后端运行在宿主机并连接 `http://localhost:19530`，诊断会标记“地址不一致”。这不是单纯的展示问题，意味着后端可能正在看另一个 Milvus 实例，需要统一运行模式后重建索引。

当系统环境存在 `HTTP_PROXY` 或 `HTTPS_PROXY` 时，本地 Milvus REST 检查会对 `localhost`、`127.0.0.1`、私有网段和 Docker 服务名地址自动绕过代理。诊断中的 `proxy.milvus_proxy_bypassed=true` 表示这个保护已生效。

## 相关文件

- `sparkweave/services/rag_support/pipelines/milvus.py`
- `sparkweave/services/rag_support/factory.py`
- `sparkweave/services/rag_support/service.py`
- `sparkweave/services/rag_support/diagnostics.py`
- `sparkweave/services/rag_support/evaluation.py`
- `sparkweave/knowledge/initializer.py`
- `sparkweave/knowledge/add_documents.py`
- `sparkweave/knowledge/reindex.py`
- `sparkweave/knowledge/manager.py`
- `sparkweave/services/kb_config.py`

## 验证

不连接真实 Milvus 的单元测试：

```powershell
pytest tests\tools\test_rag_tool.py tests\services\rag\test_rag_pipelines.py tests\services\rag\test_rag_diagnostics.py tests\knowledge\test_kb_directory_layout.py tests\services\config\test_knowledge_base_config.py tests\api\test_knowledge_router.py tests\ng\test_rag_services.py -q
```

真实索引验证：

```powershell
pip install -r requirements/server.txt
python scripts/start_docker.py --milvus-only
python -m sparkweave_cli kb doctor --no-connect
python -m sparkweave_cli kb preflight demo --no-docker
python -m sparkweave_cli kb create demo --doc tests/services/rag/testfile.txt
python -m sparkweave_cli kb doctor demo
python -m sparkweave_cli chat "根据 demo 知识库回答：Shandong 有什么？" --kb demo --tools rag
```

## RAG Evaluation Loop

SparkWeave now has one reusable evaluation layer shared by script, CLI and API:

- Service: `sparkweave/services/rag_support/evaluation.py`
- Script: `python scripts/rag_eval_experiment.py ...`
- CLI: `python -m sparkweave_cli kb eval <kb_name> <dataset.jsonl>`
- API: `POST /api/v1/knowledge/{kb_name}/rag-eval`

Example:

```powershell
python -m sparkweave_cli kb eval demo docs/examples/rag_eval_dataset.ml_course.sample.jsonl `
  --provider milvus `
  --strategy baseline:top_k=5,max_context_chars=8000 `
  --strategy candidate_rerank:top_k=5,candidate_top_k=20,reranker=keyword,rerank_top_n=5 `
  --output dist/rag-eval-demo.md `
  --json-output dist/rag-eval-demo.json
```

The report records success rate, keyword recall, source hit rate, context-pack
signals, evidence reasons, skipped duplicates, and latency. This turns RAG
optimization into an observable loop instead of a one-off tuning guess.

## Query Transform / HyDE

普通查询默认不做 LLM 改写，避免额外延迟。对概念模糊、用户表述很短的问题，可以在评测策略或运行参数中显式开启 HyDE：

```powershell
python -m sparkweave_cli kb eval demo docs/examples/rag_eval_dataset.ml_course.sample.jsonl `
  --strategy baseline:top_k=5 `
  --strategy hyde:top_k=5,query_transform=hyde,hyde_max_chars=700,hyde_timeout_seconds=8
```

也可以通过环境变量作为默认策略：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `RAG_QUERY_TRANSFORM` | `none` | 查询变换策略。可选 `none`、`hyde` |
| `RAG_HYDE_MAX_CHARS` | `700` | HyDE 假设答案的最大长度 |
| `RAG_HYDE_TIMEOUT_SECONDS` | `8` | HyDE 生成超时时间，超时后自动退回原查询 |

HyDE 的输出只作为 retrieval query 使用；返回结果会保留 `query`、`retrieval_query`、`query_transform_applied` 等字段，方便在评测报告中对比收益和延迟。

## Gated Agentic RAG

普通问题仍走 Fast RAG。复杂问题可以开启 query planner，让系统先拆成少量 focused subqueries，再分别检索并合并证据：

```powershell
python -m sparkweave_cli kb eval demo docs/examples/rag_eval_dataset.ml_course.sample.jsonl `
  --strategy baseline:top_k=5 `
  --strategy agentic:top_k=5,agentic_rag=force,agentic_max_subqueries=3 `
  --strategy agentic_hyde:top_k=5,agentic_rag=force,query_transform=hyde,agentic_max_subqueries=3
```

运行时参数：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `RAG_AGENTIC_MODE` | `off` | `off`、`auto`、`force` |
| `RAG_AGENTIC_MAX_SUBQUERIES` | `3` | 每次最多拆出的子查询数 |
| `RAG_AGENTIC_TIMEOUT_SECONDS` | `8` | LLM query planner 超时，超时后自动使用规则拆分 |
| `RAG_AGENTIC_MIN_QUERY_CHARS` | `80` | `auto` 模式下长问题触发规划的长度阈值 |
| `RAG_AGENTIC_MAX_CONCURRENCY` | `3` | Maximum parallel focused retrieval branches |
| `RAG_AGENTIC_MAX_REPAIR_BRANCHES` | `3` | Maximum weak branches retried before full fallback |
| `RAG_AGENTIC_MAX_CONTEXT_CHARS` | unset | Optional merged context budget; defaults to request `max_context_chars` then `RAG_MAX_CONTEXT_CHARS` |
| `RAG_AGENTIC_MAX_SOURCES` | unset | Optional cap for merged, deduplicated sources |
| `RAG_AGENTIC_FALLBACK_TO_SINGLE` | `true` | Retry the original query when agentic evidence is weak |
| `RAG_AGENTIC_MIN_SOURCES` | `1` | Minimum merged source count before the evidence is accepted |
| `RAG_AGENTIC_MIN_COVERAGE_RATIO` | `0.5` | Minimum ratio of subqueries that returned evidence |
| `RAG_AGENTIC_MIN_RELEVANT_COVERAGE_RATIO` | `0.67` | Minimum ratio of subqueries whose evidence overlaps the focused query |
| `RAG_AGENTIC_MIN_CONTEXT_CHARS` | `120` | Minimum merged context size before synthesis |
| `RAG_AGENTIC_MIN_SCORE` | unset | Optional high-is-better source score threshold |

返回结果会带上 `agentic_rag`、`query_plan`、`subquery_results` 和每条 source 对应的 `subquery`，适合在前端做“多路检索证据链”可视化，也适合面试时讲清楚为什么不是盲目 agent loop。
