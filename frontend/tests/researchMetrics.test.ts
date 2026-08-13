import { describe, expect, it } from "vitest";
import type { Artifact } from "../src/types/api";
import {
  aggregateArtifactMetrics,
  dedupeArtifacts,
  deriveLedgerCounts,
} from "../src/features/forecast-run/researchMetrics";

function artifact(overrides: Partial<Artifact> & { id: string; kind: string }): Artifact {
  return {
    id: overrides.id,
    run_id: "run-1",
    kind: overrides.kind,
    producer: overrides.producer ?? "agent",
    payload: overrides.payload ?? null,
    model_name: overrides.model_name ?? null,
    prompt_version: overrides.prompt_version ?? null,
    duration_ms: overrides.duration_ms ?? null,
    input_tokens: overrides.input_tokens ?? null,
    output_tokens: overrides.output_tokens ?? null,
    created_at: overrides.created_at ?? "2026-08-13T10:00:00Z",
  };
}

describe("aggregateArtifactMetrics", () => {
  it("sums confirmed tokens and duration, ignoring nulls", () => {
    const metrics = aggregateArtifactMetrics([
      artifact({ id: "a1", kind: "lens_forecast:user_trends", input_tokens: 100, output_tokens: 200, duration_ms: 1500, model_name: "deepseek-chat" }),
      artifact({ id: "a2", kind: "opportunities", input_tokens: 50, output_tokens: null, duration_ms: 800, model_name: "deepseek-chat" }),
      artifact({ id: "a3", kind: "evidence" }), // no LLM metadata
    ]);
    expect(metrics.confirmedInputTokens).toBe(150);
    expect(metrics.confirmedOutputTokens).toBe(200);
    expect(metrics.totalTokens).toBe(350);
    expect(metrics.totalDurationMs).toBe(2300);
    expect(metrics.llmArtifactCount).toBe(2);
  });

  it("counts the same artifact id only once", () => {
    const dup = artifact({ id: "same", kind: "opportunities", input_tokens: 10, output_tokens: 20 });
    const metrics = aggregateArtifactMetrics([dup, { ...dup }, { ...dup }]);
    expect(metrics.confirmedInputTokens).toBe(10);
    expect(metrics.confirmedOutputTokens).toBe(20);
    expect(metrics.llmArtifactCount).toBe(1);
  });

  it("picks the most recent model_name by created_at", () => {
    const metrics = aggregateArtifactMetrics([
      artifact({ id: "a1", kind: "x", model_name: "old-model", created_at: "2026-08-13T10:00:00Z" }),
      artifact({ id: "a2", kind: "y", model_name: "new-model", created_at: "2026-08-13T10:05:00Z" }),
    ]);
    expect(metrics.modelName).toBe("new-model");
  });

  it("returns zeros for an empty artifact set", () => {
    const metrics = aggregateArtifactMetrics([]);
    expect(metrics.totalTokens).toBe(0);
    expect(metrics.totalDurationMs).toBe(0);
    expect(metrics.modelName).toBeNull();
  });
});

describe("dedupeArtifacts", () => {
  it("keeps one entry per id", () => {
    const list = [
      artifact({ id: "a", kind: "k1" }),
      artifact({ id: "a", kind: "k1-updated" }),
      artifact({ id: "b", kind: "k2" }),
    ];
    const unique = dedupeArtifacts(list);
    expect(unique).toHaveLength(2);
    expect(unique.find((a) => a.id === "a")?.kind).toBe("k1-updated");
  });
});

describe("deriveLedgerCounts", () => {
  it("counts evidence, competitors, opportunities, gaps, candidates and lens forecasts", () => {
    const counts = deriveLedgerCounts([
      artifact({
        id: "ev",
        kind: "evidence",
        payload: [
          { layer: "user_needs" },
          { layer: "technology" },
          { layer: "user_needs" },
        ],
      }),
      artifact({ id: "comp", kind: "competitor_evidence", payload: [{}, {}] }),
      artifact({ id: "opp", kind: "opportunities", payload: [{}, {}, {}] }),
      artifact({ id: "cand", kind: "raw_candidates", payload: [{}, {}] }),
      artifact({ id: "lf1", kind: "lens_forecast:user_trends" }),
      artifact({ id: "lf2", kind: "lens_forecast:market_futures" }),
      artifact({ id: "ca", kind: "competitive_analysis", payload: { gaps: [{}, {}, {}, {}] } }),
    ]);
    expect(counts.evidenceCount).toBe(3);
    expect(counts.knowledgeLayerCount).toBe(2);
    expect(counts.competitorCount).toBe(2);
    expect(counts.opportunityCount).toBe(3);
    expect(counts.candidateCount).toBe(2);
    expect(counts.forecastCount).toBe(2);
    expect(counts.gapCount).toBe(4);
  });

  it("is defensive when artifacts are missing or malformed", () => {
    const counts = deriveLedgerCounts([artifact({ id: "x", kind: "evidence", payload: "oops" })]);
    expect(counts.evidenceCount).toBe(0);
    expect(counts.gapCount).toBe(0);
  });
});
