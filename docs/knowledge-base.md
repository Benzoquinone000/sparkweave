# 知识库与 RAG

SparkWeave 的知识库用于课程资料检索、导学 grounding、题目生成上下文和多智能体答疑。当前默认方案是：

- RAG provider：`milvus`
- 索引框架：LlamaIndex
- 向量数据库：Milvus / Milvus Lite
- Windows 推荐连接：`http://localhost:19530`
- Docker Compose 推荐连接：`http://milvus:19530`
- Linux/macOS/WSL 可选本地向量库：`./data/milvus/sparkweave.db`
- 兼容回退：`RAG_PROVIDER=llamaindex`

对用户来说，使用方式保持简单：创建资料库、上传资料、等待索引完成、在对话或导学里选择资料库。

## 目录结构

单个知识库目录：

```text
data/knowledge_bases/<kb_name>/
  raw/
  milvus_storage/
    metadata.json
  metadata.json
  .progress.json
```

全局配置：

```text
data/knowledge_bases/kb_config.json
```

重要文件：

| 文件 | 说明 |
| --- | --- |
| `raw/` | 上传或同步进来的原始文件 |
| `milvus_storage/metadata.json` | Milvus collection、embedding 模型、维度和更新时间 |
| `metadata.json` | 单库 metadata、文件 hash、linked folders |
| `.progress.json` | 最近一次创建、上传或同步任务进度 |
| `kb_config.json` | 知识库注册表、默认库、状态、embedding 指纹 |
| `data/milvus/sparkweave.db` | Milvus Lite 向量数据库文件；适合 Linux、macOS 或 WSL |

## 核心类

| 类 | 文件 | 责任 |
| --- | --- | --- |
| `KnowledgeBaseManager` | `sparkweave/knowledge/manager.py` | 列表、默认库、状态、metadata、linked folder、索引就绪判断 |
| `KnowledgeBaseInitializer` | `sparkweave/knowledge/initializer.py` | 创建目录、写 metadata、初始化 RAG 索引 |
| `DocumentAdder` | `sparkweave/knowledge/add_documents.py` | 增量添加文档、去重、更新 hash |
| `document_inventory` helpers | `sparkweave/knowledge/document_inventory.py` | 文档列表、Markdown 预览缓存、Milvus 向量块列表和删除 |
| `reindex_knowledge_base` | `sparkweave/knowledge/reindex.py` | 从 `raw/` 重新收集文件并重建当前 provider 索引 |
| `ProgressTracker` | `sparkweave/knowledge/progress_tracker.py` | 写 `.progress.json` 和 `kb_config.json`，广播进度 |
| `RAGService` | `sparkweave/services/rag_support/service.py` | 初始化、检索、删除的统一 facade |
| `MilvusPipeline` | `sparkweave/services/rag_support/pipelines/milvus.py` | 文档解析、embedding、Milvus 写入、检索 |
| `LlamaIndexPipeline` | `sparkweave/services/rag_support/pipelines/llamaindex.py` | 本地 LlamaIndex JSON 索引兼容回退 |
| `FileTypeRouter` | `sparkweave/services/rag_support/file_routing.py` | 文件类型分类和可上传扩展名 |

## 任务执行模型

知识库初始化、上传、同步文件夹和重建索引都可能触发 OCR、Embedding、Milvus 写入等重任务。当前 API 不直接在 FastAPI 请求协程里执行这些任务，而是通过 `sparkweave/api/routers/knowledge.py` 中的专用线程池调度：

```text
POST /knowledge/create
POST /knowledge/{kb}/upload
POST /knowledge/{kb}/reindex
POST /knowledge/{kb}/sync-folder/{folder_id}
  -> _schedule_kb_task()
  -> ThreadPoolExecutor(thread_name_prefix="sparkweave-kb")
  -> asyncio.run(...)
  -> ProgressTracker + task stream
```

线程池大小由环境变量控制：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `SPARKWEAVE_KB_BACKGROUND_WORKERS` | `1` | 知识库后台 worker 数，代码中限制在 1 到 4 之间 |

默认只开 1 个 worker 是有意设计：OCR、Embedding 和 Milvus 写入都比较重，而且 LlamaIndex `Settings` 是进程级全局对象。并发过高会增加资源争用和模型配置串扰风险。

任务状态有两套可观察入口：

| 入口 | 作用 |
| --- | --- |
| `/api/v1/knowledge/tasks/{task_id}/stream` | SSE 任务日志，用于查看 queued/running/completed/error 和日志 |
| `/api/v1/knowledge/{kb_name}/progress` | 读取 `.progress.json` 最近状态 |
| `/api/v1/knowledge/{kb_name}/progress/ws` | WebSocket 进度通道，任务完成或异常后会自动结束 |
| `/api/v1/knowledge/{kb_name}/progress/clear` | 清掉卡住或过期的进度文件 |

这意味着“创建知识库卡住”时，优先看 task stream 和 `.progress.json`，而不是只看 HTTP 请求是否返回。HTTP 返回 task_id 后，真正处理在后台 worker 中进行。

## 支持文件类型

`FileTypeRouter.get_supported_extensions()` 当前包含：

| 类型 | 扩展名 |
| --- | --- |
| PDF | `.pdf` |
| 文本和源码 | `.txt`、`.md`、`.json`、`.csv`、`.yaml`、`.py`、`.js`、`.ts`、`.cpp`、`.html`、`.css`、`.sql` 等文本类扩展 |

PDF 文本提取策略：

| 策略 | 行为 |
| --- | --- |
| 默认 `auto` | 先用 PyMuPDF 读文本层；如果文本过短且 OCR provider 已配置，再尝试 OCR |
| `SPARKWEAVE_PDF_OCR_STRATEGY=ocr_first` | 先用当前 OCR provider，失败或空结果再回退 PyMuPDF |
| `SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first` | 兼容旧配置；等价于 OCR 优先，但建议新配置使用 `ocr_first` |

## 创建知识库

HTTP API：

```http
POST /api/v1/knowledge/create
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 知识库名称 |
| `files` | file[] | 至少一个支持的文件 |
| `rag_provider` | string | 可选；默认 `milvus`，兼容 `llamaindex` |

后台流程：

1. `KnowledgeBaseManager.update_kb_status()` 注册为 `initializing`。
2. `KnowledgeBaseInitializer.create_directory_structure()` 创建 `raw/` 和 `milvus_storage/`。
3. 上传文件保存到 `raw/`。
4. `RAGService.initialize()` 选择 `MilvusPipeline`。
5. Pipeline 做 embedding connectivity smoke test。
6. PDF 解析或文本读取后构建 LlamaIndex `Document`。
7. LlamaIndex 切块，默认 `chunk_size=512`、`chunk_overlap=50`。
8. 当前 Embedding provider 生成向量。
9. `MilvusVectorStore` 写入 Milvus collection。
10. 写入 `milvus_storage/metadata.json` ready marker。
11. `ProgressTracker` 写入完成状态。

CLI：

```bash
sparkweave kb create math --doc textbook.pdf
sparkweave kb create math --docs-dir ./materials
```

## 增量上传

HTTP API：

```http
POST /api/v1/knowledge/{kb_name}/upload
Content-Type: multipart/form-data
```

规则：

- 只允许写入已存在且 ready 的知识库。
- 如果 `needs_reindex=true`，接口返回 409。
- `DocumentAdder` 根据 `metadata.json.file_hashes` 去重。
- 同名但内容不同的文件默认拒绝，避免覆盖已索引内容。
- 新文件会插入当前 provider 对应的索引；默认是 Milvus collection。
- 上传文件会先写入 `.uploads/<task_id>/` staging 目录，再由后台任务恢复并复制到 `raw/`。
- 增量导入成功后，`metadata.json.update_history` 会追加 `incremental_add` 记录。

CLI：

```bash
sparkweave kb add math --doc new-notes.md
sparkweave kb add math --docs-dir ./new-materials
```

## 文档管理与向量块管理

资料库页面的“文档”和“向量块”能力对应 `sparkweave/knowledge/document_inventory.py`。

### 文档列表

API：

```http
GET /api/v1/knowledge/{kb_name}/documents?include_vectors=true
```

返回内容来自 `raw/`，而不是 Milvus collection。每个文件会有稳定的 `document_id`：

```text
document_id = sha1(raw 相对路径)[:16]
```

如果 `include_vectors=true`，系统会尝试读取 Milvus rows，按 `file_name` / `file_path` 聚合每个 raw 文档对应的 vector count 和 sample chunks。若当前环境无法检查 Milvus，文档仍会返回，只是 `vectors_available=false`。

### Markdown / OCR 预览

API：

```http
GET /api/v1/knowledge/{kb_name}/documents/{document_id}/preview
```

预览逻辑：

- PDF：复用 LlamaIndex pipeline 的 PDF 文本/OCR 提取策略。
- 图片：复用 LlamaIndex pipeline 的图片 OCR 提取策略。
- 文本类文件：直接按 UTF-8 读取，错误字符替换。
- 结果缓存到：

```text
data/knowledge_bases/<kb_name>/extracted_markdown/<document_id>_<stem>.md
```

缓存的意义是让用户能看到“实际进入知识库前被提取出的文本/Markdown”，也避免频繁重复 OCR。

### 向量块列表

API：

```http
GET /api/v1/knowledge/{kb_name}/vectors
GET /api/v1/knowledge/{kb_name}/vectors?document_id=<document_id>
```

该接口会读取 `milvus_storage/metadata.json` 中的 `collection_name`，再通过 `pymilvus.MilvusClient.query()` 查看向量行，并排除 `embedding` / `vector` / `sparse_embedding` 等大字段，只返回文本预览和 metadata。

限制与边界：

- 单次扫描上限由代码常量 `MAX_VECTOR_SCAN=5000` 控制。
- `limit` 参数被限制在 1 到 200。
- Windows 原生 Python 下，`document_inventory` 会禁用 Milvus rows 检查，返回提示：`Native Windows Milvus inspection is disabled; use Docker or WSL for vector-row management.` 这是为了避免 `pymilvus` 在部分 Windows 环境中硬崩。
- Docker 或 WSL 环境更适合做向量块级管理。

### 删除文档与删除向量块

删除 raw 文档：

```http
DELETE /api/v1/knowledge/{kb_name}/documents/{document_id}
```

请求体可选：

```json
{
  "remove_raw": true,
  "remove_vectors": true
}
```

行为：

- `remove_vectors=true` 时，先尝试删除该文档对应的 Milvus rows。
- `remove_raw=true` 时，删除 `raw/` 下的原文件。
- 同时删除 `extracted_markdown/` 下对应预览缓存。
- 成功后会更新 Milvus marker 中的 `document_count`。

删除单个向量块：

```http
DELETE /api/v1/knowledge/{kb_name}/vectors/{node_id}
```

该操作只删除派生的向量 row，不会删除 `raw/` 原始文件。因此如果后续重建索引，该 chunk 可能重新出现。这是“临时清理向量数据”和“永久删除资料”的核心区别。

## 查询知识库

主路径是工具 `rag`，能力图通过工具注册表调用。

服务层入口：

```python
from sparkweave.services.rag import rag_search

result = await rag_search(query="矩阵特征值", kb_name="math")
```

返回结构：

```json
{
  "query": "矩阵特征值",
  "answer": "retrieved context...",
  "content": "retrieved context...",
  "sources": [
    {
      "title": "linear-algebra.pdf",
      "source": "data/knowledge_bases/math/raw/linear-algebra.pdf",
      "chunk_id": "...",
      "score": 0.82
    }
  ],
  "provider": "milvus",
  "collection_name": "sparkweave_math_...",
  "success": true
}
```

检索默认召回 5 个片段。需要控制上下文质量时，可以配置 `RAG_TOP_K`、`RAG_CANDIDATE_TOP_K`、`RAG_SCORE_THRESHOLD` 和 `RAG_MAX_CONTEXT_CHARS`，或在工具调用时传入对应参数。需要增强专有名词、代码符号、公式编号和章节标题的命中时，可以先开启 `RAG_RERANKER=keyword` 做二阶段重排；如果还需要 dense+sparse 融合，可以在建库前设置 `RAG_RETRIEVAL_MODE=hybrid`，再重建索引。旧 dense-only 知识库会在请求 hybrid 时自动降级到 dense，避免 schema 不匹配。

## Milvus 配置

Windows / Milvus Standalone：

```env
RAG_PROVIDER=milvus
MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
MILVUS_COLLECTION_PREFIX=sparkweave
MILVUS_SIMILARITY_METRIC=IP
MILVUS_CONSISTENCY_LEVEL=Strong
MILVUS_OVERWRITE_ON_INIT=1
```

项目自带 Docker Compose 会同时启动 Milvus、etcd 和 MinIO。SparkWeave 容器内部使用：

```env
DOCKER_MILVUS_URI=http://milvus:19530
```

Linux、macOS 或 WSL 的 Milvus Lite 文件模式：

```env
RAG_PROVIDER=milvus
MILVUS_URI=./data/milvus/sparkweave.db
```

连接 Zilliz Cloud 或远程 Milvus：

```env
RAG_PROVIDER=milvus
MILVUS_URI=http://your-milvus-host:19530
MILVUS_TOKEN=
```

兼容旧本地索引：

```env
RAG_PROVIDER=llamaindex
```

## 重建索引

以下情况建议重建知识库索引：

- 更换了 Embedding provider。
- 更换了 Embedding 模型。
- `EMBEDDING_DIMENSION` 改变。
- 旧知识库来自废弃 provider。
- `kb_config.json` 中出现 `needs_reindex=true`。

前端资料库页面可以直接点击“重建索引”。CLI：

```bash
sparkweave kb reindex math --provider milvus
```

API：

```http
POST /api/v1/knowledge/math/reindex
```

重建会从 `raw/` 原始资料重新写入当前 provider 的索引，不需要重新上传文件。

代码事实：

- `collect_raw_documents()` 只收集 `FileTypeRouter.get_glob_patterns()` 覆盖的支持文件。
- 如果 `raw/` 为空，重建会把知识库标记为 `error`，并设置 `needs_reindex=true`。
- 重建前会调用 `KnowledgeBaseManager.clean_rag_storage()` 清理旧索引；如果 marker 中记录了旧 Milvus collection，会尝试 drop collection。
- 成功后会把 `needs_reindex=false` 写回 `kb_config.json`。

因此，重建索引是“从 raw 源数据恢复向量库”的操作，不是“重新上传文件”。

## 诊断命令

资料库页面提供“检查连接”按钮，用于快速确认 Milvus 连接、collection 和向量配置。排查 RAG provider、Milvus 连接或 collection marker 时，也可以使用 CLI 轻量诊断：

```bash
sparkweave kb doctor
sparkweave kb doctor math --no-connect
sparkweave kb preflight
sparkweave kb preflight math --no-docker
```

对应 API：

```http
GET /api/v1/knowledge/diagnostics?check_connection=false
GET /api/v1/knowledge/math/diagnostics?check_connection=true
GET /api/v1/knowledge/preflight?check_connection=true&check_docker=false
GET /api/v1/knowledge/math/preflight?check_connection=true&check_docker=false
```

`check_connection=false` 不连接 Milvus，适合前端健康状态和快速配置检查；`check_connection=true` 会实际访问 Milvus，并确认目标 collection 是否存在。

`preflight` 是面向真实闭环验收的前置检查，会把诊断结果整理成用户可理解的 `status`、`label`、`summary` 和 `primary_action`，并附带本地开发可执行的推荐命令。它会识别：

- 当前后端连接的 Milvus 地址和知识库 marker 中记录的地址是否一致。
- Milvus 是否能连接，是否出现 `connection_refused`、代理误走本地地址等问题。
- 目标 collection 是否存在，向量数量是否大于 0。
- 可选 Docker 检查是否能确认本地 Compose/Milvus 服务已启动。

如果本机设置了 `HTTP_PROXY` 或 `HTTPS_PROXY`，系统会对 `localhost`、`127.0.0.1`、私有网段和 Docker 服务名 Milvus 地址自动绕过代理；诊断里会显示代理是否被绕过，避免把本地 Milvus 请求错误地发到外部代理。

## RAG 端到端验收

开发和发布前可以用 `scripts/rag_e2e_acceptance.py` 做一次真实 API 闭环验收。它模拟前端上传流程，创建一个临时 Markdown fixture，等待后台索引完成，然后依次检查文档清单、向量行、RAG 诊断和一次 `rag-test` 检索：

```bash
python scripts/rag_e2e_acceptance.py \
  --base-url http://127.0.0.1:8001 \
  --cleanup \
  --json-output dist/rag-e2e-acceptance.json
```

脚本默认会先调用 `/api/v1/knowledge/preflight`，只有环境预检通过后才会创建临时验收知识库。这样 Milvus 未启动、URI 不一致或 Embedding 配置明显不匹配时，验收会在 `rag_preflight` 阶段停止，不会在 `kb_config.json` 里留下 `sparkweave-rag-e2e-*` 残留记录。

只需要启动本机 RAG 向量库时，可以先运行：

```powershell
python scripts/start_docker.py --milvus-only
```

这个命令只启动 Milvus、etcd 和 MinIO，不会构建或重启 SparkWeave 前后端，适合本地后端已经运行、只差向量数据库的场景。

验收通过意味着：

- `POST /api/v1/knowledge/create` 能接收文件并返回任务。
- `/progress` 能进入完成态。
- `/documents` 能看到上传文件。
- `/vectors` 能看到至少 1 条向量 chunk。
- `/diagnostics` 没有报告 provider、marker 或 collection 错误。
- `/rag-test` 能返回 source，并在证据里命中 fixture 关键词。

需要验证对话入口也能使用 RAG 时，加上：

```bash
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --chat-check --cleanup
```

常用选项：

| 选项 | 说明 |
| --- | --- |
| `--no-preflight` | 跳过预检，直接执行创建/复用知识库流程；只建议在已经确认环境可用时使用 |
| `--preflight-check-docker` | 让后端额外检查 Docker CLI 和 Docker engine 状态 |
| `--reuse-existing --kb <name>` | 不创建临时库，直接验收已有知识库是否有文档、向量和可召回来源 |
| `--chat-check` | 在 `rag-test` 之外再验证 Chat 入口是否会使用 RAG tool |

如果要检查已有知识库，不重新上传文件：

```bash
python scripts/rag_e2e_acceptance.py \
  --base-url http://127.0.0.1:8001 \
  --kb math \
  --reuse-existing \
  --question "这份资料主要讲了什么？"
```

`--reuse-existing` 默认只要求已有库有文档、有向量并能返回来源；如果需要强制检查特定证据，可以重复传入 `--expected-keyword`。

## RAG 评测入口

知识库 API 也暴露了轻量 RAG 评测能力：

```http
POST /api/v1/knowledge/{kb_name}/rag-eval
GET /api/v1/knowledge/{kb_name}/rag-eval/latest
```

评测服务来自 `sparkweave/services/rag_support/evaluation.py`。它支持直接传入 cases，也支持 preset：

| preset / strategy | 说明 |
| --- | --- |
| `baseline` | 基础 dense 检索 |
| `adaptive_policy` | 让 retrieval policy 按问题类型自动选择参数 |
| `hybrid_keyword_rerank` | hybrid + keyword rerank |
| `hyde_hybrid_rerank` | HyDE + hybrid + keyword rerank |
| `agentic_hyde` | 受控 Agentic RAG + HyDE |

最新报告保存到：

```text
data/knowledge_bases/<kb_name>/rag_eval/latest.json
```

当前评测重点是 retrieval 质量和证据排序，不是完整答案事实性裁判。指标包括 keyword recall、source hit、MRR、nDCG、context chars、latency、证据理由数量和上下文预算跳过情况。

本地脚本基准入口：

```bash
python scripts/validate_rag_eval_dataset.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl \
  --min-cases 30 \
  --min-query-types 5 \
  --require-kb \
  --json-output dist/rag-eval-dataset-check.json

python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl \
  --kb ml-course \
  --provider milvus \
  --preset rag-upgrade \
  --output dist/rag-eval-report.md \
  --json-output dist/rag-eval-report.json
```

建议先验证数据集，再跑真实检索实验。验证脚本会检查 case id 是否重复、样本量是否足够、query_type 覆盖是否达标，以及每个样本是否提供 `expected_keywords` 和 `expected_sources`，避免评测结果因为数据集缺字段而失真。

## 相关文档

- [功能级代码地图](./feature-code-map.md)
- [智能体、RAG 与学习画像代码事实说明](./core-ai-code-facts.md)
- [Milvus RAG 设计说明](./milvus-rag.md)
- [RAG 升级设计与对比实验](./rag-improvement-design.md)
- [环境变量配置](./configuration.md)
- [系统诊断与 Provider 健康检查](./system-diagnostics.md)
- [工具系统](./tools.md)
