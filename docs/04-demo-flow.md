# 04 Demo Flow

更新时间：2026-08-16

本文从用户视角描述完整 Demo 流程。

## 1. 进入系统

入口页面：

- `/`

对应页面：

- `frontend/src/features/forecast-create/DeepResearchHome`

用户在这里做的事：

- 输入研究问题
- 设定研究范围、地区、目标用户、约束
- 选择策略权重和研究上下文

后端支撑接口：

- `GET /forecast-options`
- `GET /knowledge/coverage`
- `POST /knowledge/retrieval-preview`

这一步的价值：

- 不是直接“问 AI 一个问题”
- 而是先把结构化 research brief 建出来

## 2. 创建研究任务

用户点击开始研究后：

- 前端调用 `createForecastRun()`
- 路由跳转到 `/runs/:runId`

后端：

- 创建 forecast run
- 保存 request
- 通过 `BackgroundTasks` 启动 `workflow.execute(run_id)`

## 3. 实时研究工作台

页面：

- `/runs/:runId`

对应组件：

- `RunWorkbenchPage`

用户能看到：

- 当前 run 状态
- 实时阶段推进
- agent event timeline
- 已完成 artifact
- 中间分析结果
- research ledger

前端数据源：

- `useRun()`
- `useRunEvents()`
- `useRunArtifacts()`
- `useRunResult()`

后端接口：

- `GET /forecast-runs/{run_id}`
- `GET /forecast-runs/{run_id}/events`
- `GET /forecast-runs/{run_id}/events/stream`
- `GET /forecast-runs/{run_id}/artifacts`
- `GET /forecast-runs/{run_id}/result`

### 实时体验的关键点

- SSE 是主通道
- polling 是兜底
- 页面不是假进度条，而是跟真实 event / artifact 走

## 4. 研究完成，进入候选结果

当 run 完成后：

- `status = completed`
- `stage = awaiting_product_selection`

用户可以看到：

- 候选产品列表
- 多 Agent 分析
- 证据库
- 共识和分歧
- 竞品和机会

这一步的核心不是只给一个答案，而是给多个可选候选。

## 5. 用户选择一个候选

用户在 run 页面或产品定义状态页选择候选。

前端：

- 调用 `createSelection()`

后端：

- `POST /forecast-runs/{run_id}/selections`
- 调 `ProductDefinitionAgent`
- 生成 `ProductSpec`

然后前端继续查看：

- `/runs/:runId/product-definition`
- 或直接 `/products/:productId`

## 6. 产品定义页

页面：

- `/products/:productId`

对应组件：

- `ProductSpecPage`

用户看到的内容：

- hero 概览
- 核心定义
- 实现方式
- 能力增量
- 生态与隐私
- 市场与商业
- 风险与假设
- 产品定义 Copilot
- readiness 工作台

用户可做的动作：

- 问问题
- 生成 proposal
- dismiss issue
- dismiss suggestion
- 修改产品定义
- 查看 revision history
- confirm product

## 7. 产品定义状态页

页面：

- `/runs/:runId/product-definition`

作用：

- 让用户在“当前 run”的上下文里观察产品定义是否还在生成、是否 ready
- 这是 run 级状态，不等同于全局 product 列表

后端接口：

- `GET /forecast-runs/{run_id}/product-definition-state`

## 8. 确认 Validation Ready

当产品定义阻塞项被处理后：

- 用户点击 confirm
- 后端检查 readiness
- 只有满足条件才会进入 `validation_ready`

接口：

- `POST /products/{product_id}/confirm`

## 9. 进入验证实验室

页面：

- `/products/:productId/validation`

前置条件：

- `definition_status === validation_ready`

如果没到这个状态，前端会挡住并提示先回产品定义页。

## 10. 创建验证项目

进入验证页后：

- 前端会查询 latest project
- 如果没有，或版本过期，会自动创建新 project

接口：

- `GET /products/{product_id}/validation-projects/latest`
- `POST /products/{product_id}/validation-projects`

## 11. 跑预验证

用户点击开始后：

- 前端 `runValidationProject()`
- 后端执行 `validation_workflow.execute(project_id)`

执行内容：

- 针对每个 hypothesis 建 experiment
- 跑 deterministic simulation
- 跑多角色分析
- 生成 finding / trace / verdict

实时反馈接口：

- `GET /validation-projects/{project_id}`
- `GET /validation-projects/{project_id}/events`
- `GET /validation-projects/{project_id}/events/stream`

## 12. send-back 到产品定义

如果验证发现问题：

- 用户可以把 finding send-back
- 后端不会直接偷偷改 `ProductSpec`
- 而是生成 reviewable suggestion 回到产品定义工作台

接口：

- `POST /validation-findings/{finding_id}/send-back`

## 13. 一个完整 Demo 的推荐讲法

### 开场

- 从研究首页输入一个清晰的问题
- 展示 research brief 不是一句 prompt，而是结构化输入

### 中段

- 跳到实时研究页
- 展示 event timeline、artifact、evidence、candidate 不是一次性黑盒返回

### 后段

- 选择一个候选生成 `ProductSpec`
- 在产品定义页展示问答、修订、readiness

### 收尾

- 进入 validation lab
- 展示实验、trace、finding、send-back

## 14. 这条 Demo 流程的价值

它演示的不是“AI 帮我写一个方案”，而是：

- 有研究输入
- 有证据检索
- 有多 Agent 判断
- 有人选候选
- 有产品定义
- 有预验证回路

也就是一个完整的产品研究与定义闭环。
