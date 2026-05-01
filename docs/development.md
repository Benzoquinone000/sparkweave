# 开发与维护

本文档记录 SparkWeave 的开发检查、测试和维护约定。

## 目录结构

```text
sparkweave/        后端服务、LangGraph 能力图、多智能体与业务服务
sparkweave_cli/    命令行入口
web/               Vite + React + TypeScript 前端
scripts/           启动、检查和维护脚本
requirements/      分层依赖集合
assets/            Logo 与项目展示素材
data/              本地用户数据、记忆、知识库和运行产物
tests/             后端与服务测试
docs/              详细项目文档
```

## 依赖分层

| 文件 | 说明 |
| --- | --- |
| `requirements/cli.txt` | CLI 完整依赖 |
| `requirements/server.txt` | CLI + FastAPI / uvicorn |
| `requirements/math-animator.txt` | Manim 动画相关依赖 |
| `requirements/dev.txt` | 服务端、测试和 lint 工具 |
| `requirements.txt` | 项目默认依赖入口 |

## 常用检查

```powershell
python scripts/check_install.py
python scripts/check_ng_replacement.py
python scripts/check_web_api_contract.py
python scripts/smoke_ng_runtime.py
```

前端检查：

```powershell
cd web
npm run lint
npm run build
npm run check:api-contract
npm run check:replacement
cd ..
```

后端测试：

```powershell
pytest
```

按目录运行：

```powershell
pytest tests/services
pytest tests/api
pytest tests/tools
```

前端 e2e：

```powershell
cd web
npm run test:e2e
cd ..
```

## 提交前检查清单

```powershell
git status
python scripts/check_install.py
python scripts/check_ng_replacement.py
python scripts/check_web_api_contract.py
python scripts/smoke_ng_runtime.py
pytest
cd web
npm run lint
npm run build
cd ..
```

确认以下内容没有进入提交：

- `.env`
- `data/user/`
- `data/memory/`
- 本地知识库索引
- `web/node_modules/`
- `web/dist/`
- 临时日志和运行产物

## 文档维护

新增功能时，应同步更新：

- 赛题目标、学习闭环、画像/导学/评估后续计划：`docs/competition-roadmap.md`
- 统一学习画像、证据账本、画像中心、画像 API：`docs/learner-profile-design.md`
- 新环境变量：`docs/configuration.md`
- 新 Provider、设置页、模型 catalog 行为：`docs/settings-and-providers.md`
- 新系统状态、连接测试、诊断提示或 Embedding adapter 行为：`docs/system-diagnostics.md`
- 新 CLI 命令：`docs/cli-and-api.md`
- 新 WebSocket 字段：`docs/cli-and-api.md`
- 新 session、turn、事件持久化或续流行为：`docs/sessions-and-turns.md`
- 新 Notebook、Memory、历史引用或上下文注入行为：`docs/notebook-memory-context.md`
- 新 capability：`docs/architecture.md` 和 `docs/capabilities.md`
- 新 tool：`docs/tools.md`、`docs/architecture.md` 和相关 capability 文档
- 新 SparkBot 实例、渠道、工作区工具、heartbeat、cron 或 AgentsPage 行为：`docs/sparkbot-agents.md`
- 新知识库行为：`docs/knowledge-base.md`
- 新题目生成、仿题或题目本行为：`docs/question-workflows.md`
- 新导学路线、Guide V2 任务、证据、资源生成或报告行为：`docs/guided-learning.md`
- 新视觉输入、OCR、图像题解析或 GeoGebra 分析行为：`docs/vision-ocr-geogebra.md`
- 新插件约定：`docs/plugin-development.md`
- 新截图、流程图、架构图：统一放在 `docs/assets/`，文件名使用小写短横线。

## 近期开发主线

后续功能开发优先围绕比赛要求收束，完整计划见 [赛题对齐与后续开发路线](./competition-roadmap.md)。

当前优先级：

1. 统一学习画像中心：把 Chat、Memory、Notebook、题目本和 Guide V2 的画像证据合并展示，详细设计见 [学习画像设计调研与实现方案](./learner-profile-design.md)。
2. 导学闭环继续简化：围绕“当前任务 -> 资源生成 -> 交互练习 -> 提交反思 -> 推荐下一步”推进。
3. 学习效果评估：新增或强化学习报告，展示掌握度、正确率、薄弱点和推荐原因。
4. 多智能体协作可视化：用轻量轨迹展示画像、规划、检索、图解、动画、出题、评估等智能体分工。
5. 完整课程 Demo：准备一门可稳定演示的高校课程样例和 7 分钟演示路径。

## 测试建议

| 改动类型 | 建议测试 |
| --- | --- |
| 配置解析 | `tests/services/config` |
| LLM / Embedding 适配器 | `tests/services` 下对应模块 |
| 搜索工具 | `tests/services/search`、`tests/tools/test_web_search.py` |
| SparkBot / Agents | `tests/api/test_sparkbot_router.py`、`tests/api/test_sparkbot_channel_schema.py`、`tests/ng/test_sparkbot_service.py` |
| API 路由 | `tests/api` |
| 前端契约 | `python scripts/check_web_api_contract.py` |
| 前端页面 | `cd web && npm run lint && npm run build` |

## Git 注意事项

项目中可能同时存在用户本地改动。维护文档或代码时：

- 只修改当前任务需要的文件。
- 不回滚无关改动。
- 提交前用 `git status` 确认变更范围。
- 文档改动优先放在 `docs/`，避免 README 过度膨胀。
