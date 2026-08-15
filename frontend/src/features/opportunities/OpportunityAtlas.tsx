import { useState } from "react";
import { ChevronLeft, ChevronRight, Map as MapIcon, ShieldAlert, Sparkles } from "lucide-react";

import type { EvidenceRecord, Opportunity } from "../../types/api";
import { ConfidenceBar } from "../../components/ui/ConfidenceBar";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { EvidenceDrawer } from "../../components/EvidenceDrawer/EvidenceDrawer";

export interface OpportunityAtlasProps {
  opportunities: Opportunity[];
  evidence: EvidenceRecord[];
}

/** "Opportunity Atlas" - evidence-grounded future opportunity cards. */
export function OpportunityAtlas({ opportunities, evidence }: OpportunityAtlasProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [drawerIds, setDrawerIds] = useState<string[] | null>(null);
  const evidenceById = new Map(evidence.map((record) => [record.id, record]));

  if (opportunities.length === 0) {
    return (
      <EmptyState
        icon={<MapIcon size={24} aria-hidden="true" />}
        title="暂无机会方向"
        description="预测完成后，聚合后的未来机会会以图谱卡片呈现。"
      />
    );
  }

  const activeOpportunity = opportunities[activeIndex % opportunities.length]!;

  const goPrevious = () => {
    if (opportunities.length <= 1) return;
    setActiveIndex((current) => (current - 1 + opportunities.length) % opportunities.length);
  };

  const goNext = () => {
    if (opportunities.length <= 1) return;
    setActiveIndex((current) => (current + 1) % opportunities.length);
  };

  const drawerRecords = drawerIds
    ? drawerIds.map((id) => evidenceById.get(id)).filter((r): r is EvidenceRecord => Boolean(r))
    : [];

  return (
    <>
      <article className="card card-hover opp-card opportunity-carousel-card">
        <div className="row between wrap row-gap-2 opportunity-carousel-head">
          <div className="row row-gap-2 wrap opportunity-carousel-title" style={{ minWidth: 0 }}>
            <span className="chip mono">{activeOpportunity.id}</span>
            {opportunities.length > 1 && (
              <span className="chip chip-outline">
                {activeIndex + 1} / {opportunities.length}
              </span>
            )}
          </div>
          <div className="row row-gap-2 opportunity-carousel-actions">
            <button
              type="button"
              className="carousel-arrow"
              onClick={goPrevious}
              disabled={opportunities.length <= 1}
              aria-label="上一个机会"
              title="上一个机会"
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="carousel-arrow"
              onClick={goNext}
              disabled={opportunities.length <= 1}
              aria-label="下一个机会"
              title="下一个机会"
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="opportunity-carousel-body" key={activeOpportunity.id}>
          <div className="row between" style={{ alignItems: "flex-start" }}>
            <span className="chip mono">{activeOpportunity.id}</span>
            <span className="chip chip-outline">{activeOpportunity.opportunity_window}</span>
          </div>

          <div className="stack stack-2">
            <h3 className="opp-title">{activeOpportunity.title}</h3>
            <p className="opp-job">{activeOpportunity.unmet_job}</p>
          </div>

          <ConfidenceBar value={activeOpportunity.confidence} />

          <div className="stack stack-2">
            <span className="opp-section-label">Why now</span>
            <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
              {activeOpportunity.why_now}
            </p>
          </div>

          {activeOpportunity.enabling_trends.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label">
                <Sparkles size={12} aria-hidden="true" /> 驱动趋势
              </span>
              <div className="taglist">
                {activeOpportunity.enabling_trends.map((trend) => (
                  <span className="chip" key={trend}>
                    {trend}
                  </span>
                ))}
              </div>
            </div>
          )}

          {activeOpportunity.counter_evidence.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label" style={{ color: "var(--warn-ink)" }}>
                <ShieldAlert size={12} aria-hidden="true" /> 反证 Counter-evidence
              </span>
              <div className="bullets">
                {activeOpportunity.counter_evidence.map((item, index) => (
                  <div className="bullet" key={index} style={{ fontSize: "var(--text-sm)" }}>
                    {item}
                  </div>
                ))}
              </div>
            </div>
          )}

          {Object.entries(activeOpportunity.regional_differences).length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label">地区差异 Regional differences</span>
              {Object.entries(activeOpportunity.regional_differences).map(([region, differences]) => (
                <div className="def-row" key={region}>
                  <span className="def-key">{region}</span>
                  <span className="def-val">{differences.join("、")}</span>
                </div>
              ))}
            </div>
          )}

          <div className="hr" />

          <div className="row between wrap row-gap-3">
            <div className="row row-gap-2 wrap">
              {activeOpportunity.target_regions.slice(0, 3).map((region) => (
                <span className="chip chip-outline" key={region}>
                  {region}
                </span>
              ))}
            </div>
            {activeOpportunity.evidence_ids.length > 0 && (
              <button
                type="button"
                className="chip chip-evidence is-link"
                onClick={() => setDrawerIds(activeOpportunity.evidence_ids)}
              >
                {activeOpportunity.evidence_ids.length} 条证据
                <ChevronRight size={12} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </article>

      <EvidenceDrawer
        open={drawerIds !== null}
        onClose={() => setDrawerIds(null)}
        records={drawerRecords}
        title="机会引用证据"
      />
    </>
  );
}
