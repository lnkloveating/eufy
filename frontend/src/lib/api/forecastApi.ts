/** Typed wrappers around every backend endpoint the workbench uses. */

import type {
  AgentEvent,
  Artifact,
  ForecastOptions,
  ForecastRequest,
  ForecastResult,
  ForecastRun,
  HealthResponse,
  KnowledgeCoverage,
  ProductSelectionRequest,
  ProductSpec,
  RetrievalPreview,
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

export function createForecastRun(body: ForecastRequest): Promise<ForecastRun> {
  return request<ForecastRun>("/forecast-runs", { method: "POST", body });
}

export function getForecastRun(runId: string, signal?: AbortSignal): Promise<ForecastRun> {
  return request<ForecastRun>(`/forecast-runs/${encodeURIComponent(runId)}`, { signal });
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
