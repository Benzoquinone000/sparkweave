# 环境变量配置

SparkWeave 通过 `.env` 管理本地运行、模型服务、知识库、搜索、OCR 和部署配置。建议从 `.env.example` 复制后再填写真实密钥。

设置页会把 active model catalog 渲染回 `.env`；catalog、provider 推断和缓存失效细节见 [设置与 Provider 配置](./settings-and-providers.md)。

```powershell
copy .env.example .env
```

## 端口

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` | `8001` | FastAPI 后端端口 |
| `FRONTEND_PORT` | `3782` | Vite 前端端口 |

## 供应商共享凭据

设置页和 `.env` 都以供应商级密钥为主：同一家供应商只维护一套参数，再由运行时共享给问答、Embedding、联网搜索、OCR、TTS 等能力。

| 变量 | 说明 |
| --- | --- |
| `IFLYTEK_APPID` | 科大讯飞 APPID |
| `IFLYTEK_API_KEY` | 科大讯飞 APIKey |
| `IFLYTEK_API_SECRET` | 科大讯飞 APISecret |
| `IFLYTEK_API_PASSWORD` | 科大讯飞 APIPassword，可留空；留空时运行时会用 `APIKey:APISecret` |
| `SILICONFLOW_API_KEY` | 硅基流动 APIKey，LLM / Embedding / DeepSeek-OCR 共用 |

服务级变量如 `LLM_API_KEY`、`EMBEDDING_API_KEY`、`SEARCH_API_KEY`、`IFLYTEK_OCR_API_KEY`、`IFLYTEK_TTS_API_KEY` 仍保留为旧配置兼容项。新配置建议只填写本节共享凭据。

## LLM

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `LLM_BINDING` | 是 | 模型提供商，如 `openai`、`lm_studio`、`ollama`、`azure_openai`、`deepseek`、`iflytek_spark_ws` |
| `LLM_MODEL` | 是 | 聊天模型名称 |
| `LLM_API_KEY` | 是 | 模型访问密钥 |
| `LLM_HOST` | 是 | OpenAI-compatible API 地址 |
| `LLM_API_VERSION` | 否 | Azure OpenAI 等提供商可能需要 |
| `LLM_CONNECT_TIMEOUT` | 否 | 模型服务连接超时，默认 `10` 秒 |
| `LLM_REQUEST_TIMEOUT` | 否 | 单次模型请求等待时间，默认 `900` 秒 |

OpenAI-compatible 示例：

```env
LLM_BINDING=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key
LLM_HOST=https://api.openai.com/v1
LLM_CONNECT_TIMEOUT=10
LLM_REQUEST_TIMEOUT=900
```

本地 LM Studio 示例：

```env
LLM_BINDING=lm_studio
LLM_MODEL=local-model
LLM_API_KEY=not-needed
LLM_HOST=http://localhost:1234/v1
```

## 科大讯飞星火 LLM

SparkWeave 仅保留星火 X2 / X1.5 的 OpenAI 兼容 HTTP 入口，模型名统一为 `spark-x`。

```env
IFLYTEK_APPID=your-appid
IFLYTEK_API_KEY=your-api-key
IFLYTEK_API_SECRET=your-api-secret
LLM_BINDING=iflytek_spark_ws
LLM_MODEL=spark-x
LLM_API_KEY=
LLM_HOST=https://spark-api-open.xf-yun.com/x2/
```

讯飞星火大模型仅保留 X2 与 X1.5。二者模型名都填写 `spark-x`；X2 使用 `https://spark-api-open.xf-yun.com/x2/`，X1.5 使用 `https://spark-api-open.xf-yun.com/v2/`。旧的普通星火模型或旧 WebSocket 地址会在运行时迁移为 X2 的 HTTP 地址。
设置页选择 `iFlytek Spark X` 后支持两种鉴权方式：`APIPassword` 直填，或 `APIKey + APISecret` 分栏填写并自动保存为 `APIKey:APISecret`。

## Embedding

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `EMBEDDING_BINDING` | 是 | Embedding 提供商 |
| `EMBEDDING_MODEL` | 是 | Embedding 模型名称 |
| `EMBEDDING_API_KEY` | 是 | Embedding API Key |
| `EMBEDDING_HOST` | 是 | Embedding API 地址 |
| `EMBEDDING_DIMENSION` | 是 | 向量维度，必须与模型返回维度一致 |
| `EMBEDDING_API_VERSION` | 否 | 特定提供商需要 |

OpenAI 示例：

```env
EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=your-api-key
EMBEDDING_HOST=https://api.openai.com/v1
EMBEDDING_DIMENSION=3072
```

科大讯飞 Embedding 示例：

```env
IFLYTEK_APPID=your-appid
IFLYTEK_API_KEY=your-api-key
IFLYTEK_API_SECRET=your-api-secret
EMBEDDING_BINDING=iflytek_spark
EMBEDDING_MODEL=llm-embedding
EMBEDDING_API_KEY=
EMBEDDING_HOST=https://emb-cn-huabei-1.xf-yun.com/
EMBEDDING_DIMENSION=2560
```

## RAG 与 Milvus

知识库默认使用 Milvus 作为向量数据库。Windows 原生 Python 环境推荐启动 Milvus Standalone，并通过本地端口连接：

```env
RAG_PROVIDER=milvus
SPARKWEAVE_KB_BACKGROUND_WORKERS=1
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_PREFIX=sparkweave
MILVUS_SIMILARITY_METRIC=IP
MILVUS_CONSISTENCY_LEVEL=Strong
MILVUS_OVERWRITE_ON_INIT=1
RAG_TOP_K=5
RAG_CANDIDATE_TOP_K=20
RAG_SCORE_THRESHOLD=
RAG_MAX_CONTEXT_CHARS=8000
RAG_RERANKER=none
RAG_RERANK_TOP_N=5
RAG_RERANK_VECTOR_WEIGHT=0.65
RAG_RERANK_LEXICAL_WEIGHT=0.35
RAG_RETRIEVAL_MODE=dense
MILVUS_HYBRID_RANKER=RRFRanker
MILVUS_HYBRID_RRF_K=60
MILVUS_DENSE_WEIGHT=1.0
MILVUS_SPARSE_WEIGHT=0.6
```

使用项目自带 Docker Compose 时，SparkWeave 容器会连接 compose 网络内的 Milvus 服务：

```env
DOCKER_MILVUS_URI=http://milvus:19530
```

如果要让 Docker 连接外部 Milvus 或 Zilliz Cloud，请同时配置 `DOCKER_MILVUS_URI`，避免容器内部把 `localhost` 解析成 SparkWeave 容器自身。

Linux、macOS 或 WSL 环境可以使用 Milvus Lite 文件模式：

```env
MILVUS_URI=./data/milvus/sparkweave.db
```

连接独立 Milvus 或 Zilliz Cloud 时，保持 `RAG_PROVIDER=milvus`，把 `MILVUS_URI` 改成服务地址，并按需填写：

```env
MILVUS_TOKEN=your-token
```

如果需要回退到旧的本地 JSON 索引，可以显式配置：

```env
RAG_PROVIDER=llamaindex
```

切换 Embedding provider、模型名或向量维度后，已有知识库会被标记为需要重建索引。

`RAG_TOP_K` 控制最终最多使用多少个片段；`RAG_CANDIDATE_TOP_K` 控制 rerank 前先召回多少候选；`RAG_SCORE_THRESHOLD` 用于过滤低相关片段，默认留空；`RAG_MAX_CONTEXT_CHARS` 控制返回给上层智能体的上下文长度，避免大资料库检索时输出过长。`RAG_RERANKER=keyword` 可以开启轻量二阶段重排；`RAG_RETRIEVAL_MODE=hybrid` 会启用 Milvus sparse/BM25 字段和 hybrid ranker，这会改变 collection schema，因此旧知识库需要重建索引后才能真正使用 hybrid。

## 搜索

| 变量 | 说明 |
| --- | --- |
| `SEARCH_PROVIDER` | 搜索提供商 |
| `SEARCH_API_KEY` | 搜索服务密钥 |
| `SEARCH_BASE_URL` | 搜索服务地址 |

联网搜索支持 `duckduckgo`、`searxng`、`jina`、`brave`、`tavily`、`perplexity`、`serper` 和 `iflytek_spark`。

科大讯飞 ONE SEARCH 使用 `APIPassword`：

```env
IFLYTEK_API_KEY=your-api-key
IFLYTEK_API_SECRET=your-api-secret
# 或直接填写 IFLYTEK_API_PASSWORD=your-iflytek-search-apipassword
SEARCH_PROVIDER=iflytek_spark
SEARCH_API_KEY=
SEARCH_BASE_URL=https://search-api-open.cn-huabei-1.xf-yun.com/v2/search
```

旧配置也可以把讯飞搜索密钥写入 `SEARCH_API_KEY` 或 `IFLYTEK_SEARCH_API_PASSWORD`。官方文档：https://www.xfyun.cn/doc/spark/Search_API/search_API.html

## OCR 与扫描版 PDF

| 变量 | 说明 |
| --- | --- |
| `SPARKWEAVE_OCR_PROVIDER` | OCR 提供商，支持 `iflytek`、`siliconflow`、`disabled` |
| `SPARKWEAVE_PDF_OCR_STRATEGY` | PDF OCR 策略，如 `ocr_first`、`iflytek_first`、`auto` |
| `SPARKWEAVE_OCR_TIMEOUT` | OCR 超时时间，单位秒，默认 `90` |
| `SPARKWEAVE_OCR_MAX_PAGES` | 单次处理最大页数，留空默认不限制 |
| `SPARKWEAVE_OCR_DPI` | PDF 转图片 DPI，默认 `200` |
| `SPARKWEAVE_OCR_MIN_TEXT_CHARS` | 文本层最少字符数，低于该值可触发 OCR，默认 `40` |

科大讯飞 OCR 示例：

```env
IFLYTEK_APPID=your-appid
IFLYTEK_API_KEY=your-api-key
IFLYTEK_API_SECRET=your-api-secret
SPARKWEAVE_OCR_PROVIDER=iflytek
SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first
IFLYTEK_OCR_URL=https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm
IFLYTEK_OCR_SERVICE_ID=se75ocrbm
IFLYTEK_OCR_CATEGORY=ch_en_public_cloud
```

硅基流动 DeepSeek-OCR 示例：

```env
SILICONFLOW_API_KEY=your-siliconflow-api-key
SPARKWEAVE_OCR_PROVIDER=siliconflow
SPARKWEAVE_PDF_OCR_STRATEGY=ocr_first
SILICONFLOW_OCR_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_OCR_MODEL=deepseek-ai/DeepSeek-OCR
SILICONFLOW_OCR_PROMPT=<image>\n<|grounding|>Convert the document to markdown.
SILICONFLOW_OCR_MAX_TOKENS=8192
```

OCR 在知识库 PDF 解析和图像题能力中的调用链路见 [视觉输入、OCR 与 GeoGebra 图像分析](./vision-ocr-geogebra.md)。

## 数学动画

| 变量 | 说明 |
| --- | --- |
| `SPARKWEAVE_MANIM_PYTHON` | 指定 Manim 使用的 Python 解释器 |
| `SPARKWEAVE_MATH_ANIMATOR_REPAIR_TIMEOUT` | Manim 代码自动修复等待时间，默认 `300` 秒 |
| `SPARKWEAVE_MATH_ANIMATOR_RENDER_TIMEOUT` | Manim 单次渲染最长等待时间，默认 `900` 秒 |

只有当 Manim 位于另一个 Python 环境时，才需要显式配置。

## Docker 与远程部署

容器内访问宿主机模型时，不要使用 `localhost` 或 `127.0.0.1`。

Windows / macOS Docker Desktop：

```env
LLM_HOST=http://host.docker.internal:1234/v1
EMBEDDING_HOST=http://host.docker.internal:1234/v1
```

Linux 通常使用宿主机局域网 IP：

```env
LLM_HOST=http://192.168.1.100:1234/v1
```

前端远程访问后端时可配置：

```env
NEXT_PUBLIC_API_BASE_EXTERNAL=https://your-api.example.com
NEXT_PUBLIC_API_BASE=https://your-api.example.com
```

## 安全

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DISABLE_SSL_VERIFY` | `false` | 是否关闭 SSL 证书校验 |

生产环境应保持：

```env
DISABLE_SSL_VERIFY=false
```
