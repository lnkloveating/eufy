import { describe, expect, it } from "vitest";

import {
  DIGITAL_TWIN_COMPONENT_LABELS,
  englishProductName,
  localizeGeneratedText,
  localizeProductSpecForDisplay,
  localizeRegion,
} from "../src/lib/displayLocalization";
import type { ProductSpec } from "../src/types/api";

function englishSpec(): ProductSpec {
  return {
    id: "product-en",
    source_run_id: "run-en",
    source_candidate_id: "candidate-en",
    version: "1.0",
    name: "PrivacyGuard",
    one_sentence_definition:
      "A privacy-first home security hub with local AI and a physical privacy switch.",
    category: "Security",
    target_users: ["Privacy-conscious households"],
    target_regions: ["United States", "European Union"],
    core_problem: "Indoor cameras raise privacy concerns for elderly households.",
    value_proposition: "Local processing and radar reduce privacy risk and false alarms.",
    form_factor: "A compact wall-mounted radar sensor puck.",
    hardware_architecture: ["mmWave radar sensor", "Edge AI module", "Physical privacy switch"],
    ai_capabilities: ["On-device activity classification and fall detection"],
    ai_decision_boundary: "High-impact actions require explicit user confirmation.",
    user_journeys: ["Install the device and review alerts in the app"],
    ecosystem_relationships: ["HomeBase", "eufy app"],
    privacy_principles: ["Data minimization and local processing by default"],
    business_model: {
      hardware_revenue: "One-time hardware sale",
      recurring_revenue: null,
      ecosystem_pull_through: ["HomeBase"],
      cost_drivers: ["Radar sensor"],
    },
    risks: [
      {
        category: "technical",
        risk: "False alarm risk",
        mitigation: "Validate with a real user study",
        severity: "high",
      },
    ],
    key_assumptions: ["Users value local processing"],
    kill_criteria: ["False alarm rate is unacceptable"],
    evidence_ids: ["EV-001"],
    validation_readiness: [],
    regional_fit: [],
    competitive_positioning: {
      closest_alternatives: ["Ring"],
      borrowed_patterns: [],
      defensible_differences: ["Physical privacy switch and local processing"],
      non_copycat_rationale: "The hardware privacy boundary is different.",
      copycat_risks: [],
      competitor_evidence_ids: [],
      validation_questions: [],
    },
    human_selection_reason: null,
    definition_status: "validation_ready",
    created_at: "2026-08-16T00:00:00Z",
  };
}

describe("Chinese display localization", () => {
  it("localizes stable regions and component labels", () => {
    expect(localizeRegion("United States")).toBe("美国");
    expect(localizeRegion("European Union")).toBe("欧盟");
    expect(DIGITAL_TWIN_COMPONENT_LABELS.privacy_switch).toBe("物理隐私开关");
  });

  it("does not rewrite already-Chinese content", () => {
    expect(localizeGeneratedText("默认在本地处理", "privacy")).toBe("默认在本地处理");
  });

  it("keeps English product names and replaces historical Chinese names", () => {
    expect(englishProductName("SenseNova", "new_sensing")).toBe("SenseNova");
    expect(englishProductName("智衡", "human_ai_coordination")).toBe("AccordAI");
  });

  it("turns historical English descriptions into readable Chinese summaries", () => {
    const localized = localizeProductSpecForDisplay(englishSpec());

    expect(localized.name).toBe("PrivacyGuard");
    expect(localized.one_sentence_definition).toMatch(/[\u3400-\u9fff]/);
    expect(localized.one_sentence_definition).not.toContain("privacy-first");
    expect(localized.target_regions).toEqual(["美国", "欧盟"]);
    expect(localized.form_factor).toContain("毫米波雷达");
    expect(localized.hardware_architecture.join("、")).toContain("物理隐私开关");
    expect(localized.ai_capabilities[0]).toContain("跌倒检测");
  });
});
