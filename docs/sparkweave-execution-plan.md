# SparkWeave 后续开发计划书

日期：2026-05-14  
负责人：Codex  
阶段定位：产品化收口 + 可信 RAG 闭环 + 工程稳定性提升

## 0. 本次比赛可视化计划完成声明

本计划书包含长期产品化路线，也包含 2026-05-15 追加的比赛可视化专项。为避免误读，先给出本次比赛可视化计划的完成状态：

- 比赛可视化专项已经完成，已经从方案阶段进入可提交验收状态。
- 完成证据见 [比赛可视化专项完成证据](./competition-visualization-completion-report.md)。
- 评委演示入口 `/demo`、桌面/移动截图、7 分钟录屏 runbook、后端连通性记录、正式提交包均已生成。
- `python scripts/check_competition_visuals.py` 输出 `Competition visual plan is complete.`。
- `python scripts/check_competition_readiness.py --output dist/competition_readiness_latest.json` 输出 `All required competition materials are ready.`。
- `dist/competition_package` 与 `dist/sparkweave_competition_package.zip` 均已通过校验，包内包含本计划书。

## 1. 总目标

SparkWeave 后续开发不再以“继续堆功能”为主，而是围绕真实用户使用体验和软件工程质量，把现有 agent-native 架构、RAG、知识库管理、导学、学习画像和前端工作台打磨成稳定、可验证、可长期维护的产品。

核心目标：

1. 让用户从前端上传资料后，能够稳定完成索引、写入向量数据库、检索证据、在 LLM 回答中引用知识库。
2. 让 Agentic RAG 不只是后台逻辑，而是能向用户解释“为什么这样检索、找到了什么、证据是否可靠”。
3. 让前端符合 `DESIGN-notion.md` 的 Notion 风格，页面简洁，通过进入/返回的页面切换组织功能，避免把所有能力堆在一个页面。
4. 清理遗留代码、测试残留和无用路径，让项目结构更清楚，便于后续扩展。
5. 建立稳定质量门：后端测试、前端构建、设计检查、API 契约检查、RAG E2E 验收和 RAG 质量评测。

## 2. 当前基线

当前项目已经完成的基础能力：

- 后端主架构已经形成：`ChatOrchestrator`、`UnifiedContext`、`StreamBus`、`ToolRegistry`、`CapabilityRegistry`、LangGraph runtime。
- RAG 已经升级为 Milvus 优先方案，并保留 LlamaIndex local 作为兼容 provider。
- RAG 支持 retrieval policy、HyDE query transform、Gated Agentic RAG、keyword rerank、Context Pack、diagnostics、evaluation。
- 知识库前端已经拆出多个子组件，支持创建、上传、进度、诊断、文档、向量、评测和检索测试。
- Chat 前端已经开始展示 RAG evidence chain。
- 当前目标测试和前端质量门已经通过：
  - RAG/知识库相关 Python 测试：`83 passed, 1 skipped`
  - `npm run lint`
  - `npm run build`
  - `npm run check:design`
  - `npm run check:api-contract`
  - `npm run check:replacement`

当前主要问题：

- 工作区变更量很大，需要分阶段收口。
- 真实本机 RAG 环境存在 Milvus URI 不一致问题：知识库 marker 指向 `http://milvus:19530`，当前 runtime 使用 `http://localhost:19530`。
- 部分模块过大，例如 `sparkbot.py`、`guide_v2.py`、`GuidePage.tsx`、`knowledge.py`、`RAGService`。
- 知识库配置中存在历史 E2E 测试残留记录。
- Agentic RAG 后端能力已经较强，但还需要进一步产品化、可解释化和验收常态化。

## 3. 开发原则

后续所有开发必须遵守：

1. 先稳定闭环，再扩展新能力。
2. 每次改动尽量小而完整，避免跨多个业务域混杂提交。
3. 面向用户表达，不把 Milvus、chunk、embedding mismatch 等底层细节直接丢给普通用户。
4. 后端保持清晰边界：router 负责 HTTP，service 负责业务，pipeline 负责底层执行。
5. 前端保持页面化和工作流化：用户进入一个任务页面，完成后可以返回，而不是在同一屏堆叠所有功能。
6. 新增能力必须有最小测试覆盖；影响 RAG、配置、上传、检索、Chat 的改动必须跑对应质量门。
7. 清理无用代码时只删除已确认无入口、无测试依赖、无文档依赖的代码。

## 4. 阶段一：真实 RAG 闭环稳定

目标：保证真实环境中 RAG 能从前端上传一路走到向量数据库，并能被 Chat/LLM 检索和引用。

任务：

1. 统一 Milvus 运行模式。
   - 本机开发使用 `MILVUS_URI=http://localhost:19530`。
   - Docker Compose 内部使用 `DOCKER_MILVUS_URI=http://milvus:19530`。
   - 知识库 marker、诊断报告、前端提示都要能清楚解释 URI 不一致。
2. 清理或同步失效知识库记录。
   - 删除 `kb_config.json` 中目录不存在的 E2E 残留项。
   - 保留真实用户知识库和评测知识库。
3. 重建 `ml-course` 或当前默认知识库索引。
   - 确认 raw 文档存在。
   - 确认 Milvus collection 存在。
   - 确认 vector row count 大于 0。
4. 跑真实验收脚本。
   - `scripts/rag_e2e_acceptance.py`
   - 开启 `--chat-check` 验证 Chat RAG tool。
5. 修复验收中暴露的问题。

完成标准：

- `/api/v1/knowledge/{kb}/documents` 能看到 raw 文档。
- `/api/v1/knowledge/{kb}/vectors` 能看到向量 chunk。
- `/api/v1/knowledge/{kb}/diagnostics` readiness 为可用或仅有非阻塞提示。
- `/api/v1/knowledge/{kb}/rag-test` 返回 sources、content、context pack。
- Chat 选择知识库后，LLM 回答能使用 RAG tool 并带证据来源。

质量门：

```powershell
C:\Users\hjk\anaconda3\python.exe -m pytest tests/api/test_knowledge_router.py tests/services/rag/test_rag_pipelines.py tests/tools/test_rag_tool.py -q
python scripts/rag_e2e_acceptance.py --base-url http://127.0.0.1:8001 --chat-check --cleanup
cd web
npm.cmd run lint
npm.cmd run build
npm.cmd run check:api-contract
```

## 5. 阶段二：知识库管理产品化

目标：让普通用户知道资料上传后发生了什么，失败时知道下一步怎么处理。

任务：

1. 优化知识库首页。
   - 默认显示当前知识库状态、文档数、向量数、最近任务、健康状态。
   - 将“上传资料、查看文档、查看向量、诊断、质量评测、检索测试”继续保持为工作区切换。
2. 优化失败恢复体验。
   - 对连接失败、向量为空、embedding 维度不匹配、需要重建索引分别给出用户可执行动作。
   - 提供“检查连接”“重建索引”“重新上传”“打开检索测试”的明确入口。
3. 优化任务进度。
   - 前端显示阶段化说明：保存文件、解析文档、生成向量、写入 Milvus、完成索引。
   - 后端 task log 保持结构化，减少纯字符串解析。
4. 优化文档与向量管理。
   - 文档列表能展示原始文件、预览、关联向量数量。
   - 向量列表用于诊断，不把底层字段暴露得过重。

完成标准：

- 用户不理解 Milvus/chunk 也能完成知识库创建、排错和复测。
- 每个知识库子任务都有清楚入口和返回路径。
- 空状态、加载态、错误态都有符合 Notion 风格的简洁展示。

质量门：

```powershell
cd web
npm.cmd run lint
npm.cmd run build
npm.cmd run check:design
npm.cmd run check:api-contract
```

## 6. 阶段三：Agentic RAG 可解释化

目标：让用户能看懂系统为什么拆分问题、每个分支找到了什么、最终证据是否可靠。

任务：

1. 完善后端 `agentic_explanation`。
   - 输出触发原因。
   - 输出子问题列表。
   - 输出每个子问题的证据数量、相关性、是否修复、是否失败。
   - 输出 fallback 原因。
2. 完善前端证据链。
   - 在 Chat 回答中展示“检索编排、证据质量、来源片段、下一步建议”。
   - 弱证据时提供跳转到知识库检索测试的入口。
3. 优化 Agentic RAG 策略。
   - 保持 gated，不默认对所有问题开启。
   - 对复杂、多问、对比、规划类问题自动启用。
   - 弱证据自动回退单路检索。
4. 建立 Agentic RAG 测试集。
   - 覆盖单问题、多问题、对比问题、无证据问题、弱证据 fallback。

完成标准：

- 用户能看到本次回答用了哪些资料。
- 用户能看到 Agentic RAG 是否启用、是否回退、为什么回退。
- 弱证据不会被包装成强结论。

质量门：

```powershell
C:\Users\hjk\anaconda3\python.exe -m pytest tests/services/rag/test_query_planner.py tests/services/rag/test_context_pack.py tests/graphs/test_rag_overrides.py -q
cd web
npm.cmd run lint
npm.cmd run build
```

## 7. 阶段四：RAG 质量评测常态化

目标：RAG 调优不能靠感觉，要能用同一套数据持续比较策略效果。

任务：

1. 固定一套公开课程评测语料。
   - 保留 `ml-course` 作为基础评测知识库。
   - 使用 `scripts/prepare_rag_eval_corpus.py` 准备数据。
2. 固定评测样本。
   - 覆盖概念题、原文定位题、跨章节综合题、代码/公式/术语题。
3. 跑多策略评测。
   - baseline
   - adaptive policy
   - hybrid keyword rerank
   - HyDE
   - agentic HyDE
4. 在前端展示质量门。
   - 可发布
   - 需要观察
   - 暂不通过

完成标准：

- 每次改 RAG 后都能输出 JSON/Markdown 评测报告。
- 报告包含 source hit、keyword recall、MRR、nDCG、context chars、latency、diagnostics。
- 不再凭单次手工提问判断 RAG 好坏。

质量门：

```powershell
python scripts/validate_rag_eval_dataset.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl --min-cases 30 --min-query-types 5 --require-kb
python scripts/rag_eval_experiment.py docs/examples/rag_eval_dataset.ml_course.sample.jsonl --kb ml-course --provider milvus --preset rag-upgrade --output dist/rag-eval-report.md --json-output dist/rag-eval-report.json
```

## 8. 阶段五：代码结构收口

目标：降低维护成本，让项目更符合软件工程规范。

任务：

1. 拆分超大后端模块。
   - `sparkweave/api/routers/knowledge.py` 拆成 schema、tasks、documents、diagnostics、evaluation。
   - `sparkweave/services/rag_support/service.py` 拆出 agentic merge、quality、fallback、event trace。
   - `sparkweave/services/sparkbot.py` 拆分 manager、runtime、channels、workspace、memory。
   - `sparkweave/services/guide_v2.py` 拆分 session、resource generation、report、course package。
2. 拆分超大前端页面。
   - `GuidePage.tsx`
   - `ChatPage.tsx`
   - `SettingsPage.tsx`
   - `AgentsPage.tsx`
3. 清理无用代码。
   - 删除无入口脚本。
   - 删除旧兼容空壳。
   - 清理缓存和临时目录。
   - 保留有迁移价值的 legacy 兼容逻辑，但标注边界。
4. 规范环境入口。
   - 明确推荐 Python 解释器。
   - 避免 `python` 指向未安装依赖的解释器导致测试误判。

完成标准：

- 单个业务文件尽量控制在可维护范围内。
- router 不再承担大量业务逻辑。
- service 不再混合 HTTP、状态展示和底层 provider 细节。
- 测试仍全部通过。

质量门：

```powershell
C:\Users\hjk\anaconda3\python.exe -m pytest tests/api tests/services/rag tests/tools/test_rag_tool.py -q
cd web
npm.cmd run lint
npm.cmd run build
npm.cmd run check:design
npm.cmd run check:api-contract
npm.cmd run check:replacement
```

## 9. 阶段六：学习闭环整合

目标：把 SparkWeave 从“能 RAG 问答”推进到“能长期陪伴学习”。

任务：

1. Chat 回答引用知识库证据。
2. 学习画像记录用户薄弱点、偏好和近期学习上下文。
3. Guide 根据知识库、画像、练习结果生成下一步任务。
4. Question Lab 的答题结果回写学习效果。
5. Notebook 保存关键知识、错题、总结和来源。
6. 前端提供清晰路径：资料 -> 问答 -> 练习 -> 反馈 -> 下一步。

完成标准：

- 用户不只是得到答案，还能得到下一步学习建议。
- 学习建议能说明依据：知识库证据、练习表现、学习画像。
- 学习闭环可在前端完整演示。

## 10. 长期维护规则

后续每次我继续开发时，默认遵守以下顺序：

1. 先查看当前工作区和相关代码。
2. 明确本轮改动边界。
3. 优先修复真实用户路径上的问题。
4. 写最小必要测试。
5. 跑对应质量门。
6. 总结改了什么、验证了什么、还剩什么风险。

默认不做：

- 不随意推翻已有用户改动。
- 不在一个页面继续堆叠大量功能。
- 不把调试工具包装成用户产品。
- 不删除未确认用途的代码。
- 不绕过 RAG 真实验收就声称闭环完成。

## 11. 长期产品化下一次开工优先事项

以下事项属于可视化专项完成后的长期 RAG 产品化路线，不属于本次比赛可视化计划的交付缺口。下一次继续开发时，优先做：

1. 统一 Milvus URI 与当前知识库 marker。
2. 清理失效知识库配置记录。
3. 重建并验收 `ml-course`。
4. 跑 `rag_e2e_acceptance.py --chat-check`。
5. 根据验收结果修复真实 RAG 闭环。

这五项完成后，再进入知识库管理产品化和 Agentic RAG 证据链优化。

## 12. 执行记录

### 2026-05-14

- 已完成第一阶段真实 RAG 闭环验收：前端/API 上传、后端解析与分块、Milvus 向量写入、诊断、RAG 测试、Chat 检索链路均已通过。
- 已进入第二阶段知识库管理产品化：知识库页面继续向多工作区切换演进，避免所有功能堆叠在单页。
- 本轮完成知识库工作区体验优化：索引进度页已移入当前知识库工作区右侧内容流，上传页和进度页增加返回概览入口，工作区返回按钮增加稳定测试标识。
- 本轮质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`。
- 继续推进第二阶段与第五阶段前端收口：新增 `KnowledgeWorkspaceContent.tsx` 承接知识库右侧工作区渲染，新增 `ragEvaluationCases.ts` 固定快速评测样本，让 `KnowledgePage.tsx` 回到页面协调器职责。
- 本轮结构收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`。
- 已推进第三阶段 Agentic RAG 可解释化：后端 `agentic_explanation` 新增 `user_facing` 层，统一输出决策标题、触发原因、回退原因、证据摘要和下一步动作；前端证据链优先读取这些解释字段，并补充中文展示映射。
- 本轮 Agentic RAG 质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py tests\services\rag\test_rag_pipelines.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py tests\services\rag\test_rag_pipelines.py`、`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`。
- 已推进第四阶段 RAG 质量评测常态化：`validate_rag_eval_dataset.py` 输出样本标注覆盖率、完整标注数量和下一步建议，便于区分 smoke check 与可发布质量门。
- 本轮评测脚本质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\scripts\test_validate_rag_eval_dataset.py tests\scripts\test_rag_eval_experiment.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check scripts\validate_rag_eval_dataset.py tests\scripts\test_validate_rag_eval_dataset.py`、`C:\Users\hjk\anaconda3\python.exe scripts\validate_rag_eval_dataset.py docs\examples\rag_eval_dataset.ml_course.sample.jsonl --min-cases 30 --min-query-types 5 --require-kb`。
- 继续推进第五阶段代码结构收口：新增 `sparkweave/services/rag_support/agentic_explanation.py`，将 Agentic RAG 决策说明、用户可见摘要、证据质量检查和步骤解释从 `RAGService` 中拆出；`RAGService` 回到编排与调用职责，便于后续维护和扩展。
- 本轮 Agentic RAG 结构收口质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py sparkweave\services\rag_support\agentic_explanation.py tests\services\rag\test_rag_pipelines.py`。
- 继续拆分 Agentic RAG 质量门：新增 `sparkweave/services/rag_support/agentic_quality.py`，将质量评分、相关性报告、fallback 判定输入和 activity/subquery 质量回写从 `RAGService` 中移出；`RAGService` 行数进一步下降，主流程更接近编排层。
- 本轮质量规则收口质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py sparkweave\services\rag_support\agentic_explanation.py sparkweave\services\rag_support\agentic_quality.py sparkweave\services\rag_support\__init__.py tests\services\rag\test_rag_pipelines.py`。
- 继续收口 Agentic RAG 执行轨迹：新增 `sparkweave/services/rag_support/agentic_activity.py`，将 activity plan 构建和分支状态摘要从 `RAGService` 拆出，便于知识库诊断页、证据链和日志系统复用同一份结构化轨迹。
- 本轮执行轨迹收口质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py sparkweave\services\rag_support\agentic_activity.py sparkweave\services\rag_support\agentic_explanation.py sparkweave\services\rag_support\agentic_quality.py sparkweave\services\rag_support\__init__.py`。
- 补充 Agentic RAG 支撑模块单元测试：新增 `tests/services/rag/test_agentic_support_modules.py`，直接覆盖 activity trace、quality report、quality 回写和 user-facing explanation 的关键契约，避免后续只能通过完整 RAG 流程定位回归。
- 本轮支撑模块测试质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_agentic_support_modules.py tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\agentic_activity.py sparkweave\services\rag_support\agentic_explanation.py sparkweave\services\rag_support\agentic_quality.py tests\services\rag\test_agentic_support_modules.py`。
- 继续拆出 Agentic RAG 合并层：新增 `sparkweave/services/rag_support/agentic_merge.py`，集中处理多分支 sources 去重、context pack 截断、source limit 和 fallback 检索参数；`RAGService` 不再承载上下文拼装细节。
- 本轮合并层收口质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_agentic_support_modules.py tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py sparkweave\services\rag_support\agentic_activity.py sparkweave\services\rag_support\agentic_explanation.py sparkweave\services\rag_support\agentic_quality.py sparkweave\services\rag_support\agentic_merge.py sparkweave\services\rag_support\__init__.py tests\services\rag\test_agentic_support_modules.py`。
- 继续拆出 Agentic RAG 修复策略：新增 `sparkweave/services/rag_support/agentic_repair.py`，集中处理弱分支是否需要修复、修复分支选择和候选结果接受规则；`RAGService` 保留实际重试调用与事件输出。
- 本轮修复策略质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\rag\test_agentic_support_modules.py tests\services\rag\test_rag_pipelines.py tests\services\rag\test_query_planner.py tests\services\rag\test_context_pack.py tests\graphs\test_rag_overrides.py -q`、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support\service.py sparkweave\services\rag_support\agentic_activity.py sparkweave\services\rag_support\agentic_explanation.py sparkweave\services\rag_support\agentic_quality.py sparkweave\services\rag_support\agentic_merge.py sparkweave\services\rag_support\agentic_repair.py sparkweave\services\rag_support\__init__.py tests\services\rag\test_agentic_support_modules.py`。
- 修复 LlamaIndex 图片 OCR 测试稳定性：`tests/services/rag/test_llamaindex_image_ingestion.py` 在导入 pipeline 前注入轻量假的 `llama_index` 模块，避免只验证 OCR 路由的单元测试被本机 numpy/llama_index 原生扩展崩溃影响。
- 本轮 RAG/API/tool 回归质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\api\test_knowledge_router.py tests\services\rag tests\tools\test_rag_tool.py -q`（155 passed, 2 skipped）、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\rag_support tests\services\rag`。
- 修复前端质量门阻塞：`AgentsPage.tsx` 将助教聊天输入拆为独立 composer，避免 effect 内同步 setState；消息 ID 改用组件内 ref 序列生成，避免在组件渲染路径中调用 `Date.now()`。
- 本轮前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进第五阶段后端结构收口：将 `sparkweave/api/routers/knowledge.py` 中的请求/响应模型、任务调度、上传 staging、评测报告、守卫校验、后台任务实现、RAG 测试/评测操作、进度 WebSocket、知识库列表聚合、文档/向量管理和 linked folder 同步逻辑拆入独立模块；router 保留 HTTP 入口、异常映射和轻量依赖注入职责。
- 本轮知识库 router 行数从约 1470 行进一步降至约 1030 行，新增 `knowledge_catalog.py`、`knowledge_document_ops.py`、`knowledge_folder_ops.py`、`knowledge_jobs.py`、`knowledge_rag_ops.py`、`knowledge_progress.py` 等支撑模块；保留 `run_initialization_task`、`run_upload_processing_task`、`run_reindex_processing_task` 的兼容 wrapper，避免破坏现有测试和调用点。
- 本轮后端结构收口质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\api\test_knowledge_router.py tests\services\rag tests\tools\test_rag_tool.py -q`（155 passed, 2 skipped）、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\api\routers\knowledge.py sparkweave\api\routers\knowledge_catalog.py sparkweave\api\routers\knowledge_document_ops.py sparkweave\api\routers\knowledge_folder_ops.py sparkweave\api\routers\knowledge_jobs.py sparkweave\api\routers\knowledge_rag_ops.py sparkweave\api\routers\knowledge_progress.py sparkweave\api\routers\knowledge_models.py sparkweave\api\routers\knowledge_tasking.py sparkweave\api\routers\knowledge_uploads.py sparkweave\api\routers\knowledge_eval_reports.py sparkweave\api\routers\knowledge_guards.py sparkweave\services\rag_support tests\api\test_knowledge_router.py tests\services\rag tests\tools\test_rag_tool.py`。
- 继续推进第五阶段超大服务模块收口：新增 `sparkweave/services/sparkbot_support/`，将 SparkBot 配置模型、渠道配置、密钥脱敏、默认工作区模板、比赛演示素材、默认 soul、消息总线和通道文本格式化函数从 `sparkbot.py` 拆出；`sparkbot.py` 继续重新导出旧名字，保持 API、CLI 和测试导入路径兼容。
- 继续推进 Guide V2 结构收口：新增 `sparkweave/services/guide_support/models.py`，将 `LearnerProfile`、`CourseNode`、`CourseMap`、`LearningTask`、`GuideSessionV2`、`GuideV2CreateInput` 等数据契约从 `guide_v2.py` 拆出；`GuideV2Manager` 回到学习流程编排和资源生成职责。
- 本轮 SparkBot/Guide 收口后，`sparkbot.py` 从约 11078 行降至约 10572 行，`guide_v2.py` 从约 9095 行降至约 8937 行；新增支撑模块均已纳入 lint 和测试。
- 本轮 SparkBot/Guide 质量门通过：`C:\Users\hjk\anaconda3\python.exe -m pytest tests\services\sparkbot tests\api\test_sparkbot_router.py tests\api\test_sparkbot_channel_schema.py tests\ng\test_sparkbot_service.py tests\services\test_guide_v2.py tests\services\test_guide_v2_external_video.py tests\api\test_guide_v2_router.py -q`（155 passed）、`C:\Users\hjk\anaconda3\python.exe -m ruff check sparkweave\services\sparkbot.py sparkweave\services\sparkbot_support sparkweave\services\guide_v2.py sparkweave\services\guide_support tests\services\sparkbot tests\api\test_sparkbot_router.py tests\api\test_sparkbot_channel_schema.py tests\ng\test_sparkbot_service.py tests\services\test_guide_v2.py tests\services\test_guide_v2_external_video.py tests\api\test_guide_v2_router.py`。
- 继续推进第五阶段前端结构收口：`GuidePage.tsx` 新增 `guideDisplay.ts` 共享展示规则、`GuideSubPageFrame.tsx` 子页面框架、`GuideMetrics.tsx` 指标组件、`guideFormOptions.ts` 表单选项、`GuideSetupPanels.tsx` 启动区组件、`GuideDemoCards.tsx` 演示卡片和 `GuideLearningLoopSummary.tsx` 学习闭环回执模块；主页面从约 6849 行降至约 5814 行，更接近页面协调器职责。
- 本轮 Guide 前端收口同时将 `guideTaskTitle`、`taskTypeLabel` 上移为共享展示函数，避免 Demo 卡片和主流程各自维护任务文案映射；多页面进入/返回框架保持在独立组件中，继续服务 Notion-like 的简约页面流。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 页面结构收口：新增 `web/src/pages/agents/AgentWorkspaceChrome.tsx`，承接助教工作区 tabs、状态条、最近学习面板和最近会话时间格式化逻辑；`AgentsPage.tsx` 从约 3782 行降至约 3608 行，主页面更专注于数据协调和工作区切换。
- 继续推进 Agents 能力配置收口：新增 `web/src/pages/agents/AgentConfigPanels.tsx`，承接能力卡片、能力详情、能力入口映射和图标映射；`AgentsPage.tsx` 进一步降至约 3471 行，运行时能力矩阵的展示逻辑与页面数据流解耦。
- 继续推进 Agents 助教对话收口：新增 `web/src/pages/agents/SparkBotChatPanel.tsx`，承接 WebSocket 连接、流式消息、快捷动作、输入框和回答反馈写回；`AgentsPage.tsx` 进一步降至约 3162 行，助教页面的数据协调、能力配置、聊天运行时边界更清晰。
- 继续推进 Agents 配置与工作区编辑收口：新增 `BotSettingsPanels.tsx` 承接助教资料、工具 JSON、运行参数表单，新增 `AgentWorkspaceEditors.tsx` 承接渠道配置表单与工作文件编辑器，新增 `agentWorkspaceFiles.ts` 承接工作文件分类、排序与标签规则；`AgentsPage.tsx` 进一步降至约 2436 行。
- 继续推进 Agents 模板与列表组件收口：新增 `SparkBotLibraryPanels.tsx` 承接助教模板库和 Bot 卡片，页面主体不再直接维护模板详情查询、模板草稿表单和 Bot 启停按钮组；`AgentsPage.tsx` 进一步降至约 2211 行。
- 本轮 Agents 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 创建流程收口：新增 `AssistantCreateWizard.tsx` 承接助教创建三步向导，新增 `assistantCreateWizardPresets.ts` 承接课程预设、风格预设与 persona 生成规则；`AgentsPage.tsx` 从约 2211 行降至约 1963 行，主页面继续向数据协调器收敛。
- 本轮创建向导拆分同时清理了拆分后的未使用导入，并避免组件文件导出非组件工具导致 Fast Refresh 警告。
- 本轮 Agents 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 学习工作台收口：新增 `TeachingAssistantWorkbench.tsx` 承接“今日建议”、启动助教、完成行动回写和快捷学习动作；新增 `assistantLearningFlow.ts` 承接快捷动作、下一步 prompt、画像摘要和学习效果摘要规则。
- 本轮拆分保留原有用户可见文案和 prompt 行为，`AgentsPage.tsx` 进一步降至约 1702 行，主页面不再维护学习工作台内部状态。
- 本轮 Agents 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 资料与演示工作区收口：新增 `AssistantEvidencePanels.tsx`，承接资料来源、证据引用、助教产物、多模态 OCR/TTS 预览、学习协作路线和比赛演示检查；新增 `assistantHistoryUtils.ts` 承接历史消息解析、角色标签、unknown 文本归一化和 record guard。
- 本轮拆分后 `AgentsPage.tsx` 进一步降至约 717 行，页面主体基本只保留导航、数据查询、mutation 组合和子页面切换；资料/产物/演示逻辑进入独立面板，后续可单独测试和迭代。
- 本轮 Agents 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 工作区编辑收口：新增 `AssistantWorkspacePanels.tsx`，承接渠道与多模态配置面板、工作文件列表、文件创建和文件编辑壳层；`AgentsPage.tsx` 降至约 598 行，保留为助教中心的数据编排与页面切换层。
- 本轮工作区面板拆分后，渠道 schema、当前渠道配置和文件保存都通过 props 注入，避免主页面继续堆叠表单细节，也便于后续将工作区拆成更明确的子页面入口。
- 本轮 Agents 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 前端结构收口：新增 `GuideDiagnosticPanel.tsx`，将开始前小校准的答题状态、前测结果展示和提交逻辑从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 从约 5815 行降至约 5637 行。
- 本轮 Guide 拆分保持主页面负责 session、mutation 和子页面切换，诊断面板独立维护答题状态，后续可继续拆知识图谱、学习报告和课程包卡片。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 课程包展示收口：新增 `GuideCourseSyllabusPanel.tsx`，将课程大纲、学习目标、考核构成、周次安排和项目里程碑从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 5566 行。
- 本轮课程大纲拆分保持展示逻辑独立，主页面继续保留 session 状态、报告生成和子页面切换职责，后续可按同样方式拆学习报告、知识图谱和课程包答辩卡片。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 知识地图收口：新增 `GuideKnowledgeMapPanel.tsx`，将知识点路线图、节点掌握度、节点任务列表和通用任务行组件从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 5316 行。
- 本轮知识地图拆分后，路线图组件独立维护选中节点状态，主页面只传入节点、掌握度、任务队列和当前任务，符合多页面/多面板简洁化方向。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 学习日程收口：新增 `GuideStudyPlanPanel.tsx`，将学习日程、检查点、路径调度依据和学习块进度从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 5195 行。
- 本轮学习日程拆分后，路线页由课程大纲、学习日程、知识地图三个独立面板组成，主页面继续只负责子页面切换和数据请求。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 工具函数收口：新增 `guideDataUtils.ts`，将答题解析、时间格式化、选项归一化、答案判定和 record guard 从 `GuidePage.tsx` 拆出；主页面继续向会话编排和子页面切换职责收敛。
- 继续推进 Guide 学习报告收口：新增 `GuideLearningReportPanel.tsx`，将学习效果报告、评估依据、全局学习效果闭环、下一步建议、演示就绪和报告动作按钮从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 4247 行。
- 本轮学习报告拆分后，完成页只负责传入报告数据、保存/导出回调和路线/课程包跳转，报告内部展示与动作策略独立维护，便于后续继续拆课程包和资源学习流。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 课程产出包收口：新增 `GuideCoursePackagePanel.tsx`，将课程产出包、赛前检查、演示录屏检查、PPT 骨架、比赛对齐、多智能体协作蓝图、答辩预案和提交清单从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 3672 行。
- 本轮课程产出包拆分后，课程包页只保留入口、保存和导出回调，所有展示卡片在独立文件内聚合，减少主页面对比赛/演示细节的耦合。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 资源学习流收口：新增 `GuideResourceArtifactPager.tsx`，将资源分页学习、资源渲染、智能体接力说明、生成依据卡、交互式练习、答题结果构造和资源个性化说明从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 2775 行。
- 本轮资源学习流拆分后，主页面只负责把当前任务或处方产物列表传入资源学习组件，组件内部独立维护当前资源索引、逐题提交状态、保存动作和学习闭环提示。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 学习反馈收口：新增 `GuideLearningFeedbackPanel.tsx`，将任务完成反馈卡、最小补救任务、反馈路径按钮、处方复测提示和完成后下一步决策从 `GuidePage.tsx` 拆出；`GuidePage.tsx` 进一步降至约 2377 行。
- 本轮反馈收口后，任务完成后的“补救 / 复测 / 继续推进”策略由独立面板维护，主页面只负责提供反馈数据、画像刷新状态和跳转/生成回调。
- 本轮 Guide 前端质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 规则与工具收口：新增 `guideResourceUtils.ts`、`guideDemoSeedUtils.ts`、`guideLearningStrategy.ts`、`guideEffectActionSeed.ts` 和 `GuideDemoTaskShortcutCard.tsx`，将资源类型文案/图标、Demo 稳定任务链、学习画像策略、录屏提示和学习效果入口 seed 从 `GuidePage.tsx` 拆出。
- 本轮同时复用统一资源工具，移除 `GuideResourceArtifactPager.tsx` 与 `GuideLearningFeedbackPanel.tsx` 中重复的资源标签、图标和资料类型判断逻辑；`GuidePage.tsx` 从约 2377 行降至约 1629 行，主页面更接近 session/mutation/子页面编排层。
- 本轮 Guide 工具收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 页面 JSX 收口：新增 `GuideSupportDrawer.tsx`，将“查看路线”侧边抽屉、当前任务提示、学习画像入口、路线切换、新建路线、重新整理和删除入口从 `GuidePage.tsx` 拆出。
- 本轮侧边抽屉拆分后，`GuidePage.tsx` 从约 1629 行降至约 1516 行；主页面继续保留数据查询、mutation 编排和子页面状态，抽屉只通过回调触发路线管理动作。
- 本轮 Guide 抽屉收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 首屏体验收口：新增 `GuideHero.tsx`，将导学首屏 Hero、Notion-like 工作区预览、当前一步入口和路线抽屉入口从 `GuidePage.tsx` 拆出，首屏视觉与页面编排解耦。
- 本轮 Hero 拆分后，`GuidePage.tsx` 从约 1516 行降至约 1398 行，首屏文案和视觉资产保持原有用户体验，后续可单独优化 Hero 的响应式与视觉规范。
- 本轮 Guide Hero 收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 当前学习面板收口：新增 `GuideCurrentTaskPanel.tsx`，将当前任务卡、推荐资源入口、Demo 稳定提示词快捷生成、资源结果区和资源分页学习入口从 `GuidePage.tsx` 拆出。
- 本轮当前学习面板拆分后，`GuidePage.tsx` 从约 1398 行降至约 1280 行；核心学习体验通过 props 接收任务、资源、生成状态和保存/答题回调，便于后续单独做用户体验优化。
- 本轮 Guide 当前学习面板质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 提交流程收口：新增 `GuideTaskCompletionPanel.tsx`，将任务完成标准、Demo 证据快捷填充、评分选择、一句话反思和完成反馈回执从 `GuidePage.tsx` 拆出。
- 本轮提交流程拆分后，`GuidePage.tsx` 从约 1280 行降至约 1218 行；完成任务页独立接收 score/reflection 状态与提交回调，主页面只负责打开子页面和执行 mutation。
- 本轮 Guide 提交流程质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 子页收口：新增 `GuideResourceChoicePage.tsx` 与 `GuideRouteMapPage.tsx`，将“换一种学法”资源选择页和完整路线/知识地图/任务队列页从 `GuidePage.tsx` 拆出。
- 本轮资源选择与路线页拆分后，`GuidePage.tsx` 从约 1218 行降至约 1153 行；资源页只负责选择资源类型，路线页只负责展示学习计划、课程大纲、知识地图和任务队列。
- 本轮 Guide 子页拆分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 创建流程收口：新增 `GuideCreateRoutePanel.tsx` 与 `GuideSetupPage.tsx`，将快速创建路线和详细偏好设置页从 `GuidePage.tsx` 拆出。
- 本轮创建流程拆分后，`GuidePage.tsx` 从约 1153 行降至约 1053 行；主页面继续保留表单状态、mutation 编排和子页面切换，创建/设置页成为可独立优化的用户入口。
- 本轮 Guide 创建流程质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 阶段页收口：新增 `GuideCompleteStagePage.tsx`、`GuideDiagnosticStagePanel.tsx` 与 `GuideFeedbackStagePanel.tsx`，将完成报告/处方产物、前测说明与反馈收尾从 `GuidePage.tsx` 拆出。
- 本轮阶段页拆分后，`GuidePage.tsx` 从约 1053 行降至约 955 行；主页面不再直接维护报告卡、处方产物分页、诊断提示和反馈收尾卡片，只保留阶段判断与动作回调。
- 本轮 Guide 阶段页质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 入口协议收口：新增 `useGuideUrlSeed.ts`，将学习效果页/画像页跳转到导学时携带的 prompt、effect action、目标 section 和 source action 解析从 `GuidePage.tsx` 拆出。
- 本轮入口 hook 拆分后，`GuidePage.tsx` 从约 955 行降至约 904 行；URL 入口协议可以独立维护，主页面只读取 `hasUrlGuideSeed` 参与画像默认目标填充策略。
- 本轮 Guide 入口协议质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 动作层收口：新增 `useGuideSectionHighlight.ts`、`useGuideResourceJobEvents.ts`、`guideDownloadUtils.ts`、`useGuideLifecycleEffects.ts` 与 `guidePersistenceActions.ts`，将高亮滚动、资源生成 SSE、报告/课程包下载、画像默认目标填充、会话切换清理、Notebook 默认选择、保存到 Notebook 和练习回写从 `GuidePage.tsx` 拆出。
- 本轮动作层拆分后，`GuidePage.tsx` 从约 904 行降至约 769 行；主页面进一步收敛为会话数据、阶段判断和子页面编排，用户关键动作进入可独立维护的模块。
- 本轮同时补齐 `SystemStatus` 的 OCR/TTS `model` 类型字段，避免 `/demo` 运行时状态展示访问模型字段时触发类型漂移。
- 本轮 Guide 动作层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 会话动作收口：新增 `guideSessionActions.ts`、`guideResourceGenerationActions.ts` 与 `guideDemoCueActions.ts`，将模板套用、普通路线创建、稳定 Demo 路线创建、当前任务完成、前测提交、删除路线、资源生成启动和 Demo 录屏提示动作从 `GuidePage.tsx` 拆出。
- 本轮会话动作拆分后，`GuidePage.tsx` 从约 769 行降至约 662 行；页面层基本只剩数据查询、状态持有、阶段计算和子页面装配，后续可继续把状态组装改为更明确的 hooks。
- 本轮 Guide 会话动作质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 状态与数据 hooks 收口：新增 `useGuideDerivedState.ts`、`useGuidePageState.ts` 与 `useGuideRuntimeData.ts`，将课程模板选择、当前任务/阶段、Notebook 引用、资源产物、演示步骤、页面瞬态状态和导学 API 查询从 `GuidePage.tsx` 拆出。
- 本轮 hooks 拆分后，`GuidePage.tsx` 从约 662 行降至约 584 行；主页面进一步聚焦 URL seed、生命周期同步、动作编排和子页面装配，状态初始化与运行时数据查询可以独立维护。
- 本轮 Guide hooks 收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 动作与主阶段渲染收口：新增 `useGuideActions.ts` 和 `GuideMainStagePage.tsx`，将 busy 计算、画像刷新、资源任务监听、session/resource/demo/persistence action 组合，以及创建/前测/反馈/学习/完成主阶段渲染从 `GuidePage.tsx` 拆出。
- 本轮拆分后，`GuidePage.tsx` 从约 584 行降至约 341 行；页面层基本成为导学工作区壳层，保留 URL seed、生命周期同步、子页面切换、侧边路线抽屉和少量子页装配职责。
- 本轮 Guide 动作与主阶段收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Guide 工作区路由收口：新增 `GuideWorkspaceRouter.tsx`，将设置页、任务完成页、资源选择页、路线地图页、课程包页和主阶段页的分支渲染从 `GuidePage.tsx` 统一移出。
- 本轮工作区路由拆分后，`GuidePage.tsx` 从约 341 行降至约 200 行；主页面只负责准备 guide state/runtime/derived/actions、Hero、Demo 提示、工作区路由和路线抽屉，符合“页面壳层 + 子页面进入/返回”的前端组织方式。
- 本轮 Guide 工作区路由质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 前端结构收口：新增 `web/src/pages/settings/SettingsDiagnosticsPanel.tsx` 与 `settingsDiagnosticsUtils.ts`，将状态条、快速检测、服务连通性日志、运行拓扑、服务配置概览和启动向导状态从 `SettingsPage.tsx` 拆出。
- 本轮 Settings 诊断区拆分后，`SettingsPage.tsx` 从约 2164 行降至约 1639 行；设置首页保留配置表单、工作台偏好和诊断入口，排障工具箱进入独立模块，避免设置页继续堆叠所有诊断细节。
- 本轮 Settings 诊断区质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 工作台偏好收口：新增 `web/src/pages/settings/WorkbenchPreferences.tsx` 与 `settingsPreferenceUtils.ts`，将主题、语言、侧栏宣言、导航顺序编辑和偏好 key 计算从 `SettingsPage.tsx` 拆出。
- 本轮工作台偏好拆分后，`SettingsPage.tsx` 从约 1639 行降至约 1472 行；页面主体继续保留配置/偏好/诊断三块编排，偏好表单可独立维护，减少设置页继续膨胀的风险。
- 本轮 Settings 工作台偏好质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 模型配置控件收口：新增 `web/src/pages/settings/SettingsConfigControls.tsx`，将配置分区导航、配置卡片、供应商选择和模型预设输入控件从 `SettingsPage.tsx` 拆出，为后续继续拆模型配置编辑器打底。
- 本轮控件层拆分后，`SettingsPage.tsx` 从约 1472 行降至约 1317 行；保存逻辑、凭据处理和模型 catalog 变换暂时留在主配置编辑器内，避免一次性跨太多职责。
- 本轮 Settings 模型配置控件质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings catalog 逻辑收口：新增 `web/src/pages/settings/settingsCatalogUtils.ts`，将模型表单类型、供应商默认模型选择、共享凭据归一化、APIKey 兜底读取和 catalog 写回规则从 `SettingsPage.tsx` 拆出。
- 本轮 catalog 工具拆分后，`SettingsPage.tsx` 从约 1317 行降至约 956 行；页面层不再直接维护底层 provider/profile/model 变换细节，后续可以继续把模型配置编辑器本体拆成独立页面模块。
- 本轮 Settings catalog 逻辑质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 配置编辑器收口：新增 `web/src/pages/settings/SettingsCatalogEditor.tsx`，将模型配置表单、共享凭据面板、四类服务配置分区和启动向导完成按钮从 `SettingsPage.tsx` 拆出。
- 本轮编辑器拆分后，`SettingsPage.tsx` 从约 956 行降至约 335 行，主页面基本只负责设置页的数据查询、服务检测动作、启动向导状态、模块装配和结果提示，符合“页面壳层 + 独立任务模块”的前端组织方式。
- 本轮 Settings 配置编辑器质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 服务配置面板收口：新增 `web/src/pages/settings/SettingsServiceConfigPanels.tsx`，将 LLM、Embedding、Search、OCR 四个配置分区从 `SettingsCatalogEditor.tsx` 拆出。
- 本轮服务面板拆分后，`SettingsCatalogEditor.tsx` 从约 608 行降至约 255 行；编辑器层保留初始状态、提交和分区切换，具体表单交互由各服务面板独立维护，后续可按服务单独优化用户提示和校验。
- 本轮 Settings 服务配置面板质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 共享凭据收口：新增 `web/src/pages/settings/SharedCredentialsBlock.tsx`，将讯飞与硅基流动共享密钥表单从 `SettingsCatalogEditor.tsx` 拆出。
- 本轮共享凭据拆分后，`SettingsCatalogEditor.tsx` 从约 255 行降至约 175 行；编辑器层只保留配置初始化、共享凭据状态、保存提交和服务分区装配，密钥输入 UI 可独立维护。
- 本轮 Settings 共享凭据质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Settings 服务面板按职责拆分：新增 `LlmConfigPanel.tsx`、`EmbeddingConfigPanel.tsx`、`SearchConfigPanel.tsx` 与 `OcrConfigPanel.tsx`，保留 `SettingsServiceConfigPanels.tsx` 作为统一导出门面。
- 本轮服务面板细分后，每类服务配置拥有独立模块边界；`SettingsCatalogEditor.tsx` 的导入路径保持稳定，后续可按问答、向量、联网搜索、OCR 分别优化提示、校验和用户恢复路径。
- 本轮 Settings 服务面板细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 页面结构收口：新增 `web/src/pages/chat/chatPageUtils.ts`，将能力 URL seed、学习效果下一步动作解析、RAG 参数解析、状态文案和检索策略标签从 `ChatPage.tsx` 拆出。
- 本轮 Chat 工具层拆分后，`ChatPage.tsx` 从约 1875 行降至约 1693 行；页面层继续保留运行时编排和主要组件渲染，字符串协议解析与 RAG 配置解析进入可独立测试、可复用的工具模块。
- 本轮 Chat 工具层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 历史会话模块收口：新增 `web/src/pages/chat/SessionHistoryPanel.tsx`，将会话列表、重命名、删除、移动端/桌面复用状态从 `ChatPage.tsx` 拆出。
- 本轮历史会话拆分后，`ChatPage.tsx` 从约 1693 行降至约 1518 行；主页面不再维护历史列表内部草稿状态，后续可独立优化会话搜索、归档和学习线索恢复体验。
- 本轮 Chat 历史会话质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 资料与工具抽屉收口：新增 `web/src/pages/chat/ContextPanel.tsx`，将学习方式、能力参数、RAG 检索策略、辅助工具、资料范围、上下文引用和回答偏好从 `ChatPage.tsx` 拆出。
- 本轮抽屉模块拆分后，`ChatPage.tsx` 从约 1518 行降至约 1010 行；Chat 主页面基本聚焦运行时、会话、消息流、弹层开关和保存动作，RAG 策略选择成为可单独维护的用户任务模块。
- 本轮 Chat 资料与工具抽屉质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 画像首屏入口收口：新增 `web/src/pages/chat/ChatProfileStarter.tsx`，将“按画像继续”、导学入口、讲清卡点、生成练习、公开视频和图解快捷动作从 `ChatPage.tsx` 拆出。
- 本轮画像首屏拆分后，`ChatPage.tsx` 从约 1010 行降至约 739 行；首屏学习建议与快捷动作可以独立优化，主页面进一步收敛为消息流、会话加载、运行时状态和保存弹层编排。
- 本轮 Chat 画像首屏质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 底部状态与保存弹层收口：新增 `web/src/pages/chat/ChatContextStrip.tsx` 与 `SaveMessageModal.tsx`，将当前资料/RAG 状态条和保存到笔记本弹窗从 `ChatPage.tsx` 拆出。
- 本轮状态条与弹窗拆分后，`ChatPage.tsx` 从约 739 行降至约 581 行；RAG 当前上下文提示、保存学习资产表单都成为独立组件，主页面继续向运行时壳层收敛。
- 本轮 Chat 状态条与保存弹层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。

### 2026-05-15 可视化专项计划

- 新增 [比赛可视化抓眼计划书](./competition-visualization-wow-plan.md)，作为本次可视化层执行依据、调研记录和验收记录。
- 原定可视化开发优先级为：比赛演示驾驶舱、学习闭环轨道图、讯飞能力证明条、多智能体接力剧场、多模态资源 Studio、知识掌握星图/地铁图；这些优先项已全部完成并写入计划书完成记录。
- 实现原则已固化：不做泛泛数据大屏；每个视觉模块都要绑定赛题五项之一；默认隐藏内部日志、JSON 和协议字段；优先使用稳定课程模板与历史产物保障 7 分钟录屏。
- 首个落点已完成：`/demo` 与 `/guide` 课程产出包已承接评分点对齐卡、闭环轨道、讯飞工具链状态条和 Chat/Guide 多智能体接力展示。
- 本轮已完成可视化计划落地：新增 `/demo` 评委演示台、稳定课程包 `demoCoursePackage.ts`、[比赛可视化录屏与截图 Runbook](./competition-demo-visual-runbook.md)，并把 `/demo` 加入截图脚本与 Playwright 黑盒检查。
- `/demo` 现在可直接展示赛题五项证明、学习闭环轨道、讯飞能力证明条、7 分钟录屏路线、PPT 截图位和 `system/status` 服务状态，作为答辩开场直达入口。
- 本轮已将可视化专项从“计划落地”收口为“完成验收”：新增 [比赛可视化专项完成证据](./competition-visualization-completion-report.md)，沉淀完成结论、完成矩阵、前端落点、提交包证据和最终验证命令。
- 本轮已完成真实后端连通性复核：`http://127.0.0.1:8001/api/v1/system/status` 返回 200，LLM、Embedding/RAG、讯飞搜索、OCR、TTS 均显示为 `configured`，记录见 [比赛演示连通性检查记录](./competition-demo-connectivity-check.md)。
- 本轮已将完成报告纳入 `docs/README.md`、`scripts/check_competition_visuals.py`、`scripts/check_competition_readiness.py`、`scripts/export_competition_package.py`、`scripts/verify_competition_package.py` 和对应脚本测试，避免后续提交包漏掉完成证据。
- 本轮已为 `scripts/check_competition_visuals.py` 增加完成口径守护，自动检查关键文档中不再出现容易被误读为可视化专项未收口的措辞。
- 本轮正式提交包已重新导出并校验：`dist/competition_package` 与 `dist/sparkweave_competition_package.zip` 均通过校验；当前包内包含 87 个文件，`checksums.sha256` 覆盖 86 个文件。
- 本轮最终质量门通过：`python scripts/check_competition_visuals.py` 输出 `Competition visual plan is complete.`；`python scripts/check_competition_readiness.py --output dist/competition_readiness_latest.json` 输出 `All required competition materials are ready.`；脚本测试 `12 passed`；`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run test:e2e -- --grep "competition demo route"` 均已通过。

### 2026-05-15 长期产品化续做

- 继续推进 Chat 工作台壳层收口：新增 `web/src/pages/chat/ChatWorkbenchChrome.tsx`，将顶部栏、历史侧栏、移动端历史抽屉、资料与工具抽屉和保存成功提示从 `ChatPage.tsx` 拆出。
- 本轮工作台壳层拆分后，`ChatPage.tsx` 从约 581 行降至约 422 行；主页面基本聚焦会话运行时、消息提交、保存动作和页面模块装配，历史/上下文/提示层可以独立维护。
- 本轮 Chat 工作台壳层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 上下文抽屉内部收口：新增 `web/src/pages/chat/CapabilityConfigPanel.tsx` 与 `ProfileMiniCard.tsx`，将能力参数、Agentic RAG 策略预设和学习画像小卡片从 `ContextPanel.tsx` 拆出。
- 本轮上下文抽屉拆分后，`ContextPanel.tsx` 从约 508 行降至约 140 行；抽屉层只负责装配学习方式、工具、资料范围、上下文引用和回答偏好，RAG 策略配置成为可独立优化的用户任务模块。
- 本轮 Chat 上下文抽屉质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 会话动作收口：新增 `web/src/pages/chat/useChatSessionActions.ts`，将新建会话、URL 会话恢复、历史会话加载、重命名、删除和外部新聊天事件处理从 `ChatPage.tsx` 拆出。
- 本轮会话动作拆分后，`ChatPage.tsx` 从约 422 行降至约 366 行；页面层不再直接维护会话加载协议，后续可单独优化历史会话恢复、失败提示和会话归档体验。
- 本轮 Chat 会话动作质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat URL 入口协议收口：新增 `web/src/pages/chat/useChatAutoPrompt.ts`，将 `?new=1&prompt=...` 自动发起、能力 seed、知识库 seed 和 RAG 配置 seed 从 `ChatPage.tsx` 拆出。
- 本轮自动入口拆分后，`ChatPage.tsx` 从约 366 行降至约 345 行；知识库检索测试、学习效果和导学跳转到 Chat 的参数解析可以独立维护，页面层只负责挂载该入口能力。
- 本轮 Chat URL 入口协议质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Chat 保存学习资产流程收口：新增 `web/src/pages/chat/useChatNotebookSave.ts`，将保存目标消息、Notebook asset 构建、保存提交和成功提示自动消失从 `ChatPage.tsx` 拆出。
- 本轮保存流程拆分后，`ChatPage.tsx` 从约 345 行降至约 314 行；页面层只保留保存弹窗挂载，Notebook 写入协议和资产 metadata 组装进入独立 hook。
- 本轮 Chat 保存流程质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 助教证据区收口：新增 `web/src/pages/agents/AssistantDemoReadinessPanel.tsx` 与 `assistantEvidenceUtils.ts`，将比赛演示检查、录屏路线、赛题映射和共享证据引用解析从 `AssistantEvidencePanels.tsx` 拆出。
- 本轮助教证据区拆分后，`AssistantEvidencePanels.tsx` 从约 962 行降至约 740 行；资料来源、多模态产物和演示就绪检查分属独立模块，避免助教中心继续堆叠单个超大组件。
- 本轮 Agents 助教证据区质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 助教证据展示层收口：新增 `AssistantEvidenceSummaryGrid.tsx` 与 `AssistantCollaborationRoutePanel.tsx`，将资料来源/助教产物网格和学习协作路线从 `AssistantEvidencePanels.tsx` 拆出。
- 本轮展示层拆分后，`AssistantEvidencePanels.tsx` 从约 740 行降至约 608 行；主文件更聚焦证据数据组装、多模态预览状态和动作分发，展示结构可以独立演进。
- 本轮 Agents 助教证据展示层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agents 多模态预览流程收口：新增 `useAssistantMultimodalPreview.ts` 与 `AssistantMultimodalActionsPanel.tsx`，将讯飞 TTS 试听、OCR 图片读取/识别、资源动作按钮和预览状态从 `AssistantEvidencePanels.tsx` 拆出。
- 本轮多模态流程拆分后，`AssistantEvidencePanels.tsx` 从约 608 行降至约 275 行；主文件基本成为证据区编排层，OCR/TTS 运行时状态、资源预览 UI 和文件读取逻辑可独立维护。
- 本轮 Agents 多模态预览流程质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Memory 学习画像页面收口：新增 `web/src/pages/memory/MemoryEditor.tsx`、`EvidencePanel.tsx`、`memoryDisplayUtils.ts` 与 `profileChangeSummary.ts`，将手动记忆编辑器、画像证据筛选/摘要、日期百分比格式化和画像变更摘要生成从 `MemoryPage.tsx` 拆出。
- 本轮 Memory 拆分后，`MemoryPage.tsx` 从约 1726 行降至约 1137 行；主页面继续保留画像概览、校准交互和模块装配，记忆编辑、证据链展示和校准变更摘要具备独立维护边界。
- 本轮 Memory 学习画像页面质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Memory 学习推进风格收口：新增 `web/src/pages/memory/learningProgressStyle.ts`，将学习风格判定、证据信号摘要、下一步建议和近期节奏变化判断从 `MemoryPage.tsx` 拆出。
- 本轮学习推进风格拆分后，`MemoryPage.tsx` 从约 1137 行降至约 966 行；页面层不再直接承载画像推荐策略细节，后续可单独为该策略补充测试和调优规则。
- 本轮 Memory 学习推进风格质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Memory 画像概览壳层收口：新增 `web/src/pages/memory/ProfilePanel.tsx`，将画像概览视图从 `MemoryPage.tsx` 拆出，让 Memory 主页面只保留顶部说明、标签切换和三块子页面装配。
- 继续推进画像概览内部模块化：新增 `LearningStyleCard.tsx`、`ProfileChangeCard.tsx`、`ProfileLearningCards.tsx`、`profileGuideLinks.ts` 与 `profileTypes.ts`，将学习风格卡、画像变化提示、薄弱点/掌握度卡片、导学跳转链接和校准类型边界拆成独立模块。
- 本轮画像概览拆分后，`MemoryPage.tsx` 从约 966 行降至约 199 行，`ProfilePanel.tsx` 控制在约 350 行；Memory 页面形成“页面壳层 + profile/evidence/editor 子模块 + 策略工具”的结构，后续可单独优化画像、证据或手动记忆体验。
- 本轮 Memory 画像概览壳层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 开始推进 Notebook 页面收口：新增 `web/src/pages/notebook/RecordAssetPreview.tsx` 与 `recordAssetUtils.ts`，将记录资产预览 UI 和可视化/题目/动画/视频/导学 HTML 资产解析从 `NotebookPage.tsx` 拆出。
- 本轮 Notebook 资产预览拆分后，`NotebookPage.tsx` 从约 1394 行降至约 1202 行；记录卡片只负责展开/收起与操作按钮，资产渲染和 metadata 解析进入独立模块。
- 本轮 Notebook 资产预览质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Notebook 题目本收口：新增 `web/src/pages/notebook/QuestionNotebookPanels.tsx`，将分类管理、快速题目写入/查找、题目卡片和题目详情从 `NotebookPage.tsx` 拆出；Notebook 主页面从约 1202 行降至约 873 行。
- 继续推进 Notebook 页面化工作区收口：新增 `NotebookEntryPanels.tsx`、`NotebookRecordPanels.tsx` 与 `QuestionNotebookWorkspace.tsx`，将新建笔记本、手动记录、笔记本信息编辑、记录卡片、记录编辑器和题目本整页工作区拆出，主页面只保留路由状态、数据查询、动作编排和工作区切换。
- 继续推进 Notebook 浏览/详情壳层收口：新增 `NotebookBrowsePanels.tsx`，将左侧笔记本列表、空状态、刷新入口、右侧当前笔记本详情、记录列表和删除/编辑操作从 `NotebookPage.tsx` 拆出。
- 本轮 Notebook 完整拆分后，`NotebookPage.tsx` 进一步降至约 396 行；题目本、记录资产、记录编辑、新建/手动录入、浏览列表和详情工作区均具备独立维护边界，更符合“页面壳层 + 子页面进入/返回”的 Notion-like 组织方式。
- 本轮 Notebook 页面收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索测试面板收口：新增 `web/src/pages/knowledge/RagSearchSetupForm.tsx`、`RagSearchResultViews.tsx` 与 `RagAgenticTrace.tsx`，将检索预设/参数表单、结果概览/上下文/证据列表和 Agentic RAG 过程解释从 `RagSearchTestPanel.tsx` 拆出。
- 本轮 RAG 检索测试拆分后，`RagSearchTestPanel.tsx` 从约 821 行降至约 221 行；面板层只保留视图切换、恢复动作和结果路由，后续可以分别优化检索参数、证据链、召回上下文和深度检索解释。
- 本轮 RAG 检索测试面板质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库首页用户引导收口：新增 `web/src/pages/knowledge/KnowledgeNextStep.tsx` 与 `KnowledgeNextStepModel.ts`，将资料库“下一步建议”的 UI 展示和策略判断从 `KnowledgeActiveOverviewPanel.tsx` 拆出。
- 本轮知识库首页拆分后，`KnowledgeActiveOverviewPanel.tsx` 从约 435 行降至约 225 行；概览页只保留当前资料库状态、索引进度、操作按钮和工作区导航，下一步推荐可作为独立用户引导策略继续迭代。
- 本轮知识库首页引导质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 质量评测卡片收口：新增 `web/src/pages/knowledge/RagEvaluationPanels.tsx`，将评测方案选择、样本可信度、实验结论、质量门、策略收益、诊断摘要、异常样本和题型结果从 `RagEvaluationCard.tsx` 拆出。
- 本轮 RAG 评测卡片拆分后，`RagEvaluationCard.tsx` 从约 339 行降至约 130 行；卡片层只负责读取报告状态、组织摘要数据和装配评测子面板，具体用户解释与诊断展示可以独立维护。
- 本轮 RAG 评测卡片质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库工作区壳层收口：新增 `web/src/pages/knowledge/KnowledgeWorkspaceContentTypes.ts` 与 `KnowledgeWorkspaceRoutePanels.tsx`，将右侧工作区 props 契约和诊断/恢复/评测/检索/文档/上传/设置/文件夹/进度路由面板从 `KnowledgeWorkspaceContent.tsx` 拆出。
- 本轮工作区壳层拆分后，`KnowledgeWorkspaceContent.tsx` 从约 417 行降至约 68 行；主文件只负责当前资料库概览与工作区路由面板装配，后续可以按单个用户任务继续优化，不需要在同一个大文件里修改所有工作区。
- 本轮知识库工作区壳层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 评测格式化逻辑收口：新增 `ragEvaluationBaseFormat.ts`、`ragEvaluationDatasetFormat.ts`、`ragEvaluationExperimentFormat.ts`、`ragEvaluationQualityGateFormat.ts` 与 `ragEvaluationDiagnosticFormat.ts`，将预设/指标格式、样本可信度、实验结论、质量门翻译和诊断文案按职责拆开。
- 本轮格式化拆分后，`ragEvaluationFormat.ts` 从约 426 行降为 5 行稳定导出门面；现有组件导入路径不变，但后续优化质量门阈值、样本文案或诊断建议时可以只改对应模块。
- 本轮 RAG 评测格式化质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库文档管理收口：新增 `web/src/pages/knowledge/KnowledgeDocumentManagerPanels.tsx`，将文档列表、当前文档操作、文本预览和引用片段管理从 `KnowledgeDocumentManager.tsx` 拆出。
- 本轮文档管理拆分后，`KnowledgeDocumentManager.tsx` 从约 229 行降至约 121 行；主文件聚焦标题、空状态、错误状态和两栏装配，后续可以单独优化列表筛选、预览体验或片段删除确认。
- 本轮知识库文档管理质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库诊断面板收口：新增 `web/src/pages/knowledge/KnowledgeDiagnosticPanels.tsx`，将检查项列表、RAG readiness 摘要、环境预检、Docker/Milvus 状态格式化和修复命令展示从 `KnowledgeDiagnosticsPanel.tsx` 拆出。
- 本轮诊断面板拆分后，`KnowledgeDiagnosticsPanel.tsx` 从约 250 行降至约 99 行；主文件只负责打开/关闭动画、顶部状态和操作按钮，环境预检与检索可用性说明可以独立迭代。
- 本轮知识库诊断面板质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库索引进度面板收口：新增 `web/src/pages/knowledge/KnowledgeProgressPanels.tsx`，将任务状态摘要、进度条、关键进展和完整处理记录从 `KnowledgeProgressPanel.tsx` 拆出。
- 本轮进度面板拆分后，`KnowledgeProgressPanel.tsx` 从约 224 行降至约 94 行；主文件只负责进度页标题、返回入口、WebSocket 状态和清理操作，处理记录展示可独立优化。
- 本轮知识库进度面板质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索预检表单收口：新增 `web/src/pages/knowledge/RagSearchSetupPanels.tsx`，将聊天带入复测卡、检索方案预设、问题模板、基础参数、深度检索参数和提交动作从 `RagSearchSetupForm.tsx` 拆出。
- 本轮预检表单拆分后，`RagSearchSetupForm.tsx` 从约 285 行降至约 113 行；主文件只负责表单提交和子面板装配，后续可以单独优化参数说明、问题模板和 Agentic RAG 配置体验。
- 本轮 RAG 检索预检表单质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索结果视图收口：新增 `web/src/pages/knowledge/RagSearchResultPanels.tsx`，将结果概览卡、恢复建议、Chat 带证据交接、结果导航卡、证据列表和无证据空状态从 `RagSearchResultViews.tsx` 拆出。
- 本轮结果视图拆分后，`RagSearchResultViews.tsx` 从约 253 行降至约 104 行；视图层只负责 summary/context/sources 三个页面装配，结果卡片和用户下一步动作可独立维护。
- 本轮 RAG 检索结果视图质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 质量评测展示收口：新增 `web/src/pages/knowledge/RagEvaluationResultPanels.tsx` 与 `RagEvaluationDiagnosticPanels.tsx`，将实验结论、质量门、策略收益、题型结果和异常样本诊断从 `RagEvaluationPanels.tsx` 拆出。
- 本轮评测展示拆分后，`RagEvaluationPanels.tsx` 从约 327 行降至约 107 行，并保留原导出门面；评测入口、样本可信度、结果解释和诊断建议各自拥有独立维护边界。
- 本轮 RAG 质量评测展示质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agentic RAG 过程解释收口：新增 `web/src/pages/knowledge/RagAgenticTracePanels.tsx`，将深度检索头部状态、质量指标、阈值、回退原因、下一步建议、分支修复、子查询召回和上下文打包摘要从 `RagAgenticTrace.tsx` 拆出。
- 本轮 Agentic RAG 解释拆分后，`RagAgenticTrace.tsx` 从约 215 行降至约 87 行；主文件只负责读取结果结构、计算质量状态并装配解释面板，后续可以单独优化每个解释区的用户文案。
- 本轮 Agentic RAG 过程解释质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库恢复策略收口：新增 `web/src/pages/knowledge/KnowledgeRecoveryTypes.ts` 与 `KnowledgeRecoveryChecks.ts`，将修复向导类型、检查项生成、状态归一化和数字解析从 `recovery.ts` 拆出。
- 本轮恢复策略拆分后，`recovery.ts` 从约 243 行降至约 160 行，并保留原有类型与函数导出；后续新增连接异常、索引缺失、任务失败等恢复场景时可以分别维护检查项和决策分支。
- 本轮知识库恢复策略质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库首页概览收口：新增 `web/src/pages/knowledge/KnowledgeActiveOverviewPanels.tsx`，将概览头部操作、状态事实网格、索引进度卡和资料库摘要从 `KnowledgeActiveOverviewPanel.tsx` 拆出。
- 本轮首页概览拆分后，`KnowledgeActiveOverviewPanel.tsx` 从约 225 行降至约 145 行；主文件聚焦下一步推荐、当前工作区路径、工作区导航和概览装配，用户可见状态展示可以单独维护。
- 本轮知识库首页概览质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库工作区导航收口：新增 `web/src/pages/knowledge/KnowledgeWorkspaceNavItems.tsx`，将导航入口文案、图标、徽标、状态色和数量格式化从 `KnowledgeWorkspaceNav.tsx` 拆出。
- 本轮工作区导航拆分后，`KnowledgeWorkspaceNav.tsx` 从约 212 行降至约 101 行；组件层只负责概览/紧凑两种导航布局、返回概览入口和向量提示，后续调整入口策略时可以只改导航模型。
- 本轮知识库工作区导航质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索预检表单细分：新增 `web/src/pages/knowledge/RagSearchSetupHandoff.tsx`、`RagSearchSetupInputs.tsx` 与 `RagSearchSetupActions.tsx`，将聊天带入复测、检索参数输入和表单动作从 `RagSearchSetupPanels.tsx` 拆出。
- 本轮预检表单细分后，`RagSearchSetupPanels.tsx` 降为 8 行稳定导出门面；`RagSearchSetupForm.tsx` 的导入路径保持不变，后续可分别优化问题模板、深度检索参数说明和结果复测动作。
- 本轮 RAG 预检表单细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 Agentic RAG 解释面板细分：新增 `web/src/pages/knowledge/RagAgenticTraceSummaryPanels.tsx` 与 `RagAgenticTraceDetailPanels.tsx`，将质量摘要、阈值、原因和下一步建议，与分支修复、子查询召回、上下文打包明细分开维护。
- 本轮解释面板细分后，`RagAgenticTracePanels.tsx` 降为 12 行稳定导出门面；`RagAgenticTrace.tsx` 保持装配层职责不变，后续可以分别优化质量解释文案和分支召回明细。
- 本轮 Agentic RAG 解释面板细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库文档管理页细分：新增 `web/src/pages/knowledge/KnowledgeDocumentListPanel.tsx`、`KnowledgeDocumentDetailPanel.tsx`、`KnowledgeDocumentPreviewPanel.tsx` 与 `KnowledgeDocumentVectorChunksPanel.tsx`，将文档列表、选中文档操作、文本预览和引用片段列表拆成独立用户任务模块。
- 本轮文档管理细分后，`KnowledgeDocumentManagerPanels.tsx` 降为 2 行稳定导出门面；`KnowledgeDocumentManager.tsx` 保持标题、空状态、错误状态和两栏装配职责，后续可分别优化文档筛选、预览体验和片段删除确认。
- 本轮知识库文档管理细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索结果页细分：新增 `web/src/pages/knowledge/RagSearchResultSummaryPanel.tsx`、`RagSearchResultActionPanels.tsx` 与 `RagSearchSourcesPanel.tsx`，将结果摘要、恢复/Chat 交接/结果导航和证据来源列表拆开。
- 本轮检索结果页细分后，`RagSearchResultPanels.tsx` 降为 8 行稳定导出门面；`RagSearchResultViews.tsx` 继续只负责 summary/context/sources 三个页面装配，后续可分别优化结果状态解释、下一步行动和证据片段展示。
- 本轮 RAG 检索结果页细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 检索测试面板编排收口：新增 `web/src/pages/knowledge/RagSearchTestPanelHeader.tsx`、`RagSearchTestPanelRoutes.tsx` 与 `RagSearchTestPanelTypes.ts`，将顶部标题/返回操作、结果子页路由和 props 契约从 `RagSearchTestPanel.tsx` 拆出。
- 本轮检索测试面板拆分后，`RagSearchTestPanel.tsx` 从约 222 行降至约 156 行；主文件聚焦检索结果状态派生、恢复动作分发和表单/结果区装配，页面标题与结果子页可以独立迭代。
- 本轮 RAG 检索测试面板编排质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库工作区路由收口：新增 `web/src/pages/knowledge/KnowledgeWorkspaceRagRoutePanels.tsx` 与 `KnowledgeWorkspaceResourceRoutePanels.tsx`，将诊断/修复/评测/预检等 RAG 路由和文档/上传/设置/文件夹/进度等资源路由分组。
- 本轮工作区路由拆分后，`KnowledgeWorkspaceRoutePanels.tsx` 从约 192 行降至约 12 行；主文件只负责两组路由装配，后续新增用户任务页面时可以按分组扩展，不再继续膨胀同一个路由文件。
- 本轮知识库工作区路由质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 RAG 预检输入区细分：新增 `web/src/pages/knowledge/RagSearchPresetPanel.tsx`、`RagSearchQueryField.tsx`、`RagSearchBasicSettingsGrid.tsx` 与 `RagSearchAgenticSettingsPanel.tsx`，将检索预设、问题模板、基础参数和深度检索参数拆成独立表单区域。
- 本轮预检输入区拆分后，`RagSearchSetupInputs.tsx` 从约 220 行降至 4 行稳定导出门面；后续优化某个参数组的文案、默认值或控件样式时，不会牵动整张预检表单。
- 本轮 RAG 预检输入区质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库诊断面板细分：新增 `web/src/pages/knowledge/KnowledgeDiagnosticChecksPanel.tsx`、`KnowledgeReadinessFacts.tsx` 与 `KnowledgePreflightFacts.tsx`，将检查项、RAG readiness 摘要和环境预检/修复命令拆成独立诊断区域。
- 本轮诊断面板拆分后，`KnowledgeDiagnosticPanels.tsx` 从约 179 行降至 3 行稳定导出门面；连接检查页后续可以分别优化检查项文案、检索可用性摘要和本地环境修复建议。
- 本轮知识库诊断面板细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库索引进度面板细分：新增 `web/src/pages/knowledge/KnowledgeProgressStatusPanel.tsx`、`KnowledgeProgressMeterPanel.tsx` 与 `KnowledgeProgressLogsPanel.tsx`，将任务状态摘要、进度/关键进展和完整处理记录拆成独立模块。
- 本轮进度面板拆分后，`KnowledgeProgressPanels.tsx` 从约 179 行降至 3 行稳定导出门面；索引进度页后续可分别优化任务状态翻译、进度动画和日志可读性。
- 本轮知识库索引进度面板细分质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库工作区类型契约收口：新增 `web/src/pages/knowledge/KnowledgeWorkspaceOverviewTypes.ts`、`KnowledgeWorkspaceRagTypes.ts` 与 `KnowledgeWorkspaceResourceTypes.ts`，将概览、RAG/诊断/评测/预检和文档/上传/设置/进度等资源管理 props 契约按职责拆开。
- 本轮类型契约拆分后，`KnowledgeWorkspaceContentTypes.ts` 从约 195 行降至约 48 行统一导出门面；后续扩展某一组工作区页面时，可以只维护对应类型文件。
- 本轮知识库工作区类型契约质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进全局用户体验与性能调研：参考 React `lazy`/`Suspense`、Vite dynamic import 分包、TanStack Router route preloading 与 web.dev 减少 JavaScript 的官方建议，在现有页面级懒加载基础上为 `web/src/router.tsx` 启用 `defaultPreload: "intent"`，用户将要进入页面时提前准备目标路由代码/数据，降低切页等待感。
- 继续推进全局 AppShell 工程收口：新增 `AppShellModel.ts`、`AppShellStatus.tsx`、`AppShellSidebar.tsx`、`AppShellMobile.tsx` 与 `AppShellMorePanel.tsx`，将运行状态、侧栏、移动导航、更多功能面板和共享工具从 `AppShell.tsx` 拆出；`AppShell.tsx` 从约 852 行降至约 182 行，只保留全局布局状态和面板装配。
- 继续优化路由懒加载的用户体验：将 `RootLayout.tsx` 的居中加载卡片改为 Notion-like 工作区骨架屏，避免切页时内容区域突然塌成小卡片，同时严格遵守 `DESIGN-notion.md` 的 8px 圆角约束。
- 本轮全局导航与壳层优化质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进多模态结果查看器按需加载：新增 `LazyVisualizationViewer.tsx` 与 `LazyMediaResultViewers.tsx`，让 Chat、Guide、Notebook 只在实际出现可视化、数学动画、语音讲解或外部视频结果时再加载对应查看器；普通文本问答和常规页面浏览不再同步装入这些结果查看组件。
- 本轮多模态结果按需加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进全局性能收口：将 `web/src/main.tsx` 中的 KaTeX 全局样式移出首屏入口，并在 `MarkdownRenderer` 内随 KaTeX 运行时按需加载 `katex/dist/katex.min.css`；普通页面和普通路由预加载链路不再提前牵连 `visualization` 大块。
- 本轮构建产物复核确认：`index` 路由依赖表不再包含 `visualization-*.js`，只有 `MarkdownRenderer` 与 `VisualizationViewer` 在公式或图表真正出现时动态加载该块；保留 Mermaid/KaTeX/Chart.js 的懒加载能力。
- 本轮全局性能收口质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进可视化依赖分层：调整 `web/vite.config.ts` 的手动分包规则，将 KaTeX 拆为 `math-typesetting` 懒加载块，将 Mermaid、D3、Dagre、ELK 等图示引擎拆为 `diagrams` 懒加载块，避免普通公式渲染下载完整 Mermaid 引擎。
- 本轮分包复核确认：公式渲染路径只动态加载约 259KB 的 `math-typesetting` 与 29KB KaTeX CSS；Mermaid 图示路径才动态加载约 2.52MB 的 `diagrams`；首屏 `index` 路由依赖表仍不包含这两个重型块。
- 本轮可视化依赖分层质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进导学工作区按需加载：将 `web/src/pages/guide/GuideWorkspaceRouter.tsx` 的主舞台、路线图、资源选择、任务完成和课程产出包等子页面改为 `React.lazy` + `Suspense`，切页时使用 Notion-like 骨架屏承接加载状态。
- 本轮导学工作区拆分后，`GuidePage` 构建块从约 199KB 降至约 66.75KB，`GuideMainStagePage`、`GuideRouteMapPage`、`GuideCoursePackagePanel` 等重型子页面被拆入独立块，导学入口不再同步加载所有子任务。
- 本轮导学工作区按需加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库工作区任务级懒加载：将 `KnowledgePage.tsx` 的创建资料库和工作区内容改为按需加载，并在 `KnowledgeWorkspaceRoutePanels.tsx`、`KnowledgeWorkspaceRagRoutePanels.tsx`、`KnowledgeWorkspaceResourceRoutePanels.tsx` 内按 RAG/资源管理/具体任务拆分动态块。
- 本轮资料库性能拆分后，`KnowledgePage` 构建块从约 138KB 降至约 39.74KB，工作区概览块约 16.97KB；诊断、修复、RAG 评测、检索测试、文档管理、上传、设置、文件夹和索引进度均只在用户进入对应页面时加载。
- 本轮知识库工作区懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进聊天页按需加载：在 `MessageBubble.tsx` 中将协作轨迹、RAG 证据链和题目查看器改为 `React.lazy`，在 `ChatWorkbenchChrome.tsx` 中将任务快照和上下文配置面板延后到抽屉打开时加载，并将 `SaveMessageModal` 从 `ChatPage.tsx` 首包移出。
- 本轮聊天页性能拆分后，`ChatPage` 构建块从约 106KB 降至约 56.61KB；普通文本对话不再提前下载协作轨迹、证据链、练习题查看器、上下文配置和保存弹窗代码，用户需要时再进入对应交互。
- 本轮聊天页按需加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 AI 助教中心任务级懒加载：在 `AgentsPage.tsx` 中保留顶部概览、最近助教和标签导航的同步体验，将助教列表/创建、助教对话、能力矩阵、高级配置、证据工作区和文件/渠道管理改为进入对应 tab 时再加载。
- 本轮助教中心拆分后，`AgentsPage` 构建块从约 95KB 降至约 35.34KB；`AgentConfigPanels`、`AssistantCreateWizard`、`SparkBotChatPanel`、`SparkBotLibraryPanels`、`BotSettingsPanels`、`AssistantEvidencePanels` 和 `AssistantWorkspacePanels` 均成为独立任务块。
- 本轮 AI 助教中心懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进学习画像页面任务级懒加载：在 `MemoryPage.tsx` 中将画像概览、证据依据和手动补充三个 tab 改为 `React.lazy`，并把只在刷新/校准后使用的画像变更摘要逻辑改为动态导入。
- 本轮画像页拆分后，`MemoryPage` 构建块从约 76KB 降至约 7.65KB；`ProfilePanel`、`EvidencePanel`、`MemoryEditor` 和 `profileChangeSummary` 均只在用户进入对应任务或触发对应动作时加载。
- 本轮学习画像页懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进导学主舞台阶段级懒加载：在 `GuideMainStagePage.tsx` 中将创建路线、诊断题、学习反馈、当前任务和完成报告五个阶段面板改为按当前阶段加载，保留主舞台编排逻辑和阶段切换体验。
- 本轮导学阶段拆分后，`GuideMainStagePage` 构建块从约 73.8KB 降至约 6.13KB；`GuideCreateRoutePanel`、`GuideDiagnosticStagePanel`、`GuideFeedbackStagePanel`、`GuideCurrentTaskPanel`、`GuideCompleteStagePage` 和资源产物分页器均被延后到对应阶段。
- 本轮导学主舞台阶段懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进画像概览内部任务级懒加载：在 `ProfilePanel.tsx` 中保留顶部“现在只做这一件事”的即时体验，将学习效果闭环、学习推进方式、画像变化提示、薄弱点校准和掌握度校准延后到对应区域加载。
- 本轮画像概览拆分后，`ProfilePanel` 构建块从约 57KB 降至约 17.58KB；`LearningEffectLoopCard` 单独成为约 31KB 的学习闭环块，`LearningStyleCard`、`ProfileLearningCards` 和 `ProfileChangeCard` 均被拆成独立维护单元。
- 本轮画像概览懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进设置页任务级懒加载：新增 `web/src/pages/settings/SettingsStatusStrip.tsx`，将设置页同步首屏需要的服务状态条与 legacy 文案渲染从诊断面板中拆出；`SettingsPage.tsx` 将模型配置编辑器、诊断面板和工作台偏好改为 `React.lazy` + `Suspense`。
- 本轮设置页拆分后，`SettingsPage` 构建块从约 52KB 降至约 13KB；`SettingsCatalogEditor`、`SettingsDiagnosticsPanel` 和 `WorkbenchPreferences` 均成为用户进入对应任务时再加载的独立块，设置首页不再同步装入所有配置和排障细节。
- 本轮设置页任务级懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进聊天页首包收口：将 `ChatProfileStarter` 从 `ChatPage.tsx` 同步入口移为 `React.lazy`，并为新会话空态增加轻量骨架屏；已有会话和普通对话不再提前加载画像引导、快捷行动和空态演示布局。
- 本轮聊天页空态拆分后，`ChatPage` 构建块从约 56.61KB 降至约 50.61KB；`ChatProfileStarter` 单独成为约 8.39KB 的新会话空态块，用户只有进入空白对话时才加载。
- 本轮聊天页空态懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进导学页辅助功能按需加载：将 `GuideSupportDrawer` 与 `DemoRecordingCueCard` 从 `GuidePage.tsx` 同步入口移为懒加载；路线支持抽屉只在用户打开时加载，比赛录屏提示只在 demo 路线确实出现提示时加载，并补充对应骨架兜底。
- 本轮导学页辅助入口拆分后，`GuidePage` 构建块从约 66.59KB 降至约 59.04KB；`GuideSupportDrawer` 独立约 4.55KB，`GuideDemoCards` 独立约 5.52KB，主导学流程不再提前装入侧边抽屉和 demo 专用提示。
- 本轮导学页辅助懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进笔记页任务级加载与数据按需查询：将新建笔记本、手动记录和题目本工作区改为 `React.lazy`，并为 `useQuestionEntries`、`useQuestionCategories` 增加 `enabled` 选项，让默认浏览笔记本时不再提前请求题目本数据。
- 本轮笔记页拆分后，`NotebookPage` 构建块从约 36.19KB 降至约 23.39KB；`NotebookEntryPanels` 独立约 3.98KB，`QuestionNotebookWorkspace` 独立约 11.40KB，用户进入题目本或录入任务时再加载对应功能。
- 本轮笔记页任务级懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库默认页数据压力收口：为 `useKnowledgeVectorChunks` 增加 `enabled` 选项，并在 `KnowledgePage.tsx` 中仅当用户进入“文档管理”工作区且存在选中文档时加载向量片段；后台任务完成后的批量刷新也不再在概览页主动刷新片段列表。
- 本轮知识库数据路径优化后，默认知识库概览仍保留文档数、向量数、诊断入口和恢复建议，但不再提前拉取首个文档的 80 条向量片段，文档管理页进入后再加载诊断用片段。
- 本轮知识库数据按需查询质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进 AI 助教中心数据按需查询：为 `useSparkBotChannelSchemas`、`useSparkBotSouls`、`useSparkBotDetail`、`useSparkBotFile`、`useSparkBotFiles`、`useSparkBotHistory` 与 Agent 配置 hooks 增加 `enabled` 选项，并在 `AgentsPage.tsx` 中仅当用户进入对应工作区时加载渠道 schema、能力详情和单文件正文。
- 本轮 AI 助教中心数据门控后，默认入口仍保留助教概览、最近学习和学习建议；渠道配置、能力详情与工作区单文件正文进入对应 tab 后再请求，渠道区补充加载态避免把未加载误显示为空配置。
- 本轮 AI 助教中心数据门控质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进实验室页面数据按需查询：为 `useKnowledgeBases` 增加 `enabled` 选项，并在 `PlaygroundPage.tsx` 中仅当用户切到“能力”模式时读取知识库列表；默认“工具”模式不再提前请求学习资料库数据。
- 本轮实验室数据门控后，工具调试入口保持轻量，能力模式下的知识库选择区域增加加载提示，避免切换时把未加载状态误判为没有知识库。
- 本轮实验室数据门控质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进协作写作页面数据按需查询：为 `useNotebooks`、`useCoWriterOperation` 与 `useCoWriterToolCalls` 增加 `enabled` 选项，并在 `CoWriterPage.tsx` 中仅当存在保存目标或生成结果时读取笔记本列表，仅当用户打开审计详情时读取操作详情和工具调用记录。
- 本轮协作写作数据门控后，写作入口与历史列表保持即时可用；保存到笔记本时补充“正在读取笔记本...”加载提示，审计区打开前不再提前请求深层追踪数据。
- 本轮协作写作数据门控质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进题库实验室任务级加载与数据门控：将 `QuizViewer` 从 `QuestionLabPage.tsx` 同步入口移为 `React.lazy`，并让 Notebook 列表只在生成出题目、具备保存意图后读取；知识库选择与生成入口仍保持首屏可用。
- 本轮题库实验室优化后，`QuizViewer` 成为约 7.90KB 独立块，题库页首包约 17.40KB；生成结果出现前不再下载答题查看器，也不会把尚未读取的 Notebook 列表误显示为可保存目标。
- 本轮题库实验室任务级懒加载质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进图像解题页数据门控：将 `VisionPage.tsx` 的 Notebook 列表读取延后到出现 GeoGebra 指令或导师讲解之后，保存区在结果出现前显示“解析完成后选择 Notebook”，结果出现后再进入真实保存目标选择。
- 本轮图像解题页优化后，上传题图、快速解析和实时解题入口不再被保存用数据请求牵连；解析结果可保存时补充“正在读取 Notebook...”状态，避免把未加载状态误判为没有笔记本。
- 本轮图像解题页数据门控质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进前端信息架构产品化：将设置页从“模型配置、工作台偏好、连接检测堆叠在同一页”改为真实路由入口，新增 `/settings/models`、`/settings/preferences` 与 `/settings/diagnostics` 三个子页面，`/settings` 只保留面向用户的任务入口卡片和服务状态摘要。
- 本轮设置页改造后，用户进入设置时先选择一个明确任务，子页面顶部提供“返回设置”路径；模型与服务、工作台偏好、连接检测互不堆叠，后续可按同样模式继续整理知识库、AI 助教和实验室。
- 本轮设置页路由化质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
- 继续推进知识库信息架构路由化：新增 `/knowledge/create` 与 `/knowledge/{workspace}` 真实任务页入口，`/knowledge` 保持资料库概览；上传、文档管理、连接检查、恢复、质量评测、检索测试、文件夹同步、设置和索引进度都通过 URL 进入和返回，不再只依赖单页 state 切换。
- 本轮知识库页面改造后，`KnowledgePage.tsx` 的 `view/workspace` 改为由 TanStack Router 路径派生，避免 effect 内同步 setState；无效 `/knowledge/*` 路径会回到概览页，聊天证据链 handoff 仍可落到检索测试页。
- 本轮知识库路由化质量门通过：`npm.cmd run lint`、`npm.cmd run build`、`npm.cmd run check:design`、`npm.cmd run check:api-contract`、`npm.cmd run check:replacement`。
