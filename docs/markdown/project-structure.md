# 项目结构说明

SparkWeave 的提交包由后端服务、前端工作台、课程模板、部署配置、验证文件和配套文档组成。评委可以把它理解为一个可运行的学习系统，而不是只用于展示的页面原型。

## 根目录

| 路径 | 内容 | 对交付的意义 |
| --- | --- | --- |
| `sparkweave/` | 后端服务、多智能体运行时、RAG、学习画像、讯飞工具和业务能力 | 支撑个性化学习、资料问答、资源生成和评估 |
| `web/` | React 前端工作台 | 提供学习、资料、记录、设置和更多工具入口 |
| `data/course_templates/` | 完整课程模板 | 满足“至少一门完整高校专业课程”的要求 |
| `sparkweave_cli/` | 命令行入口 | 便于复用能力、检查配置和管理资料库 |
| `scripts/` | 项目检查、课程模板校验、课程课件入库、API 合约和发布安全检查 | 用于提交前验证 |
| `tests/` | 后端服务、API、运行时和验证入口测试 | 说明核心行为有自动化覆盖 |
| `requirements/` | Python 依赖分层 | 区分服务端、数学动画、课程助教和验证环境等依赖 |
| `docs/` | 配套说明文档 | 解释赛题对应、架构、配置、数据和测试方式 |
| `docker-compose.yml` | 本地完整运行编排 | 启动后端、前端和 Milvus 资料库依赖 |
| `Dockerfile` | 后端和生产镜像构建 | 提供模型服务、前端构建和运行环境基础 |
| `.env.example` | 环境变量样例 | 说明模型、Embedding、搜索、讯飞工具和端口配置 |
| `README.md` | 项目首屏说明 | 给出系统入口、Docker 启动、截图和参赛交付说明 |

## 后端结构

`sparkweave/` 是系统主体，核心目录如下：

| 路径 | 负责内容 | 典型能力 |
| --- | --- | --- |
| `sparkweave/api/` | FastAPI 路由和 WebSocket 入口 | 前端页面调用、统一对话、资料库、学习画像、设置 |
| `sparkweave/runtime/` | 一次学习请求的执行管理 | 学习任务状态、上下文注入、能力路由、事件流 |
| `sparkweave/graphs/` | 多阶段智能体流程 | 对话、解题、出题、研究、可视化、数学动画 |
| `sparkweave/tools/` | 大模型可调用工具 | RAG、联网搜索、讯飞工作流、公式识别、图片理解、代码执行 |
| `sparkweave/services/` | 可测试的业务服务 | 配置、Agentic RAG、学习画像、学习效果、语音、OCR、课程导学、课程助教 |
| `sparkweave/knowledge/` | 资料库管理 | 文档导入、进度跟踪、知识库状态和重建 |
| `sparkweave/core/` | 公共协议和数据结构 | 统一上下文、事件、工具协议、能力协议 |
| `sparkweave/plugins/` | 可扩展插件入口 | 工具和能力的发现与列表展示 |
| `sparkweave/sparkbot/` | 长期课程助教相关能力 | 课程文件、助教人格、提醒和消息通道 |

这部分对应赛题里的“多智能体系统”和“可完整运行的相关文件”。学习请求进入后端后，会被转成统一上下文，再由运行时决定是直接回答、进入 Agentic RAG 检索证据、生成练习、画图、做动画，还是进入课程助教流程。课程助教的外部通道位于 `sparkweave/services/sparkbot_support/`，其中包含 QQ 通道配置和消息收发实现。

## 前端结构

`web/` 是评委和学生直接看到的工作台。

| 路径 | 内容 | 页面体现 |
| --- | --- | --- |
| `web/src/pages/` | 页面级功能 | 学习、资料、记录、设置、问问题、练习、画像、课程助教 |
| `web/src/components/` | 可复用组件 | 应用壳、聊天消息、资料证据、按钮和结果渲染 |
| `web/src/hooks/` | 前端数据和运行时状态 | WebSocket 对话、API 查询、页面状态 |
| `web/src/lib/` | API 客户端、类型和展示工具 | 前后端接口、能力说明、路径和格式化 |
| `web/src/styles/` | 全局样式 | 简洁、低噪声的学习工作台视觉风格 |
| `web/screenshots-*.png` | 当前界面截图 | 用于 README、文档和展示材料 |

前端主入口按真实学习任务组织：学习、资料、记录、设置。Agent、RAG、诊断等能力默认收进“更多工具”，避免让学生先面对一堆技术名词。

## 课程与数据

| 路径 | 内容 | 是否建议提交 |
| --- | --- | --- |
| `data/course_templates/deep_learning/deep_learning_foundations.json` | 深度学习课程模板 | 提交 |
| `data/course_templates/intelligent_robot_systems/intelligent_robot_systems.json` | 智能机器人系统课程模板 | 提交 |
| `ppts/深度学习/` | 深度学习课程参考课件 | 按比赛材料和授权边界确认 |
| `ppts/智能机器人系统/` | 智能机器人系统课程参考课件 | 按比赛材料和授权边界确认 |
| `data/knowledge_bases/深度学习/raw/` | 深度学习课件进入 RAG 前的原始文件区 | 仅在资料授权明确时提交 |
| `data/knowledge_bases/智能机器人系统/raw/` | 机器人课件进入 RAG 前的原始文件区 | 仅在资料授权明确时提交 |
| `data/user/` | 本地用户设置、学习记录、画像和会话 | 不提交真实数据 |
| `data/knowledge_bases/` | 本地资料库文件和解析结果 | 不提交真实用户资料 |
| `data/milvus/` | Milvus 向量库运行数据 | 不提交 |
| `data/memory/` | 本地长期记忆文件 | 不提交真实数据 |

提交材料和视频建议固定使用 `deep_learning/deep_learning_foundations.json`。课程按 `ppts/深度学习/` 中的课件组织，14 周路线、节点、任务和考核方式见 [完整课程样例说明](./course-template-guide.md)。新增的 `intelligent_robot_systems/intelligent_robot_systems.json` 已单独放在机器人课程目录下，避免两门课程的课件和模板混在一起。课件进入 RAG 的同步命令是 `python scripts/sync_course_materials_to_kb.py --stage-only`，需要检索时再在完整环境里重建索引。

## 部署与依赖

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 启动后端、前端、Milvus、etcd 和 minio |
| `docker-compose.dev.yml` | 本地复核时的 Compose 覆盖配置 |
| `Dockerfile` | Python 后端、前端构建和运行镜像 |
| `requirements.txt` | 完整 Python 运行依赖 |
| `requirements/server.txt` | 后端 API 服务依赖 |
| `requirements/cli.txt` | CLI 和核心能力依赖 |
| `requirements/math-animator.txt` | Manim 数学动画依赖 |
| `requirements/sparkbot.txt` | 课程助教相关依赖 |
| `web/package.json` | 前端依赖、构建和质量检查入口 |

默认运行方式是 Docker Compose。这样评委不需要分别启动前端、后端和向量库服务，也更容易复现资料问答和学习路径流程。

## 提交边界

正式提交应包含：

- 源码：`sparkweave/`、`sparkweave_cli/`、`web/`、`scripts/`。
- 课程模板：`data/course_templates/`。
- 部署配置：`Dockerfile`、`docker-compose.yml`、`.env.example`。
- 依赖说明：`requirements/`、`requirements.txt`、`pyproject.toml`、`web/package.json`。
- 文档：`README.md`、`docs/`、`SECURITY.md`、`CONTRIBUTING.md`。

正式提交不应包含：

- `.env`、真实 API Key、账号凭证。
- `data/user/`、`data/knowledge_bases/`、`data/milvus/`、`data/memory/` 中的真实运行数据。
- `.venv/`、`node_modules/`、`web/dist/`、测试报告和本地生成目录。
- 本地临时压缩包、日志和 IDE 私有配置。

这条边界能保证提交包既能复现项目，又不混入用户数据和本地密钥。
