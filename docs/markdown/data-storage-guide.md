# 数据存储规范

本篇面向评委说明 SparkWeave 的数据边界：哪些数据随项目提交，哪些数据由系统运行后生成，哪些数据不应放进提交包。这样做的目的很直接，既要让系统可以完整运行，也要避免把真实账号、真实学生记录或未授权资料一起交出去。

## 数据分层

| 位置 | 内容 | 提交建议 |
| --- | --- | --- |
| `data/course_templates/` | 完整高校课程模板，学习页可直接选用 | 随源码提交 |
| `data/eval_corpora/` | RAG 检索评估材料和小型课程语料 | 可提交脱敏样例 |
| `data/knowledge_bases/` | 资料页上传的文档、解析信息和知识库配置 | 示例材料可提交，真实课程资料需确认授权 |
| `data/knowledge_bases/<知识库>/raw/` | 原始 PDF、Markdown、文本等资料 | 只放可公开展示的材料 |
| `data/knowledge_bases/<知识库>/milvus_storage/` | 向量库集合标记和索引信息 | 通常由运行环境生成 |
| `data/milvus/` | Milvus 本地数据、向量索引和检索状态 | 不作为源码必交内容 |
| `data/user/` | 用户设置、学习记录、会话记录、笔记和生成结果 | 不提交真实个人数据 |
| `data/user/learner_profile/evidence.jsonl` | 学习行为和反馈证据流水 | 运行时生成或提交脱敏样例 |
| `data/user/learner_profile/profile.json` | 当前学习画像结果 | 运行时生成或提交脱敏样例 |
| `data/user/workspace/guide/` | 学习路径、任务进度、学习评估结果 | 运行后生成 |
| `data/user/workspace/notebook/` | 用户保存的学习笔记 | 运行后生成 |
| `data/user/chat_history.db` | 问答与学习会话记录 | 运行后生成 |
| `data/user/settings/` | 前端设置页保存的本地配置 | 不提交真实密钥 |
| `web/screenshots-*.png` | 当前前端页面截图 | 可作为文档和展示材料使用 |
| `.env.example` | 配置项示例 | 随源码提交 |
| `.env` | 本机密钥和私有地址 | 不提交 |

## 课程模板

赛题要求自行构造至少一门完整高校专业课程。SparkWeave 把课程主线放在 `data/course_templates/`，当前提交包含两门可选课程：

| 文件 | 课程 | 节点数 | 任务数 | 用途 |
| --- | --- | ---: | ---: | --- |
| `deep_learning/deep_learning_foundations.json` | 深度学习 | 14 | 14 | 主课程，依据 `ppts/深度学习/` 课件整理 |
| `intelligent_robot_systems/intelligent_robot_systems.json` | 智能机器人系统 | 11 | 11 | 新增实践课程，依据 `ppts/智能机器人系统/` 课件整理 |

这些模板不是简单的标题列表。它们包含课程目标、学习产出、知识节点、任务安排、项目里程碑、评价方式和学习样例。学习页创建学习路线时，可以直接读取模板，再结合学习画像生成下一步任务和资源建议。

课程模板可用下面的命令核验：

```bash
python scripts/check_course_templates.py
```

这个检查会验证课程 `id`、课程名称、节点关系、任务归属和学习样例是否完整，避免出现课程能看到但不能正常选用的问题。

## 课程资料库

课程课件通过模板里的 `source_materials` 同步到资料库。当前演示课程的对应关系如下：

| 课程 | 资料库目录 | 原始资料数量 | 说明 |
| --- | --- | ---: | --- |
| 深度学习 | `data/knowledge_bases/深度学习/raw/` | 14 | 对应 `ppts/深度学习/` |
| 智能机器人系统 | `data/knowledge_bases/智能机器人系统/raw/` | 11 | 对应 `ppts/智能机器人系统/` |

同步命令：

```bash
python scripts/sync_course_materials_to_kb.py --stage-only
```

这一步只保证“课程资料已经进入资料库原始文件区”。如果资料页或问问题页要直接检索这些文件，需要在完整运行环境里重建索引：

```bash
python scripts/sync_course_materials_to_kb.py --index
```

因此提交材料里可以保留可公开展示的课程样例资料，但不要把真实学生上传资料、未授权教材或本机 Milvus 数据混进去。

## 运行数据如何产生

SparkWeave 启动后会把学习过程写入 `data/user/`，把资料库数据写入 `data/knowledge_bases/` 和向量索引目录。一次正常学习流程大致会产生这些数据：

1. 学习页选择课程并生成路线，系统在 `data/user/workspace/guide/` 保存学习会话、任务进度和阶段评估。
2. 学生完成任务、提交反馈或进行练习，系统把证据追加到 `data/user/learner_profile/evidence.jsonl`。
3. 学习画像服务读取证据后生成 `data/user/learner_profile/profile.json`，页面上的薄弱点、偏好和下一步建议由这里支撑。
4. 资料页上传课程文档，系统在 `data/knowledge_bases/<知识库>/raw/` 保存原始资料，并在向量检索层建立索引。
5. 问资料或问课程问题时，系统读取知识库结果，把引用来源带回前端，用于证明回答不是凭空生成。
6. 用户保存笔记时，笔记写入 `data/user/workspace/notebook/`，后续问答可以把笔记作为上下文。

这些数据体现了“学习画像 -> 个性化路径 -> 资料问答 -> 学习评估”的连续过程。它们应该来自真实操作，而不是只在文档里描述。

## 提交边界

建议随项目提交的内容：

- 源码、前端工程、Docker 配置和启动说明。
- `data/course_templates/` 中的完整课程模板。
- `.env.example` 等不含密钥的配置示例。
- 可公开展示的少量示例资料，放入 `data/knowledge_bases/` 时需确认来源清楚。
- 当前前端截图和配套说明文档。

不建议随项目提交的内容：

- `.env`、真实 API Key、账号 Token、私有服务地址。
- 真实学生姓名、学习记录、聊天记录、语音材料和个人画像。
- 未获授权的教材、课件、论文全文或课程资料。
- `data/milvus/` 这类由数据库服务生成的大体量运行数据。
- 本机日志、临时文件、前端构建产物和依赖目录。

如果提交材料需要展示学习记录，可以使用脱敏样例：保留知识点、任务、分数、反馈类型，去掉姓名、账号、学校、手机号、邮箱、原始语音和可识别个人身份的文本。

## 配置与密钥

讯飞模型、Embedding、搜索、OCR、语音和工作流等服务配置通过设置页或环境变量注入。提交包只提供字段名称和示例格式，不提供真实密钥。

评委在本地运行时，可以先使用 `.env.example` 确认需要哪些变量，再按实际账号填入 `.env`。设置页会展示服务连接状态，也会对敏感字段做遮盖显示。若没有配置真实密钥，系统仍可进入前端工作台，但涉及外部服务的能力会明确显示未配置或返回带标记的替代结果。

## 可复现性

SparkWeave 不依赖提交包里的个人运行数据来证明功能。评委从干净环境启动后，可以按下面顺序重新得到主要数据：

1. 用 Docker Compose 启动前后端服务。
2. 打开学习页，选择 `深度学习` 课程并生成学习路线。
3. 在资料页创建知识库、上传可公开的课程材料。
4. 在问问题页面基于资料提问，查看回答中的来源。
5. 完成一个学习任务并提交反馈，在记录页查看画像和建议变化。

这条路线覆盖了课程模板、资料检索、学习记录、画像更新和资源推荐。即使不提交 `data/user/`，评委也可以现场生成新的学习过程。

## 代码落点

| 代码位置 | 说明 |
| --- | --- |
| `sparkweave/services/paths.py` | 统一管理运行数据路径 |
| `sparkweave/services/learner_evidence.py` | 记录学习证据 |
| `sparkweave/services/learner_profile.py` | 生成学习画像 |
| `sparkweave/services/guide_v2.py` | 保存学习路线、任务进度和学习评估 |
| `sparkweave/knowledge/manager.py` | 管理知识库目录和配置 |
| `sparkweave/services/rag_support/` | 资料解析、向量索引和检索服务 |
| `sparkweave/api/routers/knowledge.py` | 资料页相关 API |
| `sparkweave/api/routers/learner_profile.py` | 画像页相关 API |
| `web/src/pages/GuidePage.tsx` | 学习页 |
| `web/src/pages/KnowledgePage.tsx` | 资料页 |
| `web/src/pages/MemoryPage.tsx` | 记录与画像页 |
| `web/src/pages/NotebookPage.tsx` | 笔记页 |

## 边界说明

数据存储规范不是为了让提交包看起来更满，而是为了让评委能分清“项目能力”和“个人运行痕迹”。课程模板、源码和配置示例应当稳定；学习记录、知识库索引、画像结果和本机日志应当可以在运行后重新生成。这样提交包更干净，也更容易在评审环境里复现。
