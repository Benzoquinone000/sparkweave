# AI Coding 工具使用说明

本文档用于比赛提交材料中的“AI Coding 工具说明”。SparkWeave 在开发过程中使用 AI 编程助手辅助调研、重构、实现和测试，但项目的需求判断、功能取舍、运行验证和提交内容由项目维护者负责。

## 使用范围

AI Coding 工具主要参与以下工作：

- 代码迁移与重构：将原有项目逐步重构为 `sparkweave` 后端和 `web` 前端，并保持接口兼容。
- 多智能体链路实现：辅助实现 Chat 协调、Guide V2、题目生成、知识可视化、数学动画、公开视频检索和 SparkBot 等模块。
- 前端体验优化：根据“简约、面向用户、少平铺、多分页”的原则优化学习工作台、导学、画像、资料库、Notebook 和设置页。
- 测试与排错：辅助编写和维护 Pytest、Playwright、前端 lint/build、课程模板校验和 CI 工作流。
- 文档整理：辅助撰写 README、架构文档、导学说明、画像设计、演示脚本和比赛路线图。

## 人工控制与审查

项目没有把 AI 输出直接当作最终结果。每次重要改动都会经过以下检查：

1. 人工确认功能目标是否服务赛题五条主线。
2. 阅读 diff，避免误删运行所需文件或泄露敏感配置。
3. 运行对应测试，例如：
   - `python scripts/check_course_templates.py`
   - `python -m pytest ...`
   - `cd web && npm run lint`
   - `cd web && npm run build`
   - `cd web && npm run check:design`
   - `cd web && npx playwright test ...`
4. 通过 Git 提交保存阶段性版本，并同步到 GitHub。

## 数据与密钥处理

- `.env` 本地配置不作为公开提交材料。
- 公开仓库只保留 `.env.example` 和配置说明。
- OCR、LLM、Embedding、Search 等外部服务密钥由运行者在本地或部署环境中配置。
- AI Coding 工具不应把真实密钥写入 README、文档、测试样例或截图。

## 质量边界

AI Coding 工具可以提高开发速度，但不能替代以下工作：

- 比赛演示前的真实运行联调。
- 用户体验判断和页面简化取舍。
- 关键服务密钥、Manim/FFmpeg/LaTeX/OCR/RAG 等本地环境配置。
- 最终 PPT、演示视频和提交材料的人工复核。

## 当前可追溯材料

- 代码与提交记录：GitHub 仓库提交历史。
- 自动化检查：`.github/workflows/ci.yml`。
- 功能路线：`docs/competition-roadmap.md`。
- 画像设计：`docs/learner-profile-design.md`。
- 导学设计：`docs/guided-learning.md`。
- 演示脚本：`docs/demo-script-profile-guide-loop.md`。

