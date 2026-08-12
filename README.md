# eufy Security Agent Platform

面向 eufy 安防业务的企业级多 Agent 协作平台骨架。

> 当前阶段仅完成工程结构，不包含任何业务功能、Agent 实现、API 路由或前端页面。
> 后续开发顺序固定为：**先后端，再前端**。

## 仓库结构

```text
eufy-security-agent-platform/
├─ backend/                 # 后端与 Agent 编排（下一阶段优先实现）
│  ├─ src/                  # Python 源码目录
│  ├─ tests/                # 单元、集成、契约测试
│  ├─ pyproject.toml        # 依赖与质量工具配置
│  └─ README.md
├─ frontend/                # 前端控制台（后端完成后实现）
│  ├─ src/                  # 前端源码目录
│  ├─ tests/                # 前端测试目录
│  ├─ package.json          # 前端工程清单
│  └─ README.md
├─ docs/                    # 架构、Agent 规格与决策记录
├─ infra/                   # 容器与部署骨架
├─ scripts/                 # 工程脚本占位
├─ .github/workflows/       # CI 骨架
├─ .env.example             # 根环境变量模板
└─ Makefile                 # 统一命令入口
```

## 计划中的后端分层

- `api`：HTTP / WebSocket 接入层
- `application`：用例与服务编排
- `domain`：领域模型、规则与接口
- `agents`：各安防 Agent 的独立实现
- `orchestration`：Agent 协作、状态机与工作流
- `infrastructure`：模型供应商、数据库、消息队列及外部集成
- `observability`：日志、指标与链路追踪
- `core`：配置、安全与跨模块基础能力

## 开发状态

| 模块 | 状态 |
|---|---|
| 企业级目录骨架 | 已完成 |
| 后端业务实现 | 等待 Agent 清单 |
| 前端业务实现 | 等待后端接口稳定 |
| 真实 eufy 设备集成 | 未开始 |

## 下一步

请提供需要实现的 Agent 名称、职责、输入、输出及协作顺序。收到后先实现后端领域模型、Agent 契约与编排层，再实现 API，最后才进入前端。

## License

Private / proprietary. eufy 名称仅用于项目命名与业务场景描述。
