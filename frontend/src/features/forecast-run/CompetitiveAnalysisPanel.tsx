import { useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  SearchCheck,
  ShieldCheck,
  Swords,
} from "lucide-react";

import type { CompetitiveAnalysis, CompetitorRecord } from "../../types/api";

export function CompetitiveAnalysisPanel({
  analysis,
  evidence,
}: {
  analysis: CompetitiveAnalysis | null;
  evidence: CompetitorRecord[];
}) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!analysis) {
    return <div className="card card-pad muted">竞争分析尚未生成。</div>;
  }

  const brands = [...new Set(evidence.map((item) => item.brand))];
  const activeGap = analysis.gaps[activeIndex % analysis.gaps.length];

  const goPrevious = () => {
    if (analysis.gaps.length <= 1) return;
    setActiveIndex((current) => (current - 1 + analysis.gaps.length) % analysis.gaps.length);
  };

  const goNext = () => {
    if (analysis.gaps.length <= 1) return;
    setActiveIndex((current) => (current + 1) % analysis.gaps.length);
  };

  return (
    <div className="stack stack-5">
      <div className="row wrap row-gap-2">
        <span className="chip">
          <Swords size={12} /> {brands.length} 个竞品品牌
        </span>
        <span className="chip">
          <SearchCheck size={12} /> {evidence.length} 条官方资料
        </span>
        <span className="chip chip-accent">{analysis.gaps.length} 个竞争空白</span>
      </div>

      <div className="spec-grid">
        <SummaryCard title="竞品已建立的能力" items={analysis.established_capabilities} />
        <SummaryCard title="仍未充分满足的需求" items={analysis.underserved_needs} />
        <SummaryCard title="订阅与锁定空白" items={analysis.subscription_or_lock_in_gaps} />
        <SummaryCard title="隐私与互操作空白" items={analysis.privacy_and_interoperability_gaps} />
      </div>

      <div className="stack stack-3">
        <span className="opp-section-label">竞争空白 White-space Map</span>
        {analysis.gaps.length > 0 && activeGap && (
          <article className="card card-pad stack stack-3 competitive-carousel-card">
            <div className="row between wrap row-gap-2 competitive-carousel-head">
              <div className="row row-gap-2 wrap competitive-carousel-title" style={{ minWidth: 0 }}>
                <span className="chip mono">{activeGap.id}</span>
                {analysis.gaps.length > 1 && (
                  <span className="chip chip-outline">
                    {activeIndex + 1} / {analysis.gaps.length}
                  </span>
                )}
              </div>
              <div className="row row-gap-2 competitive-carousel-actions">
                <button
                  type="button"
                  className="carousel-arrow"
                  onClick={goPrevious}
                  disabled={analysis.gaps.length <= 1}
                  aria-label="上一个竞争空白"
                  title="上一个竞争空白"
                >
                  <ChevronLeft size={16} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="carousel-arrow"
                  onClick={goNext}
                  disabled={analysis.gaps.length <= 1}
                  aria-label="下一个竞争空白"
                  title="下一个竞争空白"
                >
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="competitive-carousel-body" key={activeGap.id}>
              <div className="row between wrap row-gap-2">
                <span className="chip mono">{activeGap.id}</span>
                <span className="chip">置信度 {Math.round(activeGap.confidence * 100)}%</span>
              </div>
              <div>
                <h3 className="section-title">{activeGap.title}</h3>
                <p className="muted" style={{ marginTop: 6 }}>
                  {activeGap.description}
                </p>
              </div>
              <div className="alert alert-info">
                <ShieldCheck size={16} className="alert-icon" />
                <div className="alert-body">
                  <span className="alert-title">可进入的产品空白</span>
                  <span>{activeGap.white_space}</span>
                </div>
              </div>
              <div className="taglist">
                {activeGap.competitor_brands.map((brand) => (
                  <span className="chip" key={brand}>
                    {brand}
                  </span>
                ))}
              </div>
              <div>
                <span className="opp-section-label">设计启示</span>
                <Bullets items={activeGap.design_implications} />
              </div>
              <div className="decisive">
                <strong>必须验证：</strong>
                {activeGap.validation_question}
              </div>
              <div className="row row-gap-2 muted" style={{ fontSize: "var(--text-xs)" }}>
                <AlertTriangle size={12} /> 模仿风险：{activeGap.imitation_risk}
              </div>
            </div>
          </article>
        )}
      </div>

      <div className="stack stack-3">
        <span className="opp-section-label">本地竞品证据</span>
        <div className="grid-cards">
          {evidence.map((record) => (
            <article className="card card-pad stack stack-3" key={record.id}>
              <div className="row between wrap row-gap-2">
                <strong>
                  {record.brand} · {record.product_name}
                </strong>
                <span className="chip mono">{record.id}</span>
              </div>
              <Bullets items={record.verified_capabilities} />
              {record.documented_constraints.length > 0 && (
                <div>
                  <span className="opp-section-label">已记录边界</span>
                  <Bullets items={record.documented_constraints} />
                </div>
              )}
              <a
                href={record.source_url}
                target="_blank"
                rel="noreferrer"
                className="row row-gap-2 muted"
              >
                {record.source_name} <ExternalLink size={12} />
              </a>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card card-pad stack stack-2">
      <span className="opp-section-label">{title}</span>
      <Bullets items={items} />
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <div className="bullets">
      {items.map((item, index) => (
        <div className="bullet" key={index}>
          {item}
        </div>
      ))}
    </div>
  );
}
