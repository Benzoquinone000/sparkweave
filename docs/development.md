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

- 新环境变量：`docs/configuration.md`
- 新 Provider、设置页、模型 catalog 行为：`docs/settings-and-providers.md`
- 新系统状态、连接测试、诊断提示或 Embedding adapter 行为：`docs/system-diagnostics.md`
- 新 CLI 命令：`docs/cli-and-api.md`
- 新 WebSocket 字段：`docs/cli-and-api.md`
- 新 session、turn、事件持久化或续流行为：`docs/sessions-and-turns.md`
- 新 capability：`docs/architecture.md` 和 `docs/capabilities.md`
- 新 tool：`docs/tools.md`、`docs/architecture.md` 和相关 capability 文档
- 新知识库行为：`docs/knowledge-base.md`
- 新题目生成、仿题或题目本行为：`docs/question-workflows.md`
- 新视觉输入、OCR、图像题解析或 GeoGebra 分析行为：`docs/vision-ocr-geogebra.md`
- 新插件约定：`docs/plugin-development.md`
- 新截图、流程图、架构图：统一放在 `docs/assets/`，文件名使用小写短横线。

## 测试建议

| 改动类型 | 建议测试 |
| --- | --- |
| 配置解析 | `tests/services/config` |
| LLM / Embedding 适配器 | `tests/services` 下对应模块 |
| 搜索工具 | `tests/services/search`、`tests/tools/test_web_search.py` |
| API 路由 | `tests/api` |
| 前端契约 | `python scripts/check_web_api_contract.py` |
| 前端页面 | `cd web && npm run lint && npm run build` |

## Git 注意事项

项目中可能同时存在用户本地改动。维护文档或代码时：

- 只修改当前任务需要的文件。
- 不回滚无关改动。
- 提交前用 `git status` 确认变更范围。
- 文档改动优先放在 `docs/`，避免 README 过度膨胀。
