# 科大讯飞能力接入说明

本文用于比赛材料和答辩说明，回答“SparkWeave 如何选用科大讯飞相关工具”。所有真实密钥只应填写在本地 `.env` 或设置页中，公开仓库只保留变量名和配置方式。

## 接入目标

SparkWeave 把科大讯飞能力放在学习闭环里的关键位置：

- 问答模型：使用讯飞星火 X2 / X1.5 作为对话协调、导学、资源生成和评估的可选大模型。
- 向量模型：使用讯飞 llm Embedding 为知识库 RAG 建立课程资料索引。
- 联网搜索：使用讯飞 ONE SEARCH 检索公开视频、课程资料和外部学习资源。
- OCR：使用讯飞 OCR for LLM 识别扫描版 PDF，再回退到本地文本层解析，保证知识库导入不中断。

## 服务映射

| 学习场景 | 讯飞能力 | 项目入口 | 失败策略 |
| --- | --- | --- | --- |
| 聊天答疑、导学规划、学习报告 | 讯飞星火 X2 / X1.5 | 设置页“问答模型”、`.env` 的 `LLM_*` | 可切换 OpenAI-compatible、本地模型或其他 provider |
| 课程资料 RAG | 讯飞 llm Embedding | 设置页“向量模型”、`.env` 的 `EMBEDDING_*` | 维度不匹配时提示重建索引 |
| 公开视频和资料检索 | 讯飞 ONE SEARCH | 设置页“联网搜索”、`.env` 的 `SEARCH_*` | 可切换 DuckDuckGo、SearXNG、Jina、Brave 等 provider |
| 扫描版 PDF 导入 | 讯飞 OCR for LLM | 设置页“OCR 识别”、`.env` 的 `IFLYTEK_OCR_*` | OCR 不可用时自动回退 PyMuPDF 文本层解析 |

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

## 设置页操作

1. 打开 `/settings`。
2. 在“问答模型”选择 `iFlytek Spark X`，模型选择 X2 或 X1.5，鉴权方式可选 `APIPassword` 或 `APIKey + APISecret`。
3. 在“向量模型”选择 `iFlytek Spark Embedding`，确认维度为 `2560`。
4. 在“联网搜索”选择 `iFlytek ONE SEARCH`，服务地址会随 provider 自动切换。
5. 在“OCR 识别”选择 `iFlytek OCR for LLM`，填写 APPID、APIKey、APISecret。
6. 点击“保存并应用”，再运行问答模型、向量模型、联网搜索和 OCR 快速检测。

## 答辩讲法

可以用下面这段话收束：

> SparkWeave 不是只把讯飞模型作为普通聊天接口，而是把讯飞星火、Embedding、ONE SEARCH 和 OCR 放进个性化学习闭环：星火负责理解和生成，Embedding 支撑课程资料 RAG，ONE SEARCH 补充公开资源，OCR 处理扫描版资料。系统保留 provider 切换和本地回退，所以演示时可以优先展示讯飞能力，也能保证学习流程稳定不中断。

## 安全边界

- 真实 APPID、APIKey、APISecret 不提交 GitHub。
- `.env.example` 只保留变量名和示例占位符。
- 发布前运行 `python scripts/check_release_safety.py`，扫描旧项目名、本地环境文件和已知密钥片段。
- 演示截图不应露出完整密钥，设置页默认不回填已有 API key。
