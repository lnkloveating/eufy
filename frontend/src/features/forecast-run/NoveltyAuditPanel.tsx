import { CheckCircle2, GitCompareArrows, Layers3, ShieldCheck } from "lucide-react";

import type {
  CurrentCapabilityBaseline,
  NoveltyAudit,
  NoveltyClassification,
  PortfolioDiversityAudit,
  RankedCandidate,
} from "../../types/api";

const CLASSIFICATION_LABELS: Record<NoveltyClassification, string> = {
  existing_equivalent: "现有能力等价",
  feature_extension: "功能升级",
  adjacent_innovation: "邻近创新",
  new_product_category: "新品类",
};

export function NoveltyAuditPanel({
  baseline,
  audit,
  diversityAudit,
  candidates,
}: {
  baseline: CurrentCapabilityBaseline | null;
  audit: NoveltyAudit | null;
  diversityAudit: PortfolioDiversityAudit | null;
  candidates: RankedCandidate[];
}) {
  const candidateNames = new Map(
    candidates.map((item) => [item.candidate.id, item.candidate.name]),
  );

  return (
    <div className="stack stack-5">
      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">
          <Layers3 size={14} aria-hidden="true" /> eufy 当前能力基线
        </span>
        <p className="muted">{baseline?.summary ?? "本次研究没有生成当前能力基线。"}</p>
        <div className="grid-cards">
          {(baseline?.capabilities ?? []).map((item) => (
            <div className="card card-pad stack stack-2" key={item.id}>
              <div className="row between">
                <strong>{item.capability}</strong>
                <span className="chip">{item.id}</span>
              </div>
              <div className="taglist">
                {item.existing_products.map((product) => (
                  <span className="chip chip-outline" key={product}>{product}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card card-pad stack stack-4">
        <span className="opp-section-label">
          <ShieldCheck size={14} aria-hidden="true" /> 候选创新门槛判定
        </span>
        {(audit?.rescue_rounds ?? 0) > 0 && (
          <div className="alert alert-warning" role="status">
            <ShieldCheck size={18} className="alert-icon" aria-hidden="true" />
            <div className="alert-body">
              <span className="alert-title">已执行 {audit?.rescue_rounds} 轮创新救援</span>
              <span>
                常规定向重生后仍未通过的方向已切换创新向量，并重新接受完整审计。
              </span>
            </div>
          </div>
        )}
        {(audit?.dropped_candidate_ids?.length ?? 0) > 0 && (
          <div className="alert alert-warning" role="status">
            <ShieldCheck size={18} className="alert-icon" aria-hidden="true" />
            <div className="alert-body">
              <span className="alert-title">已安全移除未通过方向</span>
              <span>
                {audit?.dropped_candidate_ids?.join("、")} 在救援后仍未达到创新门槛；
                本次返回 {audit?.returned_candidate_count} / {audit?.requested_candidate_count} 个合格候选。
              </span>
            </div>
          </div>
        )}
        {(audit?.assessments ?? []).map((item) => (
          <div className="review-block" key={item.candidate_id}>
            <div className="review-head">
              <div className="stack stack-1">
                <strong>{candidateNames.get(item.candidate_id) ?? item.candidate_id}</strong>
                <span className="muted" style={{ fontSize: "var(--text-xs)" }}>
                  {CLASSIFICATION_LABELS[item.classification]} · 当前能力重合 {Math.round(item.overlap_ratio * 100)}%
                </span>
              </div>
              <span className="chip chip-accent">
                <CheckCircle2 size={12} aria-hidden="true" /> 已通过
              </span>
            </div>
            <div className="bullets">
              {item.genuinely_new_capabilities.map((capability) => (
                <div className="bullet" key={capability}>{capability}</div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="card card-pad stack stack-4">
        <div className="row between wrap row-gap-2">
          <span className="opp-section-label">
            <GitCompareArrows size={14} aria-hidden="true" /> 候选组合语义去重
          </span>
          <span className="chip chip-accent">
            <CheckCircle2 size={12} aria-hidden="true" />
            {(diversityAudit?.pair_assessments ?? []).length} 组已核验
          </span>
        </div>
        <p className="muted">
          两两比较用户任务、形态、感知与执行机制、AI 决策方式、系统架构和商业交付，
          不以名称或创新标签作为差异依据。
        </p>
        {diversityAudit?.degraded && (
          <div className="alert alert-warning" role="status">
            <GitCompareArrows size={18} className="alert-icon" aria-hidden="true" />
            <div className="alert-body">
              <span className="alert-title">组合去重已达到安全上限</span>
              <span>
                {diversityAudit.dropped_candidate_ids?.length
                  ? `已移除：${diversityAudit.dropped_candidate_ids.join("、")}。`
                  : "已停止继续重生。"}
                {(diversityAudit.unresolved_duplicate_pairs?.length ?? 0) > 0
                  ? `仍保留 ${diversityAudit.unresolved_duplicate_pairs?.length} 组待人工判断方向。`
                  : "其余候选已继续进入评审。"}
              </span>
            </div>
          </div>
        )}
        {(diversityAudit?.regeneration_rounds ?? 0) > 0 && (
          <div className="alert alert-warning" role="status">
            <GitCompareArrows size={18} className="alert-icon" aria-hidden="true" />
            <div className="alert-body">
              <span className="alert-title">
                已完成 {diversityAudit?.regeneration_rounds} 轮组合去重
              </span>
              <span>
                被替换并重新通过创新审计的候选：
                {diversityAudit?.regenerated_candidate_ids.join("、")}
              </span>
            </div>
          </div>
        )}
        <div className="grid-cards">
          {(diversityAudit?.pair_assessments ?? []).map((pair) => (
            <div className="card card-pad stack stack-2" key={`${pair.candidate_a_id}:${pair.candidate_b_id}`}>
              <div className="row between wrap row-gap-2">
                <strong>
                  {candidateNames.get(pair.candidate_a_id) ?? pair.candidate_a_id}
                  {" ↔ "}
                  {candidateNames.get(pair.candidate_b_id) ?? pair.candidate_b_id}
                </strong>
                <span className="chip chip-outline">
                  语义重合 {Math.round(pair.similarity_score * 100)}%
                </span>
              </div>
              <span className="muted" style={{ fontSize: "var(--text-xs)" }}>
                {pair.meaningful_differences.length > 0
                  ? pair.meaningful_differences.join("；")
                  : "最终组合已通过差异化门槛"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
