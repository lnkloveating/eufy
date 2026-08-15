import { useState } from "react";
import { ChevronLeft, ChevronRight, Compass, Lightbulb } from "lucide-react";

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
 * (thesis / signals / implications) - never any model chain-of-thought.
 */
export function AgentInsights({ forecasts, evidence }: AgentInsightsProps) {
  const [activeIndex, setActiveIndex] = useState(0);
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

  const activeForecast = forecasts[activeIndex % forecasts.length]!;

  const goPrevious = () => {
    if (forecasts.length <= 1) return;
    setActiveIndex((current) => (current - 1 + forecasts.length) % forecasts.length);
  };

  const goNext = () => {
    if (forecasts.length <= 1) return;
    setActiveIndex((current) => (current + 1) % forecasts.length);
  };

  const openEvidence = (ids: string[]) => setDrawerIds(ids);
  const drawerRecords = drawerIds
    ? drawerIds.map((id) => evidenceById.get(id)).filter((r): r is EvidenceRecord => Boolean(r))
    : [];

  return (
    <>
      <article className="card card-pad stack stack-4 agent-insights-carousel-card">
        <div className="row between wrap row-gap-2 agent-insights-carousel-head">
          <div className="row row-gap-2 wrap agent-insights-carousel-title" style={{ minWidth: 0 }}>
            <span className="chip chip-accent">{getLensLabel(activeForecast.lens)}</span>
            {forecasts.length > 1 && (
              <span className="chip chip-outline">
                {activeIndex + 1} / {forecasts.length}
              </span>
            )}
          </div>

          <div className="row row-gap-2 agent-insights-carousel-actions">
            <button
              type="button"
              className="carousel-arrow"
              onClick={goPrevious}
              disabled={forecasts.length <= 1}
              aria-label="上一个 Agent"
              title="上一个 Agent"
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="carousel-arrow"
              onClick={goNext}
              disabled={forecasts.length <= 1}
              aria-label="下一个 Agent"
              title="下一个 Agent"
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="agent-insights-carousel-body" key={activeForecast.lens}>
          <div className="stack stack-2">
            <div className="row row-gap-3">
              <span className="chip chip-accent">{getLensLabel(activeForecast.lens)}</span>
            </div>
            <p style={{ fontSize: "var(--text-md)", color: "var(--ink-800)" }}>
              {activeForecast.thesis}
            </p>
          </div>

          <div className="stack stack-3">
            <span className="opp-section-label">趋势信号 Signals</span>
            {activeForecast.signals.map((signal, index) => (
              <div
                key={`${activeForecast.lens}-${index}`}
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
                    </button>
                  )}
                </div>
                {signal.uncertainty && (
                  <p className="subtle" style={{ fontSize: "var(--text-xs)", marginTop: 8 }}>
                    不确定性：{signal.uncertainty}
                  </p>
                )}
              </div>
            ))}
          </div>

          {activeForecast.implications.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label">
                <Lightbulb size={13} aria-hidden="true" /> 推论 Implications
              </span>
              <div className="bullets">
                {activeForecast.implications.map((implication, index) => (
                  <div className="bullet" key={index}>
                    {implication}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </article>

      <EvidenceDrawer
        open={drawerIds !== null}
        onClose={() => setDrawerIds(null)}
        records={drawerRecords}
        title="信号引用证据"
      />
    </>
  );
}
