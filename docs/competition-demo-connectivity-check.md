# 比赛演示连通性检查记录

检查时间：2026-05-15

## 当前结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 前端开发服务 `http://localhost:3782` | 通过 | 端口处于监听状态 |
| `/demo` 评委演示台 | 通过 | HTTP 200，稳定演示入口可打开 |
| 后端 API `http://localhost:8001/api/v1/system/status` | 通过 | HTTP 200，当前由临时虚拟环境启动在 `127.0.0.1:8001` |
| 稳定演示包 | 通过 | `/demo` 不依赖现场生成，可用于录屏开场和 PPT 截图 |

## 后端状态快照

2026-05-15 最新检查结果：

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| Backend | online | `/api/v1/system/status` 可访问 |
| LLM | configured | `deepseek-chat` |
| Embedding/RAG | configured | Embedding: `Qwen/Qwen3-Embedding-8B`；RAG provider: `milvus` |
| Search | configured | `iflytek_spark` |
| OCR | configured | `iflytek` |
| TTS | configured | `iflytek` |

## 录屏建议

1. 录屏开场先使用 `/demo`，确保评委看到赛题五项、学习闭环、讯飞能力链和截图位。
2. 若需要展示真实导学会话、资源生成和报告保存，录屏前启动后端：

```powershell
sparkweave serve --port 8001
```

3. 后端启动后再打开设置页或 `/demo` 的服务状态区，确认 LLM、Embedding/RAG、搜索、OCR、TTS 的可用状态。
4. 如果外部服务暂不可用，使用稳定演示包和 `docs/competition-demo-visual-runbook.md` 的兜底路线完成视频录制。

当前机器若未全局安装 CLI，可复用本次验证过的临时虚拟环境：

```powershell
$venv = Join-Path $env:TEMP 'sparkweave_backend_venv'
& (Join-Path $venv 'Scripts\python.exe') -m sparkweave_cli.main serve --host 127.0.0.1 --port 8001
```

## 已验证命令

```powershell
Invoke-WebRequest -Uri 'http://localhost:3782/demo' -UseBasicParsing -TimeoutSec 5
Invoke-WebRequest -Uri 'http://localhost:8001/api/v1/system/status' -UseBasicParsing -TimeoutSec 5
```
