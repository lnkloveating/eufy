import { Compass, Layers3, ScrollText, Sparkles } from "lucide-react";
import type { ForecastResult } from "../../types/api";
import { SCORE_DIMENSIONS } from "../../types/api";
import { DIMENSION_LABELS } from "../../lib/agentLabels";
import { describeStrategy, getStrategyLabel, dominantSummary } from "../../lib/strategy";

const LAYER_LABELS: Record<string, string> = {
  eufy_foundation: "eufy 基础能力",
  regional_market: "地区市场",
  user_needs: "用户需求",
  technology: "技术信号",
  privacy_regulation: "隐私与法规",
  business: "商业与渠道",
  risk_counterevidence: "风险与反证",
};

/**
 * Strategy-impact report shown on a completed run. Every value is traced to a
 * real source — run.request, retrieval_plan, and each ranked candidate — so the
 * page never guesses a product's strategy influence from its name.
 */
export function StrategyImpactPanel({ result }: { result: ForecastResult }) {
  const { request } = result.run;
  const profile = request.strategy_profile ?? "balanced";
  const weights = request.weights;
  const plan = result.retrieval_plan;
  const adjustments = plan?.strategy_adjustments ?? {};
  const adjustmentEntries = Object.entries(adjustments).filter(([, delta]) => delta > 0);

  return (
    <div className="stack stack-5">
      {/* 1. Chosen profile + 6 weights + natural-language summary */}
      <div className="card card-pad stack stack-4">
        <div className="row row-gap-3">
          <Compass size={19} style={{ color: "var(--accent)" }} aria-hidden="true" />
          <div className="stack" style={{ gap: 2 }}>
            <span className="eyebrow">策略影响 · {getStrategyLabel(profile)}</span>
            <strong>{dominantSummary(weights)}</strong>
          </div>
        </div>
        <div className="row wrap row-gap-2" aria-label="最终评分使用的六维权重">
          {SCORE_DIMENSIONS.map((dimension) => (
            <span className="chip chip-outline" key={dimension}>
              {DIMENSION_LABELS[dimension]} {Math.round((weights[dimension] ?? 0) * 100)}%
            </span>
          ))}
        </div>
        <p className="subtle" style={{ fontSize: "var(--text-sm)" }}>
          {describeStrategy(profile, weights)}
        </p>
        <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
          以上权重即本次候选最终加权排名实际使用的权重。
        </p>
      </div>

      {/* 2. Real RAG adjustments from the retrieval plan */}
      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">
          <Layers3 size={14} aria-hidden="true" /> RAG 实际调整
        </span>
        {plan?.strategy_explanation ? (
          <p style={{ color: "var(--ink-800)" }}>{plan.strategy_explanation}</p>
        ) : (
          <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
            本次策略未对知识层配额做倾斜，七层保持基础配额。
          </p>
        )}
        {adjustmentEntries.length > 0 && (
          <div className="row wrap row-gap-2">
            {adjustmentEntries.map(([layer, delta]) => (
              <span className="chip chip-accent" key={layer}>
                {LAYER_LABELS[layer] ?? layer} +{delta} 条
              </span>
            ))}
          </div>
        )}
        {plan?.strategy_topics && plan.strategy_topics.length > 0 && (
          <div className="row wrap row-gap-2" aria-label="层内排序偏好主题">
            <span className="muted" style={{ fontSize: "var(--text-xs)" }}>
              层内排序偏好：
            </span>
            {plan.strategy_topics.map((topic) => (
              <span className="chip chip-outline" key={topic} style={{ fontSize: "var(--text-xs)" }}>
                {topic}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 3. Per-candidate strategy alignment + tradeoffs (guarded for old runs) */}
      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">
          <Sparkles size={14} aria-hidden="true" /> 候选产品的策略取向与代价
        </span>
        {result.candidates.length === 0 ? (
          <p className="muted" style={{ fontSize: "var(--text-sm)" }}>暂无候选产品。</p>
        ) : (
          <div className="stack stack-3">
            {result.candidates.map((ranked) => {
              const alignment = ranked.candidate.strategy_alignment;
              return (
                <div className="card card-pad stack stack-2" key={ranked.candidate.id}>
                  <div className="row row-gap-2" style={{ alignItems: "center" }}>
                    <span className="cand-rank" style={{ minWidth: 24, height: 24, fontSize: 12 }}>
                      {ranked.rank}
                    </span>
                    <strong>{ranked.candidate.name}</strong>
                  </div>
                  {alignment && alignment.aligned_dimensions.length > 0 && (
                    <div className="row wrap row-gap-2">
                      {alignment.aligned_dimensions.map((dimension) => (
                        <span className="chip chip-accent" key={dimension} style={{ fontSize: "var(--text-xs)" }}>
                          {DIMENSION_LABELS[dimension] ?? dimension}
                        </span>
                      ))}
                    </div>
                  )}
                  {alignment?.rationale ? (
                    <p className="subtle" style={{ fontSize: "var(--text-sm)" }}>
                      {alignment.rationale}
                    </p>
                  ) : (
                    <p className="muted" style={{ fontSize: "var(--text-xs)" }}>
                      该候选未附带策略取向说明（可能来自较早的研究）。
                    </p>
                  )}
                  {alignment && alignment.tradeoffs.length > 0 && (
                    <div className="stack stack-2">
                      <span className="pro-con-title con" style={{ fontSize: "var(--text-xs)" }}>
                        <ScrollText size={12} aria-hidden="true" /> 策略代价 Tradeoffs
                      </span>
                      <div className="bullets">
                        {alignment.tradeoffs.map((tradeoff, index) => (
                          <div className="bullet" key={index} style={{ fontSize: "var(--text-sm)" }}>
                            {tradeoff}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
