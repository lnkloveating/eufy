import type { ReactNode } from "react";
import { AlertTriangle, Compass, FlaskConical, Gavel, ShieldCheck, Sparkles, Swords } from "lucide-react";
import type { CandidateNoveltyAssessment, RankedCandidate } from "../../types/api";
import { SCORE_DIMENSIONS } from "../../types/api";
import { getDimensionLabel } from "../../lib/agentLabels";
import { formatScore } from "../../lib/formatters";
import { Drawer } from "../../components/ui/Drawer";
import { Button } from "../../components/ui/Button";
import { ScoreRadar } from "../../components/ScoreRadar/ScoreRadar";

function scoreClass(score: number): string {
  if (score >= 75) return "rs-high";
  if (score >= 55) return "rs-mid";
  return "rs-low";
}

export interface CandidateDetailDrawerProps {
  ranked: RankedCandidate | null;
  novelty?: CandidateNoveltyAssessment;
  onClose: () => void;
  onSelect: (ranked: RankedCandidate) => void;
}

/** Full detail + blind-review opinions for a single candidate. */
export function CandidateDetailDrawer({
  ranked,
  novelty,
  onClose,
  onSelect,
}: CandidateDetailDrawerProps) {
  if (!ranked) {
    return <Drawer open={false} title="" onClose={onClose}>{null}</Drawer>;
  }

  const { candidate, reviews, dimension_scores, weighted_score, rank } = ranked;
  const radarScores: Record<string, number> = {};
  for (const dimension of SCORE_DIMENSIONS) {
    radarScores[dimension] = dimension_scores[dimension] ?? 0;
  }

  return (
    <Drawer
      open={Boolean(ranked)}
      onClose={onClose}
      title={
        <span className="row row-gap-3">
          <span className="cand-rank">{rank}</span>
          {candidate.name}
        </span>
      }
      subtitle={candidate.tagline}
    >
      <div className="stack stack-6">
        <div className="card card-pad stack stack-4">
          <div className="row between">
            <span className="opp-section-label">五维评分</span>
            <span className="strong">
              综合 {formatScore(weighted_score)}
            </span>
          </div>
          <ScoreRadar
            series={[{ label: candidate.name, color: "var(--accent)", scores: radarScores }]}
            size={260}
          />
          <div className="dimscore-row">
            {SCORE_DIMENSIONS.map((dimension) => (
              <div className="dimscore" key={dimension}>
                <span className="dimscore-name">{getDimensionLabel(dimension)}</span>
                <span className="dimscore-track">
                  <span
                    className="dimscore-fill"
                    style={{ width: `${dimension_scores[dimension] ?? 0}%` }}
                  />
                </span>
                <span className="dimscore-val">
                  {formatScore(dimension_scores[dimension] ?? 0)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="stack stack-3">
          <span className="opp-section-label">核心信息</span>
          <div className="deflist">
            <Def label="核心问题" value={candidate.core_problem} />
            <Def label="价值主张" value={candidate.value_proposition} />
            <Def label="产品形态" value={candidate.form_factor} />
            <Def label="AI 原生机制" value={candidate.ai_native_mechanism} />
            <Def label="预估价格" value={candidate.estimated_price_range} />
          </div>
        </div>

        <TagSection title="关键场景" items={candidate.key_scenarios} />
        <TagSection title="差异化优势" items={candidate.differentiators} icon={<Sparkles size={12} />} />

        {candidate.capability_delta && (
          <div className="card card-pad stack stack-3">
            <span className="opp-section-label">
              <Sparkles size={13} aria-hidden="true" /> 未来能力增量
            </span>
            {novelty && (
              <div className="row wrap row-gap-2">
                <span className="chip chip-accent">创新门槛已通过</span>
                <span className="chip chip-outline">
                  与当前能力重合 {Math.round(novelty.overlap_ratio * 100)}%
                </span>
              </div>
            )}
            <Def label="创新探索向量" value={innovationVectorLabel(candidate.capability_delta.innovation_vector)} />
            <TagSection title="今天已有的相近能力" items={candidate.capability_delta.today_equivalents} />
            <TagSection title="真正新增的能力" items={candidate.capability_delta.new_capabilities} />
            <Def label="为什么今天还没有" value={candidate.capability_delta.why_not_available_today} />
            <Def label="硬件 / 系统增量" value={candidate.capability_delta.hardware_or_system_delta} />
            <TagSection title="三年内成立的条件" items={candidate.capability_delta.enabling_changes} />
            <TagSection title="仍需验证" items={candidate.capability_delta.proof_needed} />
          </div>
        )}

        {candidate.strategy_alignment &&
          (candidate.strategy_alignment.aligned_dimensions.length > 0 ||
            candidate.strategy_alignment.rationale ||
            candidate.strategy_alignment.tradeoffs.length > 0) && (
            <div className="card card-pad stack stack-3">
              <span className="opp-section-label">
                <Compass size={13} aria-hidden="true" /> 策略取向
              </span>
              {candidate.strategy_alignment.aligned_dimensions.length > 0 && (
                <div className="row wrap row-gap-2">
                  {candidate.strategy_alignment.aligned_dimensions.map((dimension) => (
                    <span className="chip chip-accent" key={dimension}>
                      {getDimensionLabel(dimension)}
                    </span>
                  ))}
                </div>
              )}
              {candidate.strategy_alignment.rationale && (
                <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
                  {candidate.strategy_alignment.rationale}
                </p>
              )}
              {candidate.strategy_alignment.tradeoffs.length > 0 && (
                <div className="stack stack-2">
                  <span className="pro-con-title con">
                    <AlertTriangle size={12} aria-hidden="true" /> 策略代价
                  </span>
                  <div className="bullets">
                    {candidate.strategy_alignment.tradeoffs.map((item, index) => (
                      <div className="bullet" key={index} style={{ fontSize: "var(--text-sm)" }}>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

        <div className="card card-pad stack stack-3">
          <span className="opp-section-label">
            <Swords size={13} aria-hidden="true" /> 竞争定位
          </span>
          <TagSection title="最接近的现有方案" items={candidate.competitive_positioning.closest_alternatives} />
          <TagSection title="可借鉴的成熟模式" items={candidate.competitive_positioning.borrowed_patterns} />
          <TagSection title="可防御差异" items={candidate.competitive_positioning.defensible_differences} />
          <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
            <strong>为什么不是模仿：</strong>{candidate.competitive_positioning.non_copycat_rationale}
          </p>
          <div className="decisive">
            <strong>竞争优势验证：</strong>
            {candidate.competitive_positioning.validation_questions.join("；")}
          </div>
        </div>

        <div className="stack stack-3">
          <span className="opp-section-label">
            <FlaskConical size={13} aria-hidden="true" /> 关键假设
          </span>
          <div className="bullets">
            {candidate.key_assumptions.map((item, index) => (
              <div className="bullet" key={index}>{item}</div>
            ))}
          </div>
        </div>

        <div className="stack stack-3">
          <span className="opp-section-label" style={{ color: "var(--danger-ink)" }}>
            <AlertTriangle size={13} aria-hidden="true" /> 淘汰标准
          </span>
          <div className="bullets">
            {candidate.kill_criteria.map((item, index) => (
              <div className="bullet" key={index}>{item}</div>
            ))}
          </div>
        </div>

        <div className="stack stack-3">
          <span className="opp-section-label">
            <Gavel size={13} aria-hidden="true" /> 盲评意见
          </span>
          <div className="card card-pad">
            {reviews.map((review) => (
              <div className="review-block" key={review.dimension}>
                <div className="review-head">
                  <strong>{getDimensionLabel(review.dimension)}</strong>
                  <span className={`review-score-badge ${scoreClass(review.score)}`}>
                    {formatScore(review.score)}
                  </span>
                </div>
                {review.strengths.length > 0 && (
                  <div className="stack stack-2">
                    <span className="pro-con-title pro">
                      <ShieldCheck size={12} aria-hidden="true" /> 优势
                    </span>
                    <div className="bullets">
                      {review.strengths.map((item, index) => (
                        <div className="bullet" key={index} style={{ fontSize: "var(--text-sm)" }}>
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {review.concerns.length > 0 && (
                  <div className="stack stack-2">
                    <span className="pro-con-title con">
                      <AlertTriangle size={12} aria-hidden="true" /> 顾虑
                    </span>
                    <div className="bullets">
                      {review.concerns.map((item, index) => (
                        <div className="bullet" key={index} style={{ fontSize: "var(--text-sm)" }}>
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {review.decisive_question && (
                  <div className="decisive">
                    <strong>决定性问题：</strong>
                    {review.decisive_question}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <Button
          variant="primary"
          size="lg"
          block
          onClick={() => onSelect(ranked)}
        >
          选择该方向并生成产品定义
        </Button>
      </div>
    </Drawer>
  );
}

function innovationVectorLabel(vector: NonNullable<RankedCandidate["candidate"]["capability_delta"]>["innovation_vector"]): string {
  const labels = {
    new_sensing: "新感知机制",
    proactive_intervention: "主动干预",
    distributed_architecture: "分布式协作架构",
    resilience_recovery: "韧性与恢复",
    trust_privacy: "信任与隐私控制",
    human_ai_coordination: "人机协同决策",
    new_business_delivery: "新型交付模式",
  } as const;
  return labels[vector];
}

function Def({ label, value }: { label: string; value: string }) {
  return (
    <div className="def-row">
      <span className="def-key">{label}</span>
      <span className="def-val">{value}</span>
    </div>
  );
}

function TagSection({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon?: ReactNode;
}) {
  if (items.length === 0) return null;
  return (
    <div className="stack stack-2">
      <span className="opp-section-label">
        {icon} {title}
      </span>
      <div className="taglist">
        {items.map((item) => (
          <span className="chip chip-outline" key={item}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
