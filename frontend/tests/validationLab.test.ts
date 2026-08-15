import { describe, expect, it } from "vitest";

import type {
  ExperimentType,
  ExperimentVerdict,
  FindingSeverity,
  ObservationSourceType,
  ValidationProjectStatus,
} from "../src/types/api";
import {
  EXPERIMENT_TYPE_META,
  PROJECT_STATUS_META,
  SEVERITY_META,
  SIMULATION_BOUNDARY,
  SOURCE_TYPE_META,
  VERDICT_META,
  feasibilityAssessment,
  feasibilityDimension,
  validationLabEntry,
  verdictLabel,
} from "../src/lib/validationLab";

function hypo(
  assumption: string,
  metric: string,
  experiment_type: ExperimentType,
  verdict: ExperimentVerdict,
) {
  return { assumption, metric, experiment_type, verdict };
}

const ALL_VERDICTS: ExperimentVerdict[] = [
  "not_run",
  "supported_in_simulation",
  "inconclusive",
  "contradicted",
  "requires_real_world_test",
];

describe("validationLabEntry", () => {
  it("disables the entry until the product is validation_ready", () => {
    for (const status of ["draft", "under_review", undefined] as const) {
      const entry = validationLabEntry("product-1", status);
      expect(entry.enabled).toBe(false);
      expect(entry.reason).toContain("请先完成产品定义");
    }
  });

  it("enables the entry and points at the lab when validation_ready", () => {
    const entry = validationLabEntry("product-1", "validation_ready");
    expect(entry.enabled).toBe(true);
    expect(entry.path).toBe("/products/product-1/validation");
  });

  it("encodes the product id in the path", () => {
    const entry = validationLabEntry("prod/with space", "validation_ready");
    expect(entry.path).toBe("/products/prod%2Fwith%20space/validation");
  });
});

describe("verdict copy", () => {
  it("uses the correct Chinese verdict labels", () => {
    expect(verdictLabel("supported_in_simulation")).toBe("模拟支持");
    expect(verdictLabel("inconclusive")).toBe("证据不足");
    expect(verdictLabel("contradicted")).toBe("出现反例");
    expect(verdictLabel("requires_real_world_test")).toBe("需真实测试");
    expect(verdictLabel("not_run")).toBe("未运行");
  });

  it("labels a positive result explicitly as simulation, not real validation", () => {
    const supported = VERDICT_META.supported_in_simulation;
    expect(supported.label).toContain("模拟");
    expect(supported.description).toContain("不代表真实");
    // A completed project is labelled as a simulation completion.
    expect(PROJECT_STATUS_META.completed.label).toContain("模拟");
  });

  it("has metadata for every verdict enum value", () => {
    for (const verdict of ALL_VERDICTS) {
      expect(VERDICT_META[verdict]).toBeDefined();
      expect(VERDICT_META[verdict].label.length).toBeGreaterThan(0);
    }
  });
});

describe("feasibility assessment names the gap dimension", () => {
  it("classifies a payment/pricing hypothesis as a business gap", () => {
    const input = hypo(
      "用户愿意为无中枢系统支付$149-$249",
      "付费意愿",
      "privacy_security", // even when the type is mis-labelled, text wins
      "requires_real_world_test",
    );
    expect(feasibilityDimension(input)).toBe("business");
    const assessment = feasibilityAssessment(input);
    expect(assessment.label).toBe("商业可行性");
    expect(assessment.reason).toMatch(/市场|付费/);
  });

  it("classifies a user-acceptance hypothesis as a user-research gap", () => {
    const input = hypo(
      "旁观者感知设计被用户接受",
      "接受度",
      "user_scenario",
      "requires_real_world_test",
    );
    expect(feasibilityDimension(input)).toBe("user");
    const assessment = feasibilityAssessment(input);
    expect(assessment.label).toBe("用户接受度");
    expect(assessment.reason).toContain("用户调研");
  });

  it("falls back to a technology gap for reliability/coverage claims", () => {
    const input = hypo(
      "网状网络在公寓环境中能提供可靠覆盖",
      "覆盖可靠性",
      "deterministic_simulation",
      "requires_real_world_test",
    );
    expect(feasibilityDimension(input)).toBe("technology");
    expect(feasibilityAssessment(input).reason).toMatch(/硬件|实测|技术/);
  });

  it("gives a positive read when supported in simulation, never claiming real validation", () => {
    const assessment = feasibilityAssessment(
      hypo("断网后仍能本地告警", "离线连续性", "technology", "supported_in_simulation"),
    );
    expect(assessment.reason).toContain("初步可行");
    expect(assessment.reason).not.toMatch(/通过|验证通过/);
  });

  it("never emits a percentage or pass rate in any reason", () => {
    const verdicts: ExperimentVerdict[] = [
      "supported_in_simulation",
      "requires_real_world_test",
      "inconclusive",
      "contradicted",
      "not_run",
    ];
    for (const verdict of verdicts) {
      const reason = feasibilityAssessment(hypo("成本可控，价格有竞争力", "成本", "business", verdict))
        .reason;
      expect(reason).not.toMatch(/%|通过率|准确率|成功率|接受率|\d+\s*%/);
    }
  });
});

describe("no fabricated statistics", () => {
  const FORBIDDEN = /%|通过率|准确率|成功率|接受率|\d+\s*(?:%|分)/;

  function collectLabels(): string[] {
    const labels: string[] = [SIMULATION_BOUNDARY];
    for (const verdict of ALL_VERDICTS) {
      labels.push(VERDICT_META[verdict].label, VERDICT_META[verdict].description);
    }
    (Object.keys(PROJECT_STATUS_META) as ValidationProjectStatus[]).forEach((key) =>
      labels.push(PROJECT_STATUS_META[key].label),
    );
    (Object.keys(SOURCE_TYPE_META) as ObservationSourceType[]).forEach((key) =>
      labels.push(SOURCE_TYPE_META[key].label),
    );
    (Object.keys(SEVERITY_META) as FindingSeverity[]).forEach((key) =>
      labels.push(SEVERITY_META[key].label),
    );
    (Object.keys(EXPERIMENT_TYPE_META) as ExperimentType[]).forEach((key) =>
      labels.push(EXPERIMENT_TYPE_META[key]),
    );
    return labels;
  }

  it("never renders a percentage, pass rate, or accuracy number", () => {
    for (const label of collectLabels()) {
      expect(label, `unexpected fake metric in: ${label}`).not.toMatch(FORBIDDEN);
    }
  });

  it("exposes the four evidence source types the UI must distinguish", () => {
    expect(SOURCE_TYPE_META.ai_analysis.label).toBe("AI 分析");
    expect(SOURCE_TYPE_META.deterministic_simulation.label).toBe("确定性模拟");
    expect(SOURCE_TYPE_META.existing_evidence.label).toBe("已有证据");
    expect(SOURCE_TYPE_META.human_observation.label).toBe("真实观察");
  });

  it("states the simulation boundary explicitly", () => {
    expect(SIMULATION_BOUNDARY).toContain("模拟");
    expect(SIMULATION_BOUNDARY).toContain("不代表真实");
  });
});
