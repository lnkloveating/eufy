/** Validation + normalization helpers for the five evaluation weights. */

import { SCORE_DIMENSIONS, type ScoreDimension, type ScoreWeights } from "../types/api";

/** The backend accepts a total within ±0.001 of 1.0. */
export const WEIGHT_TOLERANCE = 0.001;

export function weightsTotal(weights: ScoreWeights): number {
  return SCORE_DIMENSIONS.reduce((sum, dimension) => sum + (weights[dimension] || 0), 0);
}

/** True when the five weights sum to 1.0 within the backend tolerance. */
export function areWeightsValid(weights: ScoreWeights): boolean {
  return Math.abs(weightsTotal(weights) - 1.0) <= WEIGHT_TOLERANCE;
}

/**
 * Proportionally rescale weights so they sum to exactly 1.0.
 * If every weight is zero, falls back to an even split.
 */
export function normalizeWeights(weights: ScoreWeights): ScoreWeights {
  const total = weightsTotal(weights);
  if (total <= 0) {
    const even = 1 / SCORE_DIMENSIONS.length;
    return SCORE_DIMENSIONS.reduce((acc, dimension) => {
      acc[dimension] = even;
      return acc;
    }, {} as ScoreWeights);
  }
  return SCORE_DIMENSIONS.reduce((acc, dimension) => {
    acc[dimension] = weights[dimension] / total;
    return acc;
  }, {} as ScoreWeights);
}

/** Round every weight to `decimals` places (used when normalizing % inputs). */
export function roundWeights(weights: ScoreWeights, decimals = 2): ScoreWeights {
  const factor = 10 ** decimals;
  return SCORE_DIMENSIONS.reduce((acc, dimension) => {
    acc[dimension] = Math.round(weights[dimension] * factor) / factor;
    return acc;
  }, {} as ScoreWeights);
}

export function formatWeightPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function dimensionKeys(): ScoreDimension[] {
  return [...SCORE_DIMENSIONS];
}
