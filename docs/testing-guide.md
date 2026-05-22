# SparkWeave 测试规范

范围：约定 SparkWeave 当前测试分层、命名、运行方式和提交前验证要求。本文档只描述当前仓库已有测试目录、脚本和 package scripts；未落地测试能力不写成当前能力。

开发流程见 [开发指南](./development-guide.md)，API 规范见 [API 开发规范](./api-development-guide.md)。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| Pytest 配置 | `pyproject.toml` |
| Python 测试目录 | `tests/` |
| 前端脚本 | `web/package.json` |
| 前端 E2E | `web/tests/e2e/`, `web/scripts/e2e-isolated.mjs` |
| 设计检查 | `web/scripts/check-design.mjs` |
| API 合约检查 | `scripts/check_web_api_contract.py`, `tests/scripts/test_check_web_api_contract.py` |
| 发布安全检查 | `scripts/check_release_safety.py`, `tests/scripts/test_check_release_safety.py` |
| 课程模板检查 | `scripts/check_course_templates.py` |
| CI | `.github/workflows/ci.yml` |

## 1. 测试目标

SparkWeave 的测试重点不是追求形式覆盖率，而是保证以下能力稳定：

- Docker 部署后核心路径可运行。
- 前端页面、后端 API 和运行时协议保持一致。
- RAG、学习画像、导学、讯飞工具和学习效果闭环有可回归样例。
- 外部供应商不可用时不会打断演示主流程。
- 提交物中不包含密钥、本地环境文件或旧项目残留。

## 2. 测试目录分层

| 路径 | 关注点 |
| --- | --- |
| `tests/api/` | FastAPI 路由、请求响应、错误处理、前后端契约 |
| `tests/services/` | 服务层业务逻辑、供应商配置、RAG、学习效果、讯飞工具 |
| `tests/ng/` | 新一代运行时、ChatGraph、Capability Router、状态迁移 |
| `tests/core/` | 核心协议、工具、安全限制、输入限制 |
| `tests/agents/` | 智能体流程、研究、解题、动画等能力 |
| `tests/capabilities/` | 能力一致性和跨能力行为 |
| `tests/cli/` | CLI 命令和输出契约 |
| `tests/scripts/` | 检查脚本、评测脚本、数据准备脚本 |
| `tests/knowledge/` | 知识库目录、registry 和数据布局 |
| `web/tests/e2e/` | Playwright 端到端前端流程 |

新增测试时优先放到最靠近被测代码的目录，不把所有测试堆到单个大文件。

## 3. Pytest 约定

Pytest 配置在 `pyproject.toml`：

| 配置 | 当前约定 |
| --- | --- |
| `testpaths` | `tests` |
| `pythonpath` | 仓库根目录 |
| `--strict-markers` | marker 必须先注册 |
| `--strict-config` | pytest 配置错误直接失败 |
| `--tb=short` | 输出短 traceback |
| `--import-mode=importlib` | 避免测试导入路径污染 |

已注册 marker：

| marker | 用途 |
| --- | --- |
| `asyncio` | 异步测试 |
| `live` | 会调用真实外部供应商的可选测试 |

真实外部服务测试必须标记 `live`，默认 CI 和日常开发不应依赖真实密钥。

## 4. 后端测试运行

完整后端测试：

```powershell
uv run pytest -q
```

按模块运行：

```powershell
uv run pytest tests/api -q
uv run pytest tests/services -q
uv run pytest tests/ng -q
```

运行单个文件：

```powershell
uv run pytest tests/api/test_system_router.py -q
```

运行单个用例：

```powershell
uv run pytest tests/ng/test_chat_graph.py::test_router_uses_learning_path_mode -q
```

## 5. 前端测试与检查

前端质量检查：

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

端到端测试：

```powershell
cd web
npm run test:e2e
```

隔离式端到端测试：

```powershell
cd web
npm run test:e2e:isolated
```

截图更新：

```powershell
cd web
npm run screenshots
```

截图只在前端视觉确实变化时更新。提交前确认截图来自当前前端，不保留旧 UI。

## 6. 设计合约测试

`npm run check:design` 用于防止前端视觉偏离项目规范。当前重点包括：

- 圆角不超过 8px，不使用 `rounded-full`。
- 不加入强噪声、强波纹、鼠标跟随或晃眼背景动画。
- 文本不能溢出按钮、卡片和紧凑面板。
- 页面应优先服务真实学习路径，不把工程能力前置。

如果设计检查失败，优先修改组件样式，不要绕过检查脚本。

## 7. API 合约测试

`python scripts/check_web_api_contract.py` 会检查前端声明的 API 路径与后端路由是否匹配。

触发条件：

- 新增、删除或改名 API 路由。
- 修改 `web/src/lib/api.ts`。
- 修改前端依赖的后端路径。

前端目录下也可以运行：

```powershell
cd web
npm run check:api-contract
```

## 8. 安全与发布检查

发布安全检查：

```powershell
python scripts/check_release_safety.py
```

它用于发现：

- 已跟踪的本地 env 文件。
- 明显密钥或 token。
- 旧项目名称残留。

课程模板检查：

```powershell
python scripts/check_course_templates.py
```

旧项目替换检查：

```powershell
python scripts/check_ng_replacement.py
```

这些脚本是参赛提交和 GitHub CI 的底线检查，不应随意弱化。

## 9. 外部供应商测试策略

外部供应商包括 OpenAI-compatible LLM、Embedding、搜索、科大讯飞 OCR / 公式 / 图片 / 语音 / 工作流等。

测试原则：

- 单元测试使用 mock、fixture 或离线替补。
- 不把真实密钥写入测试文件。
- 不要求 CI 访问外网供应商。
- 真实连通性通过设置页诊断或 `system` API 手动验证。
- 讯飞工具不可用时，离线替补应返回结构化结果，并标记 `fallback: true`。

## 10. RAG 测试策略

RAG 相关改动至少考虑三类测试：

| 类型 | 目的 |
| --- | --- |
| 单元测试 | 查询改写、策略选择、质量门、repair、context pack |
| API 测试 | 知识库上传、RAG test、RAG eval、诊断和 preflight |
| 端到端 smoke | 建库、入库、检索、来源展示和前端结果渲染 |

改动 Agentic RAG 参数时，要同步：

- 工具 schema。
- `sparkweave/graphs/rag_overrides.py`。
- API request model。
- 前端 RAG 设置和结果展示。
- 相关测试。

## 11. 学习画像与学习效果测试策略

学习画像和学习效果闭环容易被“看起来能跑”掩盖问题。测试应覆盖：

- 学习事件写入 Evidence Ledger。
- 画像刷新和 evidence preview。
- 画像 hints 注入 Chat / Guide / Router。
- 练习提交、错因、掌握分进入学习效果报告。
- 下一步 action 能回到学习路线或补救任务。
- 证据不足时不强行个性化。

## 12. 前端端到端测试策略

端到端测试优先覆盖用户主路径：

1. 打开学习页，看到下一步动作。
2. 上传或选择资料。
3. 围绕资料提问。
4. 生成或完成练习。
5. 提交反馈。
6. 查看学习报告、记录或画像变化。
7. 进入设置页检查服务状态。

工程工具页可以有 smoke test，但不应喧宾夺主。

## 13. 提交前推荐命令

完整检查：

```powershell
uv run ruff check .
uv run pytest -q
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

轻量前端检查：

```powershell
cd web
npm run lint
npm run check:design
npm run build
```

轻量后端检查：

```powershell
uv run ruff check .
uv run pytest tests/api tests/services -q
python scripts/check_release_safety.py
```

## 14. 测试新增清单

- [ ] 测试名称描述行为，而不是描述实现细节。
- [ ] 不依赖真实密钥、真实网络或本地绝对路径。
- [ ] 临时目录使用 `tmp_path`。
- [ ] 异步测试标记 `pytest.mark.asyncio`。
- [ ] 外部供应商真实调用标记 `pytest.mark.live`。
- [ ] 测试失败信息能说明具体断言原因。
- [ ] 新增 API 有 `tests/api/` 覆盖。
- [ ] 新增服务有 `tests/services/` 覆盖。
- [ ] 新增前端用户路径有 e2e 或 smoke 覆盖。

## 15. 限制与待实现

- `pytest -q` 是完整 Python 测试入口，但部分依赖真实外部服务的用例必须标记 `live`，不应作为默认 CI 依赖。
- `npm run check:design` 是静态设计合约检查，不能替代截图和人工视觉复核。
- `scripts/check_web_api_contract.py` 检查路径契约，不覆盖所有请求/响应字段语义。
- 真实供应商连通性通过设置页诊断或 `/api/v1/system/test/*` 手动验证，默认测试只覆盖 mock、离线替补或结构化失败。
