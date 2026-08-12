# Backend source layout

该目录使用 `src` 布局，避免测试或脚本误加载仓库根目录中的同名模块。

- `eufy_security_agents/api`：REST、WebSocket、schema 与依赖注入
- `eufy_security_agents/application`：用例、命令、查询和事务边界
- `eufy_security_agents/domain`：纯领域模型、策略、事件和端口
- `eufy_security_agents/agents`：各 Agent 的实现；当前为空
- `eufy_security_agents/orchestration`：多 Agent 路由、图和执行状态
- `eufy_security_agents/infrastructure`：数据库、队列、LLM、eufy 适配器
- `eufy_security_agents/observability`：结构化日志、指标与 tracing
- `eufy_security_agents/core`：配置、安全和公共异常

依赖方向：`api → application → domain`，`infrastructure → domain ports`。
