# CLI 与 API 使用

SparkWeave 提供 CLI、WebSocket API、HTTP API 和 Python facade。主运行链路最终进入 `SparkWeaveApp` 和 runtime manager，因此能力、工具和事件流保持一致。

## CLI

安装：

```powershell
pip install -r requirements/cli.txt
pip install -e .
```

运行默认聊天能力：

```powershell
sparkweave run chat "Explain Fourier transform"
```

运行深度解题：

```powershell
sparkweave run deep_solve "Solve x^2=4"
```

运行题目生成：

```powershell
sparkweave run deep_question "Linear algebra" --config num_questions=5
```

进入交互式 REPL：

```powershell
sparkweave chat
```

赛前材料与检查：

```powershell
sparkweave competition-templates
sparkweave competition-check
sparkweave competition-demo --template ai_learning_agents_systems
sparkweave competition-package --template ai_learning_agents_systems
sparkweave competition-verify dist/sparkweave_competition_package.zip
sparkweave competition-preflight --template ai_learning_agents_systems
sparkweave competition-preflight --template ai_learning_agents_systems --with-build --report dist/competition-readiness.json --summary dist/competition-readiness.md --archive dist/sparkweave_competition_package.zip
python scripts/render_competition_summary.py dist/competition-readiness.json --output dist/competition-readiness.md
```

`competition-demo` 会导出 PPT 骨架、7 分钟录屏讲稿、多智能体协作蓝图、赛题评分点证据表、答辩问答预案和最终答辩材料清单。`competition-package` 会整理文档、截图、课程模板、运行配置和离线演示材料，并生成 `START_HERE.md`、解压后可直接打开的 `index.html` 材料导航页和 `checksums.sha256` 完整性校验清单。
`competition-verify` 可独立验证导出的目录或 zip，适合下载 GitHub Actions artifact 后复核文件完整性和安全结构。
`competition-preflight` 会先运行就绪检查，通过后再导出提交包，并自动运行 `competition-verify` 验证最终目录和 zip；带上 `--with-build` 时会在打包前运行 `web` 的生产构建，适合赛前最后一次归档；带上 `--summary` 时会同时写出一页 Markdown 就绪摘要；带上 `--archive` 时会额外生成可上传的 zip 提交包。
`render_competition_summary.py` 会把 JSON 就绪报告转换成一页 Markdown 摘要，适合贴到 GitHub Actions summary、答辩材料或赛前核对群。

## 知识库命令

```powershell
sparkweave kb list
sparkweave kb create my-kb --doc textbook.pdf
```

典型流程：

1. 创建知识库。
2. 导入文档。
3. 等待索引完成。
4. 在聊天或深度能力中使用 `rag` 工具。

## 插件与记忆

```powershell
sparkweave plugin list
sparkweave memory show
```

## API Server

安装服务端依赖：

```powershell
pip install -r requirements/server.txt
pip install -e .
```

启动服务：

```powershell
sparkweave serve --port 8001
```

默认地址：

| 项目 | 地址 |
| --- | --- |
| API 根地址 | `http://localhost:8001` |
| OpenAPI 文档 | `http://localhost:8001/docs` |
| WebSocket | `ws://localhost:8001/api/v1/ws` |

## WebSocket API

统一 WebSocket 端点：

```text
/api/v1/ws
```

后端路由文件：

```text
sparkweave/api/routers/unified_ws.py
```

### 启动 Turn

发送：

```json
{
  "type": "start_turn",
  "content": "Explain Fourier transform",
  "capability": "chat",
  "tools": ["rag", "web_search"],
  "knowledge_bases": ["my-kb"],
  "language": "en",
  "session_id": null,
  "config": {}
}
```

`type` 也兼容 `message`。

常用字段：

| 字段 | 说明 |
| --- | --- |
| `content` | 用户输入 |
| `capability` | `chat`、`deep_solve`、`deep_question`、`deep_research`、`visualize`、`math_animator` |
| `tools` | 启用工具列表 |
| `knowledge_bases` | 绑定知识库 |
| `language` | `en` 或 `zh` |
| `session_id` | 复用会话，不传则新建 |
| `config` | capability 配置 |
| `notebook_references` | Notebook 引用 |
| `history_references` | 历史会话引用 |
| `attachments` | 文件或图片附件 |

Notebook 引用、历史引用和 Memory 注入的上下文构造细节见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)。

### 订阅与恢复

订阅 turn：

```json
{
  "type": "subscribe_turn",
  "turn_id": "...",
  "after_seq": 0
}
```

订阅 session 当前 turn：

```json
{
  "type": "subscribe_session",
  "session_id": "...",
  "after_seq": 0
}
```

从断点续流：

```json
{
  "type": "resume_from",
  "turn_id": "...",
  "seq": 12
}
```

取消：

```json
{
  "type": "cancel_turn",
  "turn_id": "..."
}
```

服务端返回结构化流事件：

- 阶段事件。
- 内容事件。
- 结果事件。
- 错误事件。

具体字段以 `sparkweave/core/contracts.py` 中的 `StreamEvent` 协议为准：

```json
{
  "type": "content",
  "source": "chat",
  "stage": "responding",
  "content": "...",
  "metadata": {},
  "session_id": "...",
  "turn_id": "...",
  "seq": 3,
  "timestamp": 1760000000.0
}
```

事件类型包括 `session`、`stage_start`、`stage_end`、`thinking`、`observation`、`content`、`tool_call`、`tool_result`、`progress`、`sources`、`result`、`error`、`done`。

## HTTP API

FastAPI 应用在 `sparkweave/api/main.py` 组装。常用前缀：

| 前缀 | 说明 |
| --- | --- |
| `/api/v1/settings` | UI 设置、模型 catalog、服务连接测试 |
| `/api/v1/system` | 系统状态和运行拓扑 |
| `/api/v1/sessions` | 会话列表、详情、重命名、删除、题目结果 |
| `/api/v1/knowledge` | 知识库管理、上传、进度、链接文件夹 |
| `/api/v1/notebook` | Notebook 管理 |
| `/api/v1/question-notebook` | 题目记录和分类 |
| `/api/v1/plugins` | Playground 工具和能力测试 |
| `/api/v1/sparkbot` | SparkBot 实例、Soul 模板、渠道、工作区文件和聊天 |
| `/api/v1/guide` | 导学空间 |
| `/api/v1/guide/v2` | Guide V2 学习路径驾驶舱 |
| `/api/v1/co_writer` | 协作写作 |
| `/api/v1/vision` | 图像题解析 |

知识库接口细节见 [知识库详解](./knowledge-base.md)，题目生成和题目本接口见 [题目工作流](./question-workflows.md)，主 Notebook 与 Memory 接口见 [Notebook、Memory 与上下文引用](./notebook-memory-context.md)，Guide V2 接口见 [导学空间与 Guide V2](./guided-learning.md)，SparkBot 与 Agents 接口见 [SparkBot 与 Agents 工作台](./sparkbot-agents.md)。
设置页、系统状态和 Provider 连接测试见 [设置与 Provider 配置](./settings-and-providers.md)。

## Python Facade

Python facade 适合在测试、脚本或上层应用中直接调用 SparkWeave 内核。

建议调用路径：

1. 构造 `TurnRequest`。
2. 调用 `SparkWeaveApp.start_turn()`。
3. 调用 `SparkWeaveApp.stream_turn()` 消费事件。
4. 需要时用 `cancel_turn()` 取消。

示意：

```python
from sparkweave.app import SparkWeaveApp, TurnRequest

app = SparkWeaveApp()
session, turn = await app.start_turn(
    TurnRequest(
        content="Explain Fourier transform",
        capability="chat",
        tools=["web_search"],
        language="en",
    )
)

async for event in app.stream_turn(turn["id"]):
    print(event)
```

关键文件：

| 路径 | 说明 |
| --- | --- |
| `sparkweave/app/facade.py` | Python facade 和 `TurnRequest` |
| `sparkweave/runtime/turn_runtime.py` | LangGraph turn manager |
| `sparkweave/core/contracts.py` | 上下文与事件协议 |
| `sparkweave/runtime/registry/capability_registry.py` | Capability 注册表 |
| `sparkweave/tools/registry.py` | Tool 注册表 |

单个工具的参数、返回结构、Playground 执行入口和新增工具步骤见 [Tools 工具系统](./tools.md)。
会话列表、turn 订阅、`resume_from` 和事件持久化细节见 [会话、Turn 与事件持久化](./sessions-and-turns.md)。

## 选择入口

| 场景 | 推荐入口 |
| --- | --- |
| 本地快速验证 | CLI |
| 前端工作台 | WebSocket API |
| 自动化脚本 | Python facade |
| 外部产品集成 | WebSocket API |
| 能力开发调试 | CLI + Python facade |
