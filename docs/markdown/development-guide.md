# 开发与本地运行指南

本篇面向评委、助教和需要复现实验环境的同学，说明 SparkWeave 如何在本机运行、如何定位主要功能代码、如何做修改后的基本验证。推荐优先使用 Docker Compose，因为它同时启动前端、后端和 Milvus，最接近完整运行环境。

## 推荐运行方式

从仓库根目录复制配置文件：

```bash
cp .env.example .env
```

Windows PowerShell 可使用：

```powershell
copy .env.example .env
```

填写至少一组 LLM 与 Embedding 配置后启动：

```bash
docker compose up --build
```

启动后访问：

| 入口 | 地址 |
| --- | --- |
| 前端工作台 | `http://127.0.0.1:3782` |
| 后端 API | `http://127.0.0.1:8001` |
| 后端状态 | `http://127.0.0.1:8001/api/v1/system/status` |
| API 文档 | `http://127.0.0.1:8001/docs` |

如果只想确认系统是否已通，可以先看学习页是否能加载课程模板，再看资料页是否能创建知识库。

## 本地联调方式

Docker 是推荐路线；本地联调适合需要改代码、看单元测试或单独查看前后端行为的场景。

后端环境：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/server.txt
pip install -e .
sparkweave serve --port 8001 --reload
```

macOS / Linux 激活环境可使用：

```bash
source .venv/bin/activate
```

前端环境：

```bash
cd web
npm install
npm run dev
```

前端默认读取 `VITE_API_BASE`。若后端端口不是 `8001`，可以在 `web/.env.local` 或启动环境里指定：

```env
VITE_API_BASE=http://127.0.0.1:8001
```

## 配置要点

`.env.example` 已按端口、LLM、Embedding、RAG、讯飞工具和安全设置分组。运行前建议至少确认：

| 配置 | 用途 |
| --- | --- |
| `LLM_BINDING`、`LLM_MODEL`、`LLM_API_KEY`、`LLM_HOST` | 对话、资源生成、学习报告 |
| `EMBEDDING_BINDING`、`EMBEDDING_MODEL`、`EMBEDDING_API_KEY`、`EMBEDDING_HOST` | 资料入库和 RAG 检索 |
| `RAG_PROVIDER=milvus` | 使用 Docker 中的 Milvus |
| `DOCKER_MILVUS_URI=http://milvus:19530` | 容器内访问 Milvus |
| `IFLYTEK_APPID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET` | 讯飞共享凭据 |
| `IFLYTEK_WORKFLOW_*` | 星辰工作流 |

如果模型服务运行在宿主机，Docker 容器里不要写 `localhost`。Windows 和 macOS 通常使用 `host.docker.internal`，Linux 可使用宿主机局域网 IP。

## 功能定位

| 想看什么 | 主要位置 |
| --- | --- |
| 后端应用如何启动 | `sparkweave/api/app_factory.py`、`sparkweave/api/main.py` |
| API 路由如何注册 | `sparkweave/api/router_registry.py` |
| 问问题和多智能体事件 | `sparkweave/api/routers/unified_ws.py`、`sparkweave/runtime/` |
| 学习路线与资源生成 | `sparkweave/api/routers/guide_v2.py`、`sparkweave/services/guide_v2.py` |
| 学习画像 | `sparkweave/services/learner_profile.py`、`sparkweave/services/learner_evidence.py` |
| 资料库与 RAG | `sparkweave/api/routers/knowledge.py`、`sparkweave/knowledge/manager.py`、`sparkweave/services/rag_support/` |
| 讯飞工具接入 | `sparkweave/services/iflytek_*.py`、`sparkweave/services/speech.py`、`sparkweave/services/tts.py` |
| 前端入口和路由 | `web/src/router.tsx`、`web/src/routeConfig.ts` |
| 前端页面 | `web/src/pages/` |
| 前端 API 客户端 | `web/src/lib/api.ts`、`web/src/lib/http.ts` |
| 完整课程模板 | `data/course_templates/` |

## 修改功能时的顺序

如果新增或调整功能，建议按这条顺序做：

1. 先确认它服务哪条用户路径：学习、资料、记录、设置，还是更多学习工具。
2. 后端先补接口或服务，再让前端通过 `web/src/lib/api.ts` 调用。
3. 长时间任务使用 WebSocket 或 SSE 返回进度，避免页面只能等待最终结果。
4. 涉及学习行为的操作，要考虑是否写入学习证据和画像。
5. 涉及资料问答的操作，要考虑是否能展示来源。
6. 涉及讯飞工具的能力，要在设置页或系统状态里能看到配置与检测结果。

这个顺序能帮助作品保持“学习体验优先”，而不是把每个工具都暴露成一个独立入口。

## 常用验证

后端和项目结构：

```bash
python scripts/verify_project.py --profile quick
python scripts/check_course_templates.py
python scripts/check_web_api_contract.py
python -m compileall -q sparkweave sparkweave_cli scripts
```

前端：

```bash
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

完整前端验证：

```bash
cd web
npm run verify
```

资料问答验收需要后端和 Milvus 已启动：

```bash
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --provider milvus --cleanup
```

## 提交前确认

提交或打包前，建议确认：

- `.env`、真实密钥、账号 Token 不在提交包里。
- `data/user/` 中没有真实学生记录、聊天记录或个人画像。
- `data/course_templates/` 至少保留一门完整课程。
- `web/screenshots-*.png` 与当前前端页面一致。
- `docs/markdown/README.md` 中列出的文档都真实存在。
- Docker Compose 能启动前端、后端和 Milvus。

## 边界说明

开发指南不是演示稿，也不是论文式架构说明。它只回答一个朴素问题：拿到项目的人如何把 SparkWeave 运行起来，并从代码里找到学习路线、资料问答、学习画像、多智能体和讯飞工具链的实现位置。真正的功能价值仍应回到前端学习流程中验证。
