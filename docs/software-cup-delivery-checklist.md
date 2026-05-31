# 软件杯交付检查清单

范围：面向软件杯提交前的最终复核。本文档不扩展功能承诺，只把当前仓库已有交付物、检查脚本、文档和数据边界组织成可执行清单。

代码事实来源：

| 交付面 | 事实来源 |
| --- | --- |
| 可运行源码 | `sparkweave/`, `sparkweave_cli/`, `web/`, `scripts/`, `requirements/` |
| Docker 部署 | `docker-compose.yml`, `docker-compose.dev.yml`, `Dockerfile`, `web/Dockerfile` |
| 前端截图 | `web/screenshots-*.png`, `web/scripts/capture-screenshots.mjs` |
| 工程规范 | `CONTRIBUTING.md`, `SECURITY.md`, `docs/engineering-standards.md` |
| 质量门禁 | `scripts/verify_project.py`, `scripts/check_project_standards.py`, `.github/workflows/ci.yml` |
| 文档中心 | `README.md`, `docs/README.md`, `docs/*.md` |
| 课程模板 | `data/course_templates/`, `scripts/check_course_templates.py` |

## 1. 源码与运行

| 检查项 | 要求 | 验证 |
| --- | --- | --- |
| 源码完整 | 后端、前端、CLI、脚本、测试目录齐全 | `python scripts/check_project_standards.py` |
| Docker 可启动 | README 只推荐 Docker Compose 作为演示启动入口 | `docker compose up --build` |
| 依赖分层 | Python 依赖在 `pyproject.toml` 和 `requirements/`；前端依赖在 `web/package.json` | 人工复核 |
| 前端构建 | TypeScript 与 Vite 生产构建通过 | `cd web; npm run build` |
| 后端编译 | Python 源码可编译 | `python -m compileall -q sparkweave sparkweave_cli scripts` |

## 2. 功能演示主线

演示建议按用户任务组织，不按工程模块堆功能：

1. 打开“学习”，展示当前下一步、路线、任务和反馈。
2. 进入“资料”，上传或选择课程资料，展示知识库状态。
3. 在“问问题”或资料入口中围绕资料提问，展示证据链。
4. 生成练习，完成题目，并沉淀到记录或画像证据。
5. 展示学习画像、薄弱点、偏好和校准入口。
6. 展示讯飞相关工具配置、离线替补和多模态结果。
7. 进入设置页，说明模型、OCR、语音、搜索等配置与诊断。

## 3. 文档交付

| 文档 | 作用 | 提交前确认 |
| --- | --- | --- |
| `README.md` | 项目首屏、部署、功能、截图、参赛交付 | 截图与当前前端一致 |
| `docs/README.md` | 文档地图 | 新增文档已索引 |
| `docs/engineering-standards.md` | 软件工程规范 | 目录边界、门禁和清单与代码一致 |
| `docs/development-guide.md` | 开发流程 | 命令可运行 |
| `docs/testing-guide.md` | 测试分层 | 与 `tests/` 和 CI 一致 |
| `docs/configuration-guide.md` | 配置与供应商 | 不包含真实密钥 |
| `docs/api-development-guide.md` | API 契约 | 与 `web/src/lib/api.ts` 和 FastAPI 路由一致 |
| `docs/frontend-design-guide.md` | 前端视觉与交互 | 与当前导航和设计检查一致 |

文档检查：

```powershell
python scripts/check_project_standards.py
git diff --check -- README.md docs
```

## 4. 质量门禁

比赛提交前最小命令：

```powershell
python scripts/verify_project.py --profile quick
python scripts/check_release_safety.py
python scripts/check_course_templates.py

cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

如果时间允许，补充运行：

```powershell
uv run pytest -q
cd web
npm run test:e2e:isolated
```

## 5. 安全与隐私

不得提交：

- `.env`、真实 API Key、OAuth token、账号 JSON。
- `data/user/`、`data/knowledge_bases/`、`data/milvus/`、`data/memory/` 中的真实用户数据。
- `web/dist/`、`web/test-results/`、`web/playwright-report/` 等生成物。
- 本地下载目录、临时压缩包、录屏中的明文密钥。

验证：

```powershell
python scripts/check_release_safety.py
python scripts/check_project_standards.py
```

## 6. 视频与 PPT 复核

| 材料 | 检查点 |
| --- | --- |
| 7 分钟演示视频 | 先展示用户主线，再展示多智能体、讯飞工具和离线替补 |
| PPT | 对应赛题要求：个性化画像、资源生成、路径规划、智能辅导、学习效果评估 |
| 源码压缩包 | 不包含 `.env`、用户数据、构建产物和临时目录 |
| 配套文档 | README、docs、配置说明、AI Coding 说明均可追溯到代码事实 |

## 7. 最终提交前状态

```powershell
git status --short
git diff --check
python scripts/verify_project.py --profile quick
```

只有在工作区改动明确、检查通过、没有密钥和用户数据时，才上传到 GitHub 或打包提交。
