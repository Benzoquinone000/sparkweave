# 比赛可视化录屏与截图 Runbook

本文档对应 `/demo` 评委演示台，用于录制 7 分钟演示视频、整理 PPT 截图和答辩讲法。

## 1. 开场入口

优先打开：

```text
http://localhost:3782/demo
```

首屏讲法：

> 这里是评委模式。五个赛题要求不是写在文档里，而是每一项都对应系统页面证据：画像、路径、资源、辅导和评估会形成一条可追踪学习闭环。

## 2. 7 分钟录屏路线

| 时间 | 页面/区域 | 讲法 |
| --- | --- | --- |
| 0:00-0:40 | `/demo` 比赛演示驾驶舱 | 说明项目不是普通聊天，而是完整学习闭环 |
| 0:40-2:00 | `/guide` 画像、路线、知识地图 | 展示学生目标如何变成画像和当前任务 |
| 2:00-4:20 | Guide 资源 Studio | 展示图解、语音、公开视频、练习等多模态资源 |
| 4:20-6:20 | 学习报告 Before/After | 展示练习反馈如何改变下一步路线 |
| 6:20-7:00 | 课程产出包与提交清单 | 收束到 PPT、源码、视频、文档和 AI Coding 说明 |

## 3. PPT 主截图位

| PPT 页 | 截图组件 | 页面 |
| --- | --- | --- |
| 项目定位 | `competition-demo-dashboard` | `/demo` |
| 学习闭环 | `competition-loop-rail` | `/demo` |
| 讯飞能力链 | `competition-iflytek-strip` / `demo-runtime-iflytek` | `/demo` |
| 多智能体协作 | `agent-relay-theater` | `/chat` |
| 多模态资源 | `guide-multimodal-resource-studio` | `/guide` |
| 知识掌握地图 | `guide-knowledge-transit-map` | `/guide` |
| 动态评估 | `guide-path-adjustment-morph` | `/guide` |
| 证据可信度 | `rag-evidence-waterfall` | `/chat` 或知识库测试页 |

可运行截图脚本：

```powershell
cd web
$env:SCREENSHOT_ONLY="/demo"
npm.cmd run screenshots
```

会生成：

```text
web/screenshots-competition-demo.png
web/screenshots-competition-demo-mobile.png
```

## 4. 答辩问答锚点

**和普通大模型问答有什么区别？**

回答锚点：`/demo` 的学习闭环轨道和 `/guide` 的路线调整前后。

**多智能体是否真的参与？**

回答锚点：`agent-relay-theater`，展示画像、规划、检索、资源、评估的接力分工。

**讯飞能力具体用在哪里？**

回答锚点：`competition-iflytek-strip` 和 `demo-runtime-iflytek`，说明星火、Embedding、ONE SEARCH、OCR、TTS 对应的学习环节。

**学习效果评估是不是只是打分？**

回答锚点：`guide-path-adjustment-morph`，强调新证据会转成系统判断和下一步处方。

## 5. 兜底策略

- 后端未启动：使用 `/demo` 稳定演示包开场，避免录屏卡在接口加载。
- 模型生成慢：展示已生成的稳定资源和课程产出包。
- 外部搜索不可用：说明公开视频检索有可配置入口，先展示资源 Studio 的既有证据。
- 评委追问源码：指向 `ChatOrchestrator`、`ToolRegistry`、`CapabilityRegistry` 和 `sparkweave/plugins/` 的两层插件架构。

## 6. 录制前检查

```powershell
cd web
npm.cmd run lint
npm.cmd run build
npm.cmd run check:design
npm.cmd run check:api-contract
npm.cmd run check:replacement
```

黑盒检查：

```powershell
cd web
npm.cmd run test:e2e -- --grep "competition demo route"
```

正式提交包：

```powershell
python scripts/export_competition_package.py --output dist/competition_package --archive dist/sparkweave_competition_package.zip
python scripts/verify_competition_package.py dist/competition_package
python scripts/verify_competition_package.py dist/sparkweave_competition_package.zip
python scripts/check_competition_readiness.py --output dist/competition_readiness_latest.json
```
