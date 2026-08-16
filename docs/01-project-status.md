# 01 Project Status

更新时间：2026-08-16

本文只按当前代码仓库状态判断，不按旧 README 或口头规划判断。

## 一句话结论

这个项目已经不是“概念 Demo”。

- 预测主链路已打通：前端发起研究，后端执行多 Agent 预测，返回候选产品。
- 产品定义链路已打通：用户可从候选中选择，生成 `ProductSpec`，继续问答、修订、确认准备度。
- 预验证实验室已落地第一版：可以基于 `validation_readiness` 创建验证项目、跑确定性模拟、生成 finding，并回写产品定义工作台。
- 仍然是单机型架构：SQLite + FastAPI `BackgroundTasks`，适合 Demo / 内测，不是生产级分布式系统。

## P0：已经完成

### 1. 前端主流程可用

真实页面和路由已存在：

- `/`：研究首页
- `/runs/:runId`：实时研究工作台
- `/runs/:runId/product-definition`：当前 run 的产品定义状态页
- `/products/:productId`：产品定义页
- `/products/:productId/validation`：验证实验室

对应代码：

- `frontend/src/app/router.tsx`
- `frontend/src/features/forecast-create/*`
- `frontend/src/features/forecast-run/*`
- `frontend/src/features/product-spec/*`
- `frontend/src/features/validation/*`

### 2. 预测后端主链路可用

真实 API、编排器、Agent 已存在：

- API 路由：`backend/src/eufy_security_agents/api/routes.py`
- 依赖装配：`backend/src/eufy_security_agents/api/dependencies.py`
- 主编排器：`backend/src/eufy_security_agents/orchestration/workflow.py`
- 预测 Agent：`backend/src/eufy_security_agents/agents/forecasting.py`

当前主链路包含：

- 本地证据分层检索
- 4 个 futures lens
- cross-lens deliberation
- consensus
- opportunity synthesis
- competitor analysis
- current capability audit
- candidate generation
- novelty audit
- portfolio diversity audit
- blind review
- ranking
- human selection
- product definition

### 3. 产品定义工作台可用

已存在能力：

- 获取 `ProductSpec`
- 产品问答
- 生成 issue proposal
- dismiss issue / suggestion
- 修订版本
- 查看 readiness
- confirm product

对应 API：

- `/products/{product_id}`
- `/products/{product_id}/questions`
- `/products/{product_id}/revisions`
- `/products/{product_id}/issues/dismiss`
- `/products/{product_id}/suggestions/dismiss`
- `/products/{product_id}/readiness`
- `/products/{product_id}/confirm`

### 4. 预验证实验室第一版可用

已存在能力：

- 从 `validation_ready` 的 `ProductSpec` 创建验证项目
- 每条 `validation_hypothesis` 生成一个 experiment
- 跑确定性场景模拟
- 跑多角色预验证
- 生成 explainable `analysis_trace`
- 将 finding send-back 到产品定义工作台

对应代码：

- `backend/src/eufy_security_agents/orchestration/validation_workflow.py`
- `backend/src/eufy_security_agents/domain/validation.py`
- `backend/src/eufy_security_agents/agents/validation.py`
- `frontend/src/features/validation/ValidationLabPage.tsx`

## P0：半完成

### 1. 观测能力是“面向产品流程”的，不是完整平台级 observability

已经有：

- SSE 事件流
- artifact 持久化
- token / duration / model_name 记录
- validation `analysis_trace`

还没有看到：

- 独立 trace 平台接入
- span 级 tracing
- 统一 cost accounting
- 自动化离线评测平台
- Prometheus / OpenTelemetry / Sentry 一类正式接入

### 2. 产品验证是“预验证 / 模拟验证”，不是真实实验系统

代码里非常明确：

- 正向结论最多是 `supported_in_simulation`
- 经验性问题会落到 `requires_real_world_test`
- 系统不声称真实硬件测试、真实用户研究、真实市场实验已完成

这说明验证链路已经有产品形态，但仍是 pre-validation，不是 full validation platform。

### 3. LLM 容错做了不少，但仍是单进程执行

已经有：

- stage timeout
- workflow timeout
- recoverable error fallback
- idempotency
- degraded result 标注

但还没有：

- 队列系统
- worker 池
- 任务恢复 / checkpoint resume
- 多租户隔离

## P1：只有设计或基本不存在

### 1. LangGraph

代码搜索没有看到真实 LangGraph runtime 接入。当前实际编排是自定义 `ForecastWorkflow` / `ValidationWorkflow`，不是 LangGraph graph。

### 2. MCP / A2A

代码搜索没有看到项目内真实 MCP runtime 或 A2A 协议编排。当前系统主要是本地代码 + LLM + SQLite + 前端工作台。

### 3. 飞书 Aily 集成

当前仓库内未找到 `feishu` / `aily` 相关真实接入代码。至少从这个 repo 看，没有成型的飞书集成链路。

### 4. 爬虫 / 在线搜索

当前证据体系基于本地 `jsonl` 知识库，不是在线爬虫和实时搜索系统。

### 5. 独立评测体系

有不少单元测试和集成测试，但没有看到完整的“评测数据集 -> 自动跑分 -> dashboard”系统。

## 最容易误判的点

### 1. 顶层 README 比代码旧

根目录 `README.md` 和部分子 README 仍把一些功能描述成“未实现 / coming soon”，但当前前端验证页和后端验证工作流已经真实存在。

### 2. 这不是“假页面”

很多页面并不只是静态展示，它们确实连到：

- 后端 API
- SSE
- SQLite 持久化
- ProductSpec 修订链路
- Validation project 链路

### 3. 这也不是生产系统

从架构上看，它更接近：

- 单机可运行的多 Agent 产品研究工作台
- 适合演示、内测、方案验证
- 距离高并发生产化还有一段距离

## 建议的对外口径

如果要对团队介绍当前状态，比较准确的说法是：

> 项目已经完成从研究输入、证据检索、多 Agent 预测、候选生成、人工选择、产品定义到预验证实验室的一体化可运行闭环；但底层仍是单机编排和本地知识库，观测、飞书集成、在线数据接入和生产化基础设施仍未完成。
