# 03 Agent Workflow

更新时间：2026-08-16

本文聚焦每个 Agent 怎么跑、输入输出、路由、循环和状态。

## 1. Forecast Workflow 总览

主编排器：

- `backend/src/eufy_security_agents/orchestration/workflow.py`

主状态推进顺序：

1. `evidence_selection`
2. `future_forecasting`
3. `forecast_deliberation`
4. `consensus_formation`
5. `opportunity_synthesis`
6. `competitor_analysis`
7. `current_capability_audit`
8. `candidate_generation`
9. `novelty_audit`
10. `portfolio_diversity_audit`
11. `candidate_review`
12. `awaiting_product_selection`

## 2. 每个 Agent 的职责

### FuturesLensAgent

代码：

- `forecasting.py` 中 `FuturesLensAgent`

实例化为 4 个 lens：

- `user_trends`
- `technology_trends`
- `security_futures`
- `market_futures`

输入：

- `ForecastRequest`
- retrieval evidence
- strategy context

输出：

- `LensForecast`

特点：

- 必须引用提供过的 `EV-*` 证据
- 每个 lens 先独立判断，避免过早相互污染

### LensDeliberationAgent

代码：

- `forecasting.py` 中 `LensDeliberationAgent`

输入：

- 所有 `LensForecast`
- 被 forecast 引用过的证据子集

输出：

- `LensDeliberation`

作用：

- 让不同 lens 相互质疑
- 记录挑战、观点修正、保留分歧

### ForecastConsensusAgent

输入：

- forecasts
- deliberations
- evidence

输出：

- `ForecastConsensus`

作用：

- 产出共识 claim
- 标出 unresolved disagreements
- 标出 evidence gaps

### OpportunitySynthesizerAgent

输入：

- request
- evidence
- forecasts
- deliberations
- consensus

输出：

- `Opportunity[]`

作用：

- 从趋势与共识里聚合出未来机会方向

### CompetitorAnalysisAgent

输入：

- request
- opportunities
- `COMP-*` 官方竞品资料

输出：

- `CompetitiveAnalysis`

作用：

- 判断竞品已有能力、空白、跟进风险

### CurrentProductAuditorAgent

输入：

- request
- 当前 eufy 基础能力证据

输出：

- `CurrentCapabilityBaseline`

作用：

- 给候选创新提供当前基线，避免“只是把已有功能改个名字”

### CandidateNoveltyAuditorAgent

输入：

- candidates
- current baseline

输出：

- `NoveltyAudit`

作用：

- 判断候选是否真的有新意
- 如果 novelty gate 不通过，会触发修复或降级

### PortfolioDiversityAuditorAgent

输入：

- candidates
- novelty audit

输出：

- `PortfolioDiversityAudit`

作用：

- 避免多个候选只是轻微变体
- 强化组合差异化

### ProductArchitectAgent

输入：

- request
- evidence
- opportunities
- competitive analysis
- competitor evidence
- current baseline

输出：

- `ProductCandidate[]`

作用：

- 生成候选产品
- 每个候选要带能力、定位、引用、竞争视角等结构化信息

### CandidateReviewerAgent

实例化为 6 个 reviewer 维度：

- `innovation`
- `user_value`
- `business_value`
- `cost_effectiveness`
- `feasibility`
- `eufy_synergy`

输入：

- request
- evidence
- candidates
- competitor evidence

输出：

- `CandidateReview[]`

作用：

- 独立盲评，不直接改写 candidate
- 后续用于综合打分和排序

### ProductDefinitionAgent

触发时机：

- 用户从 ranked candidates 中选择一个候选后

输入：

- selected candidate
- run result 上下文
- human selection reason

输出：

- `ProductSpec`

作用：

- 把候选提炼成标准产品定义
- 生成 `validation_readiness`

### ProductSpecAnalystAgent

输入：

- `ProductSpec`
- 用户问题
- 相关证据 / competitor / baseline / consensus 子集

输出：

- `ProductQuestionRecord`

作用：

- 回答产品定义工作台里的问答
- 区分 evidence / inference / assumption / unknown

### ProductSpecReviserAgent

输入：

- 现有 `ProductSpec`
- revision request
- 已有问题与建议

输出：

- 新版 `ProductSpec`

作用：

- 根据反馈修订产品定义

## 3. Validation Workflow

主编排器：

- `backend/src/eufy_security_agents/orchestration/validation_workflow.py`

### 创建项目

触发条件：

- `ProductSpec.definition_status == validation_ready`

输入：

- `ProductSpec` snapshot

输出：

- `ValidationProject`

内部会生成：

- 每条 `ValidationHypothesis` 对应一个 `ValidationExperiment`
- 场景模拟
- digital twin

### 单个 experiment 的分析角色

不是靠一个“大验证 Agent”直接拍结论，而是多角色：

- technology
- privacy_security
- user_scenario
- business
- adversarial
- adjudicator

这些角色大部分判断是确定性规则驱动，LLM 只做补充 narrative。

### ValidationAnalysisAgent

代码：

- `backend/src/eufy_security_agents/agents/validation.py`

作用：

- 为实验补充 AI narrative
- 不允许改 verdict
- 不允许改结构化 finding

## 4. 路由与触发关系

### 预测 run

- `POST /forecast-runs`
- 后端 background task 执行 `workflow.execute(run_id)`

### 候选转 ProductSpec

- `POST /forecast-runs/{run_id}/selections`
- 后端执行 `define_selected_product`

### ProductSpec Q&A / revision

- `/products/{product_id}/questions`
- `/products/{product_id}/revisions`

### 验证项目

- `POST /products/{product_id}/validation-projects`
- `POST /validation-projects/{project_id}/run`

## 5. 循环与重试

### 预测主链路

系统不是无限循环 Agent，而是固定 stage pipeline。

存在的“循环”主要是：

- 多个 lens 并行执行
- 多个 reviewer 并行执行
- validation 多个 experiments 逐个执行
- 产品定义阶段的用户问答 / 修订回路

### 错误恢复

`ForecastWorkflow` 提供：

- stage timeout
- recoverable error fallback
- degraded result 记录

可恢复错误包括：

- `TimeoutError`
- `LLMConfigurationError`
- `LLMGenerationError`
- 某些 `ValueError`

致命错误更少，目的是让流程尽量走完而不是全盘失败。

## 6. 持久化状态

预测链路会落库：

- run
- event
- artifact
- product
- revision
- question

验证链路会落库：

- validation project
- validation event
- validation finding 索引
- analysis trace

## 7. 前端怎么消费这些状态

实时研究页：

- SSE event stream
- artifact polling
- run polling

产品定义页：

- product query
- revisions query
- readiness query

验证实验室：

- latest project query
- project query
- validation events query

## 8. 这套 Agent 工作流的真实特点

- 不是开放式 agent swarm，而是强约束 pipeline
- 不是单轮 prompt，而是结构化多 stage
- 不是只存最终答案，而是存中间 artifact 与 event
- 不是全靠 LLM 拍脑袋，很多 gate 和 verdict 有确定性规则
