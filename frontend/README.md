# Frontend

前端是第二实施阶段，仅在后端领域模型、Agent 编排和 API 契约稳定后开始实现。

当前目录只有工程骨架，不包含页面、组件或业务交互。

## 计划结构

```text
src/
├─ app/          # 应用入口、路由与全局 providers
├─ features/     # 按业务能力拆分的功能模块
├─ components/   # 可复用 UI 组件
├─ lib/          # API client、配置与通用工具
├─ types/        # 由后端 OpenAPI 生成或同步的类型
└─ styles/       # design tokens 与全局样式
```

计划使用 React、TypeScript、Vite 和企业级测试工具；实际选型可在后端完成后确认。
