import {
  Cpu,
  Gavel,
  Radar,
  ShieldQuestion,
  TrendingUp,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";
import type { AgentEvent, Artifact } from "../../types/api";
import { getStageLabel } from "../../lib/stageLabels";
import { AgentActivityGrid } from "./AgentActivityCard";
import { ResearchFindingCard } from "./ResearchFindingCard";
import { IntermediateArtifacts } from "./IntermediateArtifacts";

const LENS_AGENTS: { agent: string; icon: ReactNode }[] = [
  { agent: "futures-user_trends", icon: <Users size={17} /> },
  { agent: "futures-technology_trends", icon: <Cpu size={17} /> },
  { agent: "futures-security_futures", icon: <ShieldQuestion size={17} /> },
  { agent: "futures-market_futures", icon: <TrendingUp size={17} /> },
];

const REVIEWER_AGENTS: { agent: string; icon: ReactNode }[] = [
  { agent: "reviewer-innovation", icon: <Gavel size={17} /> },
  { agent: "reviewer-user_value", icon: <Gavel size={17} /> },
  { agent: "reviewer-business_value", icon: <Gavel size={17} /> },
  { agent: "reviewer-feasibility", icon: <Gavel size={17} /> },
  { agent: "reviewer-eufy_synergy", icon: <Gavel size={17} /> },
];

const DELIBERATION_AGENTS: { agent: string; icon: ReactNode }[] = [
  { agent: "deliberator-user_trends", icon: <Users size={17} /> },
  { agent: "deliberator-technology_trends", icon: <Cpu size={17} /> },
  { agent: "deliberator-security_futures", icon: <ShieldQuestion size={17} /> },
  { agent: "deliberator-market_futures", icon: <TrendingUp size={17} /> },
];

function focusMessage(stage: string, regions: string[]): string {
  const regionText = regions.join("、") || "目标市场";
  switch (stage) {
    case "queued":
      return "正在编排研究流水线并准备多 Agent 协作……";
    case "evidence_selection":
      return `正在从本地分层知识库检索 ${regionText} 的住宅、用户需求、隐私法规与商业模式资料……`;
    case "future_forecasting":
      return "四个视角 Agent 正在并行预测用户、技术、安防与市场趋势……";
    case "forecast_deliberation":
      return "四个视角正在交叉审核：接受有证据的观点、质疑过度推断，并修正自身置信度……";
    case "consensus_formation":
      return "独立裁决 Agent 正在区分证据共识、少数意见、未解决分歧与下一步验证需求……";
    case "opportunity_synthesis":
      return "正在合并四个预测视角，去重并形成未来机会……";
    case "competitor_analysis":
      return "正在对比 Ring、Google Nest、Arlo、Reolink、Aqara、SimpliSafe 等竞品的能力与边界，识别可验证的竞争空白……";
    case "candidate_generation":
      return "正在将未来机会与竞争空白转换为差异化产品候选……";
    case "candidate_review":
      return "五个盲评 Agent 正在从创新性、用户价值、商业价值、可行性与 eufy 协同性独立打分……";
    default:
      return "多个 Agent 正在并行工作，研究发现会实时出现在这里。";
  }
}

export interface LiveResearchCanvasProps {
  stage: string;
  regions: string[];
  events: AgentEvent[];
  artifacts: Artifact[];
}

/** Middle column: event/artifact-driven live research canvas. */
export function LiveResearchCanvas({ stage, regions, events, artifacts }: LiveResearchCanvasProps) {
  const findings = events.filter((event) => event.event_type === "artifact_ready");
  const recentFindings = [...findings].reverse().slice(0, 6);

  return (
    <div className="stack stack-5">
      {/* Current focus */}
      <div className="card focus-card">
        <div className="row row-gap-3" style={{ alignItems: "flex-start" }}>
          <span className="focus-icon">
            <Radar size={18} aria-hidden="true" />
          </span>
          <div className="stack" style={{ gap: 3, minWidth: 0 }}>
            <span className="eyebrow">当前研究阶段 · {getStageLabel(stage)}</span>
            <p style={{ color: "var(--ink-800)" }}>{focusMessage(stage, regions)}</p>
          </div>
        </div>
        <div className="scan-bar" aria-hidden="true">
          <span />
        </div>
      </div>

      {/* Parallel-agent activity for the two fan-out phases */}
      {stage === "future_forecasting" && (
        <div className="stack stack-3">
          <span className="opp-section-label">多视角未来预测 · 并行 Agent</span>
          <AgentActivityGrid agents={LENS_AGENTS} events={events} artifacts={artifacts} />
        </div>
      )}
      {stage === "forecast_deliberation" && (
        <div className="stack stack-3">
          <span className="opp-section-label">结构化审议 · 并行交叉审核</span>
          <AgentActivityGrid agents={DELIBERATION_AGENTS} events={events} artifacts={artifacts} />
        </div>
      )}
      {stage === "candidate_review" && (
        <div className="stack stack-3">
          <span className="opp-section-label">多维盲评 · 并行 Reviewer</span>
          <AgentActivityGrid agents={REVIEWER_AGENTS} events={events} artifacts={artifacts} />
        </div>
      )}

      {/* Live findings feed (real artifact_ready events only) */}
      <div className="stack stack-3">
        <span className="opp-section-label">实时研究发现</span>
        {recentFindings.length === 0 ? (
          <div className="card card-pad muted" style={{ fontSize: "var(--text-sm)" }}>
            正在生成第一份可审计研究产物…
          </div>
        ) : (
          <div className="finding-feed">
            {recentFindings.map((event) => (
              <ResearchFindingCard key={event.sequence} event={event} />
            ))}
          </div>
        )}
      </div>

      {/* Accumulated structured artifacts (reused panels) */}
      {artifacts.length > 0 && (
        <div className="stack stack-3">
          <span className="opp-section-label">已生成的研究产物</span>
          <IntermediateArtifacts artifacts={artifacts} />
        </div>
      )}
    </div>
  );
}
