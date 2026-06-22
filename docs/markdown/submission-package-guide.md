# 提交包整理说明

这篇用于整理最终提交材料。评委打开压缩包时，最好能马上分清三件事：系统代码在哪里，课程和配置样例在哪里，哪些本机数据没有放进提交物。

SparkWeave 的提交包建议保留可运行代码、课程模板、配置样例、文档、截图、PPT 和演示视频；真实密钥、账号凭证、真实学生数据和本机生成数据不放入包内。

## 建议提交内容

| 内容 | 建议保留 | 说明 |
| --- | --- | --- |
| 后端源码 | `sparkweave/`、`sparkweave_cli/` | 后端服务、能力编排、命令行入口 |
| 前端源码 | `web/` | 学习、资料、记录、设置和问问题等页面 |
| 部署文件 | `docker-compose.yml`、`Dockerfile`、`.env.example` | 用于启动前端、后端和 Milvus |
| 依赖说明 | `requirements/`、`pyproject.toml`、`web/package.json` | 后端和前端依赖入口 |
| 课程模板 | `data/course_templates/` | 完整高校课程模板，主课程为“深度学习”，另有“智能机器人系统” |
| 配套文档 | `README.md`、`docs/` | 运行方式、功能设计、数据边界、测试方式和展示材料说明 |
| 页面截图 | `web/screenshots-*.png` | 用于 PPT、文档和视频中快速定位页面 |
| 验证工具 | `scripts/check_course_templates.py`、`scripts/check_project_standards.py`、`scripts/check_web_api_contract.py`、`scripts/check_release_safety.py` | 用于确认课程模板、文档链接、API 合同和提交边界 |
| 展示材料 | PPT、7 分钟演示视频 | 建议和主课程、页面截图使用同一套学习数据 |

## 压缩包建议结构

正式提交时可以在项目根目录旁边放展示材料，保持评委打开后不需要到处找文件：

```text
SparkWeave/
  README.md
  docs/
  sparkweave/
  sparkweave_cli/
  web/
  data/course_templates/
  scripts/
  requirements/
  docker-compose.yml
  Dockerfile
  .env.example
  展示PPT/
  演示视频/
```

PPT 和视频文件名建议直接写清作品名、队伍名和版本日期，例如 `SparkWeave-PPT-2026-06-22.pptx`。如果比赛平台要求固定命名，以平台要求为准。

## 不放入提交包

| 内容 | 原因 |
| --- | --- |
| `.env` | 里面可能包含真实模型密钥和账号信息 |
| `data/user/` | 可能包含个人设置、学习记录和画像 |
| `data/memory/` | 可能包含对话记忆和用户偏好 |
| `data/knowledge_bases/` | 可能包含上传资料原文和处理结果 |
| `data/milvus/` | 本机向量库数据体积大，也可能包含课程资料内容 |
| `logs/` | 可能包含请求内容、错误栈和本机路径 |
| `web/dist/` | 前端构建产物可由源码重新生成 |
| `.venv/`、`node_modules/` | 本机依赖目录体积大，不适合作为作品材料 |
| 真实学生信息 | 包括姓名、联系方式、语音材料、学习记录和个人画像 |

如果提交材料需要展示学习记录，建议使用脱敏样例，只保留课程名、知识点、任务、分数、错因和反馈类型。

## 提交前顺序

1. 固定一门主课程。推荐使用 `data/course_templates/deep_learning/deep_learning_foundations.json`，这样 PPT、视频、截图和文档都能围绕同一条深度学习主线展开；`data/course_templates/intelligent_robot_systems/intelligent_robot_systems.json` 作为第二门课程保留在系统内，用于补充验证。
2. 确认 `.env.example` 只写配置项名称和示例值，不写真实密钥。
3. 使用 Docker Compose 启动系统，进入前端工作台确认学习、资料、问问题、记录、设置页面可访问。
4. 围绕同一门课程录制 7 分钟演示视频，视频中出现的页面和文档截图保持一致。
5. 运行轻量验证，确认课程模板、文档链接、API 合同和提交边界没有明显问题。

常用验证入口：

```powershell
python scripts/check_course_templates.py
python scripts/check_project_standards.py
python scripts/check_web_api_contract.py
python scripts/check_release_safety.py
```

前端可再补充：

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

## 评委拿到材料后的阅读路线

| 顺序 | 建议查看 | 能看到什么 |
| --- | --- | --- |
| 1 | `README.md` | 项目定位、页面截图、Docker 启动方式和赛题对应关系 |
| 2 | `docs/software-cup-delivery-checklist.md` | A3 赛题要求如何对应到当前系统 |
| 3 | `docs/project-structure.md` | 源码、课程模板、数据目录和部署文件位置 |
| 4 | `docs/configuration-guide.md` | 科大讯飞相关工具如何配置 |
| 5 | `docs/presentation-video-guide.md` | PPT 和 7 分钟视频如何讲清楚作品 |
| 6 | `docs/ai-coding-disclosure.md` | AI Coding 使用范围、人工复核和隐私边界 |

这条阅读路线的目标是让评委先看到作品能做什么，再看到代码和材料如何支撑这些能力。

## 最后确认

提交前建议团队成员换一台机器或新建目录试一次：从压缩包解出项目，按 `README.md` 配置 `.env`，启动 Docker Compose，进入前端工作台，再按演示视频路线走一遍。能顺利完成这条路线，说明提交包的主要材料已经放对位置。
