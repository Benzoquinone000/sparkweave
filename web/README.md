# SparkWeave Web

`web` 是 SparkWeave 星火织学的前端工作台，使用 Vite、React、TypeScript、TanStack Router、TanStack Query、Framer Motion 和 Tailwind。

## 启动

前端不再单独提供一套本地启动流程。请在仓库根目录通过 Docker Compose 启动完整服务：

```bash
docker compose up -d --build
```

需要前端热重载时，叠加开发覆盖文件：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

前端默认地址是 `http://localhost:3782`，后端默认地址是 `http://localhost:8001`。

## 脚本

```bash
npm run lint
npm run check:design
npm run check:api-contract
npm run check:replacement
npm run build
npm run smoke:runtime
npm run test:e2e
npm run verify
```

`npm run verify` 会串行执行设计合约、API 合约、运行时替换检查、lint、构建和隔离的 Playwright smoke test。

## 用户入口

一级导航围绕学习任务组织：

| 路径 | 入口 | 用户任务 |
| --- | --- | --- |
| `/guide` | 学习 | 生成路线、继续任务、反馈学习效果 |
| `/knowledge` | 资料 | 上传资料、管理知识库、开始资料问答 |
| `/notebook` | 记录 | 保存复盘、题目和学习结果 |
| `/settings` | 设置 | 配置模型、OCR、语音、搜索和工作台偏好 |

按需能力收进“更多入口”：

| 路径 | 能力 |
| --- | --- |
| `/chat` | 问问题与资料对话 |
| `/question` | 练习生成与答题 |
| `/memory` | 学习状态与画像校准 |
| `/agents` | 课程助教 |
| `/co-writer` | 写作助手 |
| `/vision` | 图像解题 |
| `/playground` | 工程调试台 |

页面、组件、动效和色彩约定见 [前端设计规范](../docs/markdown/frontend-design-guide.md)，项目工程门禁见 [软件工程规范](../docs/markdown/engineering-standards.md)。
