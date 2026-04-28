# SparkWeave — Agent-Native Architecture

## Overview

SparkWeave is an **agent-native** intelligent learning companion built around
a two-layer plugin model (Tools + Capabilities) with three entry points:
CLI, WebSocket API, and Python SDK.

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /api/v1/ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │              ChatOrchestrator                    │
              │   routes to ChatCapability (default)             │
              │   or a selected deep Capability                  │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

### Level 1 — Tools

Lightweight single-function tools the LLM calls on demand:

| Tool                | Description                                    |
| ------------------- | ---------------------------------------------- |
| `rag`               | Knowledge base retrieval (RAG)                 |
| `web_search`        | Web search with citations                      |
| `code_execution`    | Sandboxed Python execution                     |
| `reason`            | Dedicated deep-reasoning LLM call              |
| `brainstorm`        | Breadth-first idea exploration with rationale  |
| `paper_search`      | arXiv academic paper search                    |
| `geogebra_analysis` | Image → GeoGebra commands (4-stage vision pipeline) |

### Level 2 — Capabilities

Multi-step agent pipelines that take over the conversation:

| Capability       | Stages                                         |
| ---------------- | ---------------------------------------------- |
| `chat`           | responding (default, tool-augmented)           |
| `deep_solve`     | planning → reasoning → writing                 |
| `deep_question`  | ideation → evaluation → generation → validation |

### Playground Plugins

Extended features should target `sparkweave/plugins/` when plugin loading is enabled:

| Plugin            | Type       | Description                          |
| ----------------- | ---------- | ------------------------------------ |
| `deep_research`   | playground | Multi-agent research + reporting     |

## CLI Usage

```bash
# Install CLI
pip install -r requirements/cli.txt && pip install -e .

# Run any capability (agent-first entry point)
sparkweave run chat "Explain Fourier transform"
sparkweave run deep_solve "Solve x^2=4" -t rag --kb my-kb
sparkweave run deep_question "Linear algebra" --config num_questions=5

# Interactive REPL
sparkweave chat

# Knowledge bases
sparkweave kb list
sparkweave kb create my-kb --doc textbook.pdf

# Plugins & memory
sparkweave plugin list
sparkweave memory show

# API server (requires server.txt)
sparkweave serve --port 8001
```

## Key Files

| Path                          | Purpose                              |
| ----------------------------- | ------------------------------------ |
| `sparkweave/runtime/orchestrator.py` | ChatOrchestrator unified entry    |
| `sparkweave/core/contracts.py`    | StreamEvent protocol                 |
| `sparkweave/core/contracts.py`    | Async event fan-out                  |
| `sparkweave/core/tool_protocol.py` | BaseTool abstract class             |
| `sparkweave/core/capability_protocol.py` | BaseCapability abstract class |
| `sparkweave/core/contracts.py`    | UnifiedContext dataclass             |
| `sparkweave/tools/registry.py` | Tool discovery & registration |
| `sparkweave/runtime/registry/capability_registry.py` | Capability discovery & registration |
| `sparkweave/runtime/mode.py`      | RunMode (CLI vs SERVER)              |
| `sparkweave/graphs/`              | LangGraph capability implementations |
| `sparkweave/tools/builtin.py`     | Built-in tool wrappers               |
| `sparkweave/plugins/`             | Optional playground plugins          |
| `sparkweave/plugins/loader.py`    | Optional plugin discovery from manifest.yaml or plugin.json |
| `sparkweave_cli/main.py`             | Typer CLI entry point                |
| `sparkweave/api/routers/unified_ws.py` | Unified WebSocket endpoint      |

## Plugin Development

Create a directory under `sparkweave/plugins/<name>/` with:

```
manifest.yaml     # name, version, type, description, stages
plugin.json       # optional JSON manifest alternative
capability.py     # class extending BaseCapability
```

Minimal `manifest.yaml`:
```yaml
name: my_plugin
version: 0.1.0
type: playground
description: "My custom plugin"
stages: [step1, step2]
```

Minimal `capability.py`:
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
        await stream.result({"response": "Done!"}, source=self.name)
```

## Dependency Layers

```
requirements/cli.txt            — CLI full (LLM + RAG + providers + tools)
requirements/server.txt         — CLI + FastAPI/uvicorn (for Web/API)
requirements/math-animator.txt  — Manim addon (for `sparkweave animate`)
requirements/dev.txt            — Server + test/lint tools
```

