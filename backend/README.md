# eufy Future Product Forecaster — Backend

该服务用 AI 原生多角色流水线预测未来 eufy Security 产品方向。用户提供预测周期、地区、目标人群和约束，系统从本地分层知识库检索证据，生成多个候选产品；用户可选择任意候选，再生成标准化 `ProductSpec`。当前范围止于验证环节之前，不包含 2D、技术或商业模拟。

## 设计原则

- 不在代码或 Prompt 中预设 SenseMesh 或其他获胜产品。
- 相同问题允许产生不同候选，但每项事实性判断必须引用检索到的证据 ID。
- 严格区分已验证事实、官方主张、研究归纳和待验证假设。
- 地区结论不能无依据地迁移到其他地区。
- 生成 Agent、聚合 Agent 与盲评 Agent 分离。
- 用户可以选择任意候选，不强制选择排行榜第一名。
- ProductSpec 只生成验证计划，不伪造验证结果。

## 预测流程

```text
ForecastRequest
  -> Retrieval Planner（地区路由 + 主题识别 + 分层配额）
  -> Local Evidence Store（召回、重排、反证保留）
  -> 4 Futures Lens Agents（并行）
  -> 4 Cross-Lens Deliberation Agents（并行交叉审核）
  -> Forecast Consensus Judge（共识、少数意见与未解决分歧）
  -> Opportunity Synthesizer
  -> Competitor Analysis Agent（官方竞品资料 + 竞争空白）
  -> Product Architect
  -> 5 Blind Review Agents（并行）
  -> Ranked Candidates
  -> Human Selection（幂等）
  -> Product Definition Agent
  -> ProductSpec v1 + Validation Readiness
```

预测视角：用户趋势、技术趋势、安防威胁、市场商业。

评审维度：创新性、用户价值、商业价值、可行性、eufy 协同性。

## 结构化审议

四个未来预测视角先独立输出，避免过早互相影响；随后进入一轮固定的结构化交叉审核。每个视角必须接受有证据支持的跨领域观点、提出具体质疑、说明自身观点如何修正，并保留至少一个尚未解决的问题。最后由独立共识裁决 Agent 区分：

- 有证据支持的共识
- 已解决和未解决的分歧
- 被否决的过度推断
- 少数意见
- 证据缺口与后续验证需求

机会聚合 Agent 同时读取原始预测、交叉审核和共识裁决，不会把“多数同意”错误等同于事实。

## 候选引用修复

候选生成使用三个互斥 ID 命名空间：`opportunity_ids` 只能使用 `OPP-*`，研究 `evidence_ids` 只能使用召回的 `EV-*`，竞争定位只能使用召回的 `COMP-*`。该规则同时写入 JSON Schema、Prompt 和后端确定性校验。

如果模型输出混淆 ID 或缺少竞争定位，后端会保存失败尝试、发出 `candidate_validation_failed` 事件，并最多进行两次低温定向修复。修复仍不通过时才终止任务，不会静默删除引用或伪造替代证据。

## 竞品分析

竞品资料位于 `data/competitors/*.jsonl`。当前包含 Ring、Google Nest、Arlo、Reolink、Aqara 和 SimpliSafe 共 18 条官方产品或服务资料。每条记录保存地区、已确认能力、官方文档明确的边界、商业模式、隐私与存储方式、互操作能力和来源链接。

竞品分析发生在“未来机会聚合”之后、“候选产品生成”之前，因此竞品不会替代未来预测，也不会把流程变成照抄现有产品。竞品 Agent 输出：

- 已被市场建立的基础能力
- 各品牌有证据支持的优势与限制
- 订阅、锁定、隐私和互操作空白
- 3–6 个连接未来机会的竞争空白
- 每个空白的模仿风险、设计启示和验证问题

产品架构 Agent 必须为每个候选提供 `competitive_positioning`，说明最近替代品、可借鉴模式、可防御差异、非模仿理由、竞品跟进风险及后续验证问题。系统会校验所有竞品证据 ID，禁止引用本地资料库中不存在的记录。

## 本地分层知识库

知识库位于 `data/evidence/**/*.jsonl`，当前不使用爬虫。区域包包含中国、美国和西欧，并与全球基础证据共同检索。每条记录带有地区、知识层、主题、声明状态、时间和可信度元数据。

知识层包括：

- `eufy_foundation`：品牌、产品与现有能力边界
- `regional_market`：区域家庭、居住和市场结构
- `user_needs`：用户任务、痛点和行为
- `technology`：AI、传感器、连接与计算趋势
- `privacy_regulation`：隐私、安全和合规要求
- `business`：渠道、定价和商业模式
- `risk_counterevidence`：反证、风险与失败条件

检索不是把全部记录注入 Prompt，而是：

1. 根据 `regions` 只路由所选地区和 Global 基线。
2. 根据用户问题识别主题。
3. 按知识层配额召回并混合重排。
4. 强制保留风险或反证。
5. 返回检索计划、覆盖率与最终证据包，供前端解释。

未建设专用区域包的地区会返回 `limited` 覆盖提示，并以 Global 证据降级；模型不得把其他地区结论直接套用。

## 配置与启动

```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
python -m pip install -e ".[dev]"
python -m uvicorn eufy_security_agents.main:app --reload --port 8000
```

密钥只放在 `.env`，该文件已被 `.gitignore` 排除。API 文档位于 `http://localhost:8000/docs`。

## 主要 API

```text
GET  /api/v1/health
GET  /api/v1/knowledge/coverage?regions=China&regions=United%20States
POST /api/v1/knowledge/retrieval-preview

POST /api/v1/forecast-runs
GET  /api/v1/forecast-runs/{run_id}
GET  /api/v1/forecast-runs/{run_id}/events
GET  /api/v1/forecast-runs/{run_id}/events/stream
GET  /api/v1/forecast-runs/{run_id}/artifacts
GET  /api/v1/forecast-runs/{run_id}/result
GET  /api/v1/forecast-runs/{run_id}/candidates
POST /api/v1/forecast-runs/{run_id}/selections
```

前端可在任务运行期间通过 SSE 的 `artifact_ready` 事件和 artifacts 接口读取已经完成的中间结果。选择接口接受 `idempotency_key`，重复提交同一选择会返回同一个 ProductSpec。

### 创建预测示例

```json
{
  "question": "预测未来三年欧美家庭的 AI 原生安防产品机会",
  "category": "eufy Security",
  "forecast_horizon_years": 3,
  "regions": ["United States", "Germany"],
  "target_users": ["Families", "Detached-home households"],
  "price_segment": "mid-to-premium",
  "candidate_count": 6,
  "constraints": ["privacy-first", "manufacturable within three years"],
  "research_context": {
    "housing_types": ["独栋住宅"],
    "household_members": ["有儿童家庭", "有宠物家庭"],
    "security_scenarios": ["入侵与周界", "包裹与门前"],
    "current_devices": ["摄像头或门铃", "HomeBase 或本地存储"],
    "pain_points": ["误报过多", "告警太晚"],
    "privacy_preferences": ["优先端侧 AI", "优先本地存储"],
    "desired_outcomes": ["更早预防风险", "降低误报"],
    "innovation_posture": "平衡创新与落地"
  }
}
```

`research_context` 的所有字段均可选并向后兼容；有值时会参与本地证据与竞品检索，
同时传入预测、交叉审议、共识、产品架构和 ProductSpec Agent。空字段代表未知，
不会被解释成默认偏好。`GET /api/v1/forecast-options` 返回前端可用的选项目录。

## 可靠性边界

- 当前后台仍基于 FastAPI `BackgroundTasks`，不是分布式任务队列。
- 每个模型阶段都有独立时间预算（`STAGE_TIMEOUT_SECONDS`，默认 75 秒）。超时、模型结构错误或可修复校验错误会切换到基于本地证据与最后有效检查点的确定性降级结果，并在事件与最终结果中明确标注。
- `LLM_TIMEOUT_SECONDS` 是一次逻辑生成（包括内部重试）的总预算，不会再按重试次数成倍放大。
- 单次工作流仍有总超时保护；应用重启会把遗留的 `running` 任务标记为中断，避免永久卡住，但不会自动续跑。
- SQLite 适合单机 Demo。生产版本应使用独立 Worker、队列和外部数据库。

## 测试

```bash
pytest -q -p no:cacheprovider
ruff check src tests
ruff format --check src tests
mypy src
```

默认测试使用 Fake LLM，不消耗 API 额度。若要验证当前真实模型和 JSON Schema 输出，可显式运行：

```bash
RUN_LIVE_LLM_TEST=1 pytest -q tests/integration/test_live_llm.py
```

## 下一阶段

验证系统将读取 `ProductSpec.validation_readiness` 和 `regional_fit`，自动选择技术、商业、隐私、用户体验、空间覆盖或 2D 场景验证器，并把发现的问题回写为淘汰或迭代依据。
