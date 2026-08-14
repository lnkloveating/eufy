/** Typed wrappers around every backend endpoint the workbench uses. */

import type {
  AgentEvent,
  Artifact,
  ForecastOptions,
  ForecastRequest,
  ForecastRunListResponse,
  ForecastResult,
  ForecastRun,
  HealthResponse,
  IssueDismissRequest,
  KnowledgeCoverage,
  ProductDefinitionReadiness,
  ProductQuestionRecord,
  ProductQuestionRequest,
  ProductRevision,
  ProductRevisionRequest,
  ProductSelectionRequest,
  ProductSpec,
  RetrievalPreview,
  SuggestionDismissRequest,
} from "../../types/api";
import { request } from "./client";

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function getForecastOptions(signal?: AbortSignal): Promise<ForecastOptions> {
  return request<ForecastOptions>("/forecast-options", { signal });
}

export function getKnowledgeCoverage(
  regions: string[] = [],
  signal?: AbortSignal,
): Promise<KnowledgeCoverage> {
  const query = regions.map((region) => `regions=${encodeURIComponent(region)}`).join("&");
  return request<KnowledgeCoverage>(`/knowledge/coverage${query ? `?${query}` : ""}`, {
    signal,
  });
}

export function previewRetrieval(
  body: ForecastRequest,
): Promise<RetrievalPreview> {
  return request<RetrievalPreview>("/knowledge/retrieval-preview", {
    method: "POST",
    body,
  });
}

export function createForecastRun(
  body: ForecastRequest,
  idempotencyKey?: string,
): Promise<ForecastRun> {
  return request<ForecastRun>("/forecast-runs", {
    method: "POST",
    body,
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

export function getForecastRun(runId: string, signal?: AbortSignal): Promise<ForecastRun> {
  return request<ForecastRun>(`/forecast-runs/${encodeURIComponent(runId)}`, { signal });
}

export function listForecastRuns(
  limit = 3,
  signal?: AbortSignal,
): Promise<ForecastRunListResponse> {
  return request<ForecastRunListResponse>(`/forecast-runs?limit=${limit}`, { signal });
}

export function getForecastResult(
  runId: string,
  signal?: AbortSignal,
): Promise<ForecastResult> {
  return request<ForecastResult>(
    `/forecast-runs/${encodeURIComponent(runId)}/result`,
    { signal },
  );
}

export function getRunEvents(
  runId: string,
  afterSequence = 0,
  signal?: AbortSignal,
): Promise<AgentEvent[]> {
  return request<AgentEvent[]>(
    `/forecast-runs/${encodeURIComponent(runId)}/events?after_sequence=${afterSequence}`,
    { signal },
  );
}

export function getRunArtifacts(
  runId: string,
  signal?: AbortSignal,
): Promise<Artifact[]> {
  return request<Artifact[]>(
    `/forecast-runs/${encodeURIComponent(runId)}/artifacts`,
    { signal },
  );
}

export function createSelection(
  runId: string,
  body: ProductSelectionRequest,
): Promise<ProductSpec> {
  return request<ProductSpec>(
    `/forecast-runs/${encodeURIComponent(runId)}/selections`,
    { method: "POST", body },
  );
}

export function getProduct(productId: string, signal?: AbortSignal): Promise<ProductSpec> {
  return request<ProductSpec>(`/products/${encodeURIComponent(productId)}`, { signal });
}

function productPath(productId: string, suffix = ""): string {
  return `/products/${encodeURIComponent(productId)}${suffix}`;
}

export function askProductQuestion(
  productId: string,
  body: ProductQuestionRequest,
): Promise<ProductQuestionRecord> {
  return request<ProductQuestionRecord>(productPath(productId, "/questions"), {
    method: "POST",
    body,
  });
}

export function getProductQuestions(
  productId: string,
  signal?: AbortSignal,
): Promise<ProductQuestionRecord[]> {
  return request<ProductQuestionRecord[]>(productPath(productId, "/questions"), { signal });
}

export function getProductRevisions(
  productId: string,
  signal?: AbortSignal,
): Promise<ProductRevision[]> {
  return request<ProductRevision[]>(productPath(productId, "/revisions"), { signal });
}

export function generateIssueProposal(
  productId: string,
  questionId: string,
): Promise<ProductQuestionRecord> {
  return request<ProductQuestionRecord>(
    productPath(productId, `/questions/${encodeURIComponent(questionId)}/proposal`),
    { method: "POST" },
  );
}

export function dismissDesignIssues(
  productId: string,
  body: IssueDismissRequest,
): Promise<ProductDefinitionReadiness> {
  return request<ProductDefinitionReadiness>(productPath(productId, "/issues/dismiss"), {
    method: "POST",
    body,
  });
}

export function applyProductRevision(
  productId: string,
  body: ProductRevisionRequest,
): Promise<ProductSpec> {
  return request<ProductSpec>(productPath(productId, "/revisions"), { method: "POST", body });
}

export function dismissSuggestions(
  productId: string,
  body: SuggestionDismissRequest,
): Promise<ProductDefinitionReadiness> {
  return request<ProductDefinitionReadiness>(productPath(productId, "/suggestions/dismiss"), {
    method: "POST",
    body,
  });
}

export function getProductReadiness(
  productId: string,
  signal?: AbortSignal,
): Promise<ProductDefinitionReadiness> {
  return request<ProductDefinitionReadiness>(productPath(productId, "/readiness"), { signal });
}

export function confirmProduct(productId: string): Promise<ProductSpec> {
  return request<ProductSpec>(productPath(productId, "/confirm"), { method: "POST" });
}
