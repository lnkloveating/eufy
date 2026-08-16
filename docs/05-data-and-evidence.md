# 05 Data and Evidence

更新时间：2026-08-16

本文描述当前项目里真实存在的数据、证据、检索和存储结构。

## 1. 当前不是爬虫系统

先说结论：

- 当前仓库没有成型的在线爬虫链路
- 没有实时 web search pipeline
- 当前证据系统的基础是本地 `jsonl`

主要数据源：

- `backend/data/evidence/**/*.jsonl`
- `backend/data/competitors/*.jsonl`

## 2. Evidence 数据模型

核心模型：

- `backend/src/eufy_security_agents/domain/models.py` 中 `EvidenceRecord`

每条证据大致包含：

- `id`
- `title`
- `content`
- `evidence_type`
- `regions`
- `source_name`
- `source_url`
- `published_at`
- `retrieved_at`
- `credibility`
- `tags`
- `layer`
- `scope`
- `topics`
- `claim_status`

这说明 evidence 不是无结构长文本，而是可检索、可解释的结构化记录。

## 3. 分层知识库

当前 evidence 被组织成多层知识：

- `eufy_foundation`
- `regional_market`
- `user_needs`
- `technology`
- `privacy_regulation`
- `business`
- `risk_counterevidence`

相关实现：

- `backend/src/eufy_security_agents/infrastructure/evidence.py`

### 为什么要分层

这样做的好处是：

- 不是只做关键词命中
- 可以强制保留反证
- 可以按地区和知识层做配额
- 可以解释为什么选了这些证据

## 4. Retrieval Plan 是真实对象

接口：

- `POST /knowledge/retrieval-preview`

不会直接只返回一堆 evidence，而是返回：

- `RetrievalPlan`
- `evidence`

`RetrievalPlan` 里会说明：

- requested regions
- query topics
- required layers
- layer quotas
- coverage
- fallback used
- selected evidence ids
- selection reasons
- strategy adjustments

这也是为什么前端可以展示“检索计划”和“证据来源逻辑”。

## 5. Evidence 检索逻辑

真实实现集中在：

- `LocalEvidenceStore.plan()`
- `LocalEvidenceStore.retrieve()`

主要步骤：

1. 把 question、regions、constraints、research context 拼成 query text
2. 从 query text 推断 topic aliases
3. 基于七层知识生成 layer quota
4. 把 strategy weights 对 quota 和 topic boost 施加影响
5. 用 region routing + token overlap + topic match + credibility 排序
6. 强制保证区域覆盖
7. 返回 plan 和 selected evidence

这不是向量库，也不是 embedding 检索，而是本地规则化排序。

## 6. Competitor 数据

竞品数据源：

- `backend/data/competitors/*.jsonl`

核心实现：

- `backend/src/eufy_security_agents/infrastructure/competitors.py`

核心模型：

- `CompetitorRecord`

竞品记录包含的典型信息：

- brand
- product_name
- product_family
- regions
- verified_capabilities
- documented_constraints
- business_model
- privacy_and_storage
- interoperability
- source_url

当前定位很清楚：

- 用官方材料做结构化竞品对比
- 不是实时全网竞品抓取系统

## 7. Claim / Evidence / Hypothesis 的边界

从 README、prompt 和 domain model 看，系统刻意区分：

- verified facts
- official claims
- synthesized inference
- validation hypotheses

这点非常关键，因为它决定了：

- Agent 不能把推断当事实
- ProductSpec 不能把未验证内容写成既成事实
- Validation lab 不能伪装成真实实验

## 8. 数据库存储的核心表

实现：

- `backend/src/eufy_security_agents/infrastructure/repositories.py`

当前 SQLite 里实际创建的主要表：

- `forecast_runs`
- `forecast_run_keys`
- `artifacts`
- `agent_events`
- `products`
- `product_questions`
- `product_revisions`
- `product_suggestion_resolutions`
- `product_selections`
- `validation_projects`
- `validation_events`
- `validation_findings`

### 这些表分别存什么

- `forecast_runs`：一次研究任务的 request 和状态
- `forecast_run_keys`：幂等 key
- `artifacts`：各阶段结构化产物
- `agent_events`：SSE / timeline 事件
- `products`：最终 `ProductSpec`
- `product_questions`：Copilot 问答记录
- `product_revisions`：产品定义修订历史
- `product_selections`：候选到产品定义的选择过程
- `validation_projects`：预验证项目快照
- `validation_events`：验证事件流
- `validation_findings`：finding 到 project 的索引

## 9. Artifact 是核心审计单元

Artifact 表不是附属信息，而是整个系统审计链的核心。

字段里包括：

- `kind`
- `producer`
- `payload_json`
- `model_name`
- `prompt_version`
- `duration_ms`
- `input_tokens`
- `output_tokens`

这意味着：

- 中间结果可以回放
- 前端 ledger 可以真实汇总 token / duration
- 不是只保留最终 candidate

## 10. Schema 层面的特点

这个系统很多地方都采用“先结构化建模，再做展示”：

- request 是结构化的
- evidence 是结构化的
- candidate 是结构化的
- product spec 是结构化的
- validation experiment 是结构化的

这也是它能做工作台而不是聊天记录堆叠的原因。

## 11. 当前没有的东西

截至当前代码：

- 没看到 online crawler ingestion pipeline
- 没看到 vector DB
- 没看到 document parser ingestion workflow
- 没看到外部搜索 API aggregation
- 没看到数据版本治理后台

## 12. 结论

当前的数据与证据层更像：

- 本地结构化知识库
- 可解释规则检索
- 审计友好的 artifact/event 存储

而不是：

- 大规模实时搜索平台
- 自动爬虫数据中台
- 生产级知识图谱系统
