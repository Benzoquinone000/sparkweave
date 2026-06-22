# 配置指南

本指南面向评委说明 SparkWeave 的服务配置方式，重点说明科大讯飞相关工具在系统里的落点。项目可以先用默认配置进入前端工作台；如果要展示真实讯飞服务调用，需要在本地环境填写对应密钥，并在设置页完成检测。

配置入口主要在 [设置页](../../web/screenshots-settings.png)。页面分成三类：连接服务、工作台偏好、连接检测。评审时重点看“连接服务”和“连接检测”。

## 设置页能配置什么

| 配置类别 | 对应能力 | 影响页面 |
| --- | --- | --- |
| 问答模型 | 对话辅导、解题、出题、图解、研究、学习路径解释 | 学习页、问问题页、课程助教 |
| Embedding | 课程资料向量化和资料问答 | 资料页、问问题页 |
| 搜索服务 | 公开视频、公开资料和外部补充来源 | 问问题页、学习页 |
| OCR | 扫描课件、图片讲义、图片题入库 | 资料页、图像题 |
| 公式识别 | 手写公式、题图公式转文本 | 问问题页、图像题、解题流程 |
| 图片理解 | 板书、截图、示意图解释 | 问问题页、图像题 |
| TTS | 生成语音讲解和短视频旁白素材 | 问问题页、资源生成 |
| ASR | 学生口述问题、课堂音频转写 | 问问题页、语音输入 |
| 语音评测 | 口语或朗读任务评分，并写入学习证据 | 学习记录、学习效果评估 |
| 星辰工作流 | 调用已发布的讯飞工作流 | 问问题页、课程资源生成 |

设置页保存后，后端会刷新模型、Embedding 和 RAG 相关运行配置，不需要改代码。

## 科大讯飞工具链

赛题要求选用科大讯飞相关工具。SparkWeave 已把讯飞能力放在几个明确位置：

| 讯飞能力 | 系统中的配置/工具 | 典型用途 |
| --- | --- | --- |
| 星火大模型 | 问答模型配置 | 对话式辅导、资源生成、学习路径解释 |
| MaaS Coding / Astron Code | 代码模型配置 | 代码类任务、工程任务、工具编排 |
| Spark Embedding | 向量模型配置 | 课程资料向量化、资料检索 |
| ONE SEARCH | 搜索服务配置 | 公开资料、公开视频和外部学习资源补充 |
| OCR for LLM | OCR 配置 | 扫描资料、图片课件、图片题转文字 |
| 公式识别 | 公式识别工具 | 手写公式和题图公式进入解题或资料问答 |
| 图片理解 | 图片理解工具 | 板书、示意图、实验截图进入多模态辅导 |
| 超拟人 TTS | 语音合成配置 | 生成语音讲解和短视频旁白 |
| 语音听写 ASR | 语音识别配置 | 口述问题转文字 |
| 语音评测 ISE | 语音评测配置 | 口语练习评分，写入学习效果证据 |
| 星辰工作流 | 工作流工具 | 接入已发布工作流，生成课程资源或诊断报告 |

这些能力不是单独摆在一个展示页里，而是嵌入学习路径、资料问答、图像题、语音讲解和学习效果记录中。

## 推荐配置组合

如果要完整核验讯飞工具链，建议至少准备下面这组配置：

| 环节 | 建议配置 |
| --- | --- |
| 问答模型 | 星火大模型或 MaaS Coding 作为主要 LLM |
| 资料库 | Spark Embedding 作为向量模型，上传一门课程资料 |
| 外部资料 | ONE SEARCH 作为搜索服务 |
| 多模态输入 | OCR、公式识别、图片理解至少开启其中两项 |
| 多模态输出 | TTS 用于语音讲解，必要时结合数学动画或图解 |
| 学习评估 | ASR 或语音评测可作为加分项，和练习结果一起写入记录 |
| 工作流 | 星辰工作流可接入课程成果、诊断报告或学习材料生成 |

如果账号权限有限，优先保证“星火模型 + Spark Embedding + ONE SEARCH + OCR/公式识别”这条线。它最直接对应资料问答、资源生成和智能辅导。

## 常用环境变量

设置页会把配置写入本地环境配置。也可以直接在 `.env` 中填写。以下只列评审和部署最常用的项。

| 能力 | 常用变量 |
| --- | --- |
| 星火大模型 | `LLM_BINDING=iflytek_spark_ws`、`LLM_MODEL=spark-x`、`LLM_HOST`、`IFLYTEK_APPID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET` |
| MaaS Coding | `LLM_BINDING=iflytek_maas_coding`、`LLM_MODEL=astron-code-latest`、`LLM_HOST`、`IFLYTEK_MAAS_API_PASSWORD` |
| Spark Embedding | `EMBEDDING_BINDING=iflytek_spark`、`EMBEDDING_MODEL=llm-embedding`、`EMBEDDING_HOST`、`EMBEDDING_DIMENSION=2560`、`IFLYTEK_APPID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET` |
| ONE SEARCH | `SEARCH_PROVIDER=iflytek_spark`、`IFLYTEK_API_PASSWORD` 或 `IFLYTEK_API_KEY` + `IFLYTEK_API_SECRET` |
| OCR | `SPARKWEAVE_OCR_PROVIDER=iflytek`、`IFLYTEK_OCR_APPID`、`IFLYTEK_OCR_API_KEY`、`IFLYTEK_OCR_API_SECRET` |
| 公式识别 | `SPARKWEAVE_FORMULA_OCR_PROVIDER=iflytek`、`IFLYTEK_FORMULA_APPID`、`IFLYTEK_FORMULA_API_KEY`、`IFLYTEK_FORMULA_API_SECRET` |
| 图片理解 | `SPARKWEAVE_IMAGE_UNDERSTANDING_PROVIDER=iflytek`、`IFLYTEK_VISION_APPID`、`IFLYTEK_VISION_API_KEY`、`IFLYTEK_VISION_API_SECRET` |
| TTS | `SPARKWEAVE_TTS_PROVIDER=iflytek`、`IFLYTEK_TTS_APPID`、`IFLYTEK_TTS_API_KEY`、`IFLYTEK_TTS_API_SECRET` |
| ASR | `SPARKWEAVE_ASR_PROVIDER=iflytek`、`IFLYTEK_ASR_APPID`、`IFLYTEK_ASR_API_KEY`、`IFLYTEK_ASR_API_SECRET` |
| 语音评测 | `SPARKWEAVE_SPEECH_EVAL_PROVIDER=iflytek`、`IFLYTEK_SPEECH_EVAL_APPID`、`IFLYTEK_SPEECH_EVAL_API_KEY`、`IFLYTEK_SPEECH_EVAL_API_SECRET` |
| 星辰工作流 | `IFLYTEK_WORKFLOW_API_KEY`、`IFLYTEK_WORKFLOW_API_SECRET`、`IFLYTEK_WORKFLOW_FLOW_ID` |

多数讯飞服务也支持共享的 `IFLYTEK_APPID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET`。如果单项服务有独立密钥，系统会优先使用单项变量。

## 配置后如何核验

| 核验动作 | 预期结果 |
| --- | --- |
| 打开设置页的连接服务 | 能看到星火、Embedding、搜索、OCR、语音等配置项 |
| 保存配置 | 页面提示配置已保存，后端会刷新运行配置 |
| 进入连接检测 | 对模型、Embedding、搜索、OCR、TTS、ASR、语音评测做单项检测 |
| 上传课程资料 | 资料页能完成处理，资料库状态变为可用 |
| 问一个资料问题 | 回答旁能看到资料来源和来源状态 |
| 上传公式或图片题 | 公式识别或图片理解工具返回结构化结果 |
| 生成语音讲解 | TTS 返回音频或可播放资源 |
| 完成语音/练习任务 | 学习记录页出现新的学习证据 |

核验时建议保留一次真实检测结果，尤其是模型、Embedding 和至少一个多模态服务。

## 没有真实密钥时怎么处理

部分讯飞工具带有明确标记的替代结果，用来保证没有账号或网络异常时仍能走完整流程。它们会在结果里标出 `fallback: true` 或类似说明，表示这不是一次真实讯飞服务返回。

提交说明中建议写清楚：

- 如果展示真实服务调用，请在设置页完成连接检测。
- 如果使用替代结果，请明确说明该处不是一次真实云端返回。
- 如果要求只使用真实讯飞服务，可以关闭替代结果：`SPARKWEAVE_IFLYTEK_OFFLINE_FALLBACK=0`。

## 数据与密钥边界

- `.env`、账号 JSON、API Key、API Secret、APIPassword 不进入提交包。
- 设置页会对密钥做遮罩显示，避免在录屏或截图中暴露完整密钥。
- 课程样例和配置样例可以提交，个人资料、真实学生记录和未脱敏截图不应提交。
- 修改 Embedding 模型或向量维度后，需要重新索引资料库。
- Docker 环境访问宿主机本地模型服务时，地址通常不能写 `localhost`，应按运行环境改成可从容器访问的地址。

## 代码落点

| 模块 | 位置 |
| --- | --- |
| 设置页 | `web/src/pages/SettingsPage.tsx`、`web/src/pages/settings/` |
| 设置接口 | `sparkweave/api/routers/settings.py` |
| 模型供应商清单 | `sparkweave/services/config_support/provider_catalog.py` |
| 星火大模型 | `sparkweave/services/iflytek_spark_ws.py` |
| Spark Embedding | `sparkweave/services/embedding_support/adapters/iflytek_spark.py` |
| ONE SEARCH | `sparkweave/services/search_support/providers/iflytek_spark.py` |
| OCR | `sparkweave/services/ocr.py` |
| 公式识别 | `sparkweave/services/iflytek_formula.py` |
| 图片理解 | `sparkweave/services/iflytek_vision.py` |
| 语音与评测 | `sparkweave/services/speech.py` |
| 星辰工作流 | `sparkweave/services/iflytek_workflow.py` |
| 工具注册 | `sparkweave/tools/builtin.py` |
