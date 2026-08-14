import { useEffect, useState } from "react";
import {
  ChevronDown,
  Database,
  Layers3,
  MapPin,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { EvidenceRecord, RetrievalPlan } from "../../types/api";

const LAYER_LABELS: Record<string, string> = {
  eufy_foundation: "eufy 基础能力",
  regional_market: "地区市场",
  user_needs: "用户需求",
  technology: "技术信号",
  privacy_regulation: "隐私与法规",
  business: "商业与渠道",
  risk_counterevidence: "风险与反证",
};

export function KnowledgePlanPanel({
  plan,
  evidence,
  defaultEvidenceBundleExpanded = false,
}: {
  plan: RetrievalPlan | null;
  evidence: EvidenceRecord[];
  defaultEvidenceBundleExpanded?: boolean;
}) {
  if (!plan) return null;

  const [bundleExpanded, setBundleExpanded] = useState(defaultEvidenceBundleExpanded);

  useEffect(() => {
    setBundleExpanded(defaultEvidenceBundleExpanded);
  }, [defaultEvidenceBundleExpanded]);

  const counts = evidence.reduce<Record<string, number>>((acc, record) => {
    acc[record.layer] = (acc[record.layer] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="stack stack-5">
      <div className="alert alert-info">
        <Layers3 size={18} className="alert-icon" aria-hidden="true" />
        <div className="alert-body">
          <span className="alert-title">本次不是读取完整知识库，而是执行分层检索</span>
          <span>{plan.explanation}</span>
        </div>
      </div>

      <div className="grid-cards">
        {plan.coverage.map((item) => (
          <article className="card card-pad stack stack-3" key={item.region}>
            <div className="row between">
              <strong className="row row-gap-2">
                <MapPin size={15} aria-hidden="true" /> {item.region}
              </strong>
              <span className={`chip ${item.level === "strong" ? "chip-accent" : "chip-outline"}`}>
                {item.level === "strong"
                  ? "资料充足"
                  : item.level === "moderate"
                    ? "资料一般"
                    : "资料有限"}
              </span>
            </div>
            <div className="row wrap row-gap-2">
              <span className="chip">{item.total_records} 条地区资料</span>
              <span className="chip">{item.verified_records} 条已验证</span>
              <span className="chip">{item.hypothesis_records} 条假设</span>
            </div>
            {item.missing_layers.length > 0 && (
              <span className="muted" style={{ fontSize: "var(--text-xs)" }}>
                缺少：{item.missing_layers.map((layer) => LAYER_LABELS[layer] ?? layer).join("、")}
              </span>
            )}
          </article>
        ))}
      </div>

      {plan.fallback_used && (
        <div className="alert alert-warn">
          <TriangleAlert size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">部分地区资料有限</span>
            <span>该地区会使用全球共同证据作为补充，相关结论应降低置信度并优先验证。</span>
          </div>
        </div>
      )}

      <div className="card">
        <button
          type="button"
          className="knowledge-bundle-toggle"
          aria-expanded={bundleExpanded}
          onClick={() => setBundleExpanded((value) => !value)}
        >
          <span className="stack stack-none">
            <strong className="row row-gap-2">
              <Database size={16} aria-hidden="true" />
              <span>Evidence Bundle</span>
            </strong>
            <span className="subtle knowledge-bundle-summary">
              实际输入 {evidence.length} 条 · {plan.required_layers.length} 个维度
              {plan.query_topics.length > 0 ? ` · ${plan.query_topics.length} 个主题` : ""}
            </span>
          </span>
          <span className="row row-gap-2">
            <span className="chip chip-accent">实际输入 {evidence.length} 条</span>
            <ChevronDown
              size={16}
              aria-hidden="true"
              className={`knowledge-bundle-chevron ${bundleExpanded ? "is-expanded" : ""}`}
            />
          </span>
        </button>

        {bundleExpanded && (
          <div className="card-pad stack stack-4" style={{ borderTop: "1px solid var(--line)" }}>
            <div className="grid-cards">
              {plan.required_layers.map((layer) => (
                <div className="card card-pad stack stack-2" key={layer}>
                  <span className="muted" style={{ fontSize: "var(--text-xs)" }}>
                    {LAYER_LABELS[layer] ?? layer}
                  </span>
                  <strong>{counts[layer] ?? 0} 条</strong>
                  <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                    配额上限 {plan.layer_quotas[layer] ?? 0}
                  </span>
                </div>
              ))}
            </div>
            {plan.query_topics.length > 0 && (
              <div className="row wrap row-gap-2">
                <ShieldCheck size={15} className="muted" aria-hidden="true" />
                {plan.query_topics.map((topic) => (
                  <span className="chip chip-outline" key={topic}>
                    {topic}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
