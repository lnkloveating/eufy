/** Deterministic Research Brief collection and completeness rules. */

import type {
  ForecastOptions,
  ForecastRequest,
  ResearchContext,
  ScoreWeights,
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

export type RequiredClarificationKey = (typeof REQUIRED_FIELDS)[number];
export type ContextClarificationKey = keyof ResearchContext;
export type ClarificationKey = RequiredClarificationKey | ContextClarificationKey;

export interface ClarificationOption {
  label: string;
  value: string;
}

export interface ClarificationQuestion {
  key: ClarificationKey;
  title: string;
  description?: string;
  kind: "list" | "number" | "text";
  multi: boolean;
  allowCustom: boolean;
  required: boolean;
  section: "研究范围" | "家庭与场景" | "产品边界";
  options: ClarificationOption[];
}

const FALLBACK_CONTEXT_OPTIONS: Record<keyof ResearchContext, string[]> = {
  housing_types: ["城市公寓", "独栋住宅", "联排住宅", "租赁住房", "多代同堂住宅"],
  household_members: ["独居者", "双职工家庭", "有儿童家庭", "有老人家庭", "有宠物家庭"],
  security_scenarios: ["入侵与周界", "包裹与门前", "室内异常", "老人儿童照护", "火灾水浸等环境风险", "车辆与车库"],
  current_devices: ["尚未使用安防设备", "摄像头或门铃", "HomeBase 或本地存储", "门窗或运动传感器", "智能锁", "第三方智能家居设备"],
  pain_points: ["误报过多", "告警太晚", "室内摄像头隐私顾虑", "设备孤岛", "安装维护复杂", "电池与断网问题", "订阅费用"],
  allowed_sensors: ["摄像头", "毫米波雷达", "PIR 运动传感器", "门窗磁", "声学传感器", "环境传感器", "可穿戴或手机协同"],
  privacy_preferences: ["优先端侧 AI", "优先本地存储", "避免室内摄像头", "敏感数据不出户", "允许可撤回的云端增强"],
  installation_constraints: ["纯无线免布线", "租房可移除", "用户自行安装", "低维护长续航", "不改变家装"],
  connectivity_constraints: ["断网仍可工作", "弱网环境", "兼容 Matter", "不依赖单一中枢", "支持家庭局域网"],
  business_preferences: ["一次性硬件收入", "不依赖强制订阅", "可选增值服务", "家庭套装", "与现有 eufy 设备协同"],
  desired_outcomes: ["更早预防风险", "降低误报", "缩短处置时间", "保护隐私", "减少安装学习成本", "提升家庭成员安心感"],
  validation_priorities: ["用户愿付价格", "误报与漏报", "安装完成率", "隐私接受度", "技术可实现性", "三年量产成本", "竞品差异化"],
  innovation_posture: ["近三年可量产", "平衡创新与落地", "探索激进的新形态"],
};

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

function optionList(key: keyof ResearchContext, options?: ForecastOptions): ClarificationOption[] {
  return (options?.research_context_options?.[key] ?? FALLBACK_CONTEXT_OPTIONS[key]).map(
    (value) => ({ label: value, value }),
  );
}

export function clarificationCatalog(options?: ForecastOptions): Record<ClarificationKey, ClarificationQuestion> {
  const contextQuestion = (
    key: ContextClarificationKey,
    title: string,
    section: ClarificationQuestion["section"],
    description: string,
    multi = true,
  ): ClarificationQuestion => ({
    key,
    title,
    description,
    kind: "list",
    multi,
    allowCustom: true,
    required: false,
    section,
    options: optionList(key, options),
  });
  return {
    question: { key: "question", title: "你想研究什么未来产品机会？", kind: "text", multi: false, allowCustom: true, required: true, section: "研究范围", options: [] },
    regions: { key: "regions", title: "希望研究哪些市场？", kind: "list", multi: true, allowCustom: true, required: true, section: "研究范围", options: [
      { label: "美国", value: "United States" }, { label: "中国", value: "China" },
      { label: "欧洲", value: "European Union" }, { label: "全球", value: "Global" },
    ] },
    target_users: { key: "target_users", title: "主要面向哪类家庭？", kind: "list", multi: true, allowCustom: true, required: true, section: "研究范围", options: [
      { label: "城市公寓家庭", value: "城市公寓家庭" }, { label: "独栋住宅家庭", value: "独栋住宅家庭" },
      { label: "租房家庭", value: "租房家庭" }, { label: "有老人或儿童的家庭", value: "有老人或儿童的家庭" },
    ] },
    forecast_horizon_years: { key: "forecast_horizon_years", title: "希望预测多长时间？", kind: "number", multi: false, allowCustom: true, required: true, section: "研究范围", options: [
      { label: "未来 1 年", value: "1" }, { label: "未来 3 年", value: "3" }, { label: "未来 5 年", value: "5" },
    ] },
    housing_types: contextQuestion("housing_types", "家庭住在怎样的房屋中？", "家庭与场景", "住宅结构会影响覆盖范围、供电、安装与传感器组合。"),
    household_members: contextQuestion("household_members", "家中有哪些需要重点考虑的成员？", "家庭与场景", "用于区分行为习惯、照护需求和通知对象。"),
    security_scenarios: contextQuestion("security_scenarios", "最希望研究哪些安全场景？", "家庭与场景", "可多选；Agent 仍可发现输入之外的新机会。"),
    current_devices: contextQuestion("current_devices", "家庭现在已经使用什么设备？", "产品边界", "帮助判断替换、补充或生态协同机会。"),
    pain_points: contextQuestion("pain_points", "现有体验最不能接受的问题是什么？", "产品边界", "这些是机会线索，不会直接硬编码成产品。"),
    privacy_preferences: contextQuestion("privacy_preferences", "隐私和数据处理有什么偏好？", "产品边界", "影响摄像头、端侧 AI、本地存储与云服务边界。"),
    desired_outcomes: contextQuestion("desired_outcomes", "希望新产品优先带来什么结果？", "产品边界", "用结果约束方案，而不是预设具体产品形态。"),
    innovation_posture: contextQuestion("innovation_posture", "这次研究希望多激进？", "产品边界", "决定候选组合偏量产、平衡还是探索。", false),
    allowed_sensors: contextQuestion("allowed_sensors", "可以接受哪些传感方式？", "产品边界", "未选择不代表禁止，明确限制请同时写入限制条件。"),
    installation_constraints: contextQuestion("installation_constraints", "安装维护有哪些限制？", "产品边界", "用于约束布线、续航、租房与维护成本。"),
    connectivity_constraints: contextQuestion("connectivity_constraints", "连接和离线能力有哪些要求？", "产品边界", "用于约束中枢、弱网、局域网与互操作性。"),
    business_preferences: contextQuestion("business_preferences", "更偏好怎样的商业模式？", "产品边界", "用于分析硬件、套装、可选服务与生态拉动。"),
    validation_priorities: contextQuestion("validation_priorities", "后续最想优先验证什么？", "产品边界", "将影响 ProductSpec 中验证假设的优先方向。"),
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

function defaultWeights(options?: ForecastOptions): ScoreWeights {
  return options?.default_weights ? { ...options.default_weights } : { innovation: 0.3, user_value: 0.25, business_value: 0.2, feasibility: 0.15, eufy_synergy: 0.1 };
}

export function createEmptyBrief(options?: ForecastOptions): ResearchBrief {
  return { question: "", category: "eufy Security", forecast_horizon_years: options?.forecast_horizon_years.default ?? 3, regions: [], target_users: [], price_segment: null, constraints: [], research_context: emptyResearchContext(), candidate_count: options?.candidate_count.default ?? 6, weights: defaultWeights(options) };
}

function questionOk(brief: ResearchBrief): boolean { return brief.question.trim().length >= MIN_QUESTION_LENGTH; }

export function getMissingFields(brief: ResearchBrief): RequiredClarificationKey[] {
  const missing: RequiredClarificationKey[] = [];
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

export function getMissingClarifications(brief: ResearchBrief, options?: ForecastOptions): ClarificationQuestion[] {
  const catalog = clarificationCatalog(options);
  const required = getMissingFields(brief).map((key) => catalog[key]);
  const recommended = RECOMMENDED_CONTEXT_FIELDS.filter((key) => !contextHasValue(brief.research_context, key)).map((key) => catalog[key]);
  return [...required, ...recommended];
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

export function applyClarificationAnswers(brief: ResearchBrief, answers: Partial<Record<ClarificationKey, string[]>>): ResearchBrief {
  const next: ResearchBrief = { ...brief, research_context: { ...brief.research_context } };
  if (answers.question?.[0] != null) next.question = answers.question[0];
  if (answers.regions) next.regions = dedupeStrings(answers.regions);
  if (answers.target_users) next.target_users = dedupeStrings(answers.target_users);
  if (answers.forecast_horizon_years?.[0]) {
    const parsed = Number.parseInt(answers.forecast_horizon_years[0], 10);
    if (Number.isFinite(parsed)) next.forecast_horizon_years = Math.min(10, Math.max(1, parsed));
  }
  for (const key of Object.keys(next.research_context) as ContextClarificationKey[]) {
    const answer = answers[key];
    if (answer === undefined) continue;
    if (key === "innovation_posture") next.research_context.innovation_posture = answer[0]?.trim() || null;
    else (next.research_context[key] as string[]) = dedupeStrings(answer);
  }
  return next;
}

export function briefToRequest(brief: ResearchBrief): ForecastRequest {
  return {
    question: brief.question.trim(), category: brief.category.trim() || "eufy Security",
    forecast_horizon_years: brief.forecast_horizon_years ?? 3,
    regions: brief.regions.length ? brief.regions : ["United States"],
    target_users: brief.target_users.length ? brief.target_users : ["Households"],
    price_segment: brief.price_segment?.trim() || null,
    constraints: dedupeStrings(brief.constraints),
    research_context: { ...brief.research_context }, candidate_count: brief.candidate_count, weights: brief.weights,
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
