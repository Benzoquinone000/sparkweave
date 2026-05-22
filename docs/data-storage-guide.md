# SparkWeave 数据存储规范

范围：说明 SparkWeave 当前本地数据目录、持久化边界、提交边界和迁移检查。本文档只描述代码中已经存在的路径和约定；没有统一代码落点的目录不写成当前能力。

开发者新增数据落点前，应先确认数据属于用户运行时、知识库、课程模板、评测样本还是临时产物。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| 提交边界 | `.gitignore`, `scripts/check_release_safety.py` |
| 用户运行时路径 | `sparkweave/services/paths.py`, `sparkweave/services/session_store.py` |
| 运行时迁移 | `scripts/migrate_user_data.py` |
| Memory / Profile | `sparkweave/services/memory.py`, `sparkweave/services/learner_evidence.py`, `sparkweave/services/learner_profile.py` |
| 知识库目录 | `sparkweave/knowledge/manager.py`, `sparkweave/services/kb_config.py`, `sparkweave/api/routers/knowledge.py` |
| Milvus 索引 | `sparkweave/services/rag_support/pipelines/milvus.py`, `docker-compose.yml` |
| 课程模板 | `sparkweave/services/guide_v2.py`, `scripts/check_course_templates.py` |

## 1. 存储原则

- 运行时用户数据默认不提交。
- 可提交数据必须是脱敏、可复现、可解释的课程模板或评测样例。
- 知识库原文、真实上传资料、Milvus 数据、学习画像、会话记录和日志默认视为私有数据。
- 新增存储目录必须能说明读写服务、数据格式、清理方式和安全边界。

`.gitignore` 已忽略主要运行时目录：`data/user/`、`data/memory/`、`data/knowledge_bases/`、`data/milvus/`、`data/eval_corpora/`。

## 2. 目录总览

| 路径 | 数据类型 | 是否建议提交 | 主要代码 |
| --- | --- | --- | --- |
| `data/user/` | 设置、会话、工作区、日志、记录本、导学任务 | 否 | `sparkweave/services/paths.py` |
| `data/memory/` | 公开长期记忆 `PROFILE.md`、`SUMMARY.md` | 否 | `sparkweave/services/memory.py` |
| `data/knowledge_bases/` | 知识库配置、原始资料、解析结果、RAG 评测结果 | 否 | `sparkweave/knowledge/manager.py` |
| `data/milvus/` | Milvus etcd、minio、standalone 持久化数据 | 否 | `docker-compose.yml`, `sparkweave/services/rag_support/` |
| `data/course_templates/` | 内置课程模板 | 是，需脱敏 | `sparkweave/services/guide_v2.py` |
| `data/eval_corpora/` | 本地评测语料和实验样本 | 默认否，样例可提交 | `scripts/prepare_rag_eval_corpus.py` |
| `web/.runtime/` | 前端本地运行缓存 | 否 | Vite / 截图脚本 |

## 3. 用户运行时数据

`data/user/` 由 `PathService` 统一管理，根路径来自 `sparkweave/services/paths.py`。

当前主要结构：

```text
data/user/
├── chat_history.db
├── logs/
├── settings/
└── workspace/
    ├── chat/
    │   ├── chat/
    │   ├── deep_solve/
    │   ├── deep_question/
    │   ├── deep_research/
    │   ├── math_animator/
    │   └── _detached_code_execution/
    ├── co-writer/
    ├── guide/
    └── notebook/
```

重要文件：

| 文件 | 说明 |
| --- | --- |
| `data/user/chat_history.db` | 统一会话、消息、turn event 和错题记录 SQLite 数据库 |
| `data/user/settings/` | 前端设置页保存的模型、Embedding、搜索、OCR、语音、偏好配置 |
| `data/user/workspace/guide/` | 导学会话、学习路径、学习效果反馈和导学记忆 |
| `data/user/workspace/notebook/` | 用户记录本、保存的问答、错题和复盘 |
| `data/user/logs/` | 本地运行日志 |

新增运行时数据时，应优先通过 `PathService` 获取路径，避免在业务代码中散落硬编码目录。

## 4. 记忆与学习画像

长期记忆与画像分层存储：

| 层 | 路径 | 代码 | 说明 |
| --- | --- | --- | --- |
| Memory | `data/memory/PROFILE.md`, `data/memory/SUMMARY.md` | `sparkweave/services/memory.py` | 面向上下文注入的长期记忆 |
| Evidence Ledger | `data/user/learner_profile/evidence.jsonl` | `sparkweave/services/learner_evidence.py` | 学习行为证据账本 |
| Learner Profile | `data/user/learner_profile/profile.json` | `sparkweave/services/learner_profile.py` | 从证据聚合出的画像快照 |
| Guide Memory | `data/user/workspace/guide/v2/learner_memory.json` | `sparkweave/services/guide_v2.py` | 导学链路使用的跨会话学习记忆 |

这些数据都可能包含用户目标、薄弱点、偏好和历史上下文，不进入公开提交包。

## 5. 知识库数据

知识库默认根目录为 `data/knowledge_bases/`。

典型结构：

```text
data/knowledge_bases/
├── kb_config.json
└── <kb_name>/
    ├── metadata.json
    ├── raw/
    ├── extracted_markdown/
    ├── milvus_storage/
    │   └── metadata.json
    └── rag_eval/
        └── latest.json
```

| 子目录或文件 | 说明 |
| --- | --- |
| `kb_config.json` | 知识库列表、默认配置、RAG provider 和重建标记 |
| `<kb_name>/raw/` | 用户上传或同步的原始资料 |
| `<kb_name>/extracted_markdown/` | PDF、文档和图片解析后的文本结果 |
| `<kb_name>/milvus_storage/metadata.json` | Milvus 索引标记、collection、embedding 配置和 schema 信息 |
| `<kb_name>/rag_eval/` | 当前知识库的检索质量评测记录 |

知识库目录常包含真实课程资料、PDF、笔记、代码和检索结果，默认不提交。比赛交付如需包含资料，应使用脱敏后的公开课程材料，并在 README 中说明来源。

## 6. Milvus 数据

Docker Compose 使用 `data/milvus/` 持久化 Milvus 相关数据，通常包含：

```text
data/milvus/
├── etcd/
├── minio/
└── standalone/
```

注意事项：

- `docker compose down` 只停止容器，不会清空项目下的 `data/milvus/`。
- `docker compose down -v` 会删除 Docker volume，但不会自动删除项目目录中的手动挂载数据。
- 切换 `MILVUS_URI`、Embedding 维度或检索模式后，旧索引可能不可复用，应重新整理资料库。
- 不要提交 `data/milvus/`，体积大且不可读，还可能包含私有资料向量。

## 7. 课程模板与评测样本

`data/course_templates/` 是当前项目可以稳定提交的演示数据目录。

要求：

- 模板必须是完整高校课程或明确课程片段。
- 不包含真实学生信息、账号、密钥、私有上传文件路径。
- 字段结构通过 `python scripts/check_course_templates.py` 检查。
- 比赛演示建议固定一门主课程，README、截图、录屏和答辩材料保持同一条主线。

`data/eval_corpora/` 默认是本地评测语料目录。只有脱敏、可公开、具有说明意义的样例才适合提交到 `docs/examples/`。

## 8. 备份、清理与重建

常用 Docker 操作：

```powershell
docker compose ps
docker compose logs -f backend
docker compose restart backend
docker compose down
```

清理建议：

| 场景 | 建议 |
| --- | --- |
| 只想重启服务 | `docker compose restart backend frontend` |
| 想停止项目 | `docker compose down` |
| 想重建镜像 | `docker compose up --build` |
| 想清空用户会话 | 备份后删除 `data/user/chat_history.db` |
| 想重建资料索引 | 在资料页重新整理资料库，或按知识库目录清理索引标记 |
| 想迁移旧数据 | `python scripts/migrate_user_data.py --verify`，确认后再执行迁移 |

删除 `data/` 下目录前必须确认路径。不要递归删除不确定的计算路径。

## 9. 提交边界

禁止提交：

- `.env`、真实 API key、OAuth token、账号 JSON、临时凭证。
- `data/user/`、`data/memory/`、`data/knowledge_bases/`、`data/milvus/`。
- 用户上传的真实课件、作业、聊天记录、学习画像、语音和截图。
- Milvus、SQLite、日志、缓存、临时导出包。

可以提交：

- `.env.example` 中的占位配置。
- `data/course_templates/` 中的脱敏课程模板。
- `docs/examples/` 中的脱敏评测样例。
- README 引用的当前前端截图和 PNG 架构图。

提交前运行：

```powershell
python scripts/check_release_safety.py
python scripts/check_course_templates.py
git diff --check
```

## 10. 新增数据落点清单

- [ ] 已确认数据属于用户运行时、知识库、课程模板、评测样本或临时产物。
- [ ] 通过 `PathService` 或已有 manager 获取路径。
- [ ] 已说明文件格式、schema 版本和迁移策略。
- [ ] 已确认 `.gitignore` 覆盖私有运行时数据。
- [ ] 已补充测试或检查脚本，避免提交损坏数据。
- [ ] README 或 `docs/` 已说明公开交付边界。
- [ ] 不把真实用户数据、密钥、账号 JSON 和日志写入示例。

## 11. 测试覆盖

| 测试或脚本 | 覆盖 |
| --- | --- |
| `tests/services/test_runtime_storage_guard.py` | 运行时公开输出边界 |
| `tests/knowledge/test_kb_directory_layout.py` | 知识库目录、raw 文件和索引 marker |
| `tests/knowledge/test_registry_audit.py` | 知识库 registry 与目录一致性 |
| `tests/services/memory/test_memory_service.py` | `data/memory/` 读写和刷新 |
| `tests/services/test_learner_evidence.py` | Evidence Ledger 读写 |
| `tests/services/test_learner_profile.py` | `profile.json` 聚合输出 |
| `tests/scripts/test_check_release_safety.py` | 私有数据和密钥检查 |

聚焦命令：

```powershell
uv run pytest tests/services/test_runtime_storage_guard.py tests/knowledge/test_kb_directory_layout.py tests/knowledge/test_registry_audit.py tests/services/memory/test_memory_service.py tests/services/test_learner_evidence.py tests/services/test_learner_profile.py tests/scripts/test_check_release_safety.py -q
python scripts/check_release_safety.py
```

## 12. 限制与待实现

- 当前没有统一的 `data/tmp/` manager；临时文件主要使用系统临时目录或具体任务目录。
- 当前默认本地单用户数据目录；多用户部署前需要按用户隔离 `data/user/`、知识库、日志和配置。
- `PathService.is_public_output_path()` 只对白名单产物做公开输出判断，不表示整个 `data/user/` 可公开。
