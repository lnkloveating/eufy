import type { ReactNode } from "react";
import { Cpu, Database, Gauge, Layers3, Loader2, Boxes, Map as MapIcon, Swords } from "lucide-react";
import type { AgentEvent, Artifact } from "../../types/api";
import { useCountUp } from "../../lib/motion";
import {
  aggregateArtifactMetrics,
  deriveLedgerCounts,
  formatDurationMs,
} from "./researchMetrics";

const COMPLETED_EVENTS = new Set([
  "agent_completed",
  "product_definition_completed",
  "evidence_selected",
]);

function AnimatedValue({ value }: { value: number }) {
  const shown = useCountUp(value);
  return <span style={{ fontVariantNumeric: "tabular-nums" }}>{shown.toLocaleString()}</span>;
}

function LedgerRow({
  icon,
  label,
  children,
}: {
  icon?: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="ledger-row">
      <span className="ledger-label">
        {icon}
        {label}
      </span>
      <span className="ledger-value">{children}</span>
    </div>
  );
}

export interface ResearchLedgerProps {
  artifacts: Artifact[];
  events: AgentEvent[];
  /** True while the run is still active (drives the "计算中" state). */
  active: boolean;
}

/**
 * Research Ledger — real, deduplicated metrics from backend artifacts only.
 * Token totals never grow by time; they are the confirmed sums of completed
 * artifacts. An in-flight agent is shown as "计算中", not as fake streaming.
 */
export function ResearchLedger({ artifacts, events, active }: ResearchLedgerProps) {
  const metrics = aggregateArtifactMetrics(artifacts);
  const counts = deriveLedgerCounts(artifacts);

  const started = new Set<string>();
  const completed = new Set<string>();
  for (const event of events) {
    if (!event.agent) continue;
    if (event.event_type === "agent_started" || event.event_type === "product_definition_started") {
      started.add(event.agent);
    }
    if (COMPLETED_EVENTS.has(event.event_type)) completed.add(event.agent);
  }
  const inFlight = [...started].filter((agent) => !completed.has(agent));
  const computing = active && inFlight.length > 0;

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">
          <Gauge size={16} aria-hidden="true" /> Research Ledger
        </span>
        {computing && (
          <span className="conn-pill conn-connecting">
            <Loader2 size={11} className="spin-inline" aria-hidden="true" /> 计算中
          </span>
        )}
      </div>
      <div className="panel-body stack stack-2">
        <div className="ledger-section-label">研究产物</div>
        <LedgerRow icon={<Database size={13} aria-hidden="true" />} label="已选择证据">
          <AnimatedValue value={counts.evidenceCount} />
        </LedgerRow>
        <LedgerRow icon={<Layers3 size={13} aria-hidden="true" />} label="知识分层">
          <AnimatedValue value={counts.knowledgeLayerCount} />
        </LedgerRow>
        <LedgerRow icon={<Swords size={13} aria-hidden="true" />} label="已分析竞品资料">
          <AnimatedValue value={counts.competitorCount} />
        </LedgerRow>
        <LedgerRow icon={<Cpu size={13} aria-hidden="true" />} label="已完成 Agent">
          <AnimatedValue value={completed.size} />
        </LedgerRow>
        <LedgerRow icon={<MapIcon size={13} aria-hidden="true" />} label="机会">
          <AnimatedValue value={counts.opportunityCount} />
        </LedgerRow>
        <LedgerRow icon={<Swords size={13} aria-hidden="true" />} label="竞争空白">
          <AnimatedValue value={counts.gapCount} />
        </LedgerRow>
        <LedgerRow icon={<Boxes size={13} aria-hidden="true" />} label="候选">
          <AnimatedValue value={counts.candidateCount} />
        </LedgerRow>

        <div className="hr" style={{ margin: "var(--space-2) 0" }} />
        <div className="ledger-section-label">Token 与耗时（已确认）</div>
        <LedgerRow label="已确认输入 Token">
          <AnimatedValue value={metrics.confirmedInputTokens} />
        </LedgerRow>
        <LedgerRow label="已确认输出 Token">
          <AnimatedValue value={metrics.confirmedOutputTokens} />
        </LedgerRow>
        <LedgerRow label="总 Token">
          <strong>
            <AnimatedValue value={metrics.totalTokens} />
          </strong>
        </LedgerRow>
        <LedgerRow label="当前调用">
          {computing ? (
            <span className="subtle">计算中…</span>
          ) : (
            <span className="subtle">—</span>
          )}
        </LedgerRow>
        <LedgerRow label="累计模型耗时">
          <span style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatDurationMs(metrics.totalDurationMs)}
          </span>
        </LedgerRow>
        <LedgerRow label="当前模型">
          <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
            {metrics.modelName ?? "—"}
          </span>
        </LedgerRow>
      </div>
    </div>
  );
}
