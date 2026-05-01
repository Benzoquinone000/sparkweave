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
LLM_BINDING=iflytek_spark_ws
LLM_MODEL=spark-x
LLM_API_KEY=your-iflytek-api-password-or-ak-sk
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
EMBEDDING_BINDING=iflytek_spark
EMBEDDING_MODEL=llm-embedding
EMBEDDING_API_KEY=your-iflytek-embedding-apikey
EMBEDDING_HOST=https://emb-cn-huabei-1.xf-yun.com/
EMBEDDING_DIMENSION=2560
IFLYTEK_EMBEDDING_APPID=your-iflytek-appid
IFLYTEK_EMBEDDING_API_KEY=your-iflytek-embedding-apikey
IFLYTEK_EMBEDDING_API_SECRET=your-iflytek-embedding-apisecret
```

## 搜索

| 变量 | 说明 |
| --- | --- |
| `SEARCH_PROVIDER` | 搜索提供商 |
| `SEARCH_API_KEY` | 搜索服务密钥 |
| `SEARCH_BASE_URL` | 搜索服务地址 |

联网搜索支持 `duckduckgo`、`searxng`、`jina`、`brave`、`tavily`、`perplexity`、`serper` 和 `iflytek_spark`。

科大讯飞 ONE SEARCH 使用 `APIPassword`：

```env
SEARCH_PROVIDER=iflytek_spark
SEARCH_API_KEY=your-iflytek-search-apipassword
SEARCH_BASE_URL=https://search-api-open.cn-huabei-1.xf-yun.com/v2/search
```

也可以把讯飞搜索密钥写入 `IFLYTEK_SEARCH_API_PASSWORD`。官方文档：https://www.xfyun.cn/doc/spark/Search_API/search_API.html

## OCR 与扫描版 PDF

| 变量 | 说明 |
| --- | --- |
| `SPARKWEAVE_OCR_PROVIDER` | OCR 提供商 |
| `SPARKWEAVE_PDF_OCR_STRATEGY` | PDF OCR 策略，如 `iflytek_first`、`auto` |
| `SPARKWEAVE_OCR_TIMEOUT` | OCR 超时时间，单位秒 |
| `SPARKWEAVE_OCR_MAX_PAGES` | 单次处理最大页数 |
| `SPARKWEAVE_OCR_DPI` | PDF 转图片 DPI |
| `SPARKWEAVE_OCR_MIN_TEXT_CHARS` | 文本层最少字符数，低于该值可触发 OCR |

科大讯飞 OCR 示例：

```env
SPARKWEAVE_OCR_PROVIDER=iflytek
SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first
IFLYTEK_OCR_APPID=your-appid
IFLYTEK_OCR_API_KEY=your-api-key
IFLYTEK_OCR_API_SECRET=your-api-secret
IFLYTEK_OCR_URL=https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm
IFLYTEK_OCR_SERVICE_ID=se75ocrbm
IFLYTEK_OCR_CATEGORY=ch_en_public_cloud
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
