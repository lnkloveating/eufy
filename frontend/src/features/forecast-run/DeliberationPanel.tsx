import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  MessageSquareWarning,
  Scale,
} from "lucide-react";

import type { ForecastConsensus, LensDeliberation } from "../../types/api";
import { getLensLabel } from "../../lib/agentLabels";

export function DeliberationPanel({
  deliberations,
  consensus,
}: {
  deliberations: LensDeliberation[];
  consensus: ForecastConsensus | null;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [activeConsensusIndex, setActiveConsensusIndex] = useState(0);

  const activeDeliberation =
    deliberations.length > 0 ? deliberations[activeIndex % deliberations.length] : null;
  const activeConsensusClaim =
    consensus?.consensus_claims.length
      ? consensus.consensus_claims[activeConsensusIndex % consensus.consensus_claims.length]
      : null;

  const goPrevious = () => {
    if (deliberations.length <= 1) return;
    setActiveIndex((current) => (current - 1 + deliberations.length) % deliberations.length);
  };

  const goNext = () => {
    if (deliberations.length <= 1) return;
    setActiveIndex((current) => (current + 1) % deliberations.length);
  };

  const goPreviousConsensus = () => {
    if (!consensus || consensus.consensus_claims.length <= 1) return;
    setActiveConsensusIndex(
      (current) =>
        (current - 1 + consensus.consensus_claims.length) % consensus.consensus_claims.length,
    );
  };

  const goNextConsensus = () => {
    if (!consensus || consensus.consensus_claims.length <= 1) return;
    setActiveConsensusIndex((current) => (current + 1) % consensus.consensus_claims.length);
  };

  if (deliberations.length === 0 && !consensus) {
    return <div className="card card-pad muted">暂无交叉审查内容。</div>;
  }

  return (
    <div className="stack stack-5">
      {activeDeliberation && (
        <article className="card card-pad stack stack-3 deliberation-carousel-card">
          <div className="row between wrap row-gap-2 deliberation-carousel-head">
            <div className="row row-gap-2 wrap deliberation-carousel-title" style={{ minWidth: 0 }}>
              <strong>{getLensLabel(activeDeliberation.reviewer_lens)} Agent</strong>
              {deliberations.length > 1 && (
                <span className="chip chip-outline">
                  {activeIndex + 1} / {deliberations.length}
                </span>
              )}
            </div>
            <div className="row row-gap-2 deliberation-carousel-actions">
              <button
                type="button"
                className="carousel-arrow"
                onClick={goPrevious}
                disabled={deliberations.length <= 1}
                aria-label="上一个 Agent"
                title="上一个 Agent"
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="carousel-arrow"
                onClick={goNext}
                disabled={deliberations.length <= 1}
                aria-label="下一个 Agent"
                title="下一个 Agent"
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>

          <div className="deliberation-carousel-body" key={activeDeliberation.reviewer_lens}>
            <span className="chip chip-accent" style={{ alignSelf: "center" }}>
              修正后置信度 {Math.round(activeDeliberation.revised_confidence * 100)}%
            </span>
            <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
              {activeDeliberation.revised_thesis}
            </p>
            <div>
              <span className="opp-section-label">
                <MessageSquareWarning size={12} /> 提出的质疑
              </span>
              <div className="stack stack-2">
                {activeDeliberation.challenges.map((challenge) => (
                  <div className="decisive" key={challenge.id}>
                    <strong>{getLensLabel(challenge.target_lens)}：</strong>
                    {challenge.challenge_reason}
                  </div>
                ))}
              </div>
            </div>
            {activeDeliberation.revisions_to_own_view.length > 0 && (
              <List title="观点修正" items={activeDeliberation.revisions_to_own_view} />
            )}
            <List title="仍未解决" items={activeDeliberation.unresolved_questions} />
          </div>
        </article>
      )}

      {consensus && (
        <section className="card card-pad stack stack-4">
          <span className="opp-section-label">
            <Scale size={13} /> 共识裁决
          </span>
          {activeConsensusClaim && (
            <article className="card card-pad stack stack-2 deliberation-carousel-card">
              <div className="row between wrap row-gap-2 deliberation-carousel-head">
                <div className="row row-gap-2 wrap deliberation-carousel-title" style={{ minWidth: 0 }}>
                  <strong>共识结论</strong>
                  {consensus.consensus_claims.length > 1 && (
                    <span className="chip chip-outline">
                      {activeConsensusIndex + 1} / {consensus.consensus_claims.length}
                    </span>
                  )}
                </div>
                <div className="row row-gap-2 deliberation-carousel-actions">
                  <button
                    type="button"
                    className="carousel-arrow"
                    onClick={goPreviousConsensus}
                    disabled={consensus.consensus_claims.length <= 1}
                    aria-label="上一个共识结论"
                    title="上一个共识结论"
                  >
                    <ChevronLeft size={16} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="carousel-arrow"
                    onClick={goNextConsensus}
                    disabled={consensus.consensus_claims.length <= 1}
                    aria-label="下一个共识结论"
                    title="下一个共识结论"
                  >
                    <ChevronRight size={16} aria-hidden="true" />
                  </button>
                </div>
              </div>

              <div
                className="deliberation-carousel-body"
                key={`${activeConsensusIndex}-${activeConsensusClaim.claim}`}
              >
                <div className="row between wrap row-gap-2">
                  <CheckCircle2 size={15} style={{ color: "var(--success-ink)" }} />
                  <span className="chip">{Math.round(activeConsensusClaim.confidence * 100)}%</span>
                </div>
                <p>{activeConsensusClaim.claim}</p>
                <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                  {activeConsensusClaim.supporting_lenses.map(getLensLabel).join("、")}
                </span>
              </div>
            </article>
          )}

          {consensus.unresolved_disagreements.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label">
                <AlertTriangle size={12} /> 未解决分歧
              </span>
              {consensus.unresolved_disagreements.map((item, index) => (
                <div className="alert alert-info" key={index}>
                  <AlertTriangle size={16} className="alert-icon" />
                  <div className="alert-body">
                    <span className="alert-title">{item.topic}</span>
                    <span>{item.why_unresolved}</span>
                    <span>
                      <strong>验证需求：</strong>
                      {item.validation_need}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="spec-grid">
            <List title="少数意见" items={consensus.minority_views} />
            <List title="证据缺口" items={consensus.evidence_gaps} />
          </div>
        </section>
      )}
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;

  return (
    <div className="stack stack-2">
      <span className="opp-section-label">{title}</span>
      <div className="bullets">
        {items.map((item, index) => (
          <div className="bullet" key={index}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
