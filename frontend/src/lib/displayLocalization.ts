import type { ProductSpec, RankedCandidate } from "../types/api";

export type DisplayTextContext =
  | "general"
  | "summary"
  | "problem"
  | "value"
  | "form"
  | "hardware"
  | "ai"
  | "privacy"
  | "user"
  | "journey"
  | "business";

const REGION_LABELS: Record<string, string> = {
  China: "中国",
  "United States": "美国",
  "European Union": "欧盟",
  Germany: "德国",
  Canada: "加拿大",
  Australia: "澳大利亚",
  "United Kingdom": "英国",
  Japan: "日本",
  Singapore: "新加坡",
  India: "印度",
  France: "法国",
};

const EXACT_LABELS: Record<string, string> = {
  Security: "安防",
  "eufy Security": "eufy 安防",
  technical: "技术",
  technology: "技术",
  privacy: "隐私",
  business: "商业",
  commercial: "商业",
  user_scenario: "用户场景",
  "One-time hardware sale": "一次性硬件销售",
  "Optional subscription": "可选订阅服务",
  "No mandatory subscription": "无强制订阅",
  Households: "家庭用户",
  Families: "家庭用户",
  "Apartment dwellers": "公寓住户",
  "Privacy-conscious households": "注重隐私的家庭",
  "Families with children or older adults": "有儿童或老年人的家庭",
  "Households with elderly members at risk of falls": "有跌倒风险老年成员的家庭",
  "Local processing by default": "默认本地处理",
  "All processing local by default": "所有处理默认在本地完成",
  "No mandatory cloud upload": "不强制上传云端",
  "Physical privacy switch for user control": "通过物理隐私开关保障用户控制权",
  "Local processing and storage only": "仅在本地处理和存储",
};

const SEVERITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
  info: "提示",
  warning: "警告",
};

export const INNOVATION_VECTOR_LABELS: Record<string, string> = {
  new_sensing: "新型感知方式",
  proactive_intervention: "主动干预",
  distributed_architecture: "分布式架构",
  resilience_recovery: "韧性与恢复",
  trust_privacy: "信任与隐私",
  human_ai_coordination: "人与 AI 协同",
  new_business_delivery: "新商业交付方式",
};

const ENGLISH_PRODUCT_NAMES: Record<string, string> = {
  new_sensing: "SenseNova",
  proactive_intervention: "GuardPilot",
  distributed_architecture: "MeshSentinel",
  resilience_recovery: "EverGuard",
  trust_privacy: "TrustHalo",
  human_ai_coordination: "AccordAI",
  new_business_delivery: "SecureFlex",
};

export function englishProductName(name: string, innovationVector?: string): string {
  const cleaned = name.trim();
  if (cleaned && !containsChinese(cleaned)) return cleaned;
  return ENGLISH_PRODUCT_NAMES[innovationVector ?? ""] ?? "Eufy Horizon";
}

export function localizeSeverity(value: string): string {
  return SEVERITY_LABELS[value.trim().toLowerCase()] ?? value;
}

const CONCEPTS: readonly { pattern: RegExp; label: string }[] = [
  { pattern: /secure element|crypto chip/i, label: "硬件安全元件" },
  { pattern: /privacy switch|physical switch|mechanical disconnect|privacy shutter/i, label: "物理隐私开关" },
  { pattern: /mmwave|millimeter-wave|radar/i, label: "毫米波雷达" },
  { pattern: /camera|image capture|visual/i, label: "摄像感知" },
  { pattern: /door\/?window|contact sensor/i, label: "门窗传感器" },
  { pattern: /pir|motion sensor|motion detection/i, label: "运动传感器" },
  { pattern: /temperature|humidity|environment/i, label: "环境传感器" },
  { pattern: /microphone|\bmic\b|acoustic|audio/i, label: "声学感知" },
  { pattern: /touchscreen|display|screen/i, label: "触摸显示屏" },
  { pattern: /speaker|siren|alarm/i, label: "声光提醒" },
  { pattern: /edge ai|on-device ai|\bnpu\b|edge processor|local ai/i, label: "端侧 AI" },
  { pattern: /local storage|\bemmc\b|\bssd\b|sd card/i, label: "本地存储" },
  { pattern: /homebase|gateway|security hub|\bhub\b/i, label: "家庭安全中枢" },
  { pattern: /thread|matter|wi-?fi|bluetooth|wireless|mesh/i, label: "本地无线连接" },
  { pattern: /battery|low-power/i, label: "低功耗电池" },
  { pattern: /fall detection|detect falls|possible fall/i, label: "跌倒检测" },
  { pattern: /presence/i, label: "存在感知" },
  { pattern: /unusual inactivity|anomaly|abnormal/i, label: "异常活动识别" },
  { pattern: /activity classification|activity detection/i, label: "活动分类" },
  { pattern: /natural-language|natural language|explanation/i, label: "自然语言解释" },
  { pattern: /differential privacy/i, label: "差分隐私" },
  { pattern: /data minimization|minimi[sz]ed/i, label: "数据最小化" },
  { pattern: /local processing|on-device|locally|never leaves the device/i, label: "本地处理" },
  { pattern: /user control|explicit user|user approval|user confirmation/i, label: "用户明确控制" },
  { pattern: /audit/i, label: "可审计记录" },
  { pattern: /cloud/i, label: "云端服务" },
  { pattern: /subscription/i, label: "订阅服务" },
  { pattern: /privacy/i, label: "隐私保护" },
  { pattern: /false alarm/i, label: "降低误报" },
  { pattern: /elderly|older adult/i, label: "老年人安全" },
  { pattern: /children/i, label: "儿童家庭" },
  { pattern: /apartment|multi-unit|renter/i, label: "城市公寓" },
];

function containsChinese(text: string): boolean {
  return /[\u3400-\u9fff]/.test(text);
}

function conceptsOf(text: string): string[] {
  return CONCEPTS.filter(({ pattern }) => pattern.test(text)).map(({ label }) => label);
}

function unique(items: string[], limit = 5): string[] {
  return [...new Set(items)].slice(0, limit);
}

export function localizeRegion(region: string): string {
  return REGION_LABELS[region.trim()] ?? region;
}

export function localizeGeneratedText(
  value: string | null | undefined,
  context: DisplayTextContext = "general",
): string {
  const text = value?.trim() ?? "";
  if (!text || text === "—") return text || "—";
  if (REGION_LABELS[text]) return REGION_LABELS[text];
  if (EXACT_LABELS[text]) return EXACT_LABELS[text];
  if (containsChinese(text)) return text;

  const concepts = unique(conceptsOf(text));
  const joined = concepts.join("、");

  if (context === "hardware") return joined || "产品专用硬件模块";
  if (context === "ai") return joined ? `${joined}能力` : "端侧智能分析能力";
  if (context === "privacy") {
    return joined ? `遵循${joined}原则` : "遵循隐私优先和用户可控原则";
  }
  if (context === "user") {
    return joined || "需要家庭安全与隐私保护的用户";
  }
  if (context === "form") {
    const placement = /wall|ceiling/i.test(text)
      ? "壁挂或吸顶式"
      : /desktop/i.test(text)
        ? "桌面式"
        : /wearable|wrist/i.test(text)
          ? "可穿戴式"
          : "家用";
    return `${placement}${joined || "智能安防设备"}`;
  }
  if (context === "problem") {
    return joined
      ? `解决家庭场景中与${joined}相关的安全、隐私和使用信任问题。`
      : "解决家庭安防中的隐私、可靠性和使用信任问题。";
  }
  if (context === "value") {
    return joined
      ? `通过${joined}，提供更可靠、更透明且由用户掌控的家庭安全体验。`
      : "提供更可靠、更透明且由用户掌控的家庭安全体验。";
  }
  if (context === "summary") {
    return joined
      ? `一款以${joined}为核心的 AI 原生家庭安防产品。`
      : "一款强调隐私保护、可靠感知与用户控制的 AI 原生家庭安防产品。";
  }
  if (context === "journey") {
    return joined ? `用户通过${joined}完成设备配置、查看事件并处理提醒。` : "用户完成设备配置后，可查看事件并处理安全提醒。";
  }
  if (context === "business") {
    return joined ? `围绕${joined}形成硬件与可选服务收入。` : "以硬件销售为主，并提供可选增值服务。";
  }

  return joined ? `围绕${joined}的产品设计与验证要求。` : "当前产品定义中的设计说明与后续验证要求。";
}

function localizeList(items: string[], context: DisplayTextContext): string[] {
  return items.map((item) => localizeGeneratedText(item, context));
}

/**
 * Produces a presentation-only Chinese view of a ProductSpec. IDs, evidence,
 * lifecycle and all machine-readable enum values remain untouched.
 */
export function localizeProductSpecForDisplay(source: ProductSpec): ProductSpec {
  return {
    ...source,
    name: englishProductName(source.name, source.capability_delta?.innovation_vector),
    one_sentence_definition: localizeGeneratedText(source.one_sentence_definition, "summary"),
    category: localizeGeneratedText(source.category, "general"),
    target_users: localizeList(source.target_users, "user"),
    target_regions: source.target_regions.map(localizeRegion),
    core_problem: localizeGeneratedText(source.core_problem, "problem"),
    value_proposition: localizeGeneratedText(source.value_proposition, "value"),
    form_factor: localizeGeneratedText(source.form_factor, "form"),
    hardware_architecture: localizeList(source.hardware_architecture, "hardware"),
    ai_capabilities: localizeList(source.ai_capabilities, "ai"),
    ai_decision_boundary: localizeGeneratedText(source.ai_decision_boundary, "privacy"),
    user_journeys: localizeList(source.user_journeys, "journey"),
    privacy_principles: localizeList(source.privacy_principles, "privacy"),
    business_model: {
      ...source.business_model,
      hardware_revenue: localizeGeneratedText(source.business_model.hardware_revenue, "business"),
      recurring_revenue: source.business_model.recurring_revenue
        ? localizeGeneratedText(source.business_model.recurring_revenue, "business")
        : null,
      cost_drivers: localizeList(source.business_model.cost_drivers, "hardware"),
    },
    risks: source.risks.map((risk) => ({
      ...risk,
      category: localizeGeneratedText(risk.category),
      risk: localizeGeneratedText(risk.risk, "problem"),
      mitigation: localizeGeneratedText(risk.mitigation),
    })),
    key_assumptions: localizeList(source.key_assumptions, "general"),
    kill_criteria: localizeList(source.kill_criteria, "general"),
    validation_readiness: source.validation_readiness.map((item) => ({
      ...item,
      assumption: localizeGeneratedText(item.assumption, "general"),
      metric: localizeGeneratedText(item.metric, "general"),
      proposed_method: localizeGeneratedText(item.proposed_method, "general"),
      pass_condition: localizeGeneratedText(item.pass_condition, "general"),
      kill_condition: localizeGeneratedText(item.kill_condition, "general"),
    })),
    regional_fit: source.regional_fit.map((fit) => ({
      ...fit,
      region: localizeRegion(fit.region),
      fit_reasons: localizeList(fit.fit_reasons, "general"),
      required_adaptations: localizeList(fit.required_adaptations, "general"),
    })),
    competitive_positioning: {
      ...source.competitive_positioning,
      defensible_differences: localizeList(source.competitive_positioning.defensible_differences, "value"),
      non_copycat_rationale: localizeGeneratedText(source.competitive_positioning.non_copycat_rationale, "general"),
      copycat_risks: localizeList(source.competitive_positioning.copycat_risks, "problem"),
      validation_questions: localizeList(source.competitive_positioning.validation_questions, "general"),
    },
    capability_delta: source.capability_delta
      ? {
          ...source.capability_delta,
          today_equivalents: localizeList(source.capability_delta.today_equivalents, "general"),
          new_capabilities: localizeList(source.capability_delta.new_capabilities, "ai"),
          why_not_available_today: localizeGeneratedText(source.capability_delta.why_not_available_today, "problem"),
          enabling_changes: localizeList(source.capability_delta.enabling_changes, "general"),
          proof_needed: localizeList(source.capability_delta.proof_needed, "general"),
          hardware_or_system_delta: localizeGeneratedText(source.capability_delta.hardware_or_system_delta, "hardware"),
        }
      : undefined,
    human_selection_reason: source.human_selection_reason
      ? localizeGeneratedText(source.human_selection_reason)
      : null,
    last_change_reason: source.last_change_reason
      ? localizeGeneratedText(source.last_change_reason)
      : source.last_change_reason,
  };
}

export function localizeRankedCandidateForDisplay(source: RankedCandidate): RankedCandidate {
  const candidate = source.candidate;
  return {
    ...source,
    candidate: {
      ...candidate,
      name: englishProductName(candidate.name, candidate.capability_delta?.innovation_vector),
      tagline: localizeGeneratedText(candidate.tagline, "summary"),
      target_users: localizeList(candidate.target_users, "user"),
      target_regions: candidate.target_regions.map(localizeRegion),
      core_problem: localizeGeneratedText(candidate.core_problem, "problem"),
      value_proposition: localizeGeneratedText(candidate.value_proposition, "value"),
      form_factor: localizeGeneratedText(candidate.form_factor, "form"),
      hardware_components: localizeList(candidate.hardware_components, "hardware"),
      ai_native_mechanism: localizeGeneratedText(candidate.ai_native_mechanism, "ai"),
      key_scenarios: localizeList(candidate.key_scenarios, "journey"),
      differentiators: localizeList(candidate.differentiators, "value"),
      estimated_price_range: localizeGeneratedText(candidate.estimated_price_range, "business"),
      technical_dependencies: localizeList(candidate.technical_dependencies, "hardware"),
      key_assumptions: localizeList(candidate.key_assumptions, "general"),
      kill_criteria: localizeList(candidate.kill_criteria, "general"),
      regional_fit: candidate.regional_fit.map((fit) => ({
        ...fit,
        region: localizeRegion(fit.region),
        fit_reasons: localizeList(fit.fit_reasons, "general"),
        required_adaptations: localizeList(fit.required_adaptations, "general"),
      })),
      competitive_positioning: {
        ...candidate.competitive_positioning,
        borrowed_patterns: localizeList(candidate.competitive_positioning.borrowed_patterns, "general"),
        defensible_differences: localizeList(candidate.competitive_positioning.defensible_differences, "value"),
        non_copycat_rationale: localizeGeneratedText(candidate.competitive_positioning.non_copycat_rationale),
        copycat_risks: localizeList(candidate.competitive_positioning.copycat_risks, "problem"),
        validation_questions: localizeList(candidate.competitive_positioning.validation_questions, "general"),
      },
      strategy_alignment: candidate.strategy_alignment
        ? {
            ...candidate.strategy_alignment,
            rationale: localizeGeneratedText(candidate.strategy_alignment.rationale),
            tradeoffs: localizeList(candidate.strategy_alignment.tradeoffs, "problem"),
          }
        : undefined,
      capability_delta: candidate.capability_delta
        ? {
            ...candidate.capability_delta,
            today_equivalents: localizeList(candidate.capability_delta.today_equivalents, "general"),
            new_capabilities: localizeList(candidate.capability_delta.new_capabilities, "ai"),
            why_not_available_today: localizeGeneratedText(candidate.capability_delta.why_not_available_today, "problem"),
            enabling_changes: localizeList(candidate.capability_delta.enabling_changes, "general"),
            proof_needed: localizeList(candidate.capability_delta.proof_needed, "general"),
            hardware_or_system_delta: localizeGeneratedText(candidate.capability_delta.hardware_or_system_delta, "hardware"),
          }
        : undefined,
    },
    reviews: source.reviews.map((review) => ({
      ...review,
      strengths: localizeList(review.strengths, "value"),
      concerns: localizeList(review.concerns, "problem"),
      decisive_question: localizeGeneratedText(review.decisive_question),
    })),
  };
}

export const DIGITAL_TWIN_COMPONENT_LABELS: Record<string, string> = {
  camera: "摄像头",
  radar: "毫米波雷达",
  motion: "运动传感器",
  contact: "门窗传感器",
  acoustic: "声学传感器",
  environmental: "环境传感器",
  edge_ai: "端侧 AI",
  secure_element: "硬件安全元件",
  local_storage: "本地存储",
  privacy_switch: "物理隐私开关",
  display: "显示屏",
  speaker: "扬声器",
  microphone: "麦克风",
  siren: "警报器",
  wireless: "无线连接",
  battery: "电池",
  homebase: "家庭安全中枢",
};
