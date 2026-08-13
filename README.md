# eufy Security Agent Platform

面向 eufy 安防未来消费电子产品预测、定义与验证的企业级多 Agent 平台。

> 当前阶段已实现“本地证据 → 多 Agent 预测 → 候选产品 → 独立评审 →
> 用户选择 → ProductSpec”的后端逻辑。验证模拟器与前端尚未实现。

## 仓库结构

```text
eufy-security-agent-platform/
├─ backend/                 # 已实现的产品预测与定义后端
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
| 后端产品预测与定义 | 已完成第一版 |
| 技术/商业/2D验证 | 下一阶段 |
| 前端业务实现 | 等待后端接口稳定 |
| 真实 eufy 设备集成 | 未开始 |

## 下一步

先运行并评估后端输出，再实现读取任意ProductSpec的技术、商业、隐私、UX和2D场景验证器；后端接口稳定后再进入前端。

## License

Private / proprietary. eufy 名称仅用于项目命名与业务场景描述。
