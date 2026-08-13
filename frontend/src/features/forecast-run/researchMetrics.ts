/**
 * Deterministic Research Ledger metrics derived ONLY from real backend
 * artifacts. No time-based growth, no fabricated per-token streaming.
 *
 * Rules (per spec):
 *  - Aggregate over completed artifacts only.
 *  - The same artifact id is counted once (dedupe).
 *  - `null` token / duration values are ignored, never coerced to 0-with-weight.
 *  - Token/duration/model_name come exclusively from the artifact fields
 *    input_tokens / output_tokens / duration_ms / model_name.
 */

import type { Artifact } from "../../types/api";
import type {
  CompetitorRecord,
  EvidenceRecord,
  Opportunity,
  ProductCandidate,
} from "../../types/api";

export interface LedgerTokenMetrics {
  /** Number of distinct artifacts that reported any token/duration/model data. */
  llmArtifactCount: number;
  confirmedInputTokens: number;
  confirmedOutputTokens: number;
  totalTokens: number;
  totalDurationMs: number;
  /** Most recently used model name (latest by created_at), or null. */
  modelName: string | null;
}

/** Deduplicate artifacts by id, keeping the last occurrence for each id. */
export function dedupeArtifacts(artifacts: readonly Artifact[]): Artifact[] {
  const byId = new Map<string, Artifact>();
  for (const artifact of artifacts) {
    byId.set(artifact.id, artifact);
  }
  return [...byId.values()];
}

/**
 * Aggregate confirmed token + duration usage across artifacts. Only artifacts
 * that carry real LLM metadata contribute; `null` fields are skipped.
 */
export function aggregateArtifactMetrics(
  artifacts: readonly Artifact[],
): LedgerTokenMetrics {
  const unique = dedupeArtifacts(artifacts);

  let confirmedInputTokens = 0;
  let confirmedOutputTokens = 0;
  let totalDurationMs = 0;
  let llmArtifactCount = 0;
  let modelName: string | null = null;
  let modelAt = -Infinity;

  for (const artifact of unique) {
    const hasInput = typeof artifact.input_tokens === "number";
    const hasOutput = typeof artifact.output_tokens === "number";
    const hasDuration = typeof artifact.duration_ms === "number";
    const hasModel = typeof artifact.model_name === "string" && artifact.model_name.length > 0;

    if (hasInput) confirmedInputTokens += artifact.input_tokens as number;
    if (hasOutput) confirmedOutputTokens += artifact.output_tokens as number;
    if (hasDuration) totalDurationMs += artifact.duration_ms as number;

    if (hasInput || hasOutput || hasDuration || hasModel) {
      llmArtifactCount += 1;
    }

    if (hasModel) {
      const at = Date.parse(artifact.created_at);
      const ts = Number.isNaN(at) ? 0 : at;
      if (ts >= modelAt) {
        modelAt = ts;
        modelName = artifact.model_name as string;
      }
    }
  }

  return {
    llmArtifactCount,
    confirmedInputTokens,
    confirmedOutputTokens,
    totalTokens: confirmedInputTokens + confirmedOutputTokens,
    totalDurationMs,
    modelName,
  };
}

/** The latest payload for a given artifact kind (or exact kind match). */
function latestPayload<T>(artifacts: readonly Artifact[], kind: string): T | null {
  for (let i = artifacts.length - 1; i >= 0; i -= 1) {
    const artifact = artifacts[i];
    if (artifact && artifact.kind === kind) {
      return artifact.payload as T;
    }
  }
  return null;
}

function payloadArray<T>(artifacts: readonly Artifact[], kind: string): T[] {
  const payload = latestPayload<unknown>(artifacts, kind);
  return Array.isArray(payload) ? (payload as T[]) : [];
}

export interface LedgerCounts {
  evidenceCount: number;
  knowledgeLayerCount: number;
  competitorCount: number;
  forecastCount: number;
  opportunityCount: number;
  gapCount: number;
  candidateCount: number;
}

/** Domain counts derived from artifact payloads (defensive against missing data). */
export function deriveLedgerCounts(artifacts: readonly Artifact[]): LedgerCounts {
  const evidence = payloadArray<EvidenceRecord>(artifacts, "evidence");
  const competitors = payloadArray<CompetitorRecord>(artifacts, "competitor_evidence");
  const opportunities = payloadArray<Opportunity>(artifacts, "opportunities");
  const candidates = payloadArray<ProductCandidate>(artifacts, "raw_candidates");
  const forecastCount = dedupeArtifacts(artifacts).filter((artifact) =>
    artifact.kind.startsWith("lens_forecast:"),
  ).length;
  const analysis = latestPayload<{ gaps?: unknown[] }>(artifacts, "competitive_analysis");
  const layers = new Set(
    evidence
      .map((record) => record?.layer as string | undefined)
      .filter((layer): layer is string => typeof layer === "string"),
  );

  return {
    evidenceCount: evidence.length,
    knowledgeLayerCount: layers.size,
    competitorCount: competitors.length,
    forecastCount,
    opportunityCount: opportunities.length,
    gapCount: Array.isArray(analysis?.gaps) ? analysis.gaps.length : 0,
    candidateCount: candidates.length,
  };
}

/** Human-friendly duration formatting (ms → s). */
export function formatDurationMs(ms: number): string {
  if (ms <= 0) return "0s";
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}
