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
```

## 入口

- `/chat`
- `/knowledge`
- `/notebook`
- `/guide`
- `/co-writer`
- `/agents`
- `/settings`
