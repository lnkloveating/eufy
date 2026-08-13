import { AlertTriangle, ExternalLink, SearchCheck, ShieldCheck, Swords } from "lucide-react";
import type { CompetitiveAnalysis, CompetitorRecord } from "../../types/api";

export function CompetitiveAnalysisPanel({
  analysis,
  evidence,
}: {
  analysis: CompetitiveAnalysis | null;
  evidence: CompetitorRecord[];
}) {
  if (!analysis) {
    return <div className="card card-pad muted">竞品分析尚未生成。</div>;
  }
  const brands = [...new Set(evidence.map((item) => item.brand))];
  return (
    <div className="stack stack-5">
      <div className="row wrap row-gap-2">
        <span className="chip"><Swords size={12} /> {brands.length} 个竞品品牌</span>
        <span className="chip"><SearchCheck size={12} /> {evidence.length} 条官方资料</span>
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
        <div className="grid-cards">
          {analysis.gaps.map((gap) => (
            <article className="card card-pad stack stack-3" key={gap.id}>
              <div className="row between wrap row-gap-2">
                <span className="chip mono">{gap.id}</span>
                <span className="chip">置信度 {Math.round(gap.confidence * 100)}%</span>
              </div>
              <div>
                <h3 className="section-title">{gap.title}</h3>
                <p className="muted" style={{ marginTop: 6 }}>{gap.description}</p>
              </div>
              <div className="alert alert-info">
                <ShieldCheck size={16} className="alert-icon" />
                <div className="alert-body">
                  <span className="alert-title">可进入的产品空白</span>
                  <span>{gap.white_space}</span>
                </div>
              </div>
              <div className="taglist">
                {gap.competitor_brands.map((brand) => <span className="chip" key={brand}>{brand}</span>)}
              </div>
              <div>
                <span className="opp-section-label">设计启示</span>
                <Bullets items={gap.design_implications} />
              </div>
              <div className="decisive"><strong>必须验证：</strong>{gap.validation_question}</div>
              <div className="row row-gap-2 muted" style={{ fontSize: "var(--text-xs)" }}>
                <AlertTriangle size={12} /> 模仿风险：{gap.imitation_risk}
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="stack stack-3">
        <span className="opp-section-label">本地竞品证据</span>
        <div className="grid-cards">
          {evidence.map((record) => (
            <article className="card card-pad stack stack-3" key={record.id}>
              <div className="row between wrap row-gap-2">
                <strong>{record.brand} · {record.product_name}</strong>
                <span className="chip mono">{record.id}</span>
              </div>
              <Bullets items={record.verified_capabilities} />
              {record.documented_constraints.length > 0 && (
                <div>
                  <span className="opp-section-label">已记录边界</span>
                  <Bullets items={record.documented_constraints} />
                </div>
              )}
              <a href={record.source_url} target="_blank" rel="noreferrer" className="row row-gap-2 muted">
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
      {items.map((item, index) => <div className="bullet" key={index}>{item}</div>)}
    </div>
  );
}
