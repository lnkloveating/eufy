# Backend

后端是本项目的第一实施阶段。当前仅包含企业级分层骨架，不包含可运行接口或 Agent 逻辑。

## 技术方向

- Python 3.12+
- FastAPI（HTTP / WebSocket 接入，后续启用）
- Pydantic（契约与配置）
- PostgreSQL（业务与审计数据）
- Redis（任务状态、锁与事件流）
- Pytest、Ruff、Mypy（测试与质量）

## 源码结构

```text
src/eufy_security_agents/
├─ api/              # Transport adapters
├─ application/      # Use cases
├─ domain/           # Models, policies and ports
├─ agents/           # Security agent implementations
├─ orchestration/    # Multi-agent coordination
├─ infrastructure/   # Database, queue, LLM and eufy adapters
├─ observability/    # Logging, metrics and tracing
└─ core/             # Configuration and shared primitives
```

## 当前约束

- 暂无 `main.py`，因此不会意外启动未实现的服务。
- 暂无路由、数据库模型和 Agent 实现。
- 等 Agent 清单确定后，从 `domain` 契约开始实现。
