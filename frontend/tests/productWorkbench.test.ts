import { describe, expect, it } from "vitest";

import {
  ANSWER_MODE_META,
  CATEGORY_META,
  DEFINITION_STATUS_META,
  DISPOSITION_META,
  EPISTEMIC_STATUS_META,
  QUICK_QUESTIONS,
  RESOLUTION_META,
  SECTION_META,
  TOC_SECTIONS,
  newIdempotencyKey,
  sectionLabel,
  severityBadge,
  validationLabStatus,
} from "../src/lib/productWorkbench";
import type {
  AnswerMode,
  DefinitionStatus,
  EpistemicStatus,
  QuestionCategory,
} from "../src/types/api";

const ALL_STATUSES: EpistemicStatus[] = [
  "evidence_supported",
  "reasoned_inference",
  "design_assumption",
  "insufficient_evidence",
];

const ALL_CATEGORIES: QuestionCategory[] = [
  "technology",
  "privacy",
  "competition",
  "business",
  "ecosystem",
  "user_experience",
  "general",
];

describe("quick questions", () => {
  it("each quick prompt carries a real, non-empty question string", () => {
    expect(QUICK_QUESTIONS.length).toBeGreaterThan(4);
    for (const quick of QUICK_QUESTIONS) {
      expect(quick.label.trim().length).toBeGreaterThan(0);
      // The backend enforces question length >= 4; quick prompts must satisfy it.
      expect(quick.question.trim().length).toBeGreaterThanOrEqual(4);
    }
  });
});

describe("label maps stay complete", () => {
  it("labels every epistemic status", () => {
    for (const status of ALL_STATUSES) {
      expect(EPISTEMIC_STATUS_META[status].label.length).toBeGreaterThan(0);
      expect(EPISTEMIC_STATUS_META[status].badge.startsWith("badge-")).toBe(true);
    }
  });

  it("labels every question category", () => {
    for (const category of ALL_CATEGORIES) {
      expect(CATEGORY_META[category].length).toBeGreaterThan(0);
    }
  });

  it("labels every definition status and disposition", () => {
    const statuses: DefinitionStatus[] = ["draft", "under_review", "validation_ready"];
    for (const status of statuses) {
      expect(DEFINITION_STATUS_META[status].label.length).toBeGreaterThan(0);
    }
    for (const disposition of ["apply", "as_risk", "as_hypothesis", "dismiss"] as const) {
      expect(DISPOSITION_META[disposition].length).toBeGreaterThan(0);
    }
    expect(RESOLUTION_META.accepted?.label).toBe("已接受");
  });

  it("labels every answer mode and grades severities", () => {
    const modes: AnswerMode[] = ["explanation", "issue_detected", "change_request"];
    for (const mode of modes) {
      expect(ANSWER_MODE_META[mode].length).toBeGreaterThan(0);
    }
    expect(severityBadge("high")).toBe("badge-failed");
    expect(severityBadge("严重")).toBe("badge-failed");
    expect(severityBadge("low")).toBe("badge-completed");
    expect(severityBadge("medium")).toBe("badge-warn");
    expect(RESOLUTION_META.addressed?.label).toBe("已处理");
  });

  it("maps every table-of-contents section to a label and a scroll anchor", () => {
    for (const key of TOC_SECTIONS) {
      const meta = SECTION_META[key];
      expect(meta).toBeDefined();
      expect(meta?.anchor.startsWith("sec-")).toBe(true);
      expect(sectionLabel(key)).toBe(meta?.label);
    }
  });
});

describe("validation lab copy never fabricates results", () => {
  it("changes with definition status and reports no metrics or pass rates", () => {
    const ready = validationLabStatus("validation_ready");
    const notReady = validationLabStatus("draft");
    expect(ready.title).not.toEqual(notReady.title);
    for (const status of [ready, notReady]) {
      const text = `${status.title}${status.description}`;
      expect(text).not.toMatch(/%/);
      expect(text).not.toMatch(/通过率|pass rate/i);
    }
  });
});

describe("idempotency keys", () => {
  it("are unique and satisfy the backend minimum length", () => {
    const first = newIdempotencyKey();
    const second = newIdempotencyKey();
    expect(first.length).toBeGreaterThanOrEqual(8);
    expect(first).not.toEqual(second);
  });
});
