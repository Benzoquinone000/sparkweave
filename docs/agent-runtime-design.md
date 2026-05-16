# Agent 运行时与多智能体调度设计

本文只记录当前代码已经实现的 Agent 运行时设计，重点说明一次用户请求如何被构造成上下文、如何进入 LangGraph 能力图、何时由对话协调智能体唤醒专门智能体，以及哪些说法不能在简历和答辩中夸大。

## 一句话定位

SparkWeave 不是“完全自由游走”的多智能体系统，而是一个**统一 turn runtime + 受控对话协调器 + 多个专门能力图 + 工具层 + 事件持久化**的多智能体学习工作台。

这个设计更适合面向用户的教育产品：默认路径稳定、可追踪、可恢复；复杂请求才会被委派给专门能力，避免每轮对话都变成不可控的 Agent swarm。

```text
Web / CLI / Python facade
  -> LangGraphTurnRuntimeManager
  -> build_turn_context
  -> LangGraphRunner
     -> ChatGraph
        -> 对话协调智能体
        -> 默认 Chat Agent / Specialist Graph
        -> Tools
  -> StreamBus events
  -> SQLite turn_events
  -> assistant message
  -> best-effort Memory refresh
```

## 代码地图

| 层级 | 关键文件 | 已实现事实 |
| --- | --- | --- |
| Capability 注册 | `sparkweave/app/facade.py` | 暴露内置 capability、阶段、工具和 CLI alias |
| Turn 运行时 | `sparkweave/runtime/turn_runtime.py` | 创建 turn、订阅事件、运行后台任务、持久化事件、写 assistant message、刷新 Memory |
| 上下文构造 | `sparkweave/runtime/context_enrichment.py` | 合并会话历史、Memory、学习画像、Notebook/历史引用、附件与低置信度学习证据 |
| 能力分派 | `sparkweave/runtime/runner.py` | 只分派已迁移的 LangGraph capability |
| 对话协调 | `sparkweave/graphs/chat.py` | 规则/配置驱动地决定是否委派 specialist，并把协作路线写入事件 metadata |
| 专门能力图 | `sparkweave/graphs/deep_solve.py`、`sparkweave/graphs/deep_question.py`、`sparkweave/graphs/deep_research.py`、`sparkweave/graphs/visualize.py`、`sparkweave/graphs/math_animator.py` | 分别承载解题、出题、调研、可视化、数学动画能力 |
| 工具系统 | `sparkweave/tools/registry.py`、`sparkweave/tools/builtin.py` | Chat Agent 可绑定工具并并发执行工具调用 |

## Turn 生命周期

一次前端 WebSocket 或 CLI 调用最终进入 `LangGraphTurnRuntimeManager.start_turn()`。

1. `_prepare_turn()` 解析 session、capability、用户消息、配置覆盖项和附件。
2. `_run_prepared_turn()` 持久化 session 事件，调用 `build_turn_context()` 生成 `UnifiedContext`。
3. `build_turn_context()` 注入历史摘要、Memory、学习画像、Notebook/历史引用和附件。
4. `LangGraphRunner.handle()` 根据 `active_capability` 分派到对应能力图。
5. 能力图通过 `StreamBus` 输出 stage、progress、content、result、error 等事件。
6. runtime 持久化事件，生成 assistant message。
7. 回合结束后，runtime 通过 `MemoryService.refresh_from_turn()` 尝试更新长期 Memory。

这个链路的优势是：前端断线后可以从持久化事件回放；一次 turn 的状态、结果、工具调用和多智能体协作路线都可被追踪。

## 已迁移的能力图

`LangGraphRunner.supported_capabilities` 当前包含：

| Capability | 用户侧作用 | 主要实现 |
| --- | --- | --- |
| `chat` | 默认对话、工具调用、智能体协调 | `sparkweave/graphs/chat.py` |
| `deep_solve` | 解题、推导、验证、分步讲解 | `sparkweave/graphs/deep_solve.py` |
| `deep_question` | 题目生成、仿题、多题型练习 | `sparkweave/graphs/deep_question.py` |
| `deep_research` | 调研、资源组织、学习路径/报告 | `sparkweave/graphs/deep_research.py` |
| `visualize` | SVG、Mermaid、Chart.js 等图解产物 | `sparkweave/graphs/visualize.py` |
| `math_animator` | Manim 数学动画代码、渲染产物和讲解稿 | `sparkweave/graphs/math_animator.py` |

如果传入未迁移 capability，`LangGraphRunner` 会返回 `LangGraph runtime has not migrated capability ... yet.`。因此当前不能描述为“任意智能体能力都已经完成迁移”。

## 对话协调智能体

`ChatGraph` 中的对话协调器负责判断当前请求是留在默认 Chat Agent，还是唤醒专门能力图。

### 可委派目标

当前可被 coordinator 委派的 capability 来自 `DELEGABLE_CAPABILITIES`：

```python
{"deep_question", "deep_research", "deep_solve", "math_animator", "visualize"}
```

`external_video_search` 现在是工具路径，不是 LangGraph specialist capability。代码中会走 `_run_external_video_tool()`，而不是 `LangGraphRunner` 的 capability 分派。

### 决策策略

`_decide_specialist()` 当前采用“配置优先 + 关键词/模式识别 + 画像引导”的轻量策略：

| 优先级 | 规则 |
| --- | --- |
| 关闭自动委派 | `auto_delegate=false` 时留在默认 chat |
| 防递归 | `delegated_by_coordinator` 存在时不再二次委派 |
| 强制委派 | `delegate_capability` / `coordinator_capability` 指定目标 |
| 直答请求 | 出现“不用展开、直接回答”等 no-delegate 语义时留在 chat |
| 精选视频 | 视频检索类请求走 `external_video_search` 工具 |
| 动画讲解 | 动画/视频式讲解请求委派 `math_animator` |
| 出题练习 | 题目/练习/测验请求委派 `deep_question` |
| 图解可视化 | 画图、知识图谱、流程图请求委派 `visualize` |
| 调研规划 | 调研、学习路线、资源组织请求委派 `deep_research` |
| 解题推导 | 解题、证明、推导请求委派 `deep_solve` |
| 画像引导 | 若用户意图和画像下一步行动匹配，可生成 profile-guided decision |

这是一种工程上更稳的设计：先用明确规则覆盖高频教育场景，再把模型生成留给具体能力图处理。

## 多智能体协作可视化事件

协调器会向事件流写入 `trace_kind=coordinator_decision` 和 `trace_kind=agent_handoff`。

事件 metadata 中包含：

| 字段 | 含义 |
| --- | --- |
| `capability` | 本轮选择的目标能力 |
| `confidence` | 规则决策置信度 |
| `reason` | 为什么选择该能力 |
| `delegated` | 是否真的委派 |
| `agent_cluster` | 展示给前端的智能体簇名称 |
| `collaboration_route` | 前端可视化协作路线 |
| `collaboration_summary` | 协作过程摘要 |
| `profile_hints_applied` | 是否使用学习画像提示 |
| `rewritten_prompt` | coordinator 为 specialist 重写的任务提示 |

`_collaboration_route()` 会把协作过程组织成最多 6 个节点。若本轮有画像提示，路线会先出现“学习画像智能体”，再进入“对话协调智能体”和目标 specialist 内部角色。

## Chat Agent 工具调用

默认 Chat Agent 是一个 LangGraph 状态图：

```text
START -> agent -> tools? -> agent -> respond -> END
```

关键约束：

| 约束 | 代码事实 |
| --- | --- |
| 最大工具轮次 | `ChatGraph(max_tool_rounds=3)` |
| 单轮并发工具上限 | `MAX_PARALLEL_TOOL_CALLS = 8` |
| 无知识库时禁用 RAG | `_enabled_tools()` 会在无 KB 时移除 `rag` 工具 |
| RAG 工具可观测 | `_retrieve_metadata()` 为 RAG 工具调用附加 `trace_role=retrieve`、query、session、turn 等 metadata |
| 工具事件 | tool_call、progress、tool_result 都进入事件流 |

这使得工具调用既能并发，又不会无限循环；前端也能展示“正在检索”“检索完成”“工具结果”等过程。

## Specialist 委派边界

`_run_specialist()` 会构造一个新的 `UnifiedContext`：

- `active_capability` 改为目标 capability。
- 合并 coordinator 生成的配置。
- 移除 `auto_delegate`、`delegate_capability`、`coordinator_capability`，避免 specialist 再被二次委派。
- 写入 `metadata.delegated_by_coordinator = "chat"`。
- 写入 `metadata.coordinator_decision`，方便后续追踪。

当前是一跳式委派，而不是深层递归 Agent 网络。这是故意的：教育应用需要稳定响应和清晰可解释的过程。

## 可以写进简历的准确表述

可以写：

- 设计并实现统一 LangGraph turn runtime，支持多能力图分派、事件持久化、断线回放和 turn 后长期记忆刷新。
- 实现受控多智能体协调器，基于配置、意图规则和学习画像提示，将用户请求委派到解题、出题、调研、可视化、数学动画等专门能力图。
- 为多智能体协作过程设计可观测事件 metadata，使前端能展示 coordinator decision、agent handoff、协作路线和工具调用轨迹。

不要写：

- “实现完全自主的开放式 Agent swarm。”
- “所有能力都已迁移到 LangGraph。”
- “外部视频检索是独立 specialist capability。”当前它是工具路径。
- “智能体会无限递归协作。”当前是受控一跳委派。

## 后续优化方向

1. 把 `_decide_specialist()` 从关键词规则升级为“规则先验 + 小模型分类 + 可解释置信度”的混合路由。
2. 给每个 specialist 输出统一的 `agent_trace` schema，减少前端对不同 result payload 的适配成本。
3. 将工具调用风险分级，例如资料检索、文件写入、渲染、外部网络访问分别有不同超时和降级策略。
4. 将 coordinator decision 纳入离线评测集，用真实用户 query 计算路由准确率、误委派率和人工修正率。
