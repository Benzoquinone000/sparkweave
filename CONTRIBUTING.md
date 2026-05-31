# SparkWeave 贡献规范

范围：说明当前仓库的协作入口、代码组织、质量门禁和文档维护规则。产品说明、部署和比赛交付入口见 [README.md](README.md)；具体开发细则见 [docs/development-guide.md](docs/development-guide.md)。

## 1. 基本原则

- 面向真实学习用户，不把工程能力默认暴露成主入口。
- 改动保持小而可验证；避免把格式化、重构和功能变更混在一个提交里。
- 代码事实优先：文档、截图、README 中的能力描述必须能对应真实代码、API、脚本、数据文件或测试。
- 密钥和本地数据永不入库：`.env`、真实账号 JSON、OAuth token、用户资料、Milvus 数据和测试临时产物不能提交。
- 外部供应商能力必须有离线替补或结构化失败路径，默认测试不依赖真实密钥。

## 2. 分支与提交

推荐提交粒度：

| 类型 | 示例 |
| --- | --- |
| 功能 | `feat: add speech transcription fallback` |
| 修复 | `fix: guard guide artifact paths` |
| 文档 | `docs: document learner profile evidence flow` |
| 测试 | `test: cover iflytek workflow fallback` |
| 工程 | `chore: add project standards check` |

提交前先查看工作区：

```powershell
git status --short
git diff --check
```

不要回退自己不理解的改动；如果同一文件里有他人或用户改动，先读清上下文再继续。

## 3. 目录约定

| 路径 | 约定 |
| --- | --- |
| `sparkweave/api/` | FastAPI 应用和路由；请求响应契约变化要同步前端类型 |
| `sparkweave/services/` | 可测试的业务服务和供应商适配 |
| `sparkweave/runtime/` | 上下文、能力路由和运行时状态 |
| `sparkweave/graphs/` | LangGraph 能力图和多阶段流程 |
| `sparkweave/tools/` | LLM 可调用工具和工具注册 |
| `sparkweave_cli/` | Typer CLI |
| `web/src/components/` | 可复用组件、结果渲染、布局和基础 UI |
| `web/src/pages/` | 页面级业务模块 |
| `scripts/` | 可在 CI 或本地运行的维护脚本 |
| `tests/` | Python 单元、服务、API、运行时和脚本测试 |
| `docs/` | 稳定工程文档和架构图 |

更完整的边界说明见 [docs/engineering-standards.md](docs/engineering-standards.md)。

## 4. 推荐检查

后端与项目规范：

```powershell
python scripts/verify_project.py --profile quick
python scripts/check_project_standards.py
python scripts/check_release_safety.py
python scripts/check_course_templates.py
python scripts/check_web_api_contract.py
python scripts/check_ng_replacement.py
uv run pytest tests/scripts -q
```

前端：

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

完整测试根据改动范围选择，测试分层见 [docs/testing-guide.md](docs/testing-guide.md)。

## 5. 文档变更

- 新增功能时，同步更新 `README.md` 或 `docs/` 中对应稳定文档。
- 新增文档后必须在 [docs/README.md](docs/README.md) 建索引。
- 文档中的相对链接、图片路径、命令和代码路径必须真实存在。
- 未实现能力只能放到“限制与待实现”，不能写成当前能力。

## 6. 前端体验

前端主线遵循 [AGENTS.md](AGENTS.md) 和 [docs/frontend-design-guide.md](docs/frontend-design-guide.md)：

- 一级入口优先是学习、资料、记录、设置。
- Agent、RAG、画像、诊断、演示等工程能力默认收进“更多工具”或页面内部。
- 页面要给出明确主动作和空状态下一步。
- 视觉保持简约、低噪声、少层级；动效服务状态反馈。

## 7. 安全边界

安全问题处理见 [SECURITY.md](SECURITY.md)。任何涉及路径拼接、文件上传、压缩包解包、静态文件输出、外部 URL、命令执行和 Provider 密钥的改动，都必须添加测试或复用现有安全检查。
