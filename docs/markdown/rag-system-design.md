# RAG 系统设计

SparkWeave 的资料问答不只把问题交给大模型直接回答，也不是简单“搜一下资料”。它的核心是 Agentic RAG：学生先把课件、讲义、实验文档或课程资料放进资料库，系统把它们整理成可检索片段；提问时先判断问题是否需要拆分，再按多个查找视角检索、合并来源、判断证据覆盖度，最后把可用片段交给回答过程。回答旁边会展示来源，评委可以看到结论从哪份资料、哪个片段来。

这部分对应赛题里的“多智能体协同的资源生成”和“智能辅导”。评委可以在 [资料页](../../web/screenshots-knowledge.png) 和 [问问题页](../../web/screenshots-chat.png) 看到它的前端呈现。

## 资料从哪里进入系统

资料页承担三个学习动作：创建资料库、上传课程资料、用资料提问。

| 动作 | 系统处理 |
| --- | --- |
| 创建资料库 | 在 `data/knowledge_bases/` 下建立独立目录，并写入资料库配置 |
| 上传文件 | 保存原始文件，按文件类型抽取文本、图片或 Markdown 内容 |
| 建立索引 | 把内容切成片段，生成向量，写入 Milvus 或本地索引 |
| 查看文档 | 前端可以预览原文整理结果，确认资料是否处理成功 |
| 重建索引 | 当模型或 Embedding 配置变化时，可以重新处理资料 |

资料库不是一次性样例数据。评委可以新增资料、重新索引，再用同一问题观察来源是否变化。

## 一次资料问答怎么发生

以“请结合课程资料解释梯度下降为什么会震荡”为例：

| 步骤 | 系统动作 | 页面上能看到什么 |
| --- | --- | --- |
| 1. 选择资料库 | 本轮问题绑定课程资料库 | 问问题页显示资料库名称 |
| 2. 规划查找方式 | 根据问题类型决定快速查找，还是进入 Agentic RAG 多路查找 | 来源卡片显示检索方式 |
| 3. 拆分并查找片段 | 复杂问题会拆成多个查找视角，并发检索相关片段 | 展示来源数量、片段标题、页码和关键词 |
| 4. 合并与质量判断 | 合并不同视角的来源，检查来源数量、相关性、覆盖度和回答材料长度 | 页面显示“来源可用”“来源偏弱”或“无来源” |
| 5. 汇总回答 | 把资料片段作为依据生成学习讲解 | 回答旁保留资料来源 |
| 6. 继续学习 | 学生可追问、保存记录或进入导学练习 | 来源和学习记录可以继续被后续任务使用 |

这样做的重点不是让学生理解检索参数，而是让学生知道：这次回答有没有查到资料，查到的资料强不强，关键结论能不能追溯。

## Agentic RAG 的实现链路

这条链路在代码里是能追到的。资料页或问问题页发起 `rag-test` 时，`knowledge_rag_ops.py` 会把 `agentic_rag`、最大上下文、最大来源数、最少来源数、覆盖度阈值、相关覆盖度阈值、最低上下文长度和最低分数这些参数整理成检索配置。之后由 `RagSupportService.search()` 进入真正的检索流程。

| 阶段 | 代码位置 | 发生了什么 |
| --- | --- | --- |
| 参数进入 | `sparkweave/api/routers/knowledge_rag_ops.py` | 把前端请求里的 `agentic_*` 参数转成搜索配置，并在返回结果中保留 `agentic_quality`、`agentic_repair`、`subquery_results` 等字段 |
| 查询规划 | `sparkweave/services/rag_support/query_planner.py` | `plan_rag_queries()` 判断是否需要多路查找，并生成若干 focused retrieval query |
| 并发检索 | `sparkweave/services/rag_support/service.py` | `_agentic_search()` 用并发限制执行多个 `_single_search()`，每个分支都能复用普通 RAG 的改写、检索和来源整理 |
| 来源合并 | `sparkweave/services/rag_support/agentic_merge.py` | 合并不同分支的来源，形成 `agentic_evidence_groups` 和 `agentic_context_pack`，避免同一片段重复占用上下文 |
| 质量门 | `sparkweave/services/rag_support/agentic_quality.py` | 计算来源数、上下文长度、子查询覆盖率、相关覆盖率、最高分和平均分，给出 `weak` 或 `sufficient` |
| 分支修复 | `sparkweave/services/rag_support/agentic_repair.py` | 对没有证据或相关性弱的分支重新检索，只有候选结果更好时才接受 |
| 保守回退 | `sparkweave/services/rag_support/service.py` | 修复后仍不足时，回到单路检索，并把 `agentic_fallback_reason` 和失败计划返回给前端 |
| 前端展示 | `web/src/pages/knowledge/RagAgenticTrace.tsx` | 展示质量指标、阈值、修复记录、子查询来源和下一步建议 |

这也是 SparkWeave 把 RAG 做成“agentic”的地方：它不是多查几次就结束，而是让查询计划、证据覆盖、弱分支修复和回退原因都进入可见结果。评委可以把同一个问题分别用简单问法和复杂问法测试，观察 query plan、来源数量和质量状态是否发生变化。

## 证据链怎么展示

问问题页的资料回答会带一个“资料来源”区域。它主要展示几类信息：

| 信息 | 说明 |
| --- | --- |
| 来源状态 | “来源可用”“来源偏弱”“无来源”，提醒学生回答可信度 |
| 检索过程 | 展示问题是否被拆成多个查找视角，以及每个视角找到多少来源 |
| 来源片段 | 展示文件名、页码、片段内容、相关度和命中关键词 |
| 质量判断 | 展示覆盖度、相关来源比例、是否触发弱分支补强或保守回退 |
| 下一步建议 | 如果来源不足，提示学生补资料、换问法或进入资料库预检 |

当资料不足时，系统不会把回答包装成“有依据”。页面会明确提示本轮没有可展示来源，建议先检查资料库或补充资料。

## 普通检索与 Agentic RAG

SparkWeave 同时支持两种资料查找方式：

| 方式 | 适合场景 | 处理方式 |
| --- | --- | --- |
| 快速查找 | 问题集中，例如“什么是过拟合” | 直接按当前问题检索资料片段 |
| Agentic RAG | 问题包含多个意图，例如“解释原理、给例子、比较优缺点” | 先拆成多个查找视角，分别查资料，再合并来源 |
| 弱证据补强 | 某些查找视角没有找到足够资料 | 对薄弱分支重新检索，仍不够稳时回退到保守快速查找 |

Agentic RAG 的价值在于“知道自己查得稳不稳”。它会留下查询计划、子问题结果、来源合并记录和质量报告。评委在资料页可以看到它不是简单把几个片段拼起来，而是先判断这些片段是否足以支撑回答；证据偏弱时，系统会尝试修复薄弱分支，修复失败再回到更保守的检索结果。

## 资料质量如何判断

系统不会只看“有没有搜到东西”。它会同时看几类信号：

| 信号 | 含义 |
| --- | --- |
| 来源数量 | 是否至少有可展示的资料片段 |
| 覆盖度 | 多个查找视角是否都找到材料 |
| 相关性 | 片段是否命中问题关键词或语义相近内容 |
| 回答材料长度 | 给模型的资料上下文是否足够支撑回答 |
| 片段去重 | 避免同一段资料重复占据回答材料 |

这些判断会变成前端的状态标签。评委可以展开“查看来源与检索过程”，看到它不是只给一个答案，而是把查找过程和可用性判断一起交出来。

## 与课程学习的关系

RAG 不是独立的资料管理工具，它会进入学习主线：

| 学习场景 | RAG 的作用 |
| --- | --- |
| 学习页 | 为导学任务提供课程资料依据，避免路线脱离课程内容 |
| 问问题页 | 回答课程相关问题时给出引用片段 |
| 练习生成 | 出题时可以围绕课程资料里的知识点和表达方式 |
| 图解生成 | 把资料里的概念关系转成结构图或流程图 |
| 学习记录 | 学生保存资料问答后，资源使用会影响学习画像 |

因此，完整课程不只是一个 JSON 模板，还可以配套讲义、实验文档和参考资料，供资料问答和资源生成使用。

SparkWeave 里的课程模板通过 `source_materials` 指向课件。仓库提供脚本把这些课件同步到课程资料库：

```powershell
python scripts/sync_course_materials_to_kb.py --stage-only
```

这条命令会把深度学习和智能机器人系统的课件复制到 `data/knowledge_bases/<课程名>/raw/`，并把资料库状态标为需要重建索引。评审环境里启动 Docker Compose、Milvus 和 Embedding 后，可以继续执行：

```powershell
python scripts/sync_course_materials_to_kb.py --index
```

这样资料页和问问题页检索的就是当前课程课件，而不是旧样例或临时上传文件。

## 科大讯飞相关落点

资料问答可以结合讯飞相关能力：

| 能力 | 在 RAG 中的作用 |
| --- | --- |
| 星火大模型 | 用于资料问答、归纳解释和学习资源生成 |
| Spark Embedding | 可作为资料向量化配置，支撑语义检索 |
| ONE SEARCH | 当课程资料不足时，可补充公开资料搜索 |
| 讯飞 OCR | 把扫描课件、图片题或讲义截图转成可检索文本 |
| 公式识别 | 数学题和公式截图可以先识别，再进入资料问答或解题 |
| 图片理解 | 对板书、示意图和课程截图做多模态辅导 |

这些能力在设置页配置，在工具层和资料处理链路中按需使用。

## 接口与代码落点

| 模块 | 位置 |
| --- | --- |
| 资料库接口 | `sparkweave/api/routers/knowledge.py` |
| RAG 查询与评测接口 | `sparkweave/api/routers/knowledge_rag_ops.py` |
| 资料库管理 | `sparkweave/knowledge/manager.py` |
| 课程课件同步 | `scripts/sync_course_materials_to_kb.py` |
| 文件上传与处理 | `sparkweave/api/routers/knowledge_uploads.py`、`sparkweave/knowledge/add_documents.py` |
| RAG 服务入口 | `sparkweave/services/rag_support/service.py` |
| 检索策略 | `sparkweave/services/rag_support/retrieval_policy.py` |
| 问题改写与拆分 | `sparkweave/services/rag_support/query_transform.py`、`query_planner.py` |
| 回答材料打包 | `sparkweave/services/rag_support/context_pack.py` |
| Agentic RAG 来源合并 | `sparkweave/services/rag_support/agentic_merge.py` |
| 多路查找质量判断 | `sparkweave/services/rag_support/agentic_quality.py` |
| 弱分支补强与回退 | `sparkweave/services/rag_support/agentic_repair.py` |
| 前端资料页 | `web/src/pages/KnowledgePage.tsx`、`web/src/pages/knowledge/` |
| 前端来源展示 | `web/src/components/results/RagEvidenceChain.tsx`、`web/src/pages/knowledge/RagAgenticTrace.tsx` |

主要接口包括：

| 接口 | 作用 |
| --- | --- |
| `GET /api/v1/knowledge/list` | 查看资料库列表 |
| `POST /api/v1/knowledge/create` | 创建资料库并上传文件 |
| `POST /api/v1/knowledge/{kb_name}/upload` | 给已有资料库补充文件 |
| `GET /api/v1/knowledge/{kb_name}/documents` | 查看资料库中的文档 |
| `GET /api/v1/knowledge/{kb_name}/documents/{document_id}/preview` | 预览文档整理结果 |
| `POST /api/v1/knowledge/{kb_name}/rag-test` | 单独测试一次资料检索，可传入 `agentic_rag`、上下文长度和来源数量等参数 |
| `POST /api/v1/knowledge/{kb_name}/rag-eval` | 用题目集评估检索质量 |
| `POST /api/v1/knowledge/{kb_name}/reindex` | 重新建立索引 |

## 演示时可以这样看

1. 进入资料页，选择一门课程资料库。
2. 打开文档列表或预览，确认资料已经被系统整理。
3. 在资料页或问问题页提出一个课程相关问题。
4. 展开“资料来源”，查看文件名、页码、片段内容和命中关键词。
5. 换一个更宽的问题，观察系统是否拆成多个查找视角，并查看每个视角的来源数量。
6. 如果页面提示来源偏弱，查看是否触发弱分支补强；再补充资料或调整问题，观察来源状态是否改善。

这条演示线能说明系统不是只有自然语言回答，而是有资料入库、检索、质量判断和来源展示。

## 边界说明

- 资料问答质量取决于资料库内容、索引状态和 Embedding 配置。
- 当没有可用来源时，页面会提示“无来源”，回答不能视为课程资料结论。
- 修改 Embedding 模型或向量维度后，已有资料库需要重新索引。
- 课程资料和运行索引位于 `data/knowledge_bases/` 下，提交时应区分课程样例、运行生成数据和个人资料。
- 外部搜索只能作为补充来源，正式课程结论仍应优先来自课程资料库。
