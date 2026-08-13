import { describe, expect, it } from "vitest";
import type { ProductCandidate, RankedCandidate } from "../src/types/api";
import {
  findCandidate,
  isCandidateSelectable,
  orderForDisplay,
  topCandidate,
} from "../src/lib/candidates";

function candidate(id: string, name: string): ProductCandidate {
  return {
    id,
    name,
    tagline: `${name} tagline`,
    opportunity_ids: ["OPP-001"],
    target_users: ["Households"],
    target_regions: ["United States"],
    core_problem: "core",
    value_proposition: "value",
    form_factor: "device",
    hardware_components: ["sensor"],
    ai_native_mechanism: "on-device model",
    key_scenarios: ["scenario"],
    differentiators: ["diff"],
    estimated_price_range: "$199",
    technical_dependencies: ["dep"],
    key_assumptions: ["assume"],
    kill_criteria: ["kill"],
    evidence_ids: ["EVID-001"],
    regional_fit: [],
    competitive_positioning: {
      closest_alternatives: ["Ring"],
      borrowed_patterns: ["local hub"],
      defensible_differences: ["cross-sensor prediction"],
      non_copycat_rationale: "Different outcome",
      copycat_risks: ["incumbent response"],
      competitor_evidence_ids: ["COMP-RING-001"],
      validation_questions: ["Does it reduce incidents?"],
    },
  };
}

function ranked(id: string, rank: number, weighted: number): RankedCandidate {
  return {
    candidate: candidate(id, `Candidate ${id}`),
    reviews: [],
    dimension_scores: { innovation: weighted },
    weighted_score: weighted,
    rank,
  };
}

describe("candidate display ordering", () => {
  it("orders by backend rank without changing any rank value", () => {
    const backend = [ranked("C", 3, 60), ranked("A", 1, 90), ranked("B", 2, 75)];
    const displayed = orderForDisplay(backend);

    // Display order follows rank ascending.
    expect(displayed.map((item) => item.candidate.id)).toEqual(["A", "B", "C"]);
    // Backend rank values are preserved exactly.
    expect(displayed.map((item) => item.rank)).toEqual([1, 2, 3]);
  });

  it("does not mutate the input array", () => {
    const backend = [ranked("C", 3, 60), ranked("A", 1, 90)];
    const snapshot = backend.map((item) => item.candidate.id);
    orderForDisplay(backend);
    expect(backend.map((item) => item.candidate.id)).toEqual(snapshot);
  });

  it("identifies the top-ranked candidate (rank 1)", () => {
    const backend = [ranked("C", 3, 60), ranked("A", 1, 90), ranked("B", 2, 75)];
    expect(topCandidate(backend)?.candidate.id).toBe("A");
  });
});

describe("candidate selectability", () => {
  it("allows selecting any candidate, including the lowest-ranked", () => {
    const last = ranked("Z", 6, 40);
    expect(isCandidateSelectable(last)).toBe(true);
  });

  it("finds a candidate by id regardless of rank", () => {
    const backend = [ranked("C", 3, 60), ranked("A", 1, 90), ranked("B", 2, 75)];
    expect(findCandidate(backend, "C")?.rank).toBe(3);
    expect(findCandidate(backend, "missing")).toBeUndefined();
  });
});
