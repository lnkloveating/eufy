import { Layers } from "lucide-react";

import { SCORE_DIMENSIONS, type ScoreWeights } from "../../types/api";
import { DIMENSION_LABELS } from "../../lib/agentLabels";
import { areWeightsValid, type ResearchBrief } from "./researchBrief";

/** UI-recommended minimum per weight (%). Backend only requires the sum = 100. */
export const MIN_WEIGHT_PERCENT = 5;

/**
 * Redistribute weight fractions so they sum to exactly 1.0 (integer percents).
 * Falls back to an even six-way split when every weight is zero.
 */
export function normalizeWeights(weights: ScoreWeights): ScoreWeights {
  const pct = SCORE_DIMENSIONS.map((key) => Math.round((weights[key] || 0) * 100));
  const total = pct.reduce((sum, value) => sum + value, 0);
  const even = 100 / SCORE_DIMENSIONS.length;
  const base = total > 0 ? pct.map((value) => (value * 100) / total) : SCORE_DIMENSIONS.map(() => even);
  const floored = base.map((value) => Math.floor(value));
  let remainder = 100 - floored.reduce((sum, value) => sum + value, 0);
  const order = base
    .map((value, index) => ({ index, frac: value - Math.floor(value) }))
    .sort((a, b) => b.frac - a.frac);
  let cursor = 0;
  while (remainder > 0) {
    const target = order[cursor % order.length];
    if (target) {
      floored[target.index] = (floored[target.index] ?? 0) + 1;
      remainder -= 1;
    }
    cursor += 1;
  }
  const next = {} as ScoreWeights;
  SCORE_DIMENSIONS.forEach((key, index) => {
    next[key] = (floored[index] ?? 0) / 100;
  });
  return next;
}

export interface WeightSlidersProps {
  brief: ResearchBrief;
  /** Emits a brief patch. Any manual edit here also flips profile to `custom`. */
  onChange: (patch: Partial<ResearchBrief>) => void;
}

/**
 * The six evaluation-weight sliders, shared by the strategy card's custom area
 * and the advanced settings so there is exactly one weight-editing surface and
 * one piece of state. Moving any slider sets `strategy_profile` to `custom`.
 */
export function WeightSliders({ brief, onChange }: WeightSlidersProps) {
  const weightPct = (key: (typeof SCORE_DIMENSIONS)[number]) =>
    Math.round((brief.weights[key] || 0) * 100);
  const weightTotal = SCORE_DIMENSIONS.reduce((sum, key) => sum + weightPct(key), 0);
  const weightsOk = areWeightsValid(brief.weights);

  const setWeight = (dimension: (typeof SCORE_DIMENSIONS)[number], percent: number) => {
    onChange({
      strategy_profile: "custom",
      weights: { ...brief.weights, [dimension]: percent / 100 },
    });
  };

  return (
    <div className="stack stack-3">
      <div className="row between">
        <span className="field-label">
          <Layers size={15} aria-hidden="true" /> 评估权重（总和须为 100%）
        </span>
        <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
          建议每项 ≥ {MIN_WEIGHT_PERCENT}%
        </span>
      </div>
      {SCORE_DIMENSIONS.map((dimension) => (
        <div className="weight-row" key={dimension}>
          <span className="weight-name">{DIMENSION_LABELS[dimension]}</span>
          <input
            className="weight-range"
            type="range"
            min={MIN_WEIGHT_PERCENT}
            max={60}
            step={1}
            value={weightPct(dimension)}
            aria-label={`${DIMENSION_LABELS[dimension]} 权重`}
            aria-valuetext={`${weightPct(dimension)}%`}
            onChange={(event) => setWeight(dimension, Number(event.target.value))}
          />
          <span className="weight-pct">{weightPct(dimension)}%</span>
        </div>
      ))}
      <div className={`weight-total ${weightsOk ? "is-ok" : "is-bad"}`}>
        <span>权重总和：{weightTotal}%</span>
        {weightsOk ? (
          <span>已归一化 ✓</span>
        ) : (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() =>
              onChange({ strategy_profile: "custom", weights: normalizeWeights(brief.weights) })
            }
          >
            一键归一化为 100%
          </button>
        )}
      </div>
      {!weightsOk && (
        <p className="subtle" role="status" style={{ fontSize: "var(--text-xs)", color: "var(--danger-ink)" }}>
          权重总和不是 100%，无法开始研究。请调整任一滑块或点击一键归一化。
        </p>
      )}
    </div>
  );
}
