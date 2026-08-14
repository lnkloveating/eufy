# eufy FutureLab — Frontend

**AI-Native Product Forecasting Workbench** — 一个连接真实后端的企业级多 Agent 产品预测与决策工作台。

> 产品不是预设的，而是由多个 Agent 根据用户输入和本地证据动态预测生成。
> 同一套工作流会根据问题、地区、用户和约束生成不同的未来产品组合。

## 技术栈

- React 19 + TypeScript + Vite 7
- react-router-dom（路由）
- @tanstack/react-query（服务端状态、轮询兜底）
- lucide-react（图标）
- zod（客户端校验，按需）/ clsx
- 原生 CSS + CSS Variables（design tokens），评分雷达图用原生 SVG，无大型 UI / 图表框架

## Deep Research 体验

体验被重构为类似 Deep Research 的研究工作台流程：

```
Research Home → Research Setup（分步弹窗）→ Live Research → Research Report
→ 用户选择产品 → ProductSpec → Validation Lab（Coming Soon）
```

- **Research Home（`/`）**：只保留大型自然语言研究输入框、示例 Prompt、最近研究入口和真实系统状态，让首页保持 Deep Research 式的单一任务入口。
- **Research Setup**：点击开始后进入四步大型弹窗：研究范围 → 研究上下文 → 预测偏好与资料 → 确认 Brief。研究范围为必填；上下文与补充资料可跳过；最后一步才创建后端 Run。产品偏好继续真实影响 RAG、Agent、候选组合和六维评分。
- **补充资料**：企业内部数据和重点调研资源仅保存当前页面中的 URL 与文件元数据，不读取正文、不持久化，也不会进入 `ForecastRequest`；自动公开资料开关在当前构建中保持关闭。
- **Live Research（`/runs/:runId`）**：三栏工作台 —— 左「研究流水线」、中「实时研究画布」、右「Research Ledger」。动效**只由真实 SSE 事件与 Artifact 驱动**（阶段呼吸、Agent 扫描、发现卡淡入、数字平滑到真实值），遵守 `prefers-reduced-motion`。
- **Research Ledger（`researchMetrics.ts`）**：Token/耗时/模型仅取自 Artifact 的 `input_tokens/output_tokens/duration_ms/model_name`，按 Artifact ID 去重、`null` 不计入，当前 Agent 未完成显示“计算中”，绝不伪造逐 Token 流式数字。
- **Research Report**：完成后保持工作台结构，中间区切换为报告（研究摘要 + Tabs：产品候选 / 共识与分歧 / 机会图谱 / Agent 洞察 / RAG 检索计划 / 竞品与空白 / 证据库）。

## 页面与路由

| 路由 | 说明 |
| --- | --- |
| `/` | Deep Research Home（研究输入 + 澄清 + 研究任务确认） |
| `/runs/:runId` | Live Research 工作台（流水线、Agent 独立判断、交叉质疑、观点修正、共识与证据） |
| `/runs/:runId/product-definition` | 当前研究的产品定义工作区（预测中 → 候选对比与人工选择 → 生成中） |
| `/products/:productId` | 标准 ProductSpec（地区适配、竞争定位、Kill Criteria、Validation Readiness） |

运行工作台会实时展示分层 RAG、独立预测、交叉质疑、共识裁决、未来机会、竞品空白和候选盲评。“共识与分歧”页展示每个 Agent 提出的质疑、观点修正、少数意见、证据缺口和后续验证需求。

## 环境变量

复制 `.env.example` 为 `.env`（可选，默认已指向 `http://localhost:8000/api/v1`）：

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

前端**不会**保存、读取或展示任何 LLM API Key —— 密钥只存在后端环境变量中。

## 本地开发

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173（后端 CORS 已允许该端口）
```

## 构建与测试

```bash
npm run build    # tsc -b + vite build
npm run test     # vitest（权重校验 / 错误解析 / SSE 去重 / 阶段映射 / 候选排序）
```

## 后端联调

先启动后端（见 `../backend/README.md`）：

```bash
cd ../backend
python -m venv .venv && source .venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m uvicorn eufy_security_agents.main:app --reload --port 8000
```

- 后端：`http://localhost:8000`（API 前缀 `/api/v1`，文档 `http://localhost:8000/docs`）
- 前端：`http://localhost:5173`
- 后端需在环境变量中配置 `LLM_API_KEY` 才能真实执行多 Agent 预测；未配置时前端会显示明显但克制的警告并禁用开始按钮。

## 目录结构

```text
src/
├─ app/           # App、router、providers
├─ components/    # AppShell / StatusBadge / EmptyState / ErrorState / LoadingSkeleton
│                 # ScoreRadar / AgentTimeline / StagePipeline / EvidenceDrawer / ui/*
├─ features/      # forecast-create / forecast-run / opportunities / candidates / product-spec
├─ lib/           # api/(client,forecastApi,sse) / queries / stageLabels / agentLabels
│                 # weights / candidates / formatters / recent
├─ types/         # api.ts（与后端 Pydantic 模型 1:1）
└─ styles/        # tokens.css / globals.css / components.css
```

## 实时事件（SSE）

工作台通过带 `event:` 名称的 SSE（`addEventListener` 逐类型注册）接收进度；先用普通事件接口回放历史事件，再连接流；按 `sequence` 去重排序；断线时以每 2 秒轮询任务与事件作为兜底；`run_completed` / `run_failed` 后停止并读取结果。ProductSpec 生成不依赖原 SSE 连接（长耗时按钮 loading）。

## 当前未实现（下一阶段）

“产品验证实验室”仅显示 Coming Soon，不产生任何验证结果。未实现：2D 场景模拟、技术/商业/隐私模拟、视频生成、真实设备控制、可编辑 Agent 画布、用户登录、任务删除/取消、历史任务列表（后端暂无对应接口）。
```
