# SparkWeave API 开发规范

范围：约定 SparkWeave 后端 API 的目录职责、接口设计、错误处理、流式通信、前后端契约和测试要求。本文档只描述当前仓库已有约定和代码入口；未落地能力不写成当前 API。

部署和配置说明见根目录 `README.md` 与 [配置指南](./configuration-guide.md)。

代码事实来源：

| 模块 | 事实来源 |
| --- | --- |
| FastAPI 应用入口 | `sparkweave/api/main.py` |
| 业务路由 | `sparkweave/api/routers/` |
| 请求体与限制 | `sparkweave/core/input_limits.py`, `sparkweave/api/request_limits.py` |
| 前端 API 调用 | `web/src/lib/api.ts` |
| 前端共享类型 | `web/src/lib/types.ts` |
| 合约检查 | `scripts/check_web_api_contract.py`, `tests/scripts/test_check_web_api_contract.py` |
| API 测试 | `tests/api/` |

## 1. API 总览

后端 API 基于 FastAPI。应用入口在 `sparkweave/api/main.py`，所有业务路由按功能拆分到 `sparkweave/api/routers/`。

统一前缀为 `/api/v1`。主要路由如下：

| 模块 | 前缀 | 主要职责 |
| --- | --- | --- |
| Chat | `/api/v1/chat`、`/api/v1/ws` | 对话、会话、统一 WebSocket |
| Solve | `/api/v1/solve` | 旧解题 WebSocket 和解题会话 |
| Guide V2 | `/api/v1/guide/v2` | 学习路线、任务、资源、报告、课程产出包 |
| Guide Legacy | `/api/v1/guide` | 旧导学会话接口 |
| Knowledge | `/api/v1/knowledge` | 知识库、资料上传、RAG 测试、索引进度 |
| Dashboard | `/api/v1/dashboard` | 最近活动和入口聚合 |
| Notebook | `/api/v1/notebook` | 学习记录本、记录保存、摘要记录 |
| Question | `/api/v1/question`、`/api/v1/question-notebook` | 题目生成、题目记录、答题复盘 |
| Learner Profile | `/api/v1/learner-profile`、`/api/v1/memory` | 学习画像、证据、记忆 |
| Learning Effect | `/api/v1/learning-effect` | 学习效果报告、事件、下一步动作 |
| Sessions | `/api/v1/sessions` | 统一会话查询和测验结果写入 |
| Settings | `/api/v1/settings` | 设置 catalog、偏好、服务诊断任务 |
| System | `/api/v1/system` | 运行状态、供应商连通性测试、预览能力 |
| Speech | `/api/v1/speech` | ASR 转写、语音评测 |
| SparkBot | `/api/v1/sparkbot` | 课程助教、技能、文件、渠道、历史 |
| Plugins | `/api/v1/plugins` | 工具和能力调试执行 |
| Agent Config | `/api/v1/agent-config` | Agent 配置展示 |
| Co-writer | `/api/v1/co_writer` | 写作改写、批注、导出 |
| Vision Solver | `/api/v1/vision` | 图像解题和流式分析 |

## 2. 路由组织原则

- 每个文件只负责一个业务域，避免把新接口塞进过大的通用路由。
- 业务逻辑优先放在 `sparkweave/services/`，路由层只做输入校验、服务调用和响应转换。
- 与知识库相关的复杂操作优先拆到 `knowledge_*` 辅助模块，保持 `knowledge.py` 可读。
- 前端已有稳定路径时，不轻易改路径；必要时保留兼容层并在前端逐步迁移。
- 新路由必须在 `sparkweave/api/main.py` 注册，除非是已有 router 的内部拆分模块。

## 3. 请求与响应模型

### 3.1 模型定义

- 简单接口可在 router 文件内定义 Pydantic 模型。
- 复用范围较大的模型应放到对应领域模型文件，例如 `knowledge_models.py`。
- 响应字段使用 snake_case，前端类型保持一致。
- 数字限制、字符串长度、文件大小限制应集中到常量，避免散落魔法值。
- 跨业务共享输入限制优先复用 `sparkweave/core/input_limits.py`；API 请求体大小限制优先复用 `sparkweave/api/request_limits.py`。

示例结构：

```python
class CreateThingRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class CreateThingResponse(BaseModel):
    id: str
    title: str
    created_at: float
```

### 3.2 响应稳定性

- 新增字段优先追加，不删除旧字段。
- 字段语义发生变化时，优先新增字段并保留旧字段一段时间。
- 返回给前端的枚举值要有明确 fallback，避免未知值导致页面崩溃。
- 涉及工具结果、RAG 证据、讯飞能力的响应要保留 metadata，便于前端展示证据链。

### 3.3 题目本写入

`sparkweave/api/routers/question_notebook.py` 的 `POST /api/v1/question-notebook/entries/upsert` 当前行为：

- 默认写入或更新题目本记录，并通过 `build_quiz_answer_events()` 写入学习画像证据。
- `record_evidence=false` 时只保存题目本记录，不追加画像证据；练习实验室把已记录到 `learning-effect` 的错题镜像到题目本时使用该模式，避免同一次作答重复计分。
- `session_id` 以 `manual-` 开头且不存在时，接口会自动创建标题为“题目快录”的本地会话。

`web/src/pages/QuestionLabPage.tsx` 当前把整组练习提交结果写入 `/api/v1/learning-effect/events`：

- 事件 `id` 包含题目 ID 和 `attempt_count`，同一轮重做会形成新的尝试记录。
- 前端去重签名使用题目 ID、用户答案、正确性和 `attempt_count`，不使用耗时字段。
- 错题镜像到题目本时仍复用同一个 `manual-question-lab` 会话，便于错题本集中复盘。

## 4. 错误处理

### 4.1 HTTP 错误

| 场景 | 建议状态码 |
| --- | --- |
| 参数无效 | `400` |
| 未授权或 API key 错误 | `401` / `403` |
| 资源不存在 | `404` |
| 冲突或重复创建 | `409` |
| 上传过大 | `413` |
| 外部服务不可用 | `502` / `503` |
| 未预期内部错误 | `500` |

错误信息应面向用户或维护者可理解，不暴露密钥、完整请求头、真实 token、账号 JSON 路径。

### 4.2 外部服务失败

外部供应商调用失败时：

- 设置诊断接口返回结构化失败原因。
- 学习主流程优先降级，不让单个外部能力打断整个任务。
- 讯飞相关能力默认使用离线替补，并在结果中标记 `fallback: true`。
- 测试中使用 mock 或替补，不依赖真实外网服务。

## 5. WebSocket 与流式事件

SparkWeave 有多类流式入口：

| 入口 | 说明 |
| --- | --- |
| `/api/v1/ws` | 统一对话 WebSocket，优先使用 |
| `/api/v1/chat` | 旧聊天 WebSocket |
| `/api/v1/knowledge/{kb_name}/progress/ws` | 知识库索引进度 |
| `/api/v1/question/generate` | 题目生成流 |
| `/api/v1/vision/solve` | 图像解题流 |
| `/api/v1/sparkbot/{bot_id}/ws` | 课程助教对话 |

流式接口要求：

- 事件必须可序列化为 JSON。
- 长任务必须能发送阶段、进度、结果和错误事件。
- WebSocket 断开后后台任务要能安全收尾，不抛未处理异常。
- 旧入口新增功能时，应优先评估能否转到 `/api/v1/ws` 统一协议。

## 6. 前后端契约

前端 API 调用集中在 `web/src/lib/api.ts`，共享类型集中在 `web/src/lib/types.ts`。

新增或修改接口时：

1. 更新后端 router 和 Pydantic 模型。
2. 更新 `web/src/lib/api.ts` 的请求函数。
3. 更新 `web/src/lib/types.ts` 的类型。
4. 如果涉及页面展示，更新对应 `web/src/pages/` 或 `web/src/components/`。
5. 运行 API 合约检查。

```powershell
python scripts/check_web_api_contract.py
```

如果新增接口暂时不需要前端调用，也要确认合约检查不会误报。必要时在检查脚本中明确说明排除原因。

## 7. 文件上传与输入限制

- 上传接口必须限制文件大小、类型和路径。
- 保存到本地的数据必须使用受控目录，不能信任客户端传入路径。
- 用户输入进入 LLM、RAG、Notebook 或画像前，应遵守 `sparkweave/core/input_limits.py` 中的限制。
- Notebook metadata、会话偏好、工具参数等结构化字段要设置 JSON 大小上限。
- 对图片、音频、PDF 等大文件，优先只保存必要结果和引用，不把原始大对象写进响应。

## 8. 安全与隐私

- API key 防护逻辑在 `sparkweave/api/main.py`。
- 不在日志中打印完整密钥、Authorization header、账号 JSON、OAuth token。
- 本地 `.env`、`data/user/`、临时凭证不作为公开提交材料。
- 公开接口不要允许访问任意本地路径、内网 URL 或未校验文件。
- SparkBot、插件和外部工具调用必须遵守已有的 URL、安全执行和文件边界检查。

## 9. 新增 API 检查清单

- [ ] 路由文件职责清晰，没有把业务逻辑堆在 router 中。
- [ ] 请求 / 响应模型有明确字段和限制。
- [ ] 外部服务失败有可理解错误或降级路径。
- [ ] 前端 `api.ts` 和 `types.ts` 已同步。
- [ ] 相关 API 测试已添加或更新。
- [ ] `python scripts/check_web_api_contract.py` 通过。
- [ ] 没有泄露密钥、真实路径或敏感数据。

## 10. 推荐验证

后端 API 改动最少运行：

```powershell
uv run ruff check .
python scripts/check_web_api_contract.py
python scripts/check_release_safety.py
```

涉及具体业务时运行对应测试，例如：

```powershell
uv run pytest tests/api/test_system_router.py -q
uv run pytest tests/api/test_knowledge_router.py -q
uv run pytest tests/api/test_guide_v2_router.py -q
uv run pytest tests/api/test_api_main.py -q
```

如果改动影响前端调用，再运行：

```powershell
cd web
npm run lint
npm run check:api-contract
npm run build
```

## 11. 限制与待实现

- `/api/v1/chat`、`/api/v1/solve`、`/api/v1/guide` 仍保留旧入口；新增能力优先评估是否能进入 `/api/v1/ws` 或现有业务 router。
- API 合约检查覆盖前端声明路径与后端路由匹配，不等于完整 OpenAPI schema diff。
- 外部供应商的真实连通性依赖本地配置和官网权限，CI 默认只验证 mock、离线替补或结构化失败路径。
