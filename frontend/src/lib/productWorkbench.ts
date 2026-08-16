/**
 * Pure, side-effect-free helpers for the Product Definition Workbench UI.
 *
 * Kept dependency-free so it can be unit-tested in a Node environment without a
 * DOM. Nothing here fabricates answers or validation results — it only maps
 * backend values to display labels the design system already knows.
 */

import type {
  AnswerMode,
  DefinitionStatus,
  EpistemicStatus,
  QuestionCategory,
  SuggestionDisposition,
} from "../types/api";

export interface QuickQuestion {
  label: string;
  question: string;
}

/**
 * Quick prompts. Each only *fills or submits* a real question string — the
 * answer always comes from the backend Agent, never from the frontend.
 */
export const QUICK_QUESTIONS: readonly QuickQuestion[] = [
  { label: "与现有产品的区别", question: "这个产品与现在主流的 eufy 产品有哪些本质区别？" },
  { label: "端侧能力", question: "哪些能力可以在端侧运行，哪些必须依赖云端？" },
  { label: "断网可用性", question: "断网后这个产品还能正常工作吗？" },
  { label: "与 HomeBase 3 关系", question: "它与 HomeBase 3 及现有 eufy 设备是什么关系？" },
  {
    label: "隐私保护",
    question: "如何保护儿童、老人和访客的隐私？访客数据保留多久、如何删除？",
  },
  { label: "最接近的竞品", question: "最接近的竞品是什么？我们的可防御差异在哪里？" },
  { label: "为何愿意购买", question: "为什么用户会愿意购买这个产品？" },
  { label: "非订阅商业模式", question: "如果不采用强制订阅，这个产品在商业上如何成立？" },
  { label: "最大技术风险", question: "当前最大的技术与落地风险是什么？" },
  { label: "仍是假设的内容", question: "当前产品定义里，哪些内容仍然只是 AI 的设计假设？" },
  { label: "进入验证前要验证什么", question: "进入验证实验室前，最需要优先验证哪些关键假设？" },
];

export interface Meta {
  label: string;
  /** A design-system badge class, reused so labels look native. */
  badge: string;
}

export const EPISTEMIC_STATUS_META: Record<EpistemicStatus, Meta> = {
  evidence_supported: { label: "证据支持", badge: "badge-completed" },
  reasoned_inference: { label: "推断", badge: "badge-info" },
  design_assumption: { label: "设计假设", badge: "badge-warn" },
  insufficient_evidence: { label: "证据不足", badge: "badge-failed" },
};

export const ANSWER_MODE_META: Record<AnswerMode, string> = {
  explanation: "解释说明",
  issue_detected: "发现定义缺口",
  change_request: "修改请求",
};

/** Maps a free-form severity string to a design-system badge class. */
export function severityBadge(severity: string): string {
  const value = severity.toLowerCase();
  if (["high", "critical", "高", "严重", "critical"].some((token) => value.includes(token))) {
    return "badge-failed";
  }
  if (["low", "低", "minor"].some((token) => value.includes(token))) {
    return "badge-completed";
  }
  return "badge-warn";
}

export const CATEGORY_META: Record<QuestionCategory, string> = {
  technology: "技术",
  privacy: "隐私",
  competition: "竞品",
  business: "商业",
  ecosystem: "生态",
  user_experience: "用户体验",
  general: "综合",
};

export const DEFINITION_STATUS_META: Record<DefinitionStatus, Meta> = {
  draft: { label: "草稿 Draft", badge: "badge-pending" },
  under_review: { label: "审查中 Under Review", badge: "badge-warn" },
  validation_ready: { label: "验证准备完成", badge: "badge-completed" },
};

/** Human labels for the actions a user may take on a suggested change. */
export const DISPOSITION_META: Record<SuggestionDisposition, string> = {
  apply: "接受并修改章节",
  as_risk: "转为风险项",
  as_hypothesis: "转为验证假设",
  dismiss: "忽略",
};

export const RESOLUTION_META: Record<string, Meta> = {
  accepted: { label: "已接受", badge: "badge-completed" },
  converted_to_risk: { label: "已转为风险项", badge: "badge-info" },
  converted_to_hypothesis: { label: "已转为验证假设", badge: "badge-info" },
  addressed: { label: "已处理", badge: "badge-completed" },
  dismissed: { label: "已忽略", badge: "badge-pending" },
};

export interface SectionMeta {
  label: string;
  /** DOM id used for table-of-contents scroll targeting. */
  anchor: string;
}

/** Maps every backend ProductSpec section key to a label and a scroll anchor. */
export const SECTION_META: Record<string, SectionMeta> = {
  overview: { label: "产品概览", anchor: "sec-overview" },
  users_problem: { label: "核心用户与问题", anchor: "sec-users" },
  hardware: { label: "硬件架构", anchor: "sec-hardware" },
  ai: { label: "AI 能力与决策边界", anchor: "sec-ai" },
  capability_delta: { label: "与现有产品的能力差异", anchor: "sec-delta" },
  ecosystem: { label: "eufy 生态关系", anchor: "sec-ecosystem" },
  privacy: { label: "隐私原则", anchor: "sec-privacy" },
  regional: { label: "地区适配", anchor: "sec-regional" },
  competition: { label: "竞品与可防御差异", anchor: "sec-competition" },
  business: { label: "商业模式", anchor: "sec-business" },
  risks: { label: "风险与关键假设", anchor: "sec-risks" },
  assumptions: { label: "关键假设", anchor: "sec-assumptions" },
  validation: { label: "验证准备度", anchor: "sec-validation" },
};

/** Ordered table-of-contents entries for the Product Spec navigation column. */
export const TOC_SECTIONS: readonly string[] = [
  "overview",
  "users_problem",
  "hardware",
  "ai",
  "capability_delta",
  "ecosystem",
  "privacy",
  "regional",
  "competition",
  "business",
  "risks",
  "validation",
];

export function sectionLabel(section: string): string {
  return SECTION_META[section]?.label ?? section;
}

export interface ValidationLabStatus {
  title: string;
  description: string;
}

/**
 * The validation lab copy is derived purely from definition status. It never
 * reports pass rates, scores, or any fabricated validation outcome — the lab is
 * Coming Soon and produces nothing.
 */
export function validationLabStatus(status: DefinitionStatus | undefined): ValidationLabStatus {
  if (status === "validation_ready") {
    return {
      title: "产品定义已准备完成",
      description: "验证实验室即将上线，当前阶段不产生任何技术、商业、隐私或场景验证结果。",
    };
  }
  return {
    title: "完成产品定义后可进入验证阶段",
    description: "当前阶段仅生成标准产品定义，不产生任何验证结果。",
  };
}

/** A collision-resistant idempotency key (backend requires ≥ 8 chars). */
export function newIdempotencyKey(): string {
  const globalCrypto = typeof crypto !== "undefined" ? crypto : undefined;
  if (globalCrypto && typeof globalCrypto.randomUUID === "function") {
    return globalCrypto.randomUUID();
  }
  return `idem-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
