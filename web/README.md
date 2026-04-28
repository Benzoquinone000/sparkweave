# SparkWeave Web

`web` 是 SparkWeave 星火织学的前端工作台，使用 Vite、React、TypeScript、TanStack Router、TanStack Query、Framer Motion 和 Tailwind。

## 启动

```bash
npm install
npm run dev
```

默认后端地址来自 `VITE_API_BASE`。如果未设置，会使用 `http://localhost:${BACKEND_PORT:-8001}`。

```bash
VITE_API_BASE=http://localhost:8001 npm run dev
```

Windows PowerShell:

```powershell
$env:VITE_API_BASE = "http://localhost:8001"
npm run dev
```

## 脚本

```bash
npm run lint
npm run check:design
npm run check:api-contract
npm run check:replacement
npm run build
npm run smoke:runtime
npm run test:e2e
```

## 入口

- `/chat`
- `/knowledge`
- `/notebook`
- `/guide`
- `/co-writer`
- `/agents`
- `/settings`
