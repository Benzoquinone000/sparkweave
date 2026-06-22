# 测试与验证说明

本篇面向评委说明 SparkWeave 如何验证。这里不把测试目录逐个展开，而是围绕验收时最关心的几件事：系统能不能启动，课程能不能选用，资料问答有没有来源，学习记录能不能影响画像，前后端接口是否一致。

## 验证思路

SparkWeave 的验证分成两层。

第一层是现场操作。评委可以从前端进入学习、资料、问问题、记录、设置，直接确认作品是不是围绕真实学习流程展开。

第二层是自动检查。项目提供课程模板、API 合同、前端构建、后端编译、发布边界和 RAG 验收等验证入口，用来证明页面背后的代码、接口和数据结构没有脱节。

## 启动验证

从仓库根目录启动完整服务：

```bash
docker compose up --build
```

服务启动后，评委可访问：

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:3782` | 前端工作台 |
| `http://127.0.0.1:8001/api/v1/system/status` | 后端状态和模型配置状态 |
| `http://127.0.0.1:8001/api/v1/knowledge/health` | 资料库服务状态 |
| `http://127.0.0.1:8001/api/v1/guide/v2/health` | 学习路径服务状态 |

如果前端可以进入工作台、后端状态接口返回 JSON，并且学习页能看到课程模板，就可以继续做功能验收。

## 现场验收主线

建议按这条顺序检查，能覆盖赛题的大部分要求：

1. 进入学习页，选择 `深度学习`，生成学习路线。
2. 打开一个学习任务，查看系统给出的学习目标、资源建议和练习。
3. 在资料页创建知识库并上传可公开的课程材料。
4. 在问问题页基于资料提问，检查回答里是否带有资料来源。
5. 完成一个任务或提交学习反馈，再到记录页查看画像、薄弱点和下一步建议。
6. 打开课程助教页，查看长期助教、提醒任务和 QQ 等通道入口。
7. 打开设置页，查看模型、Embedding、搜索、OCR、语音、讯飞工作流等配置入口和连接状态。

这条路径重点验证作品是否真的把“画像、路径、资源、辅导、评估”连在一起，而不是只做了单点问答。

## 自动验证入口

| 验证内容 | 命令 | 说明 |
| --- | --- | --- |
| 项目结构、文档链接和提交边界 | `python scripts/verify_project.py --profile quick` | 综合检查项目基础质量 |
| 课程模板完整性 | `python scripts/check_course_templates.py` | 验证课程 `id`、节点、任务和学习样例 |
| 前后端 API 是否一致 | `python scripts/check_web_api_contract.py` | 检查前端调用的接口是否存在于后端 |
| 发布前敏感内容检查 | `python scripts/check_release_safety.py` | 检查本地密钥和旧项目名等不应提交内容 |
| Python 源码编译 | `python -m compileall -q sparkweave sparkweave_cli scripts` | 快速发现语法错误 |
| 后端单元测试 | `python -m pytest tests` | 覆盖 API、RAG、画像、能力路由和服务层 |
| 前端验证 | `npm run verify`（在 `web/` 目录） | 覆盖设计约束、API 合同、Lint、构建和轻量页面检查 |
| 前端构建 | `npm run build`（在 `web/` 目录） | 验证生产构建是否成功 |

如果时间有限，建议优先跑：

```bash
python scripts/verify_project.py --profile quick
```

再进入 `web/` 运行：

```bash
npm run verify
```

这两步能覆盖课程模板、文档索引、API 合同、前端设计约束和构建结果。

## 资料问答验收

资料问答是赛题里“资源生成”和“智能辅导”的关键证据。项目提供独立的 RAG 验收入口：

```bash
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --provider milvus --cleanup
```

这个验证会走和前端一致的路径：创建知识库、上传材料、等待索引、检查文档清单、检查向量结果、进行资料检索，并要求结果中带有来源。若加上 `--chat-check`，还会验证问答 WebSocket 能使用同一个资料库。

这项检查依赖后端和 Milvus 已经启动。若本机没有配置 Embedding 或外部模型服务，结果会反映在系统状态和 RAG 诊断中，不能把它当作真实资料问答已通过。

## 前端页面验收

前端验证重点不是页面是否“炫”，而是学习路径是否清楚、入口是否服务真实学习。对应检查包括：

| 页面 | 验收点 |
| --- | --- |
| 学习 | 能选择完整课程，能生成路线，能推进任务 |
| 资料 | 能创建知识库，上传材料，查看资料状态 |
| 问问题 | 能基于资料或学习上下文回答，能展示来源和 Agentic RAG 过程 |
| 记录 / 画像 | 能看到学习证据、薄弱点、偏好和建议 |
| 设置 | 能看到讯飞相关服务配置和状态 |
| 课程助教 | 能展示长期课程助教、资料同步、提醒能力和 QQ 等通道配置；真实 QQ 收发需要平台凭据 |

当前文档和提交材料引用的截图位于 `web/screenshots-*.png`。它们只作为阅读辅助，最终验收仍以可运行系统为准。

## 测试覆盖重点

后端测试主要覆盖这些模块：

| 范围 | 代表目录 |
| --- | --- |
| API 路由 | `tests/api/` |
| 多智能体能力与路由 | `tests/ng/`、`tests/capabilities/` |
| RAG 与知识库 | `tests/services/rag/`、`tests/knowledge/` |
| 学习路径和画像 | `tests/services/test_guide_v2.py`、`tests/api/test_learner_profile_router.py` |
| 讯飞相关适配 | `tests/services/llm/`、`tests/services/config/`、`tests/services/test_iflytek_formula.py`、`tests/services/test_iflytek_vision.py` |
| 命令行与验证入口 | `tests/cli/`、`tests/scripts/` |

前端测试和检查主要覆盖：

| 范围 | 代表入口 |
| --- | --- |
| 类型和构建 | `npm run build` |
| 代码规则 | `npm run lint` |
| 页面设计约束 | `npm run check:design` |
| API 调用边界 | `npm run check:api-contract` |
| 页面轻量验收 | `npm run test:e2e:isolated` |

## 结果判断

一次较完整的验收应满足：

- Docker Compose 能启动前端、后端和 Milvus。
- 学习页能选择至少一门完整高校课程。
- 资料页能完成材料入库，问答结果能展示来源。
- 记录页能看到学习证据进入画像，并影响后续建议。
- 设置页能看到讯飞相关模型、搜索、OCR、语音和工作流配置。
- 自动验证能通过课程模板、API 合同、前端构建和发布边界检查。

如果某个外部服务没有真实密钥，应该在设置页或系统状态中明确显示未配置，而不是把未配置状态说成真实调用成功。

## 边界说明

测试不能替代评委的实际体验。自动检查更擅长发现接口、路径、模板、构建和发布边界问题；学习效果、资源质量和答疑体验仍需要通过学习主线观察。SparkWeave 的验证目标是让这些证据能相互印证：页面能操作，接口能返回，数据能落盘，资料问答有来源，学习画像会变化。
