/**
 * Frontend strategy helpers. These NEVER hardcode preset weights — weights
 * always come from the backend `forecast-options` response. Only labels and
 * pure derivations of an existing `ScoreWeights` object live here.
 */

import {
  SCORE_DIMENSIONS,
  type ScoreDimension,
  type ScoreWeights,
  type StrategyProfile,
} from "../types/api";
import { DIMENSION_LABELS } from "./agentLabels";

/** Display label per profile. Labels only (not weights) may live on the client. */
export const STRATEGY_PROFILE_LABELS: Record<StrategyProfile, string> = {
  balanced: "平衡模式",
  breakthrough: "突破创新",
  value: "极致性价比",
  ecosystem: "eufy 生态优先",
  custom: "自定义权重",
};

export function getStrategyLabel(profile: StrategyProfile): string {
  return STRATEGY_PROFILE_LABELS[profile] ?? profile;
}

/** The `count` highest-weighted dimensions (ties broken by canonical order). */
export function dominantDimensions(
  weights: ScoreWeights,
  count = 2,
): ScoreDimension[] {
  return [...SCORE_DIMENSIONS]
    .sort((a, b) => {
      const delta = (weights[b] ?? 0) - (weights[a] ?? 0);
      if (delta !== 0) return delta;
      return SCORE_DIMENSIONS.indexOf(a) - SCORE_DIMENSIONS.indexOf(b);
    })
    .slice(0, count);
}

/** e.g. "创新性 40% · 用户价值 20%" for the top two dimensions. */
export function dominantSummary(weights: ScoreWeights): string {
  return dominantDimensions(weights)
    .map((dimension) => `${DIMENSION_LABELS[dimension]} ${Math.round((weights[dimension] ?? 0) * 100)}%`)
    .join(" · ");
}

/**
 * A single natural-language sentence describing the research preference. It is
 * explicit that this is a research bias, not a preset product.
 */
export function describeStrategy(
  profile: StrategyProfile,
  weights: ScoreWeights,
): string {
  const dims = dominantDimensions(weights);
  const [first, second] = dims;
  const firstText = first
    ? `${DIMENSION_LABELS[first]} ${Math.round((weights[first] ?? 0) * 100)}%`
    : "";
  const secondText = second
    ? `，${DIMENSION_LABELS[second]} ${Math.round((weights[second] ?? 0) * 100)}%`
    : "";
  return (
    `本次研究偏向${getStrategyLabel(profile)}：${firstText}${secondText}。` +
    "AI 会据此提高相关方向的探索与分析深度，但仍受三年量产、证据与反证约束——" +
    "这是研究偏好，不是预设产品，候选仍由 AI 基于证据动态生成。"
  );
}
