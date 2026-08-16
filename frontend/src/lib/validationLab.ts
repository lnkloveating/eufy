/**
 * Pure, side-effect-free helpers for the pre-validation lab UI.
 *
 * Kept dependency-free so it can be unit-tested in a Node environment. Nothing
 * here fabricates a pass rate, an accuracy number or a user-study result — every
 * label makes the "pre-validation / simulation" boundary explicit, and no label
 * ever contains a percentage or a "通过率 / 准确率 / 成功率" claim.
 */

import type {
  DefinitionStatus,
  ExperimentType,
  ExperimentVerdict,
  FindingSeverity,
  ObservationSourceType,
  ScenarioTemplate,
  ValidationProjectStatus,
} from "../types/api";

export interface Meta {
  label: string;
  /** A design-system badge class, reused so labels look native. */
  badge: string;
}

/** The single boundary statement shown wherever a result is displayed. */
export const SIMULATION_BOUNDARY =
  "预验证 / 模拟：结论基于确定性场景与产品定义推演，不代表真实硬件或真实用户测试。";

export const VERDICT_META: Record<ExperimentVerdict, Meta & { description: string }> = {
  not_run: {
    label: "未运行",
    badge: "badge-pending",
    description: "该实验尚未运行。",
  },
  supported_in_simulation: {
    label: "模拟支持",
    badge: "badge-completed",
    description: "在确定性模拟中结构上成立；不代表真实硬件或真实用户已验证。",
  },
  inconclusive: {
    label: "证据不足",
    badge: "badge-warn",
    description: "角色意见或场景结论存在缺口，现有信息不足以形成模拟支持结论。",
  },
  contradicted: {
    label: "出现反例",
    badge: "badge-failed",
    description: "模拟或角色发现阻断性反例，假设在当前定义下被证伪。",
  },
  requires_real_world_test: {
    label: "需真实测试",
    badge: "badge-info",
    description: "关键指标属经验数据，必须真实硬件或真实用户测试，模拟无法替代。",
  },
};

export const PROJECT_STATUS_META: Record<ValidationProjectStatus, Meta> = {
  draft: { label: "草稿", badge: "badge-pending" },
  planned: { label: "已生成计划", badge: "badge-info" },
  running: { label: "预验证进行中", badge: "badge-running" },
  completed: { label: "预验证完成（模拟）", badge: "badge-completed" },
  failed: { label: "运行失败", badge: "badge-failed" },
};

export const EXPERIMENT_TYPE_META: Record<ExperimentType, string> = {
  technology: "技术验证",
  privacy_security: "隐私安全",
  user_scenario: "用户场景",
  business: "商业验证",
  deterministic_simulation: "确定性模拟",
};

export const SOURCE_TYPE_META: Record<ObservationSourceType, Meta> = {
  existing_evidence: { label: "已有证据", badge: "badge-info" },
  ai_analysis: { label: "AI 分析", badge: "badge-degraded" },
  deterministic_simulation: { label: "确定性模拟", badge: "badge-completed" },
  human_observation: { label: "真实观察", badge: "badge-pending" },
  external_test: { label: "外部测试", badge: "badge-pending" },
};

export const SEVERITY_META: Record<FindingSeverity, Meta> = {
  info: { label: "提示", badge: "badge-info" },
  warning: { label: "警告", badge: "badge-warn" },
  critical: { label: "严重", badge: "badge-failed" },
};

export const SCENARIO_META: Record<ScenarioTemplate, { label: string; icon: string }> = {
  urban_apartment_intrusion: { label: "城市公寓陌生人入侵", icon: "🚪" },
  elderly_night_anomaly: { label: "老人夜间异常活动", icon: "🌙" },
  pet_false_alarm: { label: "宠物导致误报", icon: "🐾" },
  home_network_outage: { label: "家庭网络中断", icon: "📶" },
};

export function verdictLabel(verdict: ExperimentVerdict): string {
  return VERDICT_META[verdict].label;
}

/**
 * Which dimension the feasibility gap sits on. Instead of a generic "evidence
 * is insufficient", the matrix names the actual problem — is it a technology
 * gap, a business-viability gap, a lack of user research, or a privacy question.
 */
export type FeasibilityDimension = "technology" | "business" | "user" | "privacy";

const DIMENSION_LABEL: Record<FeasibilityDimension, string> = {
  technology: "技术可行性",
  business: "商业可行性",
  user: "用户接受度",
  privacy: "隐私接受度",
};

const BUSINESS_KEYWORDS = [
  "付费", "愿意支付", "支付", "价格", "定价", "订阅", "成本", "毛利", "营收", "利润",
  "套件", "竞争力", "变现", "商业", "pay", "price", "subscription", "revenue", "cost",
  "margin", "willing",
];
const USER_KEYWORDS = [
  "接受", "采用", "满意", "易用", "上手", "用户体验", "感知", "旁观", "adoption",
  "acceptance", "usability", "user",
];
const PRIVACY_KEYWORDS = ["隐私", "敏感", "合规", "脱敏", "privacy", "gdpr", "consent"];

interface FeasibilityInput {
  assumption: string;
  metric: string;
  experiment_type: ExperimentType;
  verdict: ExperimentVerdict;
}

/** Classify the feasibility dimension from the hypothesis text, then type. */
export function feasibilityDimension(input: FeasibilityInput): FeasibilityDimension {
  const text = `${input.assumption} ${input.metric}`.toLowerCase();
  const has = (keywords: string[]): boolean =>
    keywords.some((keyword) => text.includes(keyword.toLowerCase()));
  if (has(BUSINESS_KEYWORDS)) return "business";
  if (has(USER_KEYWORDS)) return "user";
  if (has(PRIVACY_KEYWORDS)) return "privacy";
  if (input.experiment_type === "business") return "business";
  if (input.experiment_type === "user_scenario") return "user";
  if (input.experiment_type === "privacy_security") return "privacy";
  return "technology";
}

const FEASIBILITY_REASON: Record<ExperimentVerdict, Record<FeasibilityDimension, string>> = {
  supported_in_simulation: {
    technology: "现有证据支持技术路径，方案初步可行。",
    business: "现有证据支持商业逻辑，方案初步可行。",
    user: "现有证据支持用户价值，方案初步可行。",
    privacy: "现有证据支持隐私设计，方案初步可行。",
  },
  requires_real_world_test: {
    technology: "关键技术指标（可靠性、误报率等）缺少真实硬件实测，需现场测试。",
    business: "价格、付费意愿与成本尚无真实市场数据，需用户/市场调研。",
    user: "尚未做过真实用户调研，用户接受度数据不足。",
    privacy: "隐私接受度需真实用户验证，缺少用户调研数据。",
  },
  inconclusive: {
    technology: "技术层面证据存在缺口，暂无法判定可行性。",
    business: "商业层面证据不足，暂无法判定可行性。",
    user: "缺少真实用户调研数据，暂无法判定接受度。",
    privacy: "缺少隐私接受度数据，暂无法判定。",
  },
  contradicted: {
    technology: "技术定义存在结构性缺口，模拟中出现反例。",
    business: "商业模式存在冲突，模拟中出现反例。",
    user: "使用链路在模拟中出现反例，用户价值不成立。",
    privacy: "隐私或决策边界存在冲突，出现反例。",
  },
  not_run: {
    technology: "尚未评估。",
    business: "尚未评估。",
    user: "尚未评估。",
    privacy: "尚未评估。",
  },
};

/**
 * A dimension-specific feasibility read for the hypothesis matrix: it names the
 * problem (technology / business / user research / privacy) instead of a generic
 * "evidence is insufficient", without inventing any pass rate.
 */
export function feasibilityAssessment(input: FeasibilityInput): {
  dimension: FeasibilityDimension;
  label: string;
  reason: string;
} {
  const dimension = feasibilityDimension(input);
  return {
    dimension,
    label: DIMENSION_LABEL[dimension],
    reason: FEASIBILITY_REASON[input.verdict][dimension],
  };
}

export interface ValidationLabEntry {
  enabled: boolean;
  path: string;
  reason: string;
}

/**
 * Where the "验证实验室" entry points and whether it is enabled.
 *
 * Enabled only once the product definition is ``validation_ready``. Before that
 * the entry is disabled with a clear "finish the product definition first" hint.
 */
export function validationLabEntry(
  productId: string | undefined,
  status: DefinitionStatus | undefined,
): ValidationLabEntry {
  const path = productId
    ? `/products/${encodeURIComponent(productId)}/validation`
    : "";
  if (status === "validation_ready") {
    return { enabled: true, path, reason: "进入产品预验证实验室（模拟）" };
  }
  return {
    enabled: false,
    path,
    reason: "请先完成产品定义并确认，再进入验证实验室。",
  };
}

/** Maps a validation event type to a timeline dot class. */
export function eventDotClass(eventType: string): string {
  if (eventType === "run_failed" || eventType === "experiment_failed") return "tl-fail";
  if (eventType === "run_completed") return "tl-done";
  if (eventType === "run_started" || eventType === "run_scheduled" || eventType === "project_created")
    return "tl-start";
  return "";
}

/** True when the finding has already been sent back to the definition Copilot. */
export function isFindingSent(status: string): boolean {
  return status === "sent_to_definition";
}
