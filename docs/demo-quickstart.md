# 演示者 5 分钟入口

这份文档只服务一件事：正式录屏或答辩前，让演示者快速确认“我现在该点哪里、讲什么、坏了怎么办”。

## 先跑一个检查

在项目根目录执行：

```powershell
python -m sparkweave_cli competition-check
```

看到 `All required competition materials are ready.` 后再开始录屏。

需要把检查结果交给 CI、前端或答辩材料归档时，可以生成结构化报告：

```powershell
python -m sparkweave_cli competition-check --format json --output dist/competition-readiness.json
```

## 录屏只走五步

1. 打开 `http://localhost:3782/guide`
   点击“开始稳定演示”或选择“大模型教育智能体系统开发”赛题主线课程。

2. 讲“当前只做这一件事”
   不展示所有工具，只讲当前任务、为什么先做它、做完去哪里提交。

3. 生成一个资源
   优先演示图解、互动练习或精选公开视频。视频生成慢时，不要等，直接展示课程产出包里的兜底材料。

4. 提交一次反馈
   输入掌握分和一句反思，让系统生成对错反馈、学习处方和下一步建议。

5. 打开课程产出包
   展示“赛题五项对齐”“7 分钟录屏讲稿”“答辩问答预案”“比赛提交清单”。

## 讲述主线

一句话版本：

> SparkWeave 先理解学生画像，再规划学习路径，再由多个智能体生成资源，最后根据练习和反思动态调整下一步。

对应赛题五项：

| 赛题要求 | 演示时指向哪里 |
| --- | --- |
| 对话式学习画像自主构建 | 学习画像中心、当前任务理由、画像驱动说明 |
| 多智能体协同资源生成 | 资源卡片里的智能体接力、Chat 协作明细 |
| 个性化学习路径规划和资源推送 | `/guide` 当前任务、补基任务、下一步建议 |
| 智能辅导 | 图解、Manim 短视频、精选公开视频、互动练习 |
| 学习效果评估 | 提交反馈、学习报告、学习处方、课程产出包 |

## 现场兜底

| 问题 | 处理 |
| --- | --- |
| 模型响应慢 | 使用稳定演示课程里的示例任务和兜底材料 |
| Manim 视频慢 | 展示图解、Manim 脚本结构或历史产物 |
| 搜索服务不稳定 | 使用精选视频的搜索入口卡片，继续回到导学闭环 |
| 页面太多 | 只停留在 `/guide`、提交页、课程产出包三处 |
| 时间不够 | 跳过 Chat，直接从导学稳定演示入口开始 |

## 赛后整理

导出或检查这些材料：

- `dist/demo_materials/sparkweave-demo-deck.html`
- `dist/demo_materials/sparkweave-demo-deck-outline.md`
- `dist/demo_materials/sparkweave-7min-recording-script.md`
- `dist/demo_materials/sparkweave-agent-collaboration-blueprint.md`
- `dist/demo_materials/sparkweave-demo-fallback-assets.md`
- `dist/demo_materials/sparkweave-competition-scorecard.md`
- `dist/demo_materials/sparkweave-evaluator-one-pager.md`
- `dist/demo_materials/sparkweave-defense-qa.md`
- `dist/demo_materials/sparkweave-final-pitch-checklist.md`
- `dist/competition_package/submission_manifest.md`

需要重新生成时：

```powershell
python -m sparkweave_cli competition-demo
python -m sparkweave_cli competition-package
```

赛前最后一次打包可以直接用：

```powershell
python -m sparkweave_cli competition-preflight --report dist/competition-readiness.json
```

要为其它完整课程生成演示包，可以指定课程模板：

```powershell
python -m sparkweave_cli competition-package --template higher_math_limits_derivatives
```
