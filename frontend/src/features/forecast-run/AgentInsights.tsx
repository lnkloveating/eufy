import { useState } from "react";
import { ChevronRight, Compass, Lightbulb } from "lucide-react";
import type { EvidenceRecord, LensForecast } from "../../types/api";
import { getLensLabel } from "../../lib/agentLabels";
import { ConfidenceBar } from "../../components/ui/ConfidenceBar";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { EvidenceDrawer } from "../../components/EvidenceDrawer/EvidenceDrawer";

export interface AgentInsightsProps {
  forecasts: LensForecast[];
  evidence: EvidenceRecord[];
}

/**
 * Structured forecasts per lens. Renders only the backend's structured output
 * (thesis / signals / implications) — never any model chain-of-thought.
 */
export function AgentInsights({ forecasts, evidence }: AgentInsightsProps) {
  const [drawerIds, setDrawerIds] = useState<string[] | null>(null);
  const evidenceById = new Map(evidence.map((record) => [record.id, record]));

  if (forecasts.length === 0) {
    return (
      <EmptyState
        icon={<Compass size={24} aria-hidden="true" />}
        title="暂无 Agent 洞察"
        description="预测完成后，四个视角的结构化分析会显示在这里。"
      />
    );
  }

  const openEvidence = (ids: string[]) => setDrawerIds(ids);
  const drawerRecords = drawerIds
    ? drawerIds.map((id) => evidenceById.get(id)).filter((r): r is EvidenceRecord => Boolean(r))
    : [];

  return (
    <>
      <div className="stack stack-5">
        {forecasts.map((forecast) => (
          <article className="card card-pad stack stack-4" key={forecast.lens}>
            <div className="stack stack-2">
              <div className="row row-gap-3">
                <span className="chip chip-accent">{getLensLabel(forecast.lens)}</span>
              </div>
              <p style={{ fontSize: "var(--text-md)", color: "var(--ink-800)" }}>
                {forecast.thesis}
              </p>
            </div>

            <div className="stack stack-3">
              <span className="opp-section-label">趋势信号 Signals</span>
              {forecast.signals.map((signal, index) => (
                <div
                  key={`${forecast.lens}-${index}`}
                  className="card"
                  style={{ padding: "var(--space-4)", background: "var(--surface-2)" }}
                >
                  <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
                    <strong style={{ fontSize: "var(--text-base)" }}>{signal.title}</strong>
                    <span className="chip chip-outline">{signal.impact_horizon}</span>
                  </div>
                  <p className="muted" style={{ fontSize: "var(--text-sm)", margin: "6px 0 10px" }}>
                    {signal.description}
                  </p>
                  <div className="row between wrap row-gap-3">
                    <div style={{ maxWidth: 220, flex: 1 }}>
                      <ConfidenceBar value={signal.confidence} />
                    </div>
                    {signal.evidence_ids.length > 0 && (
                      <button
                        type="button"
                        className="chip chip-evidence is-link"
                        onClick={() => openEvidence(signal.evidence_ids)}
                      >
                        {signal.evidence_ids.length} 条证据
                        <ChevronRight size={12} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                  {signal.uncertainty && (
                    <p
                      className="subtle"
                      style={{ fontSize: "var(--text-xs)", marginTop: 8 }}
                    >
                      不确定性：{signal.uncertainty}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {forecast.implications.length > 0 && (
              <div className="stack stack-2">
                <span className="opp-section-label">
                  <Lightbulb size={13} aria-hidden="true" /> 推论 Implications
                </span>
                <div className="bullets">
                  {forecast.implications.map((implication, index) => (
                    <div className="bullet" key={index}>
                      {implication}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>

      <EvidenceDrawer
        open={drawerIds !== null}
        onClose={() => setDrawerIds(null)}
        records={drawerRecords}
        title="信号引用证据"
      />
    </>
  );
}
