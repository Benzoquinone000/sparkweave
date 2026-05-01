# 学习画像 P9 模型上下文注入

P9 的目标是让统一学习画像真正进入模型和智能体运行时，而不只是停留在画像中心页面或导学创建表单里。模型每一轮回答、调度资源生成智能体、解释题目和生成下一步建议时，都应能看到一份短小、可控、可解释的画像摘要。

## 设计原则

- **只注入摘要，不注入原始 JSON**：避免 prompt 变长、泄露调试字段，也避免模型把内部结构直接展示给用户。
- **画像静默影响回答**：模型应根据画像调整难度、例子、资源形态和下一步建议，但不要无缘无故说“我读取到了你的画像”。
- **证据留在画像服务**：LLM 只拿到可执行提示，详细证据、可解释性和校准仍由 `/memory` 画像中心承担。
- **失败闭合**：画像读取失败时不影响正常对话，只在 metadata 中保留不可用状态。
- **统一入口**：所有 LangGraph 回合都通过运行时上下文注入，而不是每个能力单独拼一份画像。

## 后端实现

新增 `sparkweave/services/profile_context.py`，核心对象是 `ProfileContextInjector`。

它从 `LearnerProfileService.read_profile()` 读取当前画像，并抽取以下字段：

- 当前学习目标与画像摘要。
- 建议水平和时间预算。
- 长期目标、资源偏好和优势。
- Top 薄弱点。
- 需要关注的知识点掌握状态。
- 推进方式，例如“概念澄清型”“练习驱动型”以及对应策略。
- `next_action` 的类型、标题、来源、预计时长和摘要。

输出结构：

```json
{
  "available": true,
  "source": "learner_profile",
  "version": 1,
  "generated_at": "...",
  "confidence": 0.82,
  "text": "[Learner Profile Context]\n- current_focus: ...",
  "hints": {
    "current_focus": "...",
    "weak_points": ["..."],
    "next_action": {}
  }
}
```

`text` 被控制在较短长度内，专门给模型使用；`hints` 给调试、回放和后续策略层使用。推进方式也会进入 `text`，让模型知道这名学习者更适合“先图解再练习”“先做题再补讲”还是“短视频串联后验证”。

## 运行时接入

`sparkweave/runtime/context_enrichment.py` 的 `build_turn_context()` 是 LangGraph 回合进入模型前的汇流点。P9 在这里读取 `ProfileContextInjector.build_context()`，并把画像提示合并进 `UnifiedContext.memory_context`。

这样现有会读取 `context.memory_context` 的能力都能自动获得画像摘要，包括：

- Chat 对话协调。
- Deep Solve 解题。
- Deep Question 出题。
- Deep Research 研究。
- Visualize 图解。
- Math Animator 动画讲解。

同时，完整 payload 会写入：

```text
UnifiedContext.metadata["learner_profile_context"]
```

这让前端或日志可以检查本轮是否成功带入画像，而不会把 raw profile 直接塞给模型。

## 应用层默认启用

默认应用运行时通过 `sparkweave/services/session.py` 创建：

- `create_turn_runtime_manager()`
- `create_runtime_router()`
- `get_runtime_manager()`

这些入口会注入 `get_profile_context_injector()`。显式单测或自定义构造的 `LangGraphTurnRuntimeManager` 不会默认读取真实画像，除非主动传入 `profile_context_injector`，避免测试被本地用户数据污染。

## 验证

新增测试覆盖：

- `tests/services/test_profile_context.py`
  - 画像可被压缩成 prompt block。
  - 没有证据时保持空上下文。
  - 画像服务异常时失败闭合。
- `tests/ng/test_turn_runtime.py`
  - 运行时能把画像上下文合并进 `memory_context`。
  - metadata 中保留 `learner_profile_context`。

已验证命令：

```bash
python -m py_compile sparkweave/services/profile_context.py sparkweave/runtime/context_enrichment.py sparkweave/runtime/turn_runtime.py sparkweave/runtime/routing.py sparkweave/services/session.py
pytest tests/services/test_profile_context.py tests/ng/test_turn_runtime.py -q
```

## 后续

- 让前端调试面板可选择显示“本轮是否使用画像”，但默认隐藏。
- 把 `ProfileContextInjector` 扩展为策略层，可根据 capability 输出不同粒度的画像摘要。
- 将资源生成、学习报告和导学提交页都统一读取 `learner_profile_context.hints`，减少各模块重复写画像提示。
