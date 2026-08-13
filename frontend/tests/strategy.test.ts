import { describe, expect, it } from "vitest";
import {
  SCORE_DIMENSIONS,
  type ProductCandidate,
  type ScoreWeights,
  type StrategyPreset,
} from "../src/types/api";
import {
  applyCustomWeights,
  applyStrategyPreset,
  areWeightsValid,
  briefToRequest,
  createEmptyBrief,
  emptyResearchContext,
  type ResearchBrief,
} from "../src/features/forecast-create/researchBrief";
import { normalizeWeights } from "../src/features/forecast-create/WeightSliders";
import {
  describeStrategy,
  dominantDimensions,
  dominantSummary,
  getStrategyLabel,
} from "../src/lib/strategy";
import { KNOWN_EVENT_TYPES, parseAgentEvent } from "../src/lib/api/sse";

const BALANCED: ScoreWeights = {
  innovation: 0.25,
  user_value: 0.2,
  business_value: 0.15,
  cost_effectiveness: 0.15,
  feasibility: 0.15,
  eufy_synergy: 0.1,
};

const BREAKTHROUGH_PRESET: StrategyPreset = {
  id: "breakthrough",
  label: "突破创新",
  description: "探索新型 AI 原生硬件与交互",
  weights: {
    innovation: 0.4,
    user_value: 0.2,
    business_value: 0.1,
    cost_effectiveness: 0.1,
    feasibility: 0.1,
    eufy_synergy: 0.1,
  },
};

function brief(overrides: Partial<ResearchBrief> = {}): ResearchBrief {
  return {
    question: "未来三年美国独栋家庭有哪些安防机会？",
    category: "eufy Security",
    forecast_horizon_years: 3,
    regions: ["United States"],
    target_users: ["独栋住宅家庭"],
    price_segment: null,
    constraints: [],
    research_context: emptyResearchContext(),
    candidate_count: 6,
    strategy_profile: "balanced",
    weights: BALANCED,
    ...overrides,
  };
}

describe("six-dimension contract", () => {
  it("exposes exactly the six scoring dimensions including cost_effectiveness", () => {
    expect(SCORE_DIMENSIONS).toHaveLength(6);
    expect(SCORE_DIMENSIONS).toContain("cost_effectiveness");
  });

  it("seeds an empty brief with the balanced profile and a valid six-dim weight set", () => {
    const seeded = createEmptyBrief();
    expect(seeded.strategy_profile).toBe("balanced");
    expect(Object.keys(seeded.weights)).toHaveLength(6);
    expect(areWeightsValid(seeded.weights)).toBe(true);
  });
});

describe("applying a preset", () => {
  it("updates both the profile and the backend-authored weights", () => {
    const next = applyStrategyPreset(brief(), BREAKTHROUGH_PRESET);
    expect(next.strategy_profile).toBe("breakthrough");
    expect(next.weights).toEqual(BREAKTHROUGH_PRESET.weights);
    // A separate object, not the same reference (no shared mutation).
    expect(next.weights).not.toBe(BREAKTHROUGH_PRESET.weights);
  });

  it("re-applying a preset restores its exact weights", () => {
    const custom = applyCustomWeights(brief(), { ...BALANCED, innovation: 0.5, eufy_synergy: 0.05 });
    expect(custom.strategy_profile).toBe("custom");
    const restored = applyStrategyPreset(custom, BREAKTHROUGH_PRESET);
    expect(restored.strategy_profile).toBe("breakthrough");
    expect(restored.weights).toEqual(BREAKTHROUGH_PRESET.weights);
  });
});

describe("manual weight edits", () => {
  it("switches the profile to custom", () => {
    const next = applyCustomWeights(brief(), { ...BALANCED, innovation: 0.3, eufy_synergy: 0.05 });
    expect(next.strategy_profile).toBe("custom");
  });

  it("normalizes six-dimension weights to sum to 100%", () => {
    const raw: ScoreWeights = {
      innovation: 30,
      user_value: 10,
      business_value: 10,
      cost_effectiveness: 10,
      feasibility: 10,
      eufy_synergy: 5,
    };
    const normalized = normalizeWeights(raw);
    expect(areWeightsValid(normalized)).toBe(true);
    const pctTotal = SCORE_DIMENSIONS.reduce((sum, key) => sum + Math.round(normalized[key] * 100), 0);
    expect(pctTotal).toBe(100);
  });
});

describe("start gating", () => {
  it("blocks starting when weights do not sum to 100%", () => {
    const bad = applyCustomWeights(brief(), { ...BALANCED, innovation: 0.5 });
    expect(areWeightsValid(bad.weights)).toBe(false);
  });
});

describe("briefToRequest", () => {
  it("sends strategy_profile and the six-dimension weights", () => {
    const request = briefToRequest(applyStrategyPreset(brief(), BREAKTHROUGH_PRESET));
    expect(request.strategy_profile).toBe("breakthrough");
    expect(Object.keys(request.weights).sort()).toEqual([...SCORE_DIMENSIONS].sort());
    expect(request.weights.cost_effectiveness).toBe(0.1);
  });

  it("never carries any API-key-like field to the backend", () => {
    const request = briefToRequest(brief());
    const keys = Object.keys(request).map((key) => key.toLowerCase());
    expect(keys.some((key) => key.includes("key") || key.includes("secret") || key.includes("token"))).toBe(
      false,
    );
  });
});

describe("strategy summary", () => {
  it("labels the profile and names the top two dimensions", () => {
    expect(getStrategyLabel("breakthrough")).toBe("突破创新");
    expect(dominantDimensions(BREAKTHROUGH_PRESET.weights)[0]).toBe("innovation");
    expect(dominantSummary(BREAKTHROUGH_PRESET.weights)).toContain("创新性 40%");
  });

  it("describes the research bias as a preference, not a preset product", () => {
    const text = describeStrategy("breakthrough", BREAKTHROUGH_PRESET.weights);
    expect(text).toContain("突破创新");
    expect(text).toContain("不是预设产品");
  });
});

describe("backward compatibility", () => {
  it("handles a candidate that lacks strategy_alignment without crashing", () => {
    const legacy: Partial<ProductCandidate> = { id: "CAND-001", name: "Legacy" };
    const alignment = (legacy as ProductCandidate).strategy_alignment;
    expect(alignment?.aligned_dimensions ?? []).toEqual([]);
    expect(alignment?.tradeoffs ?? []).toEqual([]);
  });
});

describe("strategy_applied SSE event", () => {
  it("is a known event type", () => {
    expect(KNOWN_EVENT_TYPES).toContain("strategy_applied");
  });

  it("parses a strategy_applied payload", () => {
    const raw = JSON.stringify({
      id: 3,
      run_id: "forecast-1",
      sequence: 3,
      event_type: "strategy_applied",
      agent: "layered-retrieval-planner",
      message: "研究策略已应用：突破创新",
      payload: {
        strategy_profile: "breakthrough",
        weights: BREAKTHROUGH_PRESET.weights,
        dominant_dimensions: ["innovation", "user_value"],
        retrieval_adjustments: { technology: 2, risk_counterevidence: 1 },
      },
      created_at: "2026-08-13T00:00:00Z",
    });
    const parsed = parseAgentEvent(raw);
    expect(parsed?.event_type).toBe("strategy_applied");
    expect((parsed?.payload as { strategy_profile: string }).strategy_profile).toBe("breakthrough");
  });
});
