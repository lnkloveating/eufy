import { describe, expect, it } from "vitest";
import type { ScoreWeights } from "../src/types/api";
import {
  areWeightsValid,
  normalizeWeights,
  weightsTotal,
} from "../src/lib/weights";

const DEFAULT: ScoreWeights = {
  innovation: 0.3,
  user_value: 0.25,
  business_value: 0.2,
  feasibility: 0.15,
  eufy_synergy: 0.1,
};

describe("weights validation", () => {
  it("accepts weights that sum to 1.0", () => {
    expect(weightsTotal(DEFAULT)).toBeCloseTo(1, 5);
    expect(areWeightsValid(DEFAULT)).toBe(true);
  });

  it("rejects weights that do not sum to 1.0", () => {
    const invalid: ScoreWeights = {
      innovation: 0.5,
      user_value: 0.5,
      business_value: 0.5,
      feasibility: 0,
      eufy_synergy: 0,
    };
    expect(areWeightsValid(invalid)).toBe(false);
  });

  it("treats a total within tolerance as valid", () => {
    const nearly: ScoreWeights = {
      innovation: 0.3005,
      user_value: 0.25,
      business_value: 0.2,
      feasibility: 0.15,
      eufy_synergy: 0.0995,
    };
    expect(areWeightsValid(nearly)).toBe(true);
  });

  it("normalizes proportionally to sum to 1.0", () => {
    const raw: ScoreWeights = {
      innovation: 2,
      user_value: 2,
      business_value: 0,
      feasibility: 0,
      eufy_synergy: 0,
    };
    const normalized = normalizeWeights(raw);
    expect(weightsTotal(normalized)).toBeCloseTo(1, 5);
    expect(normalized.innovation).toBeCloseTo(0.5, 5);
    expect(normalized.user_value).toBeCloseTo(0.5, 5);
    expect(areWeightsValid(normalized)).toBe(true);
  });

  it("falls back to an even split when every weight is zero", () => {
    const zero: ScoreWeights = {
      innovation: 0,
      user_value: 0,
      business_value: 0,
      feasibility: 0,
      eufy_synergy: 0,
    };
    const normalized = normalizeWeights(zero);
    expect(weightsTotal(normalized)).toBeCloseTo(1, 5);
    expect(normalized.innovation).toBeCloseTo(0.2, 5);
  });
});
