# Architecture baseline

当前文档只定义边界，不代表已实现。

```text
Frontend (later)
      │ typed API contracts
      ▼
Backend API
      │
      ▼
Application use cases
      │
      ├── Agent orchestration ── Individual security agents
      │
      └── Domain ports ───────── Infrastructure adapters
```

## Core principles

1. 安防动作默认拒绝，必须通过显式授权和策略检查。
2. Agent 输入输出必须结构化并可验证。
3. Agent 不直接相互调用，由编排层控制协作。
4. 所有设备动作、决策与人工审批都必须可审计。
5. 外部供应商与 eufy 接入均通过领域端口隔离。
6. 后端契约稳定后，前端再通过 OpenAPI 类型接入。
