<p align="center">
  <img src="assets/logo-ver2.png" alt="SparkWeave Logo" width="112" />
</p>

<h1 align="center">SparkWeave 星火织学</h1>

<p align="center">
  <strong>面向真实学习场景的 Agent-Native 智能学习工作台</strong>
</p>

<p align="center">
  SparkWeave 把课程资料、问答、练习、学习记录、学习画像和多智能体能力收进一个低噪声的学习入口，让用户先完成学习任务，而不是先理解工程系统。
</p>

<p align="center">
  <a href="https://github.com/Benzoquinone000/sparkweave/actions/workflows/ci.yml">
    <img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Benzoquinone000/sparkweave/ci.yml?branch=main&label=CI&style=flat-square" />
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-2563EB?style=flat-square" />
  <img alt="React" src="https://img.shields.io/badge/React-TypeScript-0F766E?style=flat-square" />
  <img alt="Docker" src="https://img.shields.io/badge/Deploy-Docker_Compose-0F766E?style=flat-square" />
  <img alt="License" src="https://img.shields.io/badge/License-Apache--2.0-111827?style=flat-square" />
</p>

<p align="center">
  <a href="#功能说明">功能说明</a> ·
  <a href="#页面截图">页面截图</a> ·
  <a href="#docker-部署">Docker 部署</a> ·
  <a href="#系统架构">系统架构</a> ·
  <a href="#项目结构">项目结构</a>
</p>

## 项目定位

SparkWeave 是一个个性化学习工作台。默认入口保持简洁：学习、资料、记录、设置。Agent、RAG、画像、诊断、演示和调试能力默认后台化，真正暴露给用户的是继续学习、上传资料、问资料、做练习和复盘记录。

后端使用 FastAPI、LangGraph、Milvus 和统一的 Agent Runtime；前端使用 React、TypeScript、TanStack Router 和 Vite。项目当前推荐且唯一写入 README 的启动方式是 Docker Compose。

## 功能说明

| 功能 | 用户看到的价值 | 后台能力 |
| --- | --- | --- |
| 个性化学习路线 | 打开首页就知道今天下一步学什么 | Guide、Learning Effect、Learner Profile |
| 资料库 | 上传课程 PDF、笔记或资料后用于问答 | Milvus、Embedding、RAG 入库与检索 |
| 问资料 | 围绕资料直接提问，回答保留证据链 | Chat Graph、Evidence RAG、Context Pack |
| 练习生成 | 根据主题生成练习并沉淀错题 | Deep Question、Question Notebook |
| 学习记录 | 保存对话、笔记、题目和资料引用 | Notebook、Session Store |
| 学习画像 | 查看系统为什么这样推荐，并校准偏好 | Memory、Evidence Ledger、Learner Profile |
| 课程助教 | 用课程文件驱动一个长期课程助手 | SparkBot、课程文件、历史对话 |
| 写作助手 | 对选中文本做润色、扩写和改写 | Co-writer tool chain |
| 图像解题 | 上传题图，提取结构并生成解题结果 | Vision pipeline、GeoGebra command |
| 设置与诊断 | 配置模型、Embedding、搜索、OCR、TTS | Provider catalog、健康检查 |
| 调试台 | 给开发者检查工具、能力和运行状态 | Plugin / capability playground |

## 页面截图

以下截图由当前前端重新生成，保存在 `web/` 目录。

| 学习 | 资料 |
| --- | --- |
| <img src="web/screenshots-guide.png" alt="学习页面截图" /> | <img src="web/screenshots-knowledge.png" alt="资料页面截图" /> |
| 个性化学习入口，聚焦下一步任务、学习路线和反馈。 | 管理资料库、上传资料、查看索引状态并进入资料问答。 |

| 记录 | 设置 |
| --- | --- |
| <img src="web/screenshots-notebook.png" alt="记录页面截图" /> | <img src="web/screenshots-settings.png" alt="设置页面截图" /> |
| 复盘笔记、题目、对话结果和资料引用。 | 管理模型、Embedding、搜索、OCR、TTS 与工作台偏好。 |

| 问问题 | 练习 |
| --- | --- |
| <img src="web/screenshots-chat.png" alt="问问题页面截图" /> | <img src="web/screenshots-question.png" alt="练习页面截图" /> |
| 简洁对话输入，支持资料上下文和智能体结果。 | 生成练习、查看题目记录并追踪答题结果。 |

| 学习画像 | 课程助教 |
| --- | --- |
| <img src="web/screenshots-memory.png" alt="学习画像页面截图" /> | <img src="web/screenshots-agents.png" alt="课程助教页面截图" /> |
| 展示偏好、薄弱点、证据来源和画像校准入口。 | 管理课程助教、课程文件、渠道与历史消息。 |

| 写作助手 | 图像解题 |
| --- | --- |
| <img src="web/screenshots-co-writer.png" alt="写作助手页面截图" /> | <img src="web/screenshots-vision.png" alt="图像解题页面截图" /> |
| 对学习材料和答案文本进行改写、润色、扩写。 | 上传题图，生成结构化分析和可复用命令。 |

| 调试台 | 移动端入口 |
| --- | --- |
| <img src="web/screenshots-playground.png" alt="调试台页面截图" /> | <img src="web/screenshots-mobile-guide.png" alt="移动端学习页面截图" /> |
| 面向开发者的工具、能力和运行状态检查入口。 | 移动端保持学习入口优先，适合随手继续学习。 |

## Docker 部署

### 1. 准备环境

- Git
- Docker Desktop，或 Docker Engine + Docker Compose v2
- 一个可用的 LLM API Key
- 一个可用的 Embedding API Key，资料库和 RAG 需要它

Windows PowerShell：

```powershell
git clone https://github.com/Benzoquinone000/sparkweave.git
cd sparkweave
copy .env.example .env
```

macOS / Linux：

```bash
git clone https://github.com/Benzoquinone000/sparkweave.git
cd sparkweave
cp .env.example .env
```

### 2. 配置 `.env`

最小可运行配置如下：

```dotenv
BACKEND_PORT=8001
FRONTEND_PORT=3782

LLM_BINDING=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-llm-key
LLM_HOST=https://api.openai.com/v1

EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=your-embedding-key
EMBEDDING_HOST=https://api.openai.com/v1
EMBEDDING_DIMENSION=3072

RAG_PROVIDER=milvus
DOCKER_MILVUS_URI=http://milvus:19530
```

如果 LLM 或 Embedding 服务跑在宿主机，例如 LM Studio、Ollama、vLLM，不要在容器里写 `localhost`。Windows / macOS 使用：

```dotenv
LLM_HOST=http://host.docker.internal:1234/v1
EMBEDDING_HOST=http://host.docker.internal:1234/v1
```

Linux 可以改成宿主机局域网 IP，例如 `http://192.168.1.100:1234/v1`。

### 3. 启动

前台启动，适合首次部署和看日志：

```powershell
docker compose up --build
```

后台启动：

```powershell
docker compose up -d --build
```

启动完成后访问：

| 服务 | 地址 |
| --- | --- |
| 前端工作台 | http://localhost:3782 |
| 后端 API | http://localhost:8001 |
| API 文档 | http://localhost:8001/docs |
| Milvus Web UI | http://localhost:9091/webui/ |

### 4. 运维命令

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose restart frontend
docker compose down
```

重新构建：

```powershell
docker compose build --no-cache
docker compose up -d
```

清理容器和 Compose volume：

```powershell
docker compose down -v
```

`down -v` 会删除 Compose 管理的 volume，例如前端 `node_modules` 缓存；项目目录下的 `data/` 仍由本地文件夹保存。

### 5. Docker 服务说明

| 服务 | 作用 | 默认端口 |
| --- | --- | --- |
| `backend` | FastAPI 后端，`uvicorn --reload` 热更新 | `8001` |
| `frontend` | Vite 前端，HMR 热更新 | `3782` |
| `milvus` | 向量数据库，资料库检索默认依赖 | `19530`, `9091` |
| `milvus-etcd` | Milvus 元数据服务 | 内部端口 |
| `milvus-minio` | Milvus 对象存储 | 内部端口 |

数据落点：

| 路径 | 内容 |
| --- | --- |
| `data/user/` | 用户设置、记忆、画像、会话相关数据 |
| `data/knowledge_bases/` | 本地资料库文件与处理结果 |
| `data/milvus/` | Milvus etcd、minio、standalone 数据 |
| `sparkweave_node_modules` | Docker Compose 管理的前端依赖缓存 |

### 6. 常见问题

| 问题 | 处理 |
| --- | --- |
| 前端第一次启动较慢 | `frontend` 容器会先执行 `npm ci`，首次等待即可 |
| 端口被占用 | 在 `.env` 改 `BACKEND_PORT` 或 `FRONTEND_PORT` |
| 容器访问不到本机模型 | 把 `localhost` 改为 `host.docker.internal` 或宿主机局域网 IP |
| 上传资料后无法检索 | 确认 Embedding 配置和 Milvus 服务状态 |
| Milvus 启动慢 | 首次启动需要初始化，查看 `docker compose logs -f milvus` |
| `.env` 修改不生效 | 执行 `docker compose up -d --force-recreate` |

## 系统架构

```text
学习入口 / 资料入口 / 记录入口 / 设置入口
  -> React Web Workbench
  -> FastAPI / WebSocket API
  -> SparkWeaveApp / ChatOrchestrator
  -> ToolRegistry + CapabilityRegistry
  -> LangGraph capability graph
  -> StreamEvent / Notebook / Memory / Milvus
```

<p align="center">
  <img src="docs/assets/agent-orchestration-overview.png" alt="SparkWeave 智能体编排主链路图" />
</p>

<p align="center">
  <img src="docs/assets/rag-system-overview.png" alt="SparkWeave Evidence RAG 系统图" />
</p>

## 质量检查

在 Docker 环境内检查：

```powershell
docker compose exec backend python scripts/check_release_safety.py
docker compose exec backend python -m compileall -q sparkweave tests
docker compose exec frontend npm run build
```

本地只更新前端截图时：

```powershell
cd web
npm run screenshots
```

## 项目结构

```text
sparkweave/        后端服务、Agent Runtime、LangGraph 能力图与业务服务
sparkweave_cli/    Typer CLI 入口，供内部能力复用
web/               Vite + React + TypeScript 前端
scripts/           检查、维护、截图和开发辅助脚本
requirements/      后端依赖分层
docs/              稳定设计文档和 PNG 架构图
assets/            Logo 与项目素材
data/              本地知识库、Milvus、记忆和用户数据
```

## 设计文档

| 文档 | 说明 |
| --- | --- |
| [docs/README.md](docs/README.md) | 文档中心 |
| [docs/agent-orchestration-design.md](docs/agent-orchestration-design.md) | 智能体编排设计 |
| [docs/rag-system-design.md](docs/rag-system-design.md) | Evidence RAG 系统设计 |
| [docs/learner-profile-memory-design.md](docs/learner-profile-memory-design.md) | 学习画像与记忆设计 |

## License

Apache License 2.0
