import { describe, expect, it } from "vitest";
import type { ScoreWeights } from "../src/types/api";
import {
  applyClarificationAnswers,
  applyExamplePrompt,
  areWeightsValid,
  briefToRequest,
  createEmptyBrief,
  emptyResearchContext,
  EXAMPLE_PROMPTS,
  getBriefCompleteness,
  getMissingClarifications,
  getMissingFields,
  isBriefComplete,
  type ResearchBrief,
} from "../src/features/forecast-create/researchBrief";

const WEIGHTS: ScoreWeights = {
  innovation: 0.3,
  user_value: 0.25,
  business_value: 0.2,
  feasibility: 0.15,
  eufy_synergy: 0.1,
};

function brief(overrides: Partial<ResearchBrief> = {}): ResearchBrief {
  return {
    question: "",
    category: "eufy Security",
    forecast_horizon_years: null,
    regions: [],
    target_users: [],
    price_segment: null,
    constraints: [],
    research_context: emptyResearchContext(),
    candidate_count: 6,
    weights: WEIGHTS,
    ...overrides,
  };
}

describe("completeness check", () => {
  it("flags every missing required field in ask-order", () => {
    expect(getMissingFields(brief())).toEqual([
      "question",
      "forecast_horizon_years",
      "regions",
      "target_users",
    ]);
  });

  it("treats a too-short question as missing", () => {
    expect(getMissingFields(brief({ question: "太短" }))).toContain("question");
  });

  it("is complete once all required fields are provided", () => {
    const complete = brief({
      question: "未来三年美国独栋家庭有哪些安防机会？",
      forecast_horizon_years: 3,
      regions: ["United States"],
      target_users: ["独栋住宅家庭"],
    });
    expect(isBriefComplete(complete)).toBe(true);
    expect(getMissingFields(complete)).toEqual([]);
  });

  it("only surfaces clarification cards for currently-missing fields", () => {
    const partial = brief({
      question: "未来三年美国独栋家庭有哪些安防机会？",
      forecast_horizon_years: 3,
    });
    const questions = getMissingClarifications(partial);
    expect(questions.slice(0, 2).map((q) => q.key)).toEqual(["regions", "target_users"]);
    expect(questions.map((q) => q.key)).toContain("security_scenarios");
  });
});

describe("example prompts", () => {
  it("sets the question and applies its deterministic preset", () => {
    const example = EXAMPLE_PROMPTS[0]!;
    const next = applyExamplePrompt(brief(), example);
    expect(next.question).toBe(example.question);
    expect(next.regions).toEqual(["United States"]);
    expect(next.forecast_horizon_years).toBe(3);
    expect(next.constraints).toContain("不依赖强制订阅");
    expect(next.research_context.housing_types).toContain("独栋住宅");
  });
});

describe("clarification answers", () => {
  it("merges list, number and text answers into the brief", () => {
    const next = applyClarificationAnswers(brief({ question: "一个足够长的研究问题内容" }), {
      regions: ["United States", "China", "China"],
      target_users: ["城市公寓家庭"],
      forecast_horizon_years: ["5"],
      housing_types: ["城市公寓"],
      pain_points: ["误报过多", "误报过多"],
    });
    expect(next.regions).toEqual(["United States", "China"]); // deduped
    expect(next.target_users).toEqual(["城市公寓家庭"]);
    expect(next.forecast_horizon_years).toBe(5);
    expect(next.research_context.housing_types).toEqual(["城市公寓"]);
    expect(next.research_context.pain_points).toEqual(["误报过多"]);
    expect(isBriefComplete(next)).toBe(true);
  });

  it("clamps a custom horizon into the allowed 1..10 range", () => {
    const next = applyClarificationAnswers(brief(), { forecast_horizon_years: ["99"] });
    expect(next.forecast_horizon_years).toBe(10);
  });
});

describe("briefToRequest", () => {
  it("produces a valid request with safe fallbacks", () => {
    const request = briefToRequest(
      brief({
        question: "  未来三年美国独栋家庭有哪些安防机会？  ",
        forecast_horizon_years: 3,
        regions: ["United States"],
        target_users: ["独栋住宅家庭"],
        price_segment: "  ",
        research_context: {
          ...emptyResearchContext(),
          privacy_preferences: ["优先端侧 AI"],
        },
      }),
    );
    expect(request.question).toBe("未来三年美国独栋家庭有哪些安防机会？");
    expect(request.price_segment).toBeNull();
    expect(request.regions).toEqual(["United States"]);
    expect(request.category).toBe("eufy Security");
    expect(request.research_context.privacy_preferences).toEqual(["优先端侧 AI"]);
  });
});

describe("research context completeness", () => {
  it("raises completeness as recommended context is supplied without making it required", () => {
    const base = brief({
      question: "未来三年美国独栋家庭有哪些安防机会？",
      forecast_horizon_years: 3,
      regions: ["United States"],
      target_users: ["独栋住宅家庭"],
    });
    expect(isBriefComplete(base)).toBe(true);
    expect(getBriefCompleteness(base)).toBe(33);
    const richer = {
      ...base,
      research_context: {
        ...base.research_context,
        housing_types: ["独栋住宅"],
        security_scenarios: ["入侵与周界"],
        desired_outcomes: ["更早预防风险"],
      },
    };
    expect(getBriefCompleteness(richer)).toBeGreaterThan(getBriefCompleteness(base));
  });
});

describe("weights", () => {
  it("accepts weights summing to 1.0 and rejects otherwise", () => {
    expect(areWeightsValid(WEIGHTS)).toBe(true);
    expect(areWeightsValid({ ...WEIGHTS, innovation: 0.5 })).toBe(false);
  });
});

describe("createEmptyBrief", () => {
  it("seeds sane defaults", () => {
    const seeded = createEmptyBrief();
    expect(seeded.forecast_horizon_years).toBe(3);
    expect(seeded.candidate_count).toBe(6);
    expect(areWeightsValid(seeded.weights)).toBe(true);
  });
});
