import { AlertTriangle, CheckCircle2, MessageSquareWarning, Scale } from "lucide-react";
import type { ForecastConsensus, LensDeliberation } from "../../types/api";
import { getLensLabel } from "../../lib/agentLabels";

export function DeliberationPanel({
  deliberations,
  consensus,
}: {
  deliberations: LensDeliberation[];
  consensus: ForecastConsensus | null;
}) {
  if (deliberations.length === 0 && !consensus) {
    return <div className="card card-pad muted">交叉审核尚未生成。</div>;
  }
  return (
    <div className="stack stack-5">
      {deliberations.length > 0 && (
        <div className="grid-cards">
          {deliberations.map((item) => (
            <article className="card card-pad stack stack-3" key={item.reviewer_lens}>
              <div className="row between wrap row-gap-2">
                <strong>{getLensLabel(item.reviewer_lens)} Agent</strong>
                <span className="chip chip-accent">
                  修正后置信度 {Math.round(item.revised_confidence * 100)}%
                </span>
              </div>
              <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                {item.revised_thesis}
              </p>
              <div>
                <span className="opp-section-label">
                  <MessageSquareWarning size={12} /> 提出的质疑
                </span>
                <div className="stack stack-2">
                  {item.challenges.map((challenge) => (
                    <div className="decisive" key={challenge.id}>
                      <strong>{getLensLabel(challenge.target_lens)}：</strong>
                      {challenge.challenge_reason}
                    </div>
                  ))}
                </div>
              </div>
              {item.revisions_to_own_view.length > 0 && (
                <List title="观点修正" items={item.revisions_to_own_view} />
              )}
              <List title="仍未解决" items={item.unresolved_questions} />
            </article>
          ))}
        </div>
      )}

      {consensus && (
        <section className="card card-pad stack stack-4">
          <span className="opp-section-label"><Scale size={13} /> 共识裁决</span>
          <div className="grid-cards">
            {consensus.consensus_claims.map((claim, index) => (
              <div className="card card-pad stack stack-2" key={index}>
                <div className="row between wrap row-gap-2">
                  <CheckCircle2 size={15} style={{ color: "var(--success-ink)" }} />
                  <span className="chip">{Math.round(claim.confidence * 100)}%</span>
                </div>
                <p>{claim.claim}</p>
                <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                  {claim.supporting_lenses.map(getLensLabel).join("、")}
                </span>
              </div>
            ))}
          </div>
          {consensus.unresolved_disagreements.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label"><AlertTriangle size={12} /> 未解决分歧</span>
              {consensus.unresolved_disagreements.map((item, index) => (
                <div className="alert alert-info" key={index}>
                  <AlertTriangle size={16} className="alert-icon" />
                  <div className="alert-body">
                    <span className="alert-title">{item.topic}</span>
                    <span>{item.why_unresolved}</span>
                    <span><strong>验证需求：</strong>{item.validation_need}</span>
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
        {items.map((item, index) => <div className="bullet" key={index}>{item}</div>)}
      </div>
    </div>
  );
}
