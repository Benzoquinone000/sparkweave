# 前端工作台

SparkWeave 前端位于 `web/`，使用 Vite、React、TypeScript、TanStack Router、TanStack Query 和 Tailwind CSS。

## 启动与构建

```powershell
cd web
npm install
npm run dev
npm run build
```

常用脚本：

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动开发服务器 |
| `npm run build` | TypeScript build + Vite build |
| `npm run preview` | 预览构建结果 |
| `npm run lint` | ESLint |
| `npm run check:api-contract` | 运行后端 API 契约检查 |
| `npm run check:replacement` | 检查 NG 替换状态 |
| `npm run smoke:runtime` | 运行 NG runtime smoke |
| `npm run test:e2e` | Playwright e2e |
| `npm run verify` | 前端综合验证脚本 |

## 入口文件

| 文件 | 说明 |
| --- | --- |
| `web/src/main.tsx` | React 入口 |
| `web/src/router.tsx` | TanStack Router 路由表 |
| `web/src/routerPages.tsx` | 页面 lazy import |
| `web/src/styles/index.css` | 全局样式 |
| `web/src/lib/api.ts` | API 客户端和 URL 解析 |
| `web/src/lib/types.ts` | 前后端共享契约类型 |
| `web/src/lib/capabilities.ts` | capability 列表、默认工具、默认配置 |
| `web/src/hooks/useChatRuntime.ts` | 主聊天 WebSocket runtime hook |
| `web/src/hooks/useApiQueries.ts` | React Query hooks |

## 路由

主路由在 `web/src/router.tsx`。

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/` | redirect | 默认跳转 `/chat`，若存在 `?session=` 则跳转对应会话 |
| `/chat` | `ChatPage` | 主学习工作台 |
| `/chat/$sessionId` | `ChatPage` | 恢复指定会话 |
| `/question` | `QuestionLabPage` | 独立题目生成页面 |
| `/vision` | `VisionPage` | 图像题解析和 GeoGebra 分析 |
| `/knowledge` | `KnowledgePage` | 知识库管理 |
| `/notebook` | `NotebookPage` | Notebook 与题目本 |
| `/memory` | `MemoryPage` | 学习摘要和用户画像 |
| `/playground` | `PlaygroundPage` | 工具、能力、插件调试；保留直达路由，不放入默认导航 |
| `/guide` | `GuidePage` | 导学空间 |
| `/co-writer` | `CoWriterPage` | 协作写作 |
| `/agents` | `AgentsPage` | SparkBot 管理 |
| `/agents/$botId/chat` | `AgentsPage` | SparkBot 聊天 |
| `/settings` | `SettingsPage` | 模型、搜索、界面、系统检测 |

兼容重定向：

| 旧路由 | 新路由 |
| --- | --- |
| `/solver` | `/chat?capability=deep_solve` |
| `/research` | `/chat?capability=deep_research` |
| `/visualize` | `/chat?capability=visualize` |
| `/math_animator`、`/math-animator` | `/chat?capability=math_animator` |
| `/co_writer`、`/cowriter` | `/co-writer` |
| `/sparkbot` | `/agents` |
| `/sparkbot/$botId/chat` | `/agents/$botId/chat` |
| `/utility/knowledge` | `/knowledge` |
| `/utility/memory` | `/memory` |
| `/utility/notebook` | `/notebook` |
| `/utility/settings` | `/settings` |

## API 客户端

`web/src/lib/api.ts` 负责：

- 解析后端 base URL。
- 构造 HTTP URL、WebSocket URL。
- 封装 `fetchJson()`。
- 封装 SSE 读取 `readSseResponse()`。
- 暴露各页面使用的 API 函数。

后端地址优先级：

1. `window.__SPARKWEAVE_RUNTIME_CONFIG__?.apiBase`
2. `VITE_API_BASE`
3. `NEXT_PUBLIC_API_BASE_EXTERNAL`
4. `NEXT_PUBLIC_API_BASE`
5. 当前浏览器 hostname + 默认后端端口 `8001`

WebSocket URL 会把 `http` 转成 `ws`，`https` 转成 `wss`。

## 主聊天运行时

主工作台使用 `useChatRuntime()`：

```text
web/src/hooks/useChatRuntime.ts
```

发送 turn 时，hook 会：

1. 创建本地 user message 和空 assistant message。
2. 连接 `/api/v1/ws`。
3. 在 `onopen` 后发送 `start_turn`。
4. 持续接收 `StreamEvent`。
5. 把 `content` 事件累加为 assistant 文本。
6. 根据 `session_id` 和 `turn_id` 更新当前会话。
7. 遇到 `done`、`error` 或响应阶段结束后关闭 socket。

发送 payload 形状：

```json
{
  "type": "start_turn",
  "content": "...",
  "capability": "chat",
  "tools": ["rag", "web_search"],
  "knowledge_bases": [],
  "notebook_references": [],
  "history_references": [],
  "attachments": [],
  "language": "zh",
  "session_id": "...",
  "config": {}
}
```

## Capability 与工具默认值

前端定义在 `web/src/lib/capabilities.ts`。

| Capability | 默认工具 | 默认配置 |
| --- | --- | --- |
| `chat` | `rag`、`web_search`、`paper_search`、`code_execution`、`reason` | `{}` |
| `deep_solve` | `rag`、`web_search`、`code_execution`、`reason` | `{ detailed_answer: true }` |
| `deep_question` | `rag`、`web_search`、`code_execution` | `mode=custom`、`num_questions=5` |
| `deep_research` | `rag`、`web_search`、`paper_search`、`code_execution` | `mode=report`、`depth=standard`、`sources=["web"]` |
| `visualize` | 无 | `render_mode=auto` |
| `math_animator` | 无 | `output_mode=video`、`quality=medium`、`max_retries=4` |

注意：后端配置校验在 `sparkweave/services/validation.py`，前端默认配置应与后端 Pydantic schema 保持一致。工具开关和默认工具与后端 ToolRegistry 的关系见 [Tools 工具系统](./tools.md)。
详细字段和结果结构见 [Capabilities 详解](./capabilities.md)。
WebSocket 事件、`seq` 续流、历史消息 hydrate 和 session detail 的关系见 [会话、Turn 与事件持久化](./sessions-and-turns.md)。

## 页面与后端能力

| 页面 | 主要后端入口 |
| --- | --- |
| Chat | `/api/v1/ws`、`/api/v1/sessions`、Notebook API |
| Knowledge | `/api/v1/knowledge/*`、知识库进度 WebSocket、SSE task stream |
| Notebook | `/api/v1/notebook/*`、`/api/v1/question-notebook/*` |
| Settings | `/api/v1/settings/*`、`/api/v1/system/*` |
| Agents | `/api/v1/sparkbot/*`、SparkBot WebSocket、`/api/v1/agent-config/*` |
| Guide | `/api/v1/guide/*`、Guide WebSocket |
| Co-Writer | `/api/v1/co_writer/*`、SSE stream |
| Vision | `/api/v1/vision/analyze`、`/api/v1/vision/solve` |
| Playground | `/api/v1/plugins/*` |

NotebookPage、MemoryPage、Chat 引用面板与后端上下文注入的完整契约见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)。
GuidePage 的学习路径驾驶舱、资源 job、题目本/Notebook 保存和查询缓存约定见 [导学空间与 Guide V2](./guided-learning.md)。
AgentsPage 的 SparkBot 生命周期、渠道 schema、工作区文件、聊天 WebSocket 和缓存失效约定见 [SparkBot 与 Agents 工作台](./sparkbot-agents.md)。

## 前后端契约

设置页表单如何写入 catalog、如何触发 `/settings/apply`，见 [设置与 Provider 配置](./settings-and-providers.md)。

关键契约文件：

- 前端类型：`web/src/lib/types.ts`
- 后端事件：`sparkweave/core/contracts.py`
- 后端 capability config：`sparkweave/services/validation.py`
- API 契约检查：`scripts/check_web_api_contract.py`

涉及 API 字段、事件类型、capability 配置、页面路由时，应同时检查这些文件。
