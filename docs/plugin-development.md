# 插件开发

SparkWeave 的扩展能力优先放在 `sparkweave/plugins/` 下。插件用于承载试验性或可插拔的深度能力，例如多智能体研究、报告生成、课程资源生成等。

## 目录结构

最小插件结构：

```text
sparkweave/plugins/my_plugin/
  manifest.yaml
  capability.py
```

也可以使用 JSON manifest：

```text
sparkweave/plugins/my_plugin/
  plugin.json
  capability.py
```

## manifest.yaml

```yaml
name: my_plugin
version: 0.1.0
type: playground
description: "My custom plugin"
stages: [step1, step2]
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `name` | 是 | 插件名称，应与 capability 名称保持一致 |
| `version` | 是 | 插件版本 |
| `type` | 是 | 插件类型，如 `playground` |
| `description` | 是 | 插件描述 |
| `stages` | 是 | 运行阶段列表 |

## capability.py

```python
from sparkweave.core.capability_protocol import BaseCapability, CapabilityManifest
from sparkweave.core.contracts import StreamBus, UnifiedContext


class MyPlugin(BaseCapability):
    manifest = CapabilityManifest(
        name="my_plugin",
        description="My custom plugin",
        stages=["step1", "step2"],
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        async with stream.stage("step1", source=self.name):
            await stream.content("Working on step 1...", source=self.name)

        async with stream.stage("step2", source=self.name):
            await stream.content("Working on step 2...", source=self.name)

        await stream.result({"response": "Done!"}, source=self.name)
```

## Capability 设计建议

- 每个 stage 做一类清晰任务，例如 planning、retrieval、reasoning、writing、validation。
- 所有用户可见输出通过 `StreamBus` 发出。
- 需要结构化结果时，使用 `stream.result(...)`。
- 需要调用工具时，通过注册表或上下文提供的工具接口完成。
- 插件内部不要直接依赖 CLI 或 Web 层。

## 与 Tools 的边界

适合写成 Tool：

- 单次检索。
- 单次搜索。
- 单次代码执行。
- 格式转换。
- 外部 API 的轻量封装。

适合写成 Capability：

- 多阶段任务。
- 需要规划、执行、校验、汇总的流程。
- 会接管一轮对话的智能体。
- 需要持续向前端输出进度的任务。

## 加载与验证

查看插件：

```powershell
sparkweave plugin list
```

通过 CLI 调用：

```powershell
sparkweave run my_plugin "Your task"
```

开发时建议同时验证：

```powershell
python scripts/check_install.py
pytest tests
```

## 常见问题

### 插件没有被发现

检查：

- 插件目录是否在 `sparkweave/plugins/<name>/`。
- 是否存在 `manifest.yaml` 或 `plugin.json`。
- manifest 中的 `name` 是否与 capability manifest 一致。
- `capability.py` 是否能被正常 import。

### 前端没有显示阶段进度

检查：

- 是否使用 `async with stream.stage(...)` 包裹阶段。
- `source` 是否传入稳定名称。
- 是否通过 `stream.content(...)` 输出阶段内容。
