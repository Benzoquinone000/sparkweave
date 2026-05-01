# 运行时链路

本文档说明一次用户请求如何从 CLI 或 Web 前端进入后端，如何被转成 `UnifiedContext`，如何执行 LangGraph capability，并最终把事件、消息和记忆写回本地数据。SparkBot/Agents 的长期 Bot 实例不走这条 turn runtime，详见 [SparkBot 与 Agents 工作台](./sparkbot-agents.md)。

## 核心对象

| 对象 | 文件 | 作用 |
| --- | --- | --- |
| `TurnRequest` | `sparkweave/app/facade.py` | CLI/SDK 层稳定请求对象 |
| `SparkWeaveApp` | `sparkweave/app/facade.py` | 应用层 facade，统一操作 runtime、session、notebook |
| `RuntimeRoutingTurnManager` | `sparkweave/runtime/routing.py` | 根据 runtime 策略选择 LangGraph 或兼容运行时 |
| `LangGraphTurnRuntimeManager` | `sparkweave/runtime/turn_runtime.py` | 创建 session/turn、构造上下文、执行图、持久化事件 |
| `UnifiedContext` | `sparkweave/core/contracts.py` | capability 和 tool 处理一轮请求所需的统一上下文 |
| `StreamBus` | `sparkweave/core/contracts.py` | 单个 turn 内的异步事件 fan-out |
| `LangGraphRunner` | `sparkweave/runtime/runner.py` | 根据 `active_capability` 调用具体图 |
| `SQLiteSessionStore` | `sparkweave/services/session_store.py` | 会话、消息、turn、turn_events、题目本持久化 |

## WebSocket Turn

前端主聊天入口使用 `web/src/hooks/useChatRuntime.ts` 连接：

```text
ws://localhost:8001/api/v1/ws
```

发送消息：

```json
{
  "type": "start_turn",
  "content": "解释傅里叶变换",
  "capability": "chat",
  "tools": ["rag", "web_search"],
  "knowledge_bases": ["course-kb"],
  "language": "zh",
  "session_id": null,
  "config": {}
}
```

后端链路：

```text
unified_ws.py
  -> get_runtime_manager()
  -> RuntimeRoutingTurnManager.start_turn(payload)
  -> LangGraphTurnRuntimeManager.start_turn(payload)
  -> _prepare_turn()
  -> SQLiteSessionStore.create_session/create_turn
  -> background _run_prepared_turn()
  -> build_turn_context()
  -> LangGraphRunner.handle(context)
  -> concrete graph.run(context, stream)
  -> persist events to turn_events
  -> stream persisted events back to WebSocket subscriber
```

`unified_ws.py` 不直接执行业务逻辑，它只处理：

- `start_turn` / `message`：启动一个 turn。
- `subscribe_turn`：按 `turn_id` 订阅事件。
- `subscribe_session`：订阅当前 session 的活跃或最近 turn。
- `resume_from`：从指定 seq 继续订阅。
- `unsubscribe`：取消订阅。
- `cancel_turn`：取消正在运行的 turn。

## CLI Turn

CLI 单轮命令：

```powershell
sparkweave run chat "Explain Fourier transform" -t rag --kb course-kb
```

链路：

```text
sparkweave_cli/main.py
  -> build_turn_request()
  -> SparkWeaveApp.start_turn()
  -> SparkWeaveApp.stream_turn()
  -> RuntimeRoutingTurnManager
  -> LangGraphTurnRuntimeManager
  -> LangGraphRunner
```

交互式 CLI `sparkweave chat` 维护一个 `ChatState`，支持 `/tool`、`/cap`、`/kb`、`/history`、`/notebook`、`/config` 等命令。每次用户输入仍然会构造成 `TurnRequest`。

## Runtime 选择

选择逻辑在 `sparkweave/runtime/policy.py`。

优先级：

1. 请求显式指定 `runtime` 或 config 中的 `_runtime`。
2. 环境变量 `SPARKWEAVE_RUNTIME`。
3. 已迁移 capability 默认走 LangGraph。

已迁移的 LangGraph capability：

```text
chat
deep_question
deep_research
deep_solve
math_animator
visualize
```

可用值：

| 值 | 含义 |
| --- | --- |
| `langgraph` / `ng` | 强制使用 LangGraph |
| `auto` / `rollout` | 根据默认 allowlist 决定 |
| `compatibility` / `legacy` / `off` / `false` / `0` | 走兼容层，若兼容层不可用则回退 |

默认情况下，已迁移 capability 走 LangGraph。

## Context 构造

`build_turn_context()` 位于 `sparkweave/runtime/context_enrichment.py`，它把原始 payload 转成 `UnifiedContext`。

主要输入：

- `content`
- `capability`
- `tools`
- `knowledge_bases`
- `language`
- `config`
- `notebook_references`
- `history_references`
- `attachments`
- `session_id`

构造时会补充：

- 会话历史和压缩上下文，来自 `ContextBuilder`。
- 记忆上下文，来自 `MemoryService.build_memory_context()`。
- Notebook 引用上下文，来自 `NotebookAnalysisAgent`。
- 历史会话引用上下文。
- 附件对象列表。
- `turn_id`、runtime、conversation summary 等 metadata。

Notebook、Memory、历史引用和题目追问上下文的更细说明见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)。

如果 config 中有 `_persist_user_message=false`，则当前用户输入不会写入 messages 表。`followup_question_context` 会被转成 system message，用于题目追问场景。

## 事件协议

事件类型定义在 `StreamEventType`：

| 类型 | 说明 |
| --- | --- |
| `session` | 会话和 turn 建立 |
| `stage_start` / `stage_end` | 阶段开始和结束 |
| `thinking` | 中间推理、计划或 LLM 输出摘要 |
| `observation` | 校验、观察或评审结果 |
| `content` | 面向用户的正文增量或最终正文 |
| `tool_call` | 工具调用开始 |
| `tool_result` | 工具调用结果 |
| `progress` | 进度、状态、警告 |
| `sources` | 引用来源 |
| `result` | 结构化最终结果 |
| `error` | 错误 |
| `done` | turn 完成 |

持久化事件会被补充：

- `session_id`
- `turn_id`
- `seq`
- `timestamp`

前端 `useChatRuntime` 会把 `content` 累加到 assistant message，把 `result` 用作兜底最终文本，把 `done`、`result`、响应阶段结束视为完成信号。

工具事件的生成位置、`ToolResult` 结构和各 capability 的工具补参逻辑见 [Tools 工具系统](./tools.md)。

## Graph 执行

`LangGraphRunner` 根据 `context.active_capability` 分派：

| Capability | 图类 |
| --- | --- |
| `chat` | `ChatGraph` |
| `deep_solve` | `DeepSolveGraph` |
| `deep_question` | `DeepQuestionGraph` |
| `deep_research` | `DeepResearchGraph` |
| `visualize` | `VisualizeGraph` |
| `math_animator` | `MathAnimatorGraph` |

每个图都会通过 `context_to_state()` 转成 `TutorState`，然后执行 LangGraph 节点。节点只通过 `StreamBus` 输出用户可见进度和结果。

各图的配置、阶段语义和结果结构见 [Capabilities 详解](./capabilities.md)。

## Chat 自动委派

`ChatGraph` 是默认能力，但它内置了对话协调器：

- 检测动画、出题、可视化、研究、解题等关键词。
- 若命中，会把请求委派给 specialist capability。
- 委派时会设置 `delegated_by_coordinator`，避免重复委派。
- 可通过 `auto_delegate=false` 或 `delegate_capability` 控制。

这意味着前端选择 `chat` 时，也可能收到 `deep_solve`、`deep_question` 等能力的阶段事件。

## 持久化与记忆

`LangGraphTurnRuntimeManager` 在执行期间会：

1. 创建或复用 session。
2. 创建 turn。
3. 把用户消息写入 `messages`。
4. 把每个事件写入 `turn_events`。
5. 根据 `content` 或 `result` 提取 assistant 内容。
6. 把 assistant message 写入 `messages`。
7. 将 turn 状态标记为 `completed`、`failed` 或 `cancelled`。
8. 调用 `MemoryService.refresh_from_turn()` 更新 `SUMMARY.md` 和 `PROFILE.md`。

SQLite 表位于 `data/user/chat_history.db`，主要包括：

- `sessions`
- `messages`
- `turns`
- `turn_events`
- `notebook_entries`
- `notebook_categories`
- `notebook_entry_categories`

SQLite 表结构、`messages` 与 `turn_events` 的分工、断线续流和取消语义见 [会话、Turn 与事件持久化](./sessions-and-turns.md)。

## 取消与恢复

`cancel_turn` 会取消当前进程内活跃 task；若 task 不在当前进程但 turn 仍是 running，会写入 detached cancel 事件。

`resume_from` 和 `subscribe_turn(after_seq)` 支持从已持久化事件继续读取，再接上活跃 turn 的实时队列。因此 WebSocket 中断后，前端可以用最后看到的 `seq` 续流。
