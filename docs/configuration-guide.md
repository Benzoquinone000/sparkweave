# SparkWeave 配置指南

范围：说明 SparkWeave 当前配置来源、供应商预设、讯飞工具链和离线替补策略。本文档只描述仓库中已经实现的配置项；供应商官网新能力未接入前不写成当前能力。实际部署入口仍以根目录 `README.md` 的 Docker 部署章节为准。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| 环境变量样例 | `.env.example` |
| 配置解析与 provider catalog | `sparkweave/services/config.py` |
| 设置 API | `sparkweave/api/routers/settings.py`, `sparkweave/api/routers/system.py` |
| 设置页 | `web/src/pages/settings/` |
| 讯飞离线替补 | `sparkweave/services/iflytek_offline.py` |
| 讯飞能力服务 | `sparkweave/services/ocr.py`, `sparkweave/services/iflytek_formula.py`, `sparkweave/services/iflytek_vision.py`, `sparkweave/services/tts.py`, `sparkweave/services/speech.py`, `sparkweave/services/iflytek_workflow.py` |
| 配置测试 | `tests/api/test_settings_provider_choices.py`, `tests/api/test_system_router.py`, `tests/services/config/`, `tests/services/test_iflytek_*.py`, `tests/services/test_speech.py` |

## 1. 配置优先级

SparkWeave 支持两类配置来源：

| 来源 | 位置 | 适用场景 |
| --- | --- | --- |
| 环境变量 | `.env` | Docker 部署、CI、服务器和不可交互环境 |
| 前端设置页 | `设置 -> 模型配置` | 本地演示、比赛排练、快速切换供应商 |

运行时会把 `.env`、设置页 catalog 和共享供应商凭据合并为实际配置。共享凭据优先用于同一家供应商的多个能力，例如科大讯飞的 LLM、Embedding、搜索、OCR、语音和工作流。

## 2. 基础端口

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BACKEND_PORT` | `8001` | FastAPI 后端端口 |
| `FRONTEND_PORT` | `3782` | Vite 前端端口 |

Docker 启动后：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://localhost:3782` |
| 后端 API | `http://localhost:8001` |
| API 文档 | `http://localhost:8001/docs` |
| Milvus Web UI | `http://localhost:9091/webui/` |

## 3. LLM 配置

最小配置：

```dotenv
LLM_BINDING=openai
LLM_MODEL=gpt-5.4-mini
LLM_API_KEY=your-llm-key
LLM_HOST=https://api.openai.com/v1
```

常用字段：

| 变量 | 说明 |
| --- | --- |
| `LLM_BINDING` | 供应商标识，例如 `openai`、`iflytek_spark_ws`、`iflytek_maas_coding`、`deepseek`、`gemini`、`dashscope`、`zhipu`、`moonshot`、`anthropic`、`siliconflow` |
| `LLM_MODEL` | 模型 ID；供应商发布新模型时可以直接填写新 ID |
| `LLM_API_KEY` | API key 或兼容接口 token |
| `LLM_HOST` | OpenAI-compatible base URL 或供应商 endpoint |
| `LLM_API_VERSION` | Azure OpenAI 等供应商需要时填写 |
| `LLM_CONNECT_TIMEOUT` | 连接超时 |
| `LLM_REQUEST_TIMEOUT` | 请求超时 |

Docker 容器访问宿主机模型时，不要写 `localhost`。Windows / macOS 使用：

```dotenv
LLM_HOST=http://host.docker.internal:1234/v1
```

Linux 可使用宿主机局域网 IP。

## 4. Embedding 与 RAG

知识库和资料问答需要 Embedding。

```dotenv
EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=your-embedding-key
EMBEDDING_HOST=https://api.openai.com/v1
EMBEDDING_DIMENSION=3072
```

Milvus 是当前默认 RAG 后端：

```dotenv
RAG_PROVIDER=milvus
MILVUS_URI=http://localhost:19530
DOCKER_MILVUS_URI=http://milvus:19530
MILVUS_COLLECTION_PREFIX=sparkweave
```

关键 RAG 参数：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RAG_TOP_K` | `5` | 最终返回来源数量 |
| `RAG_CANDIDATE_TOP_K` | `20` | 候选召回数量 |
| `RAG_MAX_CONTEXT_CHARS` | `8000` | 上下文打包字符上限 |
| `RAG_RETRIEVAL_MODE` | `dense` | 检索模式，`hybrid` 需要重建知识库索引 |
| `RAG_AGENTIC_MODE` | `off` | 全局 Agentic RAG 开关；默认关闭，前端/API 可按请求开启 |

Agentic RAG 相关参数：

| 变量 | 说明 |
| --- | --- |
| `RAG_AGENTIC_MAX_SUBQUERIES` | 子问题数量上限 |
| `RAG_AGENTIC_TIMEOUT_SECONDS` | 多路召回超时 |
| `RAG_AGENTIC_MAX_CONCURRENCY` | 并发召回数量 |
| `RAG_AGENTIC_FALLBACK_TO_SINGLE` | 质量不足时回退单路检索 |
| `RAG_AGENTIC_MIN_RELEVANT_COVERAGE_RATIO` | 质量门覆盖率阈值 |

## 5. 搜索配置

搜索能力用于公开资料补充、视频发现和研究类任务。

```dotenv
SEARCH_PROVIDER=
SEARCH_API_KEY=
SEARCH_BASE_URL=
```

常见 provider 包括 Brave、Tavily、Jina、SearXNG、DuckDuckGo、Perplexity、Serper、科大讯飞 ONE SEARCH。前端设置页会展示可用预设和诊断入口。

## 6. 科大讯飞共享凭据

推荐优先填写共享凭据：

```dotenv
IFLYTEK_APPID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=
IFLYTEK_API_PASSWORD=
IFLYTEK_MAAS_API_PASSWORD=
```

说明：

| 变量 | 用途 |
| --- | --- |
| `IFLYTEK_APPID` | OCR、Embedding、公式识别、图片理解、语音等能力常用 |
| `IFLYTEK_API_KEY` | APIKey |
| `IFLYTEK_API_SECRET` | APISecret |
| `IFLYTEK_API_PASSWORD` | APIPassword；为空时系统可由 APIKey 与 APISecret 组合推导 |
| `IFLYTEK_MAAS_API_PASSWORD` | MaaS Coding / Astron Code 专用 APIPassword |

共享凭据会被设置页和运行时复用到以下能力：

| 能力 | 主要配置 |
| --- | --- |
| 星火大模型 | `LLM_BINDING=iflytek_spark_ws` |
| MaaS Coding | `LLM_BINDING=iflytek_maas_coding` |
| 星火 Embedding | `EMBEDDING_BINDING=iflytek_spark` |
| ONE SEARCH | `SEARCH_PROVIDER=iflytek_spark` |
| OCR | `SPARKWEAVE_OCR_PROVIDER=iflytek` |
| 公式识别 | `IFLYTEK_FORMULA_*` 或共享 `IFLYTEK_*` |
| 图片理解 | `IFLYTEK_VISION_*` 或共享 `IFLYTEK_*` |
| TTS | `SPARKWEAVE_TTS_PROVIDER=iflytek` |
| ASR | `SPARKWEAVE_ASR_PROVIDER=iflytek` |
| 语音评测 | `SPARKWEAVE_SPEECH_EVAL_PROVIDER=iflytek` |
| 星辰工作流 | `IFLYTEK_WORKFLOW_*` |

## 7. 讯飞 MaaS Coding

MaaS Coding / Astron Code 可作为问答模型或代码智能体模型：

```dotenv
LLM_BINDING=iflytek_maas_coding
LLM_MODEL=astron-code-latest
LLM_HOST=https://maas-coding-api.cn-huabei-1.xf-yun.com/v2
IFLYTEK_MAAS_API_PASSWORD=your-maas-apipassword
```

如需 Anthropic-compatible 入口，可在自定义供应商中填写：

```text
https://maas-coding-api.cn-huabei-1.xf-yun.com/anthropic
```

不要把真实 APIPassword 写入 README、测试文件或截图。

## 8. OCR、公式识别与图片理解

### OCR

```dotenv
SPARKWEAVE_OCR_PROVIDER=iflytek
SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first
SPARKWEAVE_OCR_TIMEOUT=90
IFLYTEK_OCR_APPID=
IFLYTEK_OCR_API_KEY=
IFLYTEK_OCR_API_SECRET=
```

`SPARKWEAVE_PDF_OCR_STRATEGY`：

| 值 | 行为 |
| --- | --- |
| `auto` | 优先文本层，文本过少再尝试 OCR |
| `iflytek_first` / `ocr_first` | 优先 OCR，失败后回退文本层 |

### 公式识别

```dotenv
IFLYTEK_FORMULA_URL=https://rest-api.xfyun.cn/v2/itr
IFLYTEK_FORMULA_APPID=
IFLYTEK_FORMULA_API_KEY=
IFLYTEK_FORMULA_API_SECRET=
IFLYTEK_FORMULA_ENT=teach-photo-print
```

公式识别结果会转成工具结果，进入解题、RAG 或回答上下文。

### 图片理解

```dotenv
SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER=iflytek
IFLYTEK_VISION_PROTOCOL=spark_image
IFLYTEK_VISION_URL=wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image
IFLYTEK_VISION_DOMAIN=imagev3
```

如需切换到星辰 MaaS 多模态接口，调整 `IFLYTEK_VISION_PROTOCOL` 和对应 URL。

## 9. 语音能力

### TTS

```dotenv
SPARKWEAVE_TTS_PROVIDER=iflytek
IFLYTEK_TTS_VOICE=x5_lingxiaoxuan_flow
IFLYTEK_TTS_SAMPLE_RATE=24000
```

用于语音讲解预览、短视频旁白和多模态学习资源。

### ASR

```dotenv
SPARKWEAVE_ASR_PROVIDER=iflytek
IFLYTEK_ASR_LANGUAGE=zh_cn
IFLYTEK_ASR_ACCENT=mandarin
IFLYTEK_ASR_DOMAIN=iat
```

用于聊天语音输入和课堂录音转写。

### 语音评测

```dotenv
SPARKWEAVE_SPEECH_EVAL_PROVIDER=iflytek
IFLYTEK_SPEECH_EVAL_CATEGORY=read_sentence
IFLYTEK_SPEECH_EVAL_LANGUAGE=zh_cn
```

用于口语跟读、表达训练和学习效果证据闭环。

## 10. 星辰工作流

```dotenv
IFLYTEK_WORKFLOW_URL=https://xingchen-api.xf-yun.com/workflow/v1/chat/completions
IFLYTEK_WORKFLOW_API_KEY=
IFLYTEK_WORKFLOW_API_SECRET=
IFLYTEK_WORKFLOW_FLOW_ID=
IFLYTEK_WORKFLOW_INPUT_KEY=AGENT_USER_INPUT
```

适合接入已发布的讯飞星辰工作流，例如 PPT 大纲生成、课程资源生成、学习诊断报告或比赛演示标准流程。

## 11. 离线替补

默认启用：

```dotenv
SPARKWEAVE_IFLYTEK_OFFLINE_FALLBACK=1
```

当密钥、网络或产品权限不可用时，以下能力会返回带 `fallback: true` 的替补结果，保证演示流程不中断：

| 能力 | 替补行为 |
| --- | --- |
| OCR | 返回可解释的占位文本，提示补充图片内容 |
| 公式识别 | 返回占位公式说明 |
| 图片理解 | 返回图像理解占位分析 |
| TTS | 生成演示可用的替补音频结果 |
| ASR | 使用 `SPARKWEAVE_OFFLINE_ASR_TEXT` 或默认占位转写 |
| 语音评测 | 返回基础评分结构 |
| 星辰工作流 | 返回结构化工作流占位结果 |

如果提交或验收要求必须只使用真实讯飞服务：

```dotenv
SPARKWEAVE_IFLYTEK_OFFLINE_FALLBACK=0
```

## 12. 安全检查

提交前必须运行：

```powershell
python scripts/check_release_safety.py
```

同时人工确认：

- `.env` 未提交。
- 真实 API key、OAuth token、账号 JSON、临时凭证未提交。
- 截图和录屏中没有明文密钥。
- 测试只使用 mock、fixture 或离线替补。

## 13. 配置变更验证

| 变更 | 推荐验证 |
| --- | --- |
| 修改 `.env.example` | `python scripts/check_release_safety.py` |
| 修改 Provider catalog | `uv run pytest tests/api/test_settings_provider_choices.py tests/api/test_settings_router.py tests/services/config -q` |
| 修改 API 配置字段 | `python scripts/check_web_api_contract.py` |
| 修改前端设置页 | `npm run lint`、`npm run check:design`、`npm run build` |
| 修改 RAG 参数 | RAG 单测、知识库入库与检索 smoke |

聚焦命令：

```powershell
uv run pytest tests/api/test_settings_provider_choices.py tests/api/test_system_router.py tests/services/config tests/services/test_iflytek_formula.py tests/services/test_iflytek_vision.py tests/services/test_iflytek_workflow.py tests/services/test_speech.py -q
python scripts/check_release_safety.py
python scripts/check_web_api_contract.py
```

## 14. 限制与待实现

- 配置页保存的是本地运行时配置，不能替代供应商官网开通权限。
- 讯飞离线替补只保证演示链路返回结构化结果，并会标记 `fallback: true`；它不是对真实讯飞能力的质量承诺。
- Provider catalog 里的模型预设来自当前代码和 `.env.example`，供应商发布新模型后需要同步 preset 或手动填写模型 ID。
- 真实连通性由设置页诊断或 `/api/v1/system/test/*` 接口验证，CI 默认不依赖真实密钥。
