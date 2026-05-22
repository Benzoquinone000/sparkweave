# SparkWeave 智能体编排设计

范围：记录当前 Agent Runtime、Tool、Capability、Graph 和事件流实现。本文档只描述代码中已经存在的行为；未落地能力统一放到“限制与待实现”，不写成当前能力。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| 统一入口 | `sparkweave/app/facade.py`, `sparkweave/runtime/orchestrator.py`, `sparkweave/runtime/routing.py` |
| Turn Runtime | `sparkweave/runtime/turn_runtime.py`, `sparkweave/runtime/context_enrichment.py`, `sparkweave/runtime/runner.py` |
| Capability 路由 | `sparkweave/runtime/capability_router.py`, `sparkweave/graphs/chat.py` |
| Tool 层 | `sparkweave/tools/registry.py`, `sparkweave/tools/builtin.py`, `sparkweave/runtime/tool_execution.py` |
| Graph 能力 | `sparkweave/graphs/deep_solve.py`, `sparkweave/graphs/deep_question.py`, `sparkweave/graphs/deep_research.py`, `sparkweave/graphs/visualize.py`, `sparkweave/graphs/math_animator.py` |
| 插件发现 | `sparkweave/plugins/loader.py`, `sparkweave/runtime/registry/capability_registry.py` |
| 前端消费 | `web/src/hooks/useChatRuntime.ts`, `web/src/components/chat/AgentCollaborationPanel.tsx`, `web/src/lib/capabilities.ts` |

## 1. 定位

SparkWeave 的智能体编排核心是：

```text
Tool + Capability 双层架构
  + 统一 Orchestrator
  + Turn Runtime
  + StreamEvent 可观测事件流
```

目标不是把所有能力堆成一个工具列表，而是把一次学习请求路由到合适的学习智能体，由专业流程调用轻量工具，最后以可追踪事件流返回给前端。

主链路：

```text
CLI / WebSocket / Python SDK
  -> SparkWeaveApp / ChatOrchestrator
  -> RuntimeRoutingTurnManager
  -> LangGraphTurnRuntimeManager
  -> build_turn_context
  -> LangGraphRunner
  -> ChatGraph coordinator
  -> Capability Graph / Tool calls
  -> StreamEvent 持久化、订阅、重放
```

![SparkWeave Agent 总体架构与主链路](assets/agent-orchestration-overview.png)

## 2. 代码落点

| 模块 | 职责 |
| --- | --- |
| `sparkweave/app/facade.py` | SDK / CLI 门面，定义 `TurnRequest` 和 capability contract |
| `sparkweave/runtime/routing.py` | 选择 LangGraph 主运行时或兼容运行时 |
| `sparkweave/runtime/turn_runtime.py` | turn 创建、事件持久化、订阅、取消、归档 |
| `sparkweave/runtime/context_enrichment.py` | 构造 `UnifiedContext`，注入学习上下文 |
| `sparkweave/runtime/runner.py` | 根据 `active_capability` 调用具体 graph |
| `sparkweave/runtime/capability_router.py` | 学习任务路由策略，输出 `CoordinatorDecision` |
| `sparkweave/runtime/tool_execution.py` | 统一工具执行、事件输出和 `ToolResult` 标准化 |
| `sparkweave/runtime/orchestrator.py` | 兼容入口：`UnifiedContext -> StreamEvent` |
| `sparkweave/graphs/chat.py` | 默认聊天能力，也是学习智能体协调器 |
| `sparkweave/graphs/deep_*.py`、`visualize.py`、`math_animator.py` | 专业 Capability Graph |
| `sparkweave/tools/registry.py` | 工具注册、别名、schema、LangChain 适配 |
| `sparkweave/core/contracts.py` | `UnifiedContext`、`StreamEvent`、`StreamBus` |

## 3. Tool + Capability 双层架构

### 3.1 分层原则

| 层级 | 解决的问题 | 粒度 | 控制权 |
| --- | --- | --- | --- |
| `Tool` | 做一个动作 | 单函数、轻状态 | 被模型或 graph 调用 |
| `Capability` | 完成一个学习任务 | 多阶段、有状态、有产物 | 接管 turn 流程 |

核心规则：

```text
Capability 编排 Tool，Tool 不反向控制 Capability。
```

这条边界让系统同时具备两种能力：

- 简单动作可以快速扩展为工具。
- 复杂学习任务可以沉淀为稳定流程。

### 3.2 Tool 层

Tool 是轻量原子能力，适合边界明确的外部动作。

| Tool | 用途 |
| --- | --- |
| `rag` | 知识库检索 |
| `web_search` | 联网搜索并返回引用 |
| `external_video_search` | 公开视频 / 公开课推荐 |
| `external_image_search` | 公开图片 / 示意图推荐 |
| `canvas` | 按需打开 / 更新右侧可编辑文档 |
| `code_execution` | 沙箱 Python 执行 |
| `reason` | 专门推理调用 |
| `brainstorm` | 发散式思考 |
| `paper_search` | arXiv 论文搜索 |
| `geogebra_analysis` | 图片几何题分析 |

统一返回：

```text
ToolResult = content + sources + metadata + success
```

`ToolRegistry` 负责注册工具、解析别名、生成 function schema、转换 `StructuredTool`、标准化结果。

当前实现体现：Tool 只暴露动作能力，不承载学习流程。工具结果通过 `sources` 和 `metadata` 被统一汇总，避免每个智能体各自定义证据格式。

### 3.3 Capability 层

Capability 是面向学习任务的专业智能体。

| Capability | 典型流程 | 产物 |
| --- | --- | --- |
| `chat` | coordinate -> tools -> respond | 默认问答 / 协调结果 |
| `deep_solve` | plan -> tools -> solve -> verify -> write | 分步解题讲解 |
| `deep_question` | ideate -> generate -> validate -> repair -> write | 题目、答案、解析 |
| `deep_research` | rephrase -> decompose -> research -> report | 研究报告 / 学习路径 |
| `visualize` | analyze -> generate -> review -> write | SVG / Mermaid / Chart.js |
| `math_animator` | analyze -> design -> code -> render -> summary | Manim 动画 / 图片 |

Capability manifest 描述 `name`、`description`、`stages`、`tools_used`、`cli_aliases`、`request_schema`、`config_defaults`。

当前实现体现：复杂能力不是一次 prompt，而是有阶段、有校验、有事件的 graph。比如 `deep_question` 把出题拆成“构思、生成、校验、修复”，`deep_solve` 把“推理”和“教学表达”拆开，并加入验证阶段。

### 3.4 双层协同流程

```text
用户请求
  -> Orchestrator 选择 Capability
  -> Capability 拆解阶段
  -> 阶段内按需调用 Tool
  -> Tool 返回证据 / 计算 / 外部信息
  -> Capability 汇总为学习结果
  -> StreamEvent 输出过程和结果
```

设计收益：

- 新工具不需要改主流程。
- 新 capability 可以复用旧工具。
- 前端展示的是学习阶段，而不是零散 function call。
- 测试可以分别覆盖工具契约和 capability 流程。

## 4. 统一 Orchestrator

统一 Orchestrator 不是单个类，而是一条统一控制链路：

```text
SparkWeaveApp / ChatOrchestrator
  -> RuntimeRoutingTurnManager
  -> LangGraphTurnRuntimeManager
  -> build_turn_context
  -> LangGraphRunner
  -> ChatGraph coordinator
```

它对外提供一个入口，对内负责四件事：

| 职责 | 说明 |
| --- | --- |
| 统一接入 | CLI、WebSocket、SDK 都转成同一种 turn payload |
| 动态路由 | 根据显式 capability、用户意图、画像 hints、runtime 配置选择路径 |
| 工具协同 | 将 enabled tools 注入 graph，统一执行、追踪、汇总证据 |
| 流程编排 | 将复杂任务交给专业 Capability Graph，并用事件流暴露进展 |

当前实现体现：用户只需要从“学习”入口表达任务，不需要理解 Agent、RAG、Tool、Capability。工程能力被后台化，符合学习产品入口设计。

## 5. 动态路由

动态路由分三层。

### 5.1 Runtime 路由

```text
payload capability + _runtime + env policy
  -> LangGraph 主运行时
  -> compatibility orchestrator
```

作用：让新 LangGraph runtime 和旧 `ChatOrchestrator` 共存，降低迁移风险。

### 5.2 Capability 路由

`ChatGraph` 是默认入口，也是协调器。它根据用户意图和画像 hints 生成 `CoordinatorDecision`。

路由策略集中在 `LearningCapabilityRouter`，`ChatGraph` 只消费决策结果：

```text
UnifiedContext
  -> LearningCapabilityRouter.decide()
  -> CoordinatorDecision
  -> stay in chat / direct tool / specialist graph
```

| 请求类型 | 路由目标 |
| --- | --- |
| 普通学习问答 | `chat` |
| 解题、证明、推导、计算 | `deep_solve` |
| 出题、测验、仿题、练习 | `deep_question` |
| 研究报告、资料规划、学习路径 | `deep_research` |
| 图解、流程图、知识结构 | `visualize` |
| 动画讲解、Manim、视频化说明 | `math_animator` |
| 公开视频 / 公开课推荐 | `external_video_search` tool |
| 公开图片 / 示意图素材 | `external_image_search` tool |
| 草稿、学习计划、报告、提纲 | `chat` + `canvas` tool |

协调结果包含 `capability`、`confidence`、`reason`、`config`、`tools`。

控制项：

- `auto_delegate=false`：关闭自动委派。
- `delegate_capability=...`：强制委派。
- `coordinator_capability=...`：指定协调目标。
- `coordinator_llm=auto|true|false` / `intent_classifier=...`：控制 LLM 意图判别。

当前实现体现：画像 hints 不只进入 prompt，也进入确定性路由。模糊请求可以被转成具体学习动作，例如继续练习、找资料、画图、生成动画。

### 5.3 LLM 意图判断提示词

确定性规则先处理高置信请求；当请求模糊、规则置信度低，或显式开启 `coordinator_llm` / `intent_classifier` 时，`LearningCapabilityRouter` 会构造专门的意图判断 prompt。

提示词原则：

- 只做路由，不回答用户。
- 输出严格 JSON，字段映射到 `CoordinatorDecision`。
- 先尊重用户约束：直接回答、不用工具、不画图、不委派。
- 区分“找公开视频”和“生成视频动画”。
- 区分“找图片素材 / 示意图参考”和“生成图解 / 画流程图”。
- 普通解释优先留在 `chat`，不要为了展示能力而过度委派。
- 画像只用于“继续学习 / 下一步”这类模糊请求，不在证据不足时强行个性化。

输出结构：

```json
{
  "capability": "chat | deep_solve | deep_question | deep_research | visualize | math_animator",
  "direct_tool": "external_video_search | external_image_search | null",
  "confidence": 0.0,
  "reason": "short reason",
  "rewritten_user_message": "optional clearer task",
  "tools": ["canvas", "rag", "web_search", "external_video_search", "external_image_search"],
  "config": {
    "mode": "learning_path",
    "render_mode": "mermaid",
    "output_mode": "video",
    "num_questions": 3
  },
  "profile_hints_applied": true
}
```

LLM 判别结果不会直接执行。运行时还会做 capability 白名单、置信度阈值、工具名过滤、用户约束复核和 config 标准化，失败时回退到规则结果。

硬约束优先级高于 LLM 分类器：用户说“不要用工具 / 直接回答”时，本轮 `tools=[]`；用户说“不要打开画布 / no canvas”时，只移除 `canvas`，保留 RAG、联网检索等其他可用工具；用户说“不要联网 / 不要搜索 / offline”时，只移除 RAG、联网搜索、论文搜索、公开视频和公开图片检索。

### 5.4 Tool 路由

进入 capability 后，工具选择在 graph 内发生：

```text
enabled_tools
  -> ToolRegistry 过滤与解析
  -> StructuredTool 注入模型 / graph
  -> tool_call
  -> ToolResult
  -> sources / metadata 汇总到 result
```

工具执行由 `GraphToolExecutor` 统一处理：

- 发出 `tool_call` 和 `tool_result`。
- 为 RAG 类工具补充检索进度事件。
- 捕获异常并转成失败的工具记录。
- 标准化 `content`、`sources`、`metadata`、`success`。

默认 `chat` 不委派时走标准工具循环：

```text
agent -> tools -> agent -> respond
```

实现要点：

- 最多并行执行多个工具调用。
- 每次工具调用发出 `tool_call` / `tool_result`。
- 工具证据统一进入最终 `result.sources`。
- `canvas` 只由工具结果触发右侧文档，不靠长文本启发式自动弹出。
- 模型吐出未启用工具时，`ChatGraph` 会跳过调用并写入内部 ToolMessage，避免越权执行。
- 模型一次请求过多工具时，只执行上限内的调用，其余调用补齐“已跳过” ToolMessage，保持后续模型轮次协议完整。
- 每轮系统提示都会注入 tool policy：模型只能调用 `enabled_tools`，没有启用 `canvas` 时必须把草稿写在聊天里。

## 6. 流程编排

### 6.1 Turn 生命周期

`LangGraphTurnRuntimeManager` 把一次执行建模为 `turn`：

```text
start_turn
  -> create session / turn
  -> build UnifiedContext
  -> run graph in background
  -> persist StreamEvent
  -> archive assistant message
  -> complete / fail / cancel
```

`subscribe_turn(turn_id, after_seq)` 支持：

- 读取历史事件。
- 接续 live events。
- WebSocket 断线后按 `seq` 补发。

当前实现体现：一次智能体执行不是临时函数调用，而是可持久化、可重放、可取消、可订阅的学习任务。

### 6.2 事件流

所有 graph 通过 `StreamBus` 输出结构化事件。

| 事件内容 | 用途 |
| --- | --- |
| `content` | 拼接自然语言回答 |
| `result` | 输出结构化产物 |
| `tool_call` | 展示工具开始 |
| `tool_result` | 展示工具结果 |
| `sources` | 展示证据来源 |
| `metadata` | 展示协作路线、阶段、画像命中 |

前端看到的是智能体协作过程，不只是最终答案。

### 6.3 专业 Graph 流程

| Graph | 编排重点 | 当前实现体现 |
| --- | --- | --- |
| `deep_solve` | 先规划，后工具，再求解、验证、讲解 | 解题推理和教学表达分离 |
| `deep_question` | 题目生成后校验，不合格自动修复 | 出题从一次生成升级为生产线 |
| `deep_research` | 改写、拆解、检索、报告 | outline checkpoint，先确认计划再继续 |
| `visualize` | 分析、生成、审查、输出可渲染代码 | 前端直接渲染结构化图形产物 |
| `math_animator` | 概念、分镜、代码、渲染、总结 | 从数学概念到动画产物闭环 |

## 7. 学习上下文

`UnifiedContext` 是所有 graph 和 tool 的统一输入。

| 字段 | 作用 |
| --- | --- |
| `user_message` | 当前任务文本 |
| `conversation_history` | 会话历史 |
| `enabled_tools` | 本轮可用工具 |
| `active_capability` | 当前能力 |
| `knowledge_bases` | 挂载知识库 |
| `attachments` | 图片 / 文件 |
| `config_overrides` | runtime 和 capability 配置 |
| `memory_context` | 长期记忆和学习画像文本 |
| `notebook_context` | Notebook 引用 |
| `history_context` | 历史会话引用 |
| `metadata` | turn id、画像 hints、协调信息 |

`build_turn_context` 注入：

- 会话历史。
- 长期记忆。
- 学习画像。
- Notebook 引用。
- 历史会话引用。
- 单题追问上下文。
- 附件。

当前实现体现：学习画像有双通道用途。

```text
memory_context
  -> 给模型读

metadata.learner_profile_context.hints
  -> 给 Orchestrator 做路由
```

## 8. 工具协同重点：RAG 双通道

RAG 同时是 Tool，也是上下文增强能力。

### 8.1 工具调用路径

```text
模型 / graph 显式调用 rag
  -> runtime 补齐 query、kb_name、override config
  -> 返回 content、sources、metadata
```

### 8.2 预取路径

```text
prefetch_rag=true
  -> ChatGraph 在模型调用前检索知识库
  -> 检索结果注入 memory_context
  -> 后续回答直接使用
```

当前实现体现：知识库能力不完全依赖模型主动调用工具。系统可以在 runtime 层主动把学习资料变成上下文，提高资料问答稳定性。

## 9. 长任务与扩展控制

### 9.1 Answer Now

`answer_now_context` 用于长任务中途收束。

```text
partial events + partial response + original question
  -> best-effort answer
  -> metadata.answer_now=true
```

当前用途：用户不用等完整流程结束，也不是简单取消，而是基于已有执行轨迹得到当前可交付答案。

### 9.2 Deep Research Checkpoint

`deep_research` 可先返回研究大纲和 checkpoint id。用户确认后，带 `confirmed_outline` 继续执行。

当前用途：长研究任务可以先确认方向，再消耗搜索和写作成本。

### 9.3 Plugin Capability

插件能力预留路径：

```text
discover manifest
  -> import entrypoint
  -> 校验 BaseCapability
  -> register
  -> runtime execute
```

当前代码里，`sparkweave/plugins/loader.py` 已实现 manifest 发现和读取，主要服务插件 API / CLI 列表；`CapabilityRegistry.load_plugins()` 仍是预留方法，尚未把第三方插件能力注册到运行时执行闭环。

## 10. 当前实现要点

| 要点 | 说明 |
| --- | --- |
| Turn-native Runtime | 把一次智能体执行变成可持久化、可重放、可取消、可订阅的 turn |
| Chat as Coordinator | 默认 chat 是学习任务协调器，不只是问答模型 |
| Tool / Capability 分层 | 工具负责动作，能力负责流程，边界清晰 |
| Profile-driven Routing | 学习画像既给模型读，也参与确定性路由 |
| RAG 双通道 | RAG 可被调用，也可被 runtime 预取注入上下文 |
| Structured Collaboration | 智能体委派、工具调用、证据来源都通过事件结构化输出 |
| Checkpoint / Answer Now | 长任务支持先确认计划，也支持中途收束 |

## 11. 测试覆盖

| 测试 | 覆盖 |
| --- | --- |
| `tests/ng/test_turn_runtime.py` | turn 生命周期、事件订阅、上下文合并 |
| `tests/ng/test_chat_graph.py` | ChatGraph 工具循环、RAG 预取、协调行为 |
| `tests/ng/test_capability_router.py` | `LearningCapabilityRouter` 规则、LLM 分类、用户约束 |
| `tests/capabilities/test_answer_now.py` | answer_now 上下文和中途收束 |
| `tests/ng/test_deep_research_graph.py` | deep research checkpoint 与继续执行 |
| `tests/core/test_builtin_tools.py` | 内置工具契约和工具结果结构 |

聚焦命令：

```powershell
uv run pytest tests/ng/test_turn_runtime.py tests/ng/test_chat_graph.py tests/ng/test_capability_router.py tests/capabilities/test_answer_now.py tests/ng/test_deep_research_graph.py tests/core/test_builtin_tools.py -q
```

## 12. 限制与待实现

- `CapabilityRegistry.load_plugins()` 当前没有加载第三方 capability 的执行闭环。
- 自动路由仍依赖规则、关键词、画像 hints 和可选 LLM 分类；不是全局最优规划器。
- `answer_now` 是基于已有事件和部分结果的 best-effort 收束，不保证等价于完整任务最终答案。
- 工具调用权限由 `enabled_tools`、工具白名单和 graph 检查共同约束；新增工具时必须同步 schema、前端结果渲染和测试。

## 13. 总结

SparkWeave 的编排设计把学习请求拆成三层控制：统一 Orchestrator 负责入口和路由，Capability 负责学习流程，Tool 负责原子动作。所有执行都落在 turn 生命周期内，通过 `StreamEvent` 暴露过程、证据和结果，从而支持多类学习智能体的动态路由、工具协同和可观测流程编排。
