<p align="center">
  <img src="assets/logo-ver2.png" alt="SparkWeave Logo" width="112" />
</p>

<h1 align="center">SparkWeave 星火织学</h1>

<p align="center">
  面向高校课程学习的多智能体学习工作台
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-2563EB?style=flat-square" />
  <img alt="React" src="https://img.shields.io/badge/React-TypeScript-0F766E?style=flat-square" />
  <img alt="Docker" src="https://img.shields.io/badge/Deploy-Docker_Compose-0F766E?style=flat-square" />
  <img alt="License" src="https://img.shields.io/badge/License-Apache--2.0-111827?style=flat-square" />
</p>

## 项目是什么

SparkWeave 做的是一个可以运行的个性化学习系统，而不是单独的聊天页面。学生从一门课程开始，系统根据目标、资料、练习反馈和学习记录生成学习路径、学习资源和下一步建议；资料问答会保留来源，学习行为会回到记录和画像里。

前端入口尽量保持简单：学习、资料、记录、设置。智能体、RAG、画像、图解、语音、公式识别这些能力不抢主入口，而是在学习过程中被调用。

项目面向软件杯 A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”，重点覆盖：

| 赛题要求 | SparkWeave 中的落点 |
| --- | --- |
| 对话式学习画像 | 目标、偏好、薄弱点、练习反馈和学习记录进入画像 |
| 多智能体资源生成 | 对话协调器调度资料检索、出题、解题、图解、动画、语音等能力 |
| 个性化路径规划 | 学习页按课程目标、时间预算和画像生成当前任务 |
| 智能辅导 | 问问题页和资料页支持带来源的答疑、多模态输入和学习资源生成 |
| 学习效果评估 | 练习、反思和资源使用反馈进入记录页，影响下一步建议 |
| 科大讯飞工具 | 星火、MaaS Coding、Embedding、ONE SEARCH、OCR、公式识别、图片理解、TTS、ASR、语音评测和星辰工作流都有配置或工具落点 |

## 核心创新点

下面这些点都能从页面追到代码，不是只写在答辩稿里的概念。SparkWeave 的核心设计是把“画像 -> 资料证据 -> 智能体调度 -> 资源生成 -> 评估回写”做成一条学习链路：前端保持学习入口简单，后端用路由器、Agentic RAG、证据账本和通道层把复杂能力接起来。

| 创新点 | 技术实现 | 在系统里怎么看 |
| --- | --- | --- |
| Agentic RAG 质量门 | `rag_support/service.py` 会先生成 query plan，再并发执行多路检索；`agentic_quality.py` 按来源数、覆盖度、相关覆盖度、上下文长度和分数给出质量报告；证据弱时由 `agentic_repair.py` 修复分支或保守回退 | 资料页、`RagAgenticTrace.tsx`、RAG 设计文档 |
| 证据化学习画像 | `learner_evidence.py` 使用追加式 `evidence.jsonl` 保存导学、练习、资源和校准事件；`learner_profile.py` 聚合成画像快照；`profile_context.py` 只把精简提示注入运行上下文 | 记录 / 画像页、学习画像设计文档 |
| 自动调度的多智能体 | `LearningCapabilityRouter` 先按规则判断解释、解题、出题、图解、动画、研究和外部资源搜索，置信度不足时可用 LLM intent coordinator 细分；同时尊重“不要联网 / 不用工具 / 不开画布”等约束 | 问问题页、智能体编排文档 |
| 课程模板和 RAG 同源 | 课程 JSON 通过 `source_materials` 指向真实课件，`sync_course_materials_to_kb.py` 把课件同步到课程资料库，学习路径和资料问答围绕同一门课展开 | 深度学习课程、资料页、课程模板说明 |
| QQ 可接入课程助教 | `sparkbot_support/config_models.py` 定义 `qq` 通道，`channels.py` 的 `QQChannel` 处理私聊、群聊和提醒发送；未配置凭据时退回内存通道，管理能力仍可演示 | 课程助教页、`sparkweave/services/sparkbot_support/` |
| 讯飞能力嵌入场景 | 星火模型、Spark Embedding、ONE SEARCH、OCR、公式识别、图片理解、TTS、ASR、语音评测和星辰工作流分别接在模型、资料、搜索、多模态输入、语音讲解和评估链路上 | 设置页、资料页、问问题页、讯飞工具链文档 |
| 学习闭环优先 | 工程能力默认后台化，一级入口仍是学习、资料、记录、设置；结果回到任务和画像，而不是停留在一次问答结果 | 学习页、记录页、前端设计文档 |

## 快速运行

推荐用 Docker Compose 启动完整环境。它会同时拉起前端、后端和 Milvus，最接近评审时的运行方式。

```powershell
copy .env.example .env
docker compose up --build
```

启动后访问：

| 入口 | 地址 |
| --- | --- |
| 前端工作台 | http://127.0.0.1:3782 |
| 后端 API | http://127.0.0.1:8001 |
| API 文档 | http://127.0.0.1:8001/docs |
| 系统状态 | http://127.0.0.1:8001/api/v1/system/status |

`.env.example` 已列出模型、Embedding、搜索、OCR、语音和讯飞工作流等配置项。至少需要配置一组可用的 LLM 和 Embedding，资料库问答才有完整效果。如果模型服务在宿主机运行，容器里不要写 `localhost`，Windows 和 macOS 通常用 `host.docker.internal`。

## 建议核验路线

评委或老师拿到项目后，可以按下面这条路线看，不需要先读代码：

1. 打开学习页，选择主课程“深度学习”。
2. 生成学习路线，查看当前任务、学习资源和任务反馈入口。
3. 打开资料页，创建资料库或查看已有课程资料。
4. 在问问题页围绕课件内容提问，展开回答旁边的来源。
5. 完成一次练习或提交反馈，再到记录页查看画像、薄弱点和下一步建议。
6. 打开设置页，查看星火、Embedding、ONE SEARCH、OCR、公式识别、图片理解、语音和星辰工作流的配置入口与连接检测。

这条路线能同时看到课程主线、资料证据、多智能体协作、学习画像和讯飞工具链。

## 主要页面

| 页面 | 作用 | 截图 |
| --- | --- | --- |
| 学习 | 选择课程、生成路线、推进任务和反馈学习效果 | [web/screenshots-guide.png](web/screenshots-guide.png) |
| 资料 | 上传课程资料、管理知识库、查看资料处理状态 | [web/screenshots-knowledge.png](web/screenshots-knowledge.png) |
| 问问题 | 基于资料或学习上下文提问，查看来源和多智能体结果 | [web/screenshots-chat.png](web/screenshots-chat.png) |
| 记录 / 画像 | 查看学习证据、薄弱点、偏好和下一步建议 | [web/screenshots-memory.png](web/screenshots-memory.png) |
| 设置 | 配置模型、Embedding、搜索、OCR、语音和讯飞工具 | [web/screenshots-settings.png](web/screenshots-settings.png) |
| 课程助教 | 管理长期课程助教、课程资料、提醒任务和 QQ 等消息通道 | [web/screenshots-agents.png](web/screenshots-agents.png) |

更多前端设计取舍见 [前端设计说明](docs/markdown/frontend-design-guide.md)。

## 完整课程

评审演示建议仍固定使用主课程“深度学习”，模板位于 `data/course_templates/deep_learning/deep_learning_foundations.json`。它是一门 14 周、3 学分的高校专业课程，依据 `ppts/深度学习/` 下的课件组织，覆盖绪论、前馈神经网络、CNN、深度学习软硬件、CNN 图像检索、多模态学习、RNN、注意力机制、Transformer、大模型应用、强化学习、无监督学习和深度生成模型。

仓库还接入了第二门课程“智能机器人系统”，模板位于 `data/course_templates/intelligent_robot_systems/intelligent_robot_systems.json`，课件放在 `ppts/智能机器人系统/`。这门课覆盖机器人概论、运动、控制与规划、传感、导航定位、ROS 基础、ROS 通信、roscpp/rospy、常用工具、TF/URDF 和基于 ROS 的导航应用，可用于展示系统对不同专业课程的迁移能力。

课程模板中的 `source_materials` 会同步到对应资料库：`深度学习` 对应 `data/knowledge_bases/深度学习/raw/`，`智能机器人系统` 对应 `data/knowledge_bases/智能机器人系统/raw/`。新增或替换课件后，先运行：

```powershell
python scripts/sync_course_materials_to_kb.py --stage-only
```

如果 Docker Compose、Milvus 和 Embedding 服务已经可用，再重建索引，让资料问答真正检索到新课件：

```powershell
python scripts/sync_course_materials_to_kb.py --index
```

课程模板可用下面的命令校验：

```powershell
python scripts/check_course_templates.py
```

完整说明见 [完整课程样例说明](docs/markdown/course-template-guide.md)。

## 科大讯飞工具链

SparkWeave 把讯飞能力放在学习流程里，而不是单独做一个展示菜单：

| 能力 | 系统落点 |
| --- | --- |
| 星火大模型 | 对话辅导、资源生成、学习路径解释 |
| MaaS Coding / Astron Code | 代码类任务、工具编排和代码讲解 |
| Spark Embedding | 课程资料向量化和资料问答 |
| ONE SEARCH | 公开资料、公开视频和外部学习资源补充 |
| OCR for LLM | 扫描讲义、图片资料、题图文字入库 |
| 公式识别 | 手写公式和题图公式进入解题或资料问答 |
| 图片理解 | 板书、示意图、实验截图进入多模态辅导 |
| TTS / ASR / 语音评测 | 语音讲解、口述提问和学习效果证据 |
| 星辰工作流 | 接入已发布工作流，生成课程资源或诊断报告 |

配置细节见 [配置指南](docs/markdown/configuration-guide.md) 和 [科大讯飞工具链说明](docs/markdown/iflytek-toolchain-guide.md)。

## 代码结构

| 路径 | 说明 |
| --- | --- |
| `sparkweave/` | 后端服务、多智能体运行时、RAG、学习画像和讯飞工具 |
| `sparkweave_cli/` | Typer 命令行入口 |
| `web/` | React + TypeScript 前端工作台 |
| `data/course_templates/` | 完整课程模板 |
| `ppts/深度学习/` | 主课程参考课件 |
| `ppts/智能机器人系统/` | 智能机器人系统课程参考课件 |
| `scripts/` | 项目检查、课程模板校验、课程资料入库、API 合同和资料问答验收 |
| `requirements/` | Python 依赖分层 |
| `docs/markdown/` | Markdown 源文档 |
| `docs/html/` | HTML 阅读版文档 |

更细的目录说明见 [项目结构说明](docs/markdown/project-structure.md)。

## 文档入口

HTML 版适合直接阅读和放进提交材料，Markdown 版适合维护。

| 文档 | 入口 |
| --- | --- |
| 一页版项目说明 | [docs/html/sparkweave-overview.html](docs/html/sparkweave-overview.html) |
| HTML 文档中心 | [docs/html/README.html](docs/html/README.html) |
| Markdown 文档中心 | [docs/markdown/README.md](docs/markdown/README.md) |
| 功能代码链路说明 | [docs/markdown/feature-code-walkthrough.md](docs/markdown/feature-code-walkthrough.md) |
| 软件杯交付检查清单 | [docs/markdown/software-cup-delivery-checklist.md](docs/markdown/software-cup-delivery-checklist.md) |
| 提交包整理说明 | [docs/markdown/submission-package-guide.md](docs/markdown/submission-package-guide.md) |
| AI Coding 使用说明 | [docs/markdown/ai-coding-disclosure.md](docs/markdown/ai-coding-disclosure.md) |

## 提交边界

建议随项目提交：

- 源码、前端工程、Docker 配置和依赖说明。
- `data/course_templates/` 中的完整课程模板。
- `.env.example` 等不含密钥的配置示例。
- 当前前端截图和配套文档。

不应提交：

- `.env`、真实 API Key、账号 Token、私有服务地址。
- 真实学生姓名、聊天记录、学习记录、语音材料和个人画像。
- 未获授权的教材、课件、论文全文或课程资料。
- `data/user/`、`data/milvus/`、`.venv/`、`node_modules/`、`web/dist/` 等本机生成内容。

## 常用检查

后端和项目结构：

```powershell
python scripts/verify_project.py --profile quick
python scripts/check_project_standards.py
python scripts/check_course_templates.py
python scripts/check_web_api_contract.py
python -m compileall -q sparkweave sparkweave_cli scripts
```

前端：

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

资料问答端到端验收需要后端和 Milvus 已启动：

```powershell
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --provider milvus --cleanup
```

## License

Apache License 2.0
