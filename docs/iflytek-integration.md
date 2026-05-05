# 科大讯飞能力接入说明

本文用于比赛材料、答辩说明和工程配置说明，回答“SparkWeave 如何选用科大讯飞相关工具”。真实密钥只应保存在本地 `.env` 或设置页，不应提交到仓库。

## 接入目标

SparkWeave 把讯飞能力放在个性化学习闭环的关键节点：

- 问答模型：使用讯飞星火 X2 / X1.5 作为对话、导学、资源生成和评估的可选大模型。
- 向量模型：使用讯飞 Embedding 为课程资料 RAG 建立知识索引。
- 联网搜索：使用讯飞 ONE SEARCH 检索公开视频、课程资料和外部学习资源。
- OCR：使用讯飞 OCR for LLM 处理扫描版 PDF，失败时回退到本地文本层解析。
- TTS：使用讯飞超拟人语音合成，为导学讲解、学习资源和视频脚本生成可播放音频。

## 服务映射

| 学习场景 | 讯飞能力 | 项目入口 | 回退策略 |
| --- | --- | --- | --- |
| 聊天答疑、导学规划、学习评估 | 讯飞星火 X2 / X1.5 | 设置页“问答模型” / `.env` 的 `LLM_*` | 可切换 OpenAI-compatible、本地模型或其他 provider |
| 课程资料 RAG | 讯飞 Embedding | 设置页“向量模型” / `.env` 的 `EMBEDDING_*` | 维度不匹配时提示重建索引 |
| 外部资料与视频检索 | 讯飞 ONE SEARCH | 设置页“联网搜索” / `.env` 的 `SEARCH_*` | 可切换 DuckDuckGo、SearXNG、Jina、Brave 等 provider |
| 扫描版 PDF 导入 | 讯飞 OCR for LLM | 设置页“OCR 识别” / `.env` 的 `IFLYTEK_OCR_*` | OCR 不可用时自动回退 PyMuPDF 文本层解析 |
| 语音讲解 / 多模态播报 | 讯飞超拟人语音合成 | `.env` 的 `IFLYTEK_TTS_*`，系统探针 `/api/v1/system/test/tts` | 后续可回退本地 TTS 或仅输出文字脚本 |

## 推荐配置

讯飞星火 X2：

```env
LLM_BINDING=iflytek_spark_ws
LLM_MODEL=spark-x
LLM_API_KEY=your-iflytek-api-password-or-api-key:api-secret
LLM_HOST=https://spark-api-open.xf-yun.com/x2/
```

讯飞星火 X1.5：

```env
LLM_BINDING=iflytek_spark_ws
LLM_MODEL=spark-x
LLM_API_KEY=your-iflytek-api-password-or-api-key:api-secret
LLM_HOST=https://spark-api-open.xf-yun.com/v2/
```

讯飞 Embedding：

```env
EMBEDDING_BINDING=iflytek_spark
EMBEDDING_MODEL=llm-embedding
EMBEDDING_API_KEY=your-iflytek-embedding-apikey
EMBEDDING_HOST=https://emb-cn-huabei-1.xf-yun.com/
EMBEDDING_DIMENSION=2560
IFLYTEK_EMBEDDING_APPID=your-iflytek-appid
IFLYTEK_EMBEDDING_API_SECRET=your-iflytek-embedding-apisecret
```

讯飞 ONE SEARCH：

```env
SEARCH_PROVIDER=iflytek_spark
SEARCH_API_KEY=your-iflytek-search-apipassword
SEARCH_BASE_URL=https://search-api-open.cn-huabei-1.xf-yun.com/v2/search
```

讯飞 OCR：

```env
SPARKWEAVE_OCR_PROVIDER=iflytek
SPARKWEAVE_PDF_OCR_STRATEGY=iflytek_first
IFLYTEK_OCR_APPID=your-appid
IFLYTEK_OCR_API_KEY=your-api-key
IFLYTEK_OCR_API_SECRET=your-api-secret
IFLYTEK_OCR_URL=https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm
```

讯飞超拟人语音合成：

```env
SPARKWEAVE_TTS_PROVIDER=iflytek
SPARKWEAVE_TTS_TIMEOUT=30
IFLYTEK_TTS_APPID=your-appid
IFLYTEK_TTS_API_KEY=your-api-key
IFLYTEK_TTS_API_SECRET=your-api-secret
IFLYTEK_TTS_URL=wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6
IFLYTEK_TTS_VOICE=x5_lingxiaoxuan_flow
IFLYTEK_TTS_ENCODING=lame
IFLYTEK_TTS_SAMPLE_RATE=24000
```

## 当前实现状态

- 已支持讯飞大模型、Embedding、ONE SEARCH、OCR。
- 已新增讯飞超拟人语音合成后端接入。
- 当前可通过 `/api/v1/system/status` 查看 TTS 是否已配置。
- 当前可通过 `/api/v1/system/test/tts` 做快速连通性检测。
- 下一步适合把 TTS 接入导学资源、视频讲解旁白和设置页表单。

## 讯飞 TTS 接口说明

本项目按照讯飞官方“超拟人语音合成 API 文档”接入：

- 协议：WebSocket 双向流式通信
- 鉴权：APPID + APIKey + APISecret
- 默认输出：`lame`（mp3）
- 推荐采样率：`24000`
- 默认发音人：`x5_lingxiaoxuan_flow`

官方文档：

- 超拟人语音合成 API：https://www.xfyun.cn/doc/spark/super%20smart-tts.html

## 答辩讲法

可以这样概括：

> SparkWeave 不是只把讯飞模型当成普通聊天接口，而是把讯飞星火、Embedding、ONE SEARCH、OCR 和超拟人语音合成放进学习闭环：星火负责理解与生成，Embedding 支撑课程资料 RAG，ONE SEARCH 补充外部资源，OCR 处理扫描版资料，TTS 负责把学习讲解转成可听的语音资源。这样系统既有多模态表达能力，也保留了回退策略，保证比赛演示稳定。

## 安全边界

- 真实 APPID、APIKey、APISecret 不提交 GitHub。
- `.env.example` 只保留变量名和示例占位符。
- 发布前运行 `python scripts/check_release_safety.py`，扫描密钥泄漏和本地环境残留。
- 演示截图中不要暴露完整密钥。
