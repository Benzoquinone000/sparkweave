## 变更摘要

- 

## 影响范围

- [ ] 后端服务 / API
- [ ] Agent Runtime / 工具 / 能力图
- [ ] 前端页面 / 组件 / 样式
- [ ] 文档 / 截图 / 交付材料
- [ ] 配置 / Docker / CI

## 质量检查

- [ ] `python scripts/verify_project.py --profile quick`
- [ ] 相关 `pytest`
- [ ] `cd web && npm run lint`
- [ ] `cd web && npm run check:design`
- [ ] `cd web && npm run build`

## 安全与交付

- [ ] 没有提交 `.env`、真实密钥、账号 JSON、用户数据或临时凭证。
- [ ] 新增 API 已同步前端类型和 API 客户端。
- [ ] 新增文档基于代码事实，并已加入文档索引。
- [ ] 前端入口仍服务学习、资料、记录、设置中的用户路径。
- [ ] 外部供应商能力有失败提示、离线替补或可解释降级。

## 备注

- 
