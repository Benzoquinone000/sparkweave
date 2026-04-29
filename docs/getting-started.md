# 快速开始

本文档说明如何在本地启动 SparkWeave。命令默认在项目根目录执行。

## 环境要求

- Python 3.11+
- Node.js 20+
- 可用的 LLM API Key
- 可用的 Embedding API Key
- 可选：FFmpeg，用于数学动画视频编码
- 可选：MiKTeX，用于 Manim 公式渲染

## 创建 Python 环境

推荐使用独立 Conda 环境：

```powershell
conda create -n sparkweave python=3.11 -y
conda activate sparkweave
```

安装基础依赖：

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .
```

如需完整开发环境，可安装开发依赖：

```powershell
pip install -r requirements/dev.txt
```

## 安装前端依赖

```powershell
cd web
npm install
cd ..
```

## 配置环境变量

复制示例配置：

```powershell
copy .env.example .env
```

至少需要配置：

```env
LLM_BINDING=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-api-key
LLM_HOST=https://api.openai.com/v1

EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=your-api-key
EMBEDDING_HOST=https://api.openai.com/v1
EMBEDDING_DIMENSION=3072
```

更多配置见 [环境变量配置](./configuration.md)。

## 启动 Web 工作台

```powershell
python scripts/start_web.py
```

默认访问地址：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://localhost:3782` |
| 后端 | `http://localhost:8001` |
| API 文档 | `http://localhost:8001/docs` |

## 使用 CLI

```powershell
sparkweave run chat "Explain Fourier transform"
sparkweave run deep_solve "Solve x^2=4"
sparkweave run deep_question "Linear algebra" --config num_questions=5
sparkweave chat
```

## 知识库基本流程

1. 在 `/knowledge` 创建知识库。
2. 上传课程 PDF、讲义或文本资料。
3. 等待索引完成。
4. 在 `/chat` 选择知识库并提问。
5. 将重要结果保存到 Notebook。

## 常见问题

### 前端无法连接后端

确认后端端口和前端配置一致：

```env
BACKEND_PORT=8001
FRONTEND_PORT=3782
NEXT_PUBLIC_API_BASE=http://localhost:8001
```

### Docker 内访问本机模型失败

容器内的 `localhost` 指向容器自身。Windows 和 macOS Docker Desktop 通常应使用：

```env
LLM_HOST=http://host.docker.internal:1234/v1
EMBEDDING_HOST=http://host.docker.internal:1234/v1
```

### Manim 公式渲染失败

确认 FFmpeg 和 LaTeX 工具可用：

```powershell
ffmpeg -version
latex --version
dvisvgm --version
```
