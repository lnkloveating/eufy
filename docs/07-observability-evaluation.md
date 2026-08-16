# 07 Observability and Evaluation

更新时间：2026-08-16

本文聚焦当前系统真实存在的观测与评估能力。

## 1. 当前已经有的 observability

### 1. 事件流

预测链路事件：

- `GET /forecast-runs/{run_id}/events`
- `GET /forecast-runs/{run_id}/events/stream`

验证链路事件：

- `GET /validation-projects/{project_id}/events`
- `GET /validation-projects/{project_id}/events/stream`

作用：

- 驱动前端实时 timeline
- 记录 run / validation project 的阶段推进
- 记录 degradation 和 terminal state

### 2. Artifact 审计链

当前系统会持久化中间 artifact，而不是只存最终结果。

artifact 里记录：

- `kind`
- `producer`
- `payload_json`
- `model_name`
- `prompt_version`
- `duration_ms`
- `input_tokens`
- `output_tokens`

这已经构成了最基础的可回放 observability。

### 3. Token / duration / model_name

LLM 适配层：

- `backend/src/eufy_security_agents/infrastructure/llm.py`

会收集：

- prompt tokens
- completion tokens
- duration
- failure category

前端 ledger 汇总逻辑：

- `frontend/src/features/forecast-run/researchMetrics.ts`

特点：

- 只汇总 artifact 上真实存在的数据
- `null` 不伪造
- 按 artifact id 去重

### 4. Validation analysis trace

验证实验室不是只给 verdict，还会保存：

- `analysis_trace`

相关模型：

- `backend/src/eufy_security_agents/domain/validation.py`

前端展示：

- `frontend/src/features/validation/ValidationLabPage.tsx`

这相当于 validation 子系统的一条 explainable replay chain。

## 2. 当前没有看到的 observability

### 1. 独立 tracing 平台

没有看到：

- OpenTelemetry
- Jaeger
- Datadog APM
- LangSmith
- Arize Phoenix

### 2. 统一 metrics 管道

没有看到：

- Prometheus exporter
- Grafana dashboard 配置
- 系统级 SLA 指标采集

### 3. 成本核算系统

虽然有 token，但没有看到完整：

- provider price table
- per-run cost
- per-agent cost
- budget policy

所以当前是“token 可见”，不是“成本完整可见”。

## 3. AgentInsight 的真实状态

代码里有 `AgentInsights.tsx`：

- `frontend/src/features/forecast-run/AgentInsights.tsx`

但这里的 `AgentInsights` 更像前端分析展示组件，不是外部独立 observability 产品。

如果有人提到 “AgentInsight / trace 平台”，目前更准确的说法应当是：

> 有面向产品界面的 agent insights 展示，但没有看到独立平台级 trace / observability 系统接入。

## 4. Trace 的真实状态

### Forecast 链路

没有 span 级 trace，但有这些替代件：

- stage 状态
- agent event
- artifact
- degradation event

这能支持业务回放，但不等同于底层 tracing。

### Validation 链路

有更强的 explainability：

- `analysis_trace`
- `ValidationAnalysisActor`
- `ValidationObservation`
- `ValidationFinding`

所以 validation 子系统的“trace 感”比 forecast 主链路更强。

## 5. Evaluation 的真实状态

### 已有

- 单元测试
- 集成测试
- live LLM test 开关
- 多处 deterministic validation

相关目录：

- `backend/tests/unit/*`
- `backend/tests/integration/*`
- `frontend/tests/*`

### 未看到

- 标准评测集
- 自动跑分 pipeline
- golden set regression dashboard
- 离线 benchmark 报告
- AI vs traditional 的系统化对照实验框架

## 6. Reliability / degrade 机制

当前 workflow 做了不少可靠性兜底：

- workflow timeout
- stage timeout
- recoverable error fallback
- degradation 记录
- idempotency

这类能力主要在：

- `backend/src/eufy_security_agents/orchestration/workflow.py`
- `backend/src/eufy_security_agents/orchestration/validation_workflow.py`

它们更偏“流程可靠性”，不是“平台可观测性”。

## 7. AI vs traditional 的现状

当前代码没有看到完整的 AI vs traditional 双轨实现，比如：

- 同一问题的规则版 vs Agent 版
- 自动 A/B 输出对比
- 质量回归统计

但 validation workflow 中有大量确定性规则逻辑，这意味着系统内部已经不是“纯 LLM 黑盒”。

更准确的说法是：

- forecast 主链路：LLM 主导，规则兜底
- validation 链路：规则主导，LLM 补充 narrative

## 8. 如果要把这部分继续补强，建议顺序

### P0

- 给每个 run 产出统一 observability summary
- 把 token 映射为估算 cost
- 增加 per-stage 成功率 / 降级率统计

### P1

- 接 OpenTelemetry 或 LangSmith 一类 trace 平台
- 增加 offline eval dataset
- 增加 prompt / model version 对比报告

### P2

- 建立 AI vs deterministic baseline dashboard
- 建立候选质量与用户选择行为的长期反馈闭环

## 9. 当前最准确的判断

这套系统已经有：

- 面向产品工作流的事件观测
- artifact 审计
- token / duration 统计
- validation trace replay

但还没有：

- 平台级 tracing
- 完整 cost accounting
- 正式 evaluation platform

所以它处于“有足够产品观测能力，尚未进入成熟工程观测平台”的阶段。
