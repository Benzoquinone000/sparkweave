# SparkWeave 前端设计规范

范围：面向 SparkWeave 前端功能开发、页面重构和视觉复核。本文档记录当前前端信息架构、组件职责、视觉约束和检查脚本；不把未实现的交互写成当前能力。

目标不是展示工程能力，而是让真实学习用户在进入页面后立刻知道下一步该做什么。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| 导航与入口 | `web/src/lib/navigation.ts`, `web/src/components/layout/AppShell*.tsx` |
| 页面实现 | `web/src/pages/GuidePage.tsx`, `web/src/pages/KnowledgePage.tsx`, `web/src/pages/NotebookPage.tsx`, `web/src/pages/SettingsPage.tsx` |
| 输入框 | `web/src/components/chat/Composer.tsx`, `web/src/components/ui/Field.tsx` |
| 结果渲染 | `web/src/components/results/`, `web/src/components/chat/MessageBubble.tsx` |
| 视觉动效 | `web/src/components/visual/`, `web/src/styles/index.css` |
| 设计检查 | `web/scripts/check-design.mjs`, `web/package.json` |
| 截图复核 | `web/scripts/capture-screenshots.mjs`, `web/tests/e2e/` |

## 1. 设计目标

SparkWeave 前端采用学习任务优先的信息架构。页面应保持 Notion 风的简约、低噪声、少层级，避免把 Agent、RAG、画像、诊断、演示等内部能力直接堆给用户。

前端设计必须满足三点：

- 用户能在首屏看到一个明确主动作。
- 工程能力可以被解释为学习行为，例如查资料、继续学习、保存记录、检查设置。
- 视觉效果服务状态反馈，不制造晃眼、抢注意力或难以长期使用的动画。

## 2. 信息架构

一级导航只保留稳定用户任务：

| 入口 | 用户任务 | 代码位置 |
| --- | --- | --- |
| 学习 | 继续学习、生成路径、完成任务、提交反馈 | `web/src/pages/guide/`, `web/src/pages/GuidePage.tsx` |
| 资料 | 上传资料、管理资料库、问资料 | `web/src/pages/knowledge/`, `web/src/pages/KnowledgePage.tsx` |
| 记录 | 保存问答、错题、复盘和学习成果 | `web/src/pages/notebook/`, `web/src/pages/NotebookPage.tsx` |
| 设置 | 配置模型、检索、OCR、语音和工作台偏好 | `web/src/pages/settings/`, `web/src/pages/SettingsPage.tsx` |

高级入口统一收进“更多工具”或页面内部二级入口：

| 能力 | 对外表达 | 入口原则 |
| --- | --- | --- |
| Agent 编排 | 学习流程、步骤接续 | 默认不作为一级入口 |
| RAG / Agentic RAG | 查资料、资料来源检查 | 放在资料页工作区 |
| 学习画像 | 学习记录、学习状态 | 放在记录或更多工具 |
| 诊断 / 评测 | 检查连接、资料体检 | 作为异常处理和高级检查 |
| 演示 / Playground | 演示工作台 | 只面向开发或答辩准备 |

导航定义优先维护在 `web/src/lib/navigation.ts`，布局容器维护在 `web/src/components/layout/`。

## 3. 页面结构

每个页面优先围绕一个主动作组织：

| 页面类型 | 主动作示例 | 空状态要求 |
| --- | --- | --- |
| 学习页 | 继续当前学习或创建学习路径 | 说明可输入学习目标，并给出课程模板 |
| 资料页 | 上传资料或选择资料库提问 | 说明先放入资料，再开始问资料 |
| 记录页 | 查看最近记录或保存新结果 | 说明记录会来自问答、练习和复盘 |
| 设置页 | 选择供应商预设并检查状态 | 说明缺少哪些配置，不展示真实密钥 |

页面内部可以有多个面板，但必须有清晰主次。不要把“创建、诊断、日志、设置、评测”同时摆成同等权重入口。

## 4. 组件职责

| 目录 | 职责 |
| --- | --- |
| `web/src/components/ui/` | 通用按钮、徽标、表单壳、状态提示等基础组件 |
| `web/src/components/layout/` | 桌面与移动端应用框架、导航和更多工具面板 |
| `web/src/components/chat/` | 输入框、消息气泡、资料选择、协作流程展示 |
| `web/src/components/results/` | 后端工具结果、证据、视频、图片、代码、动画等结果渲染 |
| `web/src/components/visual/` | 轻量视觉背景、状态动效和可视化效果 |
| `web/src/pages/<feature>/` | 页面级业务模块，不沉淀通用 UI |

新增组件时先判断是否可复用。只能被一个页面使用、且强依赖业务数据的组件，应放在对应 `pages/<feature>/` 下。

## 5. 视觉规则

### 5.1 圆角与层级

- 卡片、按钮、输入框、弹窗、浮层圆角不超过 8px。
- 禁止使用 `rounded-full` 作为常规视觉语言。
- 不使用卡片套卡片，不把整段页面区域做成漂浮卡片。
- 页面 section 应是无框布局或全宽分区，卡片只用于重复项、弹窗和真正需要框定的工具。

### 5.2 颜色与密度

- 避免单一色系铺满页面，尤其避免大面积紫蓝渐变、深蓝灰、米色或棕橙色。
- 文本、边框和背景保持低对比但可读；重要状态用小面积强调色。
- 导航、小标签、快捷操作的小色块使用 `web/tailwind.config.js` 中的 `accent` 语义色板；不要在组件里散落新的十六进制颜色。
- 页面默认偏紧凑，优先让学习内容、资料来源和用户输入占据空间。
- 图像、可视化和装饰不能压缩主要阅读区域。

### 5.3 文本与按钮

- 按钮文案必须对应明确动作，例如“继续学习”“上传资料”“开始试问”。
- 能用图标表达的工具按钮优先使用 lucide 图标，并补充 `title` 或可访问标签。
- 页面文案面向学习用户，不默认展示内部工程术语。
- 文本必须在移动端和桌面端都不溢出、不遮挡、不挤压主内容。

## 6. 表单与输入框

输入区域应轻巧、可持续使用：

- 单行问题输入默认使用紧凑高度，长文本再自适应增高。
- 聊天或问资料输入支持 `Enter` 提交，`Shift + Enter` 换行。
- 长文本编辑器必须有最大高度，避免占满首屏。
- 标签说明只写必要上下文，不写功能介绍式长段落。
- 错误提示要给出下一步，例如检查配置、换资料库、重试整理。

聊天输入组件维护在 `web/src/components/chat/Composer.tsx`；通用表单样式集中在 `web/src/styles/index.css` 和 `web/src/components/ui/`。

## 7. 动效规范

动效只用于状态反馈、空间过渡和轻量氛围，不用于持续抢注意力。

允许：

- 输入框聚焦、按钮 hover、面板切换等短反馈。
- 低强度背景光场或渐变，但不能影响阅读。
- 进度、检索、生成中的轻量状态动画。
- 尊重 `prefers-reduced-motion` 的降级效果。

禁止：

- 鼠标跟随背景。
- 强波纹、强闪烁、强粒子密集运动。
- 页面全局持续大幅移动背景。
- 因动画导致滚动、文字或按钮位置抖动。

视觉动效组件维护在 `web/src/components/visual/`。修改后必须在真实页面确认首屏不晃眼、不遮挡、不干扰阅读。

## 8. 响应式规则

- 移动端保持同一主动作，不把主任务藏到深层菜单。
- 固定格式元素要有稳定尺寸，例如棋盘、图表、工具栏、按钮组和计数器。
- 不使用视口宽度直接缩放字体。
- 侧边栏折叠后仍能识别当前任务和返回路径。
- 宽屏下可以提高信息密度，但不要同时展示过多低优先级面板。

## 9. 截图与视觉复核

改动主页面、布局、主题、动效或截图内容后，需要重新生成截图：

```powershell
cd web
npm run screenshots
```

前端提交前至少运行：

```powershell
cd web
npm run lint
npm run check:design
npm run check:api-contract
npm run build
```

设计检查脚本维护在 `web/scripts/check-design.mjs`。如果脚本报错，优先修正页面，而不是绕过规则。

## 10. 前端改动清单

- [ ] 新入口服务“学习、资料、记录、设置”中的至少一条用户路径。
- [ ] 首屏只有一个主要动作，其余入口有明确主次。
- [ ] 空状态告诉用户下一步怎么做。
- [ ] 无 `rounded-full`、过度圆角、卡片套卡片和强装饰背景。
- [ ] 动画不跟随鼠标、不强波纹、不影响长时间阅读。
- [ ] 输入框大小合理，并支持预期键盘行为。
- [ ] 移动端文本、按钮和可视化不溢出、不重叠。
- [ ] `npm run lint`、`npm run check:design`、`npm run build` 已通过。

## 11. 测试与检查来源

| 检查 | 覆盖 |
| --- | --- |
| `npm run lint` | React Hooks、TypeScript/ESLint 规则 |
| `npm run check:design` | 圆角、强动效、文本溢出等视觉合约 |
| `npm run check:api-contract` | 前端 API 路径与后端路由匹配 |
| `npm run build` | TypeScript 构建和 Vite 构建 |
| `npm run screenshots` | 主要页面截图回归 |
| `npm run test:e2e` | Playwright 用户路径 smoke |

## 12. 限制与待实现

- 设计合约脚本能拦截常见 CSS 类和文本溢出风险，但不能替代真实浏览器截图复核。
- 动效是否“晃眼”需要在桌面和移动端实际页面中检查；脚本只提供底线。
- 新增页面如果绕开 `web/src/lib/navigation.ts` 或通用布局组件，需要单独说明入口原因。
