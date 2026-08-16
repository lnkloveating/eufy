import {
  Boxes,
  Database,
  FileSearch,
  Gavel,
  Layers3,
  Map as MapIcon,
  MessageSquareWarning,
  Swords,
  Scale,
  TrendingUp,
  Trophy,
} from "lucide-react";
import type { ReactNode } from "react";
import type { AgentEvent } from "../../types/api";
import { getAgentLabel } from "../../lib/agentLabels";
import { formatClock } from "../../lib/formatters";

/** Nature of a finding — classifies the artifact TYPE, never fabricated data. */
type Nature = "事实" | "官方主张" | "研究归纳" | "假设";

interface FindingMeta {
  label: string;
  nature: Nature;
  icon: ReactNode;
}

function findingMeta(kind: string): FindingMeta {
  if (kind === "retrieval_plan") return { label: "分层检索计划", nature: "研究归纳", icon: <Layers3 size={14} /> };
  if (kind === "evidence") return { label: "本地证据检索", nature: "事实", icon: <Database size={14} /> };
  if (kind.startsWith("lens_forecast:")) return { label: "未来趋势预测", nature: "研究归纳", icon: <TrendingUp size={14} /> };
  if (kind === "lens_forecasts") return { label: "趋势预测汇总", nature: "研究归纳", icon: <TrendingUp size={14} /> };
  if (kind.startsWith("lens_deliberation:")) return { label: "智能体交叉质疑", nature: "研究归纳", icon: <MessageSquareWarning size={14} /> };
  if (kind === "lens_deliberations") return { label: "交叉审核汇总", nature: "研究归纳", icon: <MessageSquareWarning size={14} /> };
  if (kind === "forecast_consensus" || kind === "forecast_consensus_call") return { label: "共识与分歧裁决", nature: "研究归纳", icon: <Scale size={14} /> };
  if (kind.startsWith("candidate_generation_attempt:")) return { label: "候选生成与契约校验", nature: "假设", icon: <Boxes size={14} /> };
  if (kind === "opportunities") return { label: "未来机会聚合", nature: "研究归纳", icon: <MapIcon size={14} /> };
  if (kind === "competitor_evidence") return { label: "竞品资料", nature: "官方主张", icon: <Swords size={14} /> };
  if (kind === "competitive_analysis") return { label: "竞争空白分析", nature: "研究归纳", icon: <Swords size={14} /> };
  if (kind === "raw_candidates") return { label: "产品候选", nature: "假设", icon: <Boxes size={14} /> };
  if (kind.startsWith("reviews:")) return { label: "盲评意见", nature: "研究归纳", icon: <Gavel size={14} /> };
  if (kind === "ranked_candidates") return { label: "候选排名", nature: "研究归纳", icon: <Trophy size={14} /> };
  if (kind.startsWith("product_spec:")) return { label: "标准产品定义", nature: "研究归纳", icon: <FileSearch size={14} /> };
  return { label: kind, nature: "研究归纳", icon: <FileSearch size={14} /> };
}

const NATURE_CLASS: Record<Nature, string> = {
  事实: "chip-accent",
  官方主张: "chip-outline",
  研究归纳: "",
  假设: "chip-outline",
};

/** One research finding, derived from a real `artifact_ready` event. */
export function ResearchFindingCard({ event }: { event: AgentEvent }) {
  const kind =
    typeof event.payload.artifact_kind === "string" ? event.payload.artifact_kind : "artifact";
  const producer =
    typeof event.payload.producer === "string" ? event.payload.producer : event.agent;
  const meta = findingMeta(kind);

  return (
    <article className="finding-card fade-in">
      <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
        <div className="row row-gap-2">
          <span className="finding-icon">{meta.icon}</span>
          <div className="stack" style={{ gap: 1, minWidth: 0 }}>
            <span className="finding-title">{meta.label}</span>
            <span className="agent-role">{getAgentLabel(producer)}</span>
          </div>
        </div>
        <span className={`chip ${NATURE_CLASS[meta.nature]}`}>{meta.nature}</span>
      </div>
      <p className="finding-msg">{event.message}</p>
      <div className="row between" style={{ fontSize: "var(--text-xs)" }}>
        <span className="mono subtle">{String(event.payload.artifact_id ?? "")}</span>
        <span className="subtle">{formatClock(event.created_at)}</span>
      </div>
    </article>
  );
}
