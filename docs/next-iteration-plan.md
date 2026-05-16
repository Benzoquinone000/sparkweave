# 下一阶段执行计划

本文记录 SparkWeave 后续默认推进方向。当前不要继续横向堆功能，优先进入 **产品化收敛 + 可信 RAG 闭环** 阶段。

## 当前判断

SparkWeave 已经具备 agent-native 架构、知识库管理、RAG 诊断、Agentic RAG 解释层和评测脚本。下一阶段目标不是“功能更多”，而是让用户能稳定、清楚、长期地使用它：

- RAG 要真实可验收。
- 知识库管理要像产品工作流，而不是调试页面。
- Agentic RAG 要能解释“为什么这么检索”。
- RAG 质量要可持续度量。
- 学习画像、导学和知识库证据要形成学习闭环。

## 进展记录

### 2026-05-13

- 真实 RAG E2E 已通过：上传、索引、向量库存储、检索、Chat RAG tool 均可复现验收。
- 知识库管理已增加失败恢复向导、进度解释、诊断与评测入口，前端按进入/返回的工作流拆分。
- Agentic RAG 结果已接入前端证据链，能展示计划、子问题、质量检查、fallback 和来源依据。
- `ml-course` 公开评测数据集与准备脚本已建立，评测报告支持策略对比、样本诊断和 Markdown/JSON 输出。
- 学习效果闭环已接入资料库依据，下一步学习建议能携带可用 KB 并优先使用 RAG 检索。
- RAG 评测报告新增 `quality_gate`，前端“检索质量评估”会显示可发布、需观察或暂不通过的质量门结论。

## 优先级

### 1. 真实环境 RAG 验收

目标：在真实 Milvus / Embedding / LLM 环境里跑通闭环。

验收顺序：

1. 启动后端、前端、Milvus 和当前 embedding provider。
2. 运行 `scripts/rag_e2e_acceptance.py` 上传测试文档。
3. 确认 `/documents` 能看到 raw 文档。
4. 确认 `/vectors` 能看到向量 chunk。
5. 确认 `/rag-test` 能返回 source 和 evidence。
6. 使用 `--chat-check` 确认 Chat 能实际引用知识库。

推荐命令：

```bash
python scripts/rag_e2e_acceptance.py \
  --base-url http://127.0.0.1:8001 \
  --cleanup \
  --json-output dist/rag-e2e-acceptance.json

python scripts/rag_e2e_acceptance.py \
  --base-url http://127.0.0.1:8001 \
  --chat-check \
  --cleanup
```

完成标准：从前端式上传到向量库写入、RAG 检索、Chat 引用知识库全部可复现。

### 2. 知识库体验产品化

目标：让普通用户知道“上传后发生了什么、失败后该怎么办、下一步去哪里”。

重点：

- 资料库详情继续按页面/子页面组织，不把文档、向量、诊断、评测堆在一屏。
- 上传后显示用户语言的阶段说明。
- 失败时给出明确动作：重试、重建索引、检查连接、查看日志。
- 文档、向量块、诊断、评测都保留进入/返回的工作流。
- UI 风格继续遵守 `DESIGN-notion.md`，保持 Notion 式克制、清晰、低噪声。

完成标准：用户不用理解 Milvus、chunk、SSE，也能完成资料库创建、排错和验证。

### 3. Agentic RAG 可解释性前端化

目标：把后端 `agentic_explanation` 变成用户可读的证据链。

重点：

- 展示为什么触发 Agentic RAG。
- 展示拆分出的子问题。
- 展示每个分支是否拿到证据、是否相关、是否修复。
- 展示为什么 fallback 到单路检索。
- 最终回答要能回看用了哪些证据。

完成标准：用户看到回答时，能理解它来自哪些资料、检索过程哪里强、哪里弱。

### 4. RAG 质量基准常态化

目标：让 RAG 修改有质量门，而不是凭感觉。

固定流程：

```bash
python scripts/validate_rag_eval_dataset.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl \
  --min-cases 30 \
  --min-query-types 5 \
  --require-kb \
  --json-output dist/rag-eval-dataset-check.json

python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl \
  --kb ml-course \
  --provider milvus \
  --preset rag-upgrade \
  --output dist/rag-eval-report.md \
  --json-output dist/rag-eval-report.json
```

用户侧快速验收先跑：

```bash
python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.sample.jsonl \
  --kb ml-course \
  --provider milvus \
  --preset quick-check
```

评测报告里的 `dataset_profile` 用来区分快速体检和正式质量门：`smoke_check` 只说明检索链路是否通畅；只有补齐期望关键词和期望来源、样本量足够后，才把结果当成 `release_ready` 质量基准。

重点指标：

- source hit
- keyword recall
- MRR / nDCG
- source count
- context chars
- latency
- evidence reason coverage

完成标准：每次改 RAG，都能用同一套样本看质量变化。

### 5. 学习闭环与 RAG 打通

目标：让 SparkWeave 不只是普通 RAG 聊天，而是学习 companion。

后续要串起来：

- 知识库证据
- 用户错题与薄弱点
- 学习画像
- Guide V2 导学计划
- 学习效果评估
- 下一步学习建议

完成标准：系统不仅回答“是什么”，还能判断用户为什么卡住，并给出下一步学习路径。

## 下一次开工建议

优先做 **真实 RAG E2E + 知识库失败恢复体验**。

原因：

- 真实 RAG E2E 是地基验收。
- 失败恢复体验直接影响用户信任。
- 这两项做好后，Agentic RAG 展示和质量评测才有稳定输入。

## 回归要求

常规改动后至少运行：

```bash
python -m pytest tests/api/test_knowledge_router.py tests/services/rag/test_rag_pipelines.py -q
python -m pytest tests/scripts/test_rag_e2e_acceptance.py tests/scripts/test_validate_rag_eval_dataset.py -q
python -m ruff check sparkweave/api/routers/knowledge.py sparkweave/services/rag_support/service.py scripts/rag_e2e_acceptance.py scripts/validate_rag_eval_dataset.py
```

涉及前端时运行：

```bash
cd web
npm.cmd run lint
npm.cmd run build
npm.cmd run check:design
npm.cmd run check:api-contract
```
