# SparkWeave 软件工程规范

范围：记录当前仓库的软件工程边界、代码组织、文档治理和自动化门禁。本文档只描述已经存在或本次补齐的工程约束；未来计划不写成当前能力。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| Python 项目 | `pyproject.toml`, `requirements/`, `sparkweave/`, `sparkweave_cli/` |
| 前端项目 | `web/package.json`, `web/src/`, `web/scripts/`, `web/tests/e2e/` |
| CI | `.github/workflows/ci.yml` |
| 工程检查 | `scripts/verify_project.py`, `scripts/check_project_standards.py`, `scripts/check_release_safety.py`, `scripts/check_web_api_contract.py`, `scripts/check_course_templates.py`, `scripts/check_ng_replacement.py` |
| 文档入口 | `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/README.md` |
| 编辑与行尾 | `.editorconfig`, `.gitattributes` |

## 1. 工程目标

SparkWeave 的工程规范服务三个目标：

1. 让学习用户入口保持稳定，不被工程能力列表淹没。
2. 让后端服务、前端页面、文档和测试能互相追溯。
3. 让发布前风险能被脚本提前发现，而不是靠人工记忆。

## 2. 目录边界

| 路径 | 当前职责 | 不应放入 |
| --- | --- | --- |
| `sparkweave/api/` | FastAPI 应用、HTTP 路由、WebSocket 路由 | 大块业务算法、前端展示逻辑 |
| `sparkweave/services/` | 可测试业务服务、供应商适配、RAG/OCR/语音/学习画像等能力 | FastAPI 路由细节、React 类型 |
| `sparkweave/runtime/` | ChatOrchestrator、上下文增强、能力路由和运行时状态 | 供应商 SDK 细节、页面状态 |
| `sparkweave/graphs/` | LangGraph 能力图和多阶段 Agent 流程 | API 请求解析、前端渲染 |
| `sparkweave/tools/` | LLM 工具注册、工具 metadata 和内置工具实现 | 页面 UI、长期数据迁移脚本 |
| `sparkweave_cli/` | Typer CLI 命令 | Web API 专用状态 |
| `web/src/components/` | 可复用组件、基础 UI、布局和结果渲染 | 页面级业务编排 |
| `web/src/pages/` | 页面级业务模块 | 全局基础控件 |
| `web/src/lib/` | 前端 API 客户端、类型辅助、展示格式化 | React 组件 |
| `scripts/` | CI、本地检查、迁移、评测和维护脚本 | 长期业务服务 |
| `tests/` | Python 单元、服务、API、运行时、脚本测试 | 真实密钥、真实用户数据 |
| `docs/` | 稳定文档、架构图、示例评测集 | 临时排查记录、未实现功能宣传 |

## 3. 后端组织规范

新增后端能力按以下顺序落地：

| 步骤 | 落点 | 要求 |
| --- | --- | --- |
| 服务实现 | `sparkweave/services/` | 业务逻辑可脱离 FastAPI 测试 |
| API 暴露 | `sparkweave/api/routers/` | 路由只做参数校验、调用服务、错误映射 |
| 运行时接入 | `sparkweave/runtime/`, `sparkweave/graphs/` | 影响对话编排时才修改 |
| 工具接入 | `sparkweave/tools/builtin.py` | 明确 tool name、输入 schema、metadata、失败策略 |
| 测试 | `tests/services/`, `tests/api/`, `tests/ng/` | 至少覆盖正常路径和失败路径 |
| 文档 | `docs/` 或 `README.md` | 标注代码路径、API、数据落点和验证命令 |

约束：

- 供应商真实调用与离线替补分层实现。
- 路径、文件名、压缩包成员和静态资源输出必须校验边界。
- API 响应新增字段要同步 `web/src/lib/types.ts` 和 `web/src/lib/api.ts`。
- 默认测试不依赖真实网络、真实密钥或本地绝对路径。

## 4. 前端组织规范

前端以用户任务组织，而不是以工程能力炫技组织。

| 层级 | 当前落点 | 规则 |
| --- | --- | --- |
| 全局壳层 | `web/src/components/layout/` | 控制导航、更多工具、状态和移动端入口 |
| 页面模块 | `web/src/pages/<feature>/` | 聚合页面状态、API 调用和业务流程 |
| 通用 UI | `web/src/components/ui/` | Button、Panel、Field、Badge 等基础控件 |
| 结果渲染 | `web/src/components/results/` | 视频、图像、图解、证据链、音频等结果视图 |
| 视觉动效 | `web/src/components/visual/`, `web/src/styles/` | 微动效、背景和设计令牌 |
| 数据访问 | `web/src/lib/api.ts` | 前端请求入口，路径与后端合约检查同步 |

视觉约束：

- 一级导航优先保留学习、资料、记录、设置。
- 卡片圆角不超过 8px。
- 动效服务状态反馈，不使用强鼠标跟随、强波纹或闪烁背景。
- 色彩用于分组和识别，不用大面积高饱和背景。
- 新增页面要有明确主动作和空状态下一步。

## 5. 文档治理

| 文档 | 作用 |
| --- | --- |
| `README.md` | 项目定位、截图、部署、参赛交付、结构总览 |
| `CONTRIBUTING.md` | 贡献流程、提交检查、协作规则 |
| `SECURITY.md` | 敏感信息、安全边界、漏洞报告 |
| `docs/README.md` | 文档地图和维护原则 |
| `docs/development-guide.md` | 开发流程、目录职责、质量矩阵 |
| `docs/testing-guide.md` | 测试分层、运行命令、CI 约束 |
| `docs/frontend-design-guide.md` | 前端信息架构、视觉和动效规范 |

文档必须满足：

- 关键结论能对应真实代码路径、函数、API、数据文件、脚本或测试。
- 相对链接必须存在。
- 新增稳定文档必须加入 `docs/README.md`。
- 未实现能力只能写在“限制与待实现”。

## 6. 自动化门禁

| 门禁 | 命令 | 覆盖 |
| --- | --- | --- |
| 轻量总检 | `python scripts/verify_project.py --profile quick` | 项目规范、发布安全、课程模板、API 合约、替换约束、Python 编译 |
| 项目结构规范 | `python scripts/check_project_standards.py` | 必需文件、文档索引、相对链接、前端脚本、禁止提交目录 |
| 发布安全 | `python scripts/check_release_safety.py` | 本地 env、已知密钥片段、旧项目名 |
| 课程模板 | `python scripts/check_course_templates.py` | `data/course_templates/` 模板结构 |
| API 合约 | `python scripts/check_web_api_contract.py` | 前端 API 路径与后端路由 |
| 旧运行时替换 | `python scripts/check_ng_replacement.py` | 新工作台替换约束 |
| 前端设计 | `cd web; npm run check:design` | 视觉约束和禁用样式 |
| 前端构建 | `cd web; npm run build` | TypeScript 与生产构建 |

## 7. 提交前最小清单

- [ ] `python scripts/check_project_standards.py`
- [ ] `python scripts/verify_project.py --profile quick`
- [ ] `python scripts/check_release_safety.py`
- [ ] 按改动范围运行相关 `pytest`
- [ ] 前端改动运行 `npm run lint`、`npm run check:design`、`npm run build`
- [ ] API 改动运行 `python scripts/check_web_api_contract.py`
- [ ] 文档链接和截图路径真实存在
- [ ] 没有提交 `.env`、运行时数据、构建产物或临时目录

说明：`verify_project.py` 是源码树门禁，依赖 `docs/`、`.github/` 等工程文件；不要把它作为 Docker 运行容器内的健康检查。

## 8. 限制与待实现

- 当前规范检查是结构门禁，不替代架构评审。
- Python 类型检查仍是渐进式配置，不是严格模式。
- CI 当前只跑聚焦测试和构建检查，不等于完整 `pytest -q`。
- 多用户部署仍需要身份认证、租户隔离、审计和生产密钥管理。
