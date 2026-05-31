# SparkWeave 开发指南

范围：面向参与 SparkWeave 开发、调试、交付和复核的维护者。根目录 `README.md` 负责产品介绍、Docker 部署和比赛交付说明；本文档只记录当前仓库稳定的工程开发流程。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| Python 项目配置 | `pyproject.toml`, `requirements/` |
| Docker 运行 | `docker-compose.yml`, `Dockerfile`, `web/Dockerfile` |
| 后端入口 | `sparkweave/api/main.py`, `sparkweave/app/facade.py`, `sparkweave_cli/main.py` |
| 运行时与服务 | `sparkweave/runtime/`, `sparkweave/services/`, `sparkweave/graphs/`, `sparkweave/tools/` |
| 前端工程 | `web/package.json`, `web/src/`, `web/scripts/` |
| 检查脚本 | `scripts/verify_project.py`, `scripts/check_project_standards.py`, `scripts/check_release_safety.py`, `scripts/check_web_api_contract.py`, `scripts/check_course_templates.py`, `scripts/check_ng_replacement.py` |
| 测试 | `tests/`, `web/tests/e2e/` |

## 1. 开发原则

- 用户入口优先：前端默认围绕学习、资料、记录、设置组织，不把 Agent、RAG、画像、诊断等工程名词作为主入口。
- Docker 启动优先：项目运行、演示和部署统一使用 Docker Compose；不要新增 Python 脚本包装 Docker 启动。
- 改动保持可验证：新增后端能力必须有 API、服务层或端到端测试；新增前端入口必须通过 lint、设计合约和构建。
- 文档只保留稳定内容：阶段计划、临时修复记录和一次性 runbook 不进入 `docs/`，完成后合并到稳定设计文档或根 README。
- 密钥绝不入库：`.env`、真实账号 JSON、OAuth token、API key、录屏中的明文密钥都不能提交。

## 2. 目录职责

| 路径 | 职责 |
| --- | --- |
| `sparkweave/` | 后端服务、Agent Runtime、LangGraph 能力图、RAG、画像、讯飞工具和业务服务 |
| `sparkweave/api/` | FastAPI 应用和 HTTP / WebSocket 路由 |
| `sparkweave/runtime/` | Orchestrator、能力路由、上下文增强和运行时状态 |
| `sparkweave/services/` | LLM、Embedding、RAG、OCR、语音、学习效果、课程导学等服务 |
| `sparkweave/tools/` | LLM 可调用工具注册和内置工具实现 |
| `sparkweave_cli/` | Typer CLI 入口，主要用于复用内部能力和维护命令 |
| `web/` | React、TypeScript、TanStack Router、Vite 前端 |
| `web/src/components/` | 可复用 UI、聊天组件、结果渲染、布局组件 |
| `web/src/pages/` | 页面级业务模块，按学习任务拆分 |
| `scripts/` | 检查、迁移、截图、评测和维护脚本 |
| `tests/` | Python 单元、API、服务和运行时测试 |
| `data/course_templates/` | 可演示课程模板，比赛建议固定使用一门主课程 |
| `docs/` | 稳定开发文档和 PNG 架构图 |

## 3. 本地运行

项目运行统一使用 Docker Compose。

```powershell
copy .env.example .env
docker compose up --build
```

启动后访问：

| 服务 | 地址 |
| --- | --- |
| 前端工作台 | `http://localhost:3782` |
| 后端 API | `http://localhost:8001` |
| API 文档 | `http://localhost:8001/docs` |
| Milvus Web UI | `http://localhost:9091/webui/` |

常用维护命令：

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose restart frontend
docker compose down
```

## 4. 配置与数据边界

### 4.1 配置来源

| 配置 | 位置 | 说明 |
| --- | --- | --- |
| 环境变量样例 | `.env.example` | 可提交，只放占位值和默认说明 |
| 本地真实配置 | `.env` | 不提交 |
| 前端设置 | `data/user/` | 用户在设置页保存的模型、搜索、OCR、语音等配置 |
| Provider catalog | `sparkweave/services/config.py` | 后端可用供应商、模型预设和配置 schema |
| 前端设置面板 | `web/src/pages/settings/` | 配置展示、诊断和预设应用 |

### 4.2 数据目录

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| 用户画像、记忆、会话 | `data/user/` | 本地运行时数据 |
| 知识库文件 | `data/knowledge_bases/` | 用户上传资料和解析结果 |
| Milvus 数据 | `data/milvus/` | 向量库持久化数据 |
| 课程模板 | `data/course_templates/` | 可提交的演示课程样例 |

提交前需要确认没有把真实用户资料、密钥、私有截图或临时凭证加入 Git。

## 5. 后端开发流程

### 5.1 新增服务

1. 在 `sparkweave/services/` 新增服务实现，保持纯业务逻辑可测试。
2. 如果需要 API，新增或扩展 `sparkweave/api/routers/` 下的路由。
3. 如果需要 LLM 工具调用，在 `sparkweave/tools/builtin.py` 注册工具，并补充工具别名、metadata 和前端结果渲染。
4. 如果影响运行时路由，在 `sparkweave/runtime/` 或 `sparkweave/graphs/` 中补齐决策逻辑。
5. 在 `tests/services/`、`tests/api/` 或 `tests/ng/` 添加覆盖。

### 5.2 API 约定

- 后端响应字段必须尽量稳定，前端依赖的新字段要同步 `web/src/lib/types.ts`。
- 新增前端 API 调用要同步 `web/src/lib/api.ts`。
- 新增或删除接口后必须运行 API 合约检查。

```powershell
python scripts/check_web_api_contract.py
```

### 5.3 讯飞工具接入约定

- 真实服务调用和离线替补分层实现，真实服务不可用时默认不打断演示流程。
- 结果 metadata 需要明确 `provider`、`tool_name`、`render_type` 和 `fallback`。
- 设置页必须能看到配置入口、诊断状态和必要说明。
- 测试中只使用模拟响应或离线替补，不依赖真实密钥。

## 6. 前端开发流程

### 6.1 页面入口

一级导航优先保留：

| 入口 | 用户任务 |
| --- | --- |
| 学习 | 继续学习、生成路线、完成任务、提交反馈 |
| 资料 | 上传资料、管理知识库、问资料 |
| 记录 | 保存复盘、题目、对话结果和资料引用 |
| 设置 | 配置模型、搜索、OCR、语音和工作台偏好 |

Agent、RAG、画像、诊断、演示、调试等能力默认收进“更多工具”或页面内部，不抢用户主路径。

### 6.2 组件与样式

- 页面级组件放在 `web/src/pages/<feature>/`。
- 通用 UI 放在 `web/src/components/ui/`。
- 结果渲染放在 `web/src/components/results/`。
- 视觉动画放在 `web/src/components/visual/`，必须支持 `prefers-reduced-motion`。
- 卡片圆角不超过 8px，不使用 `rounded-full`。
- 动画应服务状态反馈，不做鼠标跟随、强波纹、强闪烁背景。
- 文案面向学习用户，避免默认展示内部工程术语。

### 6.3 前端验证

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

如果修改了主要页面视觉，需要重新截图：

```powershell
cd web
npm run screenshots
```

## 7. 质量检查矩阵

| 改动类型 | 必跑检查 |
| --- | --- |
| Python 服务、路由、工具 | `uv run ruff check .`、相关 `pytest`、`python scripts/check_web_api_contract.py` |
| RAG、知识库、Embedding | RAG 相关测试、课程模板检查、API 合约检查 |
| 前端页面、组件、样式 | `npm run lint`、`npm run check:design`、`npm run build` |
| 设置页、Provider、环境变量 | Provider 测试、release safety、README / `.env.example` 同步检查 |
| 文档和截图 | `git diff --check`、文档链接检查、截图是否为当前前端 |
| 参赛交付材料 | release safety、课程模板检查、前后端构建、README 赛题映射复核 |
| 项目结构、文档索引、提交边界 | `python scripts/check_project_standards.py` |
| 比赛提交前轻量总检 | `python scripts/verify_project.py --profile quick` |

推荐提交前完整检查：

```powershell
uv run ruff check .
uv run pytest -q
python scripts/verify_project.py --profile quick
python scripts/check_project_standards.py
python scripts/check_release_safety.py
python scripts/check_course_templates.py
python scripts/check_web_api_contract.py
python scripts/check_ng_replacement.py

cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

## 8. 文档规范

新增或修改文档时遵循以下规则：

- 先查代码，再写文档；每个关键结论都要能对应真实路径、函数、API、数据文件、脚本或前端组件。
- 代码里没有确认的内容不能写成当前能力；只能删除，或明确放到“限制与待实现”并标注不是当前实现。
- 根 README：产品定位、截图、Docker 部署、讯飞工具链、参赛交付。
- `docs/README.md`：文档索引和维护原则。
- 架构文档：只写稳定架构、关键数据流、代码落点和验证方式。
- 不新增空泛文档；每份文档必须能回答“谁会读、读完能做什么、对应代码在哪里”。
- 图片只保留 PNG，且必须被文档引用。
- 文档中的命令必须能在当前仓库运行，避免写过期脚本或不存在路径。

## 9. 提交前清单

- [ ] 没有提交 `.env`、真实密钥、账号 JSON、临时凭证或私有数据。
- [ ] `python scripts/verify_project.py --profile quick` 通过。
- [ ] `python scripts/check_project_standards.py` 通过。
- [ ] 新增 API 已同步前端类型和 API 调用。
- [ ] 新增前端入口符合学习、资料、记录、设置的主路径。
- [ ] 新增工具有配置说明、失败提示和测试覆盖。
- [ ] 质量检查已按改动类型运行。
- [ ] README 和 docs 链接真实存在。
- [ ] 如果截图变化，已重新生成并确认不是旧前端截图。

## 10. 常见问题

| 问题 | 处理 |
| --- | --- |
| 容器内访问宿主机模型失败 | 将 `localhost` 改为 `host.docker.internal` 或宿主机局域网 IP |
| 资料上传后检索不到 | 检查 Embedding 配置、Milvus 状态和知识库索引日志 |
| 前端设计检查失败 | 检查圆角、动效、文字溢出和禁止的装饰类 |
| 讯飞工具不可用 | 先确认官网服务已开通，再检查 `.env`；演示可临时使用离线替补 |
| API 合约检查失败 | 同步后端路由、`web/src/lib/api.ts` 和 `web/src/lib/types.ts` |
