/** Deterministic Research Brief collection and completeness rules. */

import type {
  ForecastOptions,
  ForecastRequest,
  ResearchContext,
  ScoreWeights,
  StrategyPreset,
  StrategyProfile,
} from "../../types/api";
import { SCORE_DIMENSIONS } from "../../types/api";

export interface ResearchBrief {
  question: string;
  category: string;
  forecast_horizon_years: number | null;
  regions: string[];
  target_users: string[];
  price_segment: string | null;
  constraints: string[];
  research_context: ResearchContext;
  candidate_count: number;
  strategy_profile: StrategyProfile;
  weights: ScoreWeights;
}

export const MIN_QUESTION_LENGTH = 12;

export const REQUIRED_FIELDS = [
  "question",
  "forecast_horizon_years",
  "regions",
  "target_users",
] as const;

export const RECOMMENDED_CONTEXT_FIELDS = [
  "housing_types",
  "household_members",
  "security_scenarios",
  "current_devices",
  "pain_points",
  "privacy_preferences",
  "desired_outcomes",
  "innovation_posture",
] as const satisfies readonly (keyof ResearchContext)[];

export type RequiredBriefField = (typeof REQUIRED_FIELDS)[number];

export function emptyResearchContext(): ResearchContext {
  return {
    housing_types: [],
    household_members: [],
    security_scenarios: [],
    current_devices: [],
    pain_points: [],
    allowed_sensors: [],
    privacy_preferences: [],
    installation_constraints: [],
    connectivity_constraints: [],
    business_preferences: [],
    desired_outcomes: [],
    validation_priorities: [],
    innovation_posture: null,
  };
}

export interface ExamplePrompt {
  id: string;
  question: string;
  preset: Partial<Pick<ResearchBrief, "regions" | "target_users" | "forecast_horizon_years" | "constraints">> & {
    research_context?: Partial<ResearchContext>;
  };
}

export const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  { id: "us-no-subscription", question: "未来三年美国独栋家庭有哪些不依赖订阅的安防机会？", preset: { regions: ["United States"], target_users: ["独栋住宅家庭"], forecast_horizon_years: 3, constraints: ["不依赖强制订阅"], research_context: { housing_types: ["独栋住宅"], business_preferences: ["不依赖强制订阅"] } } },
  { id: "cn-apartment", question: "中国城市公寓中，AI 原生家庭安防还能解决什么问题？", preset: { regions: ["China"], target_users: ["城市公寓家庭"], forecast_horizon_years: 3, research_context: { housing_types: ["城市公寓"] } } },
  { id: "eu-us-elderly-children", question: "面向欧美有老人和儿童的家庭，eufy 可以预测什么新产品？", preset: { regions: ["United States", "European Union"], target_users: ["有老人或儿童的家庭"], forecast_horizon_years: 3, research_context: { household_members: ["有儿童家庭", "有老人家庭"], security_scenarios: ["老人儿童照护"] } } },
  { id: "camera-free", question: "未来无摄像头安防是否存在新的产品机会？", preset: { constraints: ["无摄像头"], forecast_horizon_years: 3, research_context: { privacy_preferences: ["避免室内摄像头"], desired_outcomes: ["保护隐私"] } } },
];

/** Six-dimension fallback used only when the backend options are unavailable. */
function defaultWeights(options?: ForecastOptions): ScoreWeights {
  return options?.default_weights
    ? { ...options.default_weights }
    : { innovation: 0.25, user_value: 0.2, business_value: 0.15, cost_effectiveness: 0.15, feasibility: 0.15, eufy_synergy: 0.1 };
}

export function createEmptyBrief(options?: ForecastOptions): ResearchBrief {
  return { question: "", category: "安防", forecast_horizon_years: options?.forecast_horizon_years.default ?? 3, regions: [], target_users: [], price_segment: null, constraints: [], research_context: emptyResearchContext(), candidate_count: options?.candidate_count.default ?? 6, strategy_profile: options?.default_strategy_profile ?? "balanced", weights: defaultWeights(options) };
}

/** Apply a backend-authored preset: sets both the profile label and its weights. */
export function applyStrategyPreset(brief: ResearchBrief, preset: StrategyPreset): ResearchBrief {
  return { ...brief, strategy_profile: preset.id, weights: { ...preset.weights } };
}

/** Any manual weight edit converts the profile to `custom`. */
export function applyCustomWeights(brief: ResearchBrief, weights: ScoreWeights): ResearchBrief {
  return { ...brief, strategy_profile: "custom", weights };
}

function questionOk(brief: ResearchBrief): boolean { return brief.question.trim().length >= MIN_QUESTION_LENGTH; }

export function getMissingFields(brief: ResearchBrief): RequiredBriefField[] {
  const missing: RequiredBriefField[] = [];
  if (!questionOk(brief)) missing.push("question");
  if (brief.forecast_horizon_years == null || brief.forecast_horizon_years < 1) missing.push("forecast_horizon_years");
  if (!brief.regions.length) missing.push("regions");
  if (!brief.target_users.length) missing.push("target_users");
  return missing;
}

export function isBriefComplete(brief: ResearchBrief): boolean { return getMissingFields(brief).length === 0; }

function contextHasValue(context: ResearchContext, key: keyof ResearchContext): boolean {
  const value = context[key];
  return Array.isArray(value) ? value.length > 0 : Boolean(value?.trim());
}

export function getBriefCompleteness(brief: ResearchBrief): number {
  const requiredDone = REQUIRED_FIELDS.length - getMissingFields(brief).length;
  const recommendedDone = RECOMMENDED_CONTEXT_FIELDS.filter((key) => contextHasValue(brief.research_context, key)).length;
  return Math.round(((requiredDone + recommendedDone) / (REQUIRED_FIELDS.length + RECOMMENDED_CONTEXT_FIELDS.length)) * 100);
}

export function applyExamplePrompt(brief: ResearchBrief, example: ExamplePrompt): ResearchBrief {
  return {
    ...brief,
    question: example.question,
    regions: example.preset.regions ?? brief.regions,
    target_users: example.preset.target_users ?? brief.target_users,
    forecast_horizon_years: example.preset.forecast_horizon_years ?? brief.forecast_horizon_years,
    constraints: example.preset.constraints ?? brief.constraints,
    research_context: { ...brief.research_context, ...example.preset.research_context },
  };
}

function dedupeStrings(values: string[]): string[] { return [...new Set(values.map((value) => value.trim()).filter(Boolean))]; }

export function briefToRequest(brief: ResearchBrief): ForecastRequest {
  return {
    question: brief.question.trim(), category: brief.category.trim() || "安防",
    forecast_horizon_years: brief.forecast_horizon_years ?? 3,
    regions: brief.regions.length ? brief.regions : ["United States"],
    target_users: brief.target_users.length ? brief.target_users : ["Households"],
    price_segment: brief.price_segment?.trim() || null,
    constraints: dedupeStrings(brief.constraints),
    research_context: { ...brief.research_context }, candidate_count: brief.candidate_count,
    strategy_profile: brief.strategy_profile, weights: brief.weights,
  };
}

export function areWeightsValid(weights: ScoreWeights): boolean {
  return Math.abs(SCORE_DIMENSIONS.reduce((sum, key) => sum + (weights[key] || 0), 0) - 1) <= 0.001;
}

export function describeBrief(brief: ResearchBrief, regionLabel: (region: string) => string): string {
  const years = brief.forecast_horizon_years ?? 3;
  const regions = brief.regions.map(regionLabel).join("、") || "目标市场";
  const users = brief.target_users.join("、") || "目标家庭";
  const scenarios = brief.research_context.security_scenarios.length ? `，重点关注${brief.research_context.security_scenarios.join("、")}` : "";
  return `我将研究未来 ${years} 年，${regions}中，面向${users}的 AI 原生安防产品机会${scenarios}。`;
}
