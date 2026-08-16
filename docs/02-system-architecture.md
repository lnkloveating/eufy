# 02 System Architecture

更新时间：2026-08-16

本文描述“实际代码关系”，不是理想分层图。

## 总体结构

```text
Frontend (React/Vite)
  -> typed API client + React Query + SSE
  -> FastAPI backend
      -> ForecastWorkflow / ValidationWorkflow
      -> local evidence store / competitor store
      -> OpenAI-compatible LLM adapter
      -> SQLite repository
```

仓库顶层：

- `frontend/`
- `backend/`
- `docs/`
- `infra/`
- `scripts/`

## 真实运行时拓扑

### 前端

入口：

- `frontend/src/app/router.tsx`
- `frontend/src/components/AppShell/AppShell.tsx`

主要页面：

- `DeepResearchHome`
- `RunWorkbenchPage`
- `ProductDefinitionStatePage`
- `ProductSpecPage`
- `ValidationLabPage`

前端通过这几层访问后端：

- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/forecastApi.ts`
- `frontend/src/lib/queries.ts`
- `frontend/src/lib/api/sse.ts`

### 后端

ASGI 入口：

- `backend/src/eufy_security_agents/main.py`

应用装配：

- `backend/src/eufy_security_agents/api/dependencies.py`

这里完成了真实依赖注入：

- `SqlAlchemyRunRepository`
- `LocalEvidenceStore`
- `LocalCompetitorStore`
- `OpenAICompatibleLLM`
- `ForecastWorkflow`
- `ValidationWorkflow`

API 路由：

- `backend/src/eufy_security_agents/api/routes.py`

## 前后端的实际关系

### 研究创建

前端：

- `forecastApi.createForecastRun()`
- `useCreateRun()`

后端：

- `POST /forecast-runs`
- `workflow.create()` 或 `workflow.create_idempotent()`
- `BackgroundTasks.add_task(workflow.execute, run_id)`

### 实时研究

前端：

- `useRun()`
- `useRunArtifacts()`
- `useRunEvents()`
- `useRunResult()`

后端：

- `/forecast-runs/{run_id}`
- `/forecast-runs/{run_id}/events`
- `/forecast-runs/{run_id}/events/stream`
- `/forecast-runs/{run_id}/artifacts`
- `/forecast-runs/{run_id}/result`

### 产品定义

前端：

- `ProductDefinitionStatePage`
- `ProductSpecPage`
- `ProductDefinitionCopilot`

后端：

- `/forecast-runs/{run_id}/product-definition-state`
- `/forecast-runs/{run_id}/selections`
- `/products/{product_id}`
- `/products/{product_id}/questions`
- `/products/{product_id}/revisions`
- `/products/{product_id}/readiness`
- `/products/{product_id}/confirm`

### 验证实验室

前端：

- `ValidationLabPage`
- lazy-loaded `ProductDigitalTwin`

后端：

- `/products/{product_id}/validation-projects`
- `/products/{product_id}/validation-projects/latest`
- `/validation-projects/{project_id}`
- `/validation-projects/{project_id}/run`
- `/validation-projects/{project_id}/events`
- `/validation-findings/{finding_id}/send-back`

## 后端内部结构

### 1. API 层

职责：

- 暴露 REST / SSE 接口
- 做 HTTP 层错误转换
- 调 workflow 和 repository

核心文件：

- `backend/src/eufy_security_agents/api/routes.py`

### 2. 编排层

职责：

- 决定 stage 顺序
- 控制 timeout / fallback / degrade
- 保存 artifact 和 event

核心文件：

- `backend/src/eufy_security_agents/orchestration/workflow.py`
- `backend/src/eufy_security_agents/orchestration/validation_workflow.py`

这层是当前系统真正的“大脑”。

### 3. Agent 层

职责：

- 拼 prompt
- 调 LLM
- 输出结构化对象

核心文件：

- `backend/src/eufy_security_agents/agents/forecasting.py`
- `backend/src/eufy_security_agents/agents/validation.py`

### 4. Domain 层

职责：

- 领域模型
- 枚举
- ProductSpec / Validation contract
- readiness 和问题分类等纯规则逻辑

核心文件：

- `backend/src/eufy_security_agents/domain/models.py`
- `backend/src/eufy_security_agents/domain/product_workbench.py`
- `backend/src/eufy_security_agents/domain/validation.py`
- `backend/src/eufy_security_agents/domain/validation_roles.py`

### 5. Infrastructure 层

职责：

- SQLite 持久化
- 本地 evidence / competitor 读取与检索
- LLM provider 适配

核心文件：

- `backend/src/eufy_security_agents/infrastructure/repositories.py`
- `backend/src/eufy_security_agents/infrastructure/evidence.py`
- `backend/src/eufy_security_agents/infrastructure/competitors.py`
- `backend/src/eufy_security_agents/infrastructure/llm.py`

## 数据库的真实角色

当前数据库是 SQLite。

`SqlAlchemyRunRepository` 负责保存：

- forecast run
- run idempotency key
- artifact
- agent event
- product
- product question
- product revision
- suggestion resolution
- product selection
- validation project
- validation event
- validation finding 索引

也就是说，数据库不是只存最终结果，而是存整条研究与验证过程。

## LangGraph、MCP、A2A 的实际状态

### LangGraph

未看到真实 LangGraph 依赖或 graph 定义。当前系统是自定义 workflow，不是 LangGraph runtime。

### MCP / A2A

未看到项目内真实 MCP server/client 或 A2A runtime。当前系统没有形成这类协议层架构。

## 代码层面的真实关系图

```text
RunWorkbenchPage / ProductSpecPage / ValidationLabPage
  -> forecastApi.ts
  -> queries.ts
  -> /api/v1/*

routes.py
  -> dependencies.py
  -> ForecastWorkflow
  -> ValidationWorkflow
  -> repository

ForecastWorkflow
  -> LocalEvidenceStore
  -> LocalCompetitorStore
  -> forecasting agents
  -> repository.save_artifact / save_event / save_product

ValidationWorkflow
  -> ProductSpec snapshot
  -> validation roles + deterministic simulation
  -> ValidationAnalysisAgent
  -> repository.save_validation_project / save_validation_event

repository
  -> SQLite tables
```

## 当前架构优点

- 单仓可跑通完整闭环
- 前后端契约比较清楚
- artifact / event / product / validation project 都有持久化
- workflow 层把降级逻辑集中起来了

## 当前架构短板

- 任务执行仍依赖 FastAPI `BackgroundTasks`
- 没有独立 worker / queue
- 没有正式 tracing / metrics / cost pipeline
- 没有外部知识接入层
- 没有组织级身份、权限、多租户模型

## 对“实际代码关系”的最短总结

这不是“前端调一个黑盒 AI API”的系统，而是：

- 前端工作台
- 后端自定义 workflow
- 本地知识库检索
- 结构化 Agent 输出
- SQLite 审计留痕

共同组成的一条可追踪研究流水线。
