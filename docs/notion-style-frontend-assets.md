# Notion 风前端素材调研清单

调研日期：2026-05-15

这份清单用于 SparkWeave 后续视觉优化。原则是：先保证比赛包可离线运行和授权清晰，再考虑是否足够像 Notion。

## 结论

优先级最高的是“本地自制 + CC0 辅助元素”。Notion-style 商业包可以作为风格参考或购买后用于最终产品，但不适合把原始素材大量打进提交包。免费聚合站和需要署名的平台只做灵感参考。

## 推荐素材池

| 来源 | 链接 | 类型 | 授权/限制 | SparkWeave 用法 |
| --- | --- | --- | --- | --- |
| ctrlv.design | https://ctrlv.design/ | SVG 插画库 | 页面标注 CC0，可商用、无需署名 | 优先候选。适合补充空状态、资料库、学习策略、数据图表类插画。只挑少量并统一改色。 |
| Highlights | https://www.highlights.design/ | 手绘高亮元素 | CC0，可商用、可修改 | 适合做 Notion 风标注线、圈注、箭头、下划线，不做主图。 |
| unDraw | https://undraw.co/license | SVG 插画库 | 可商用、无需署名；禁止打包成素材库、禁止 AI/ML 训练 | 可少量用于页面主图或 PPT，但不要批量 vendoring。最好二次改色、裁剪成产品场景。 |
| Lucide | https://github.com/lucide-icons/lucide | UI 图标 | ISC license | 已在项目中使用。继续作为按钮、状态、工具图标主来源。 |
| Notioly | https://notioly.com/terms-license/ | Notion-style 插画包 | 免费/付费下载后可用于 End Product；不可转售、托管或再分发原始素材 | 如果要最像 Notion，可购买或用免费包做少量页面插画。提交包中避免暴露成“素材库”。 |
| Overflow Design | https://www.overflow.design/ | Notion-style 图标/插画 | 有免费 starter 和付费包；可用于真实项目，完整条款需下载前确认 | 可作为图标和插画参考。若使用，必须记录具体 license 和下载来源。 |
| Nucleus UI Lite | https://www.nucleus-ui.com/ | Figma UI kit | 免费商用，禁止直接转售组件库 | 只做 UI 结构参考：表单、卡片、设置页、面板密度。不要直接照搬视觉。 |

## 不建议直接使用

| 来源 | 原因 |
| --- | --- |
| Notion 官方插图、图标、产品截图 | 品牌资产风险高，只做风格参考。 |
| Freepik / Storyset / Vecteezy / IconScout 免费资源 | 常见署名、账户、再分发限制；比赛包离线提交时容易解释不清。 |
| TitanUI 等聚合下载页 | 页面往往声明“不持有版权”，来源链不稳定。 |
| Open Peeps / DiceBear Peeps / Open Doodles 人物 | 授权可以，但人物造型不适合当前教育产品气质，已淘汰。 |
| AI 生成的“Notion-style”人物图 | 风格可控性和版权解释成本高，除非用于自制 bitmap 且保留生成说明。 |

## 推荐搜索关键词

用于继续搜图和挑主题：

- `notion style education illustration svg`
- `notion style classroom illustration`
- `notion style learning dashboard`
- `minimal education svg illustration commercial use`
- `course map svg illustration`
- `study notes svg illustration`
- `teacher whiteboard svg illustration`
- `student progress dashboard illustration`
- `knowledge base illustration svg`
- `ai tutor illustration svg`

## 落地规范

1. 第三方素材不能直接热链，必须本地化到 `web/public/illustrations/vendor/<source>/`。
2. 每个 vendor 目录必须带 `SOURCE.md`，记录下载 URL、下载日期、授权摘要和使用页面。
3. 每次最多引入 1-3 张同源素材，避免项目变成素材包分发。
4. SVG 需要统一颜色到 SparkWeave/Notion palette：`#37352f`、`#5645d4`、`#fef7d6`、`#dcecfa`、`#d9f3e1`、`#e6e0f5`、`#fde0ec`。
5. 删除脚本、外链字体、外链图片和不必要 metadata；保留必要 license 文件。
6. 页面使用前必须跑 `npm run build`、`npm run check:design`，并截图检查 `/guide`、`/memory`、`/vision`、`/co-writer`、`/agents`。

## 当前建议

短期继续以自制 SVG 为主，把 ctrlv 和 Highlights 当作可安全补充的素材池。若需要更明显的 Notion-style 人物/场景，可优先评估 Notioly，但购买或下载后只用于最终页面，不做公共素材库暴露。
