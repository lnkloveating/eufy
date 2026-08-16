/** Typed wrappers around every backend endpoint the workbench uses. */

import type {
  AgentEvent,
  Artifact,
  ForecastOptions,
  ForecastRequest,
  ForecastRunListResponse,
  ForecastResult,
  ForecastRun,
  FeishuSyncResult,
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
  RunProductDefinitionState,
  RetrievalPreview,
  SendBackResponse,
  SurveyAccess,
  SurveyResults,
  SurveySubmissionRequest,
  SurveySubmissionResult,
  SuggestionDismissRequest,
  ValidationEvent,
  ValidationProject,
  ValidationProjectCreateRequest,
  ValidationVisualSummary,
} from "../../types/api";
import { ApiError, request } from "./client";

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

export function getRunProductDefinitionState(
  runId: string,
  signal?: AbortSignal,
): Promise<RunProductDefinitionState> {
  return request<RunProductDefinitionState>(
    `/forecast-runs/${encodeURIComponent(runId)}/product-definition-state`,
    { signal },
  );
}

export function listForecastRuns(
  limit = 3,
  signal?: AbortSignal,
): Promise<ForecastRunListResponse> {
  return request<ForecastRunListResponse>(`/forecast-runs/recent?limit=${limit}`, { signal }).catch(
    (error: unknown) => {
      if (error instanceof ApiError && (error.status === 404 || error.status === 405)) {
        return request<ForecastRunListResponse>(`/forecast-runs?limit=${limit}`, { signal });
      }
      throw error;
    },
  );
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

/* ---------- Pre-validation lab ---------- */

export function createValidationProject(
  productId: string,
  body: ValidationProjectCreateRequest = {},
): Promise<ValidationProject> {
  return request<ValidationProject>(productPath(productId, "/validation-projects"), {
    method: "POST",
    body,
  });
}

export function getLatestValidationProject(
  productId: string,
  signal?: AbortSignal,
): Promise<ValidationProject> {
  return request<ValidationProject>(
    productPath(productId, "/validation-projects/latest"),
    { signal },
  );
}

export function getValidationProject(
  projectId: string,
  signal?: AbortSignal,
): Promise<ValidationProject> {
  return request<ValidationProject>(
    `/validation-projects/${encodeURIComponent(projectId)}`,
    { signal },
  );
}

export function runValidationProject(projectId: string): Promise<ValidationProject> {
  return request<ValidationProject>(
    `/validation-projects/${encodeURIComponent(projectId)}/run`,
    { method: "POST" },
  );
}

export function getValidationEvents(
  projectId: string,
  afterSequence = 0,
  signal?: AbortSignal,
): Promise<ValidationEvent[]> {
  return request<ValidationEvent[]>(
    `/validation-projects/${encodeURIComponent(projectId)}/events?after_sequence=${afterSequence}`,
    { signal },
  );
}

export function sendBackFinding(findingId: string): Promise<SendBackResponse> {
  return request<SendBackResponse>(
    `/validation-findings/${encodeURIComponent(findingId)}/send-back`,
    { method: "POST" },
  );
}

export function syncValidationReportToFeishu(
  projectId: string,
): Promise<FeishuSyncResult> {
  return request<FeishuSyncResult>(
    `/validation-projects/${encodeURIComponent(projectId)}/feishu-sync`,
    { method: "POST" },
  );
}

export function getValidationVisualSummary(
  projectId: string,
  signal?: AbortSignal,
): Promise<ValidationVisualSummary> {
  return request<ValidationVisualSummary>(
    `/validation-projects/${encodeURIComponent(projectId)}/visual-summary`,
    { signal },
  );
}

export function createValidationSurvey(projectId: string): Promise<SurveyAccess> {
  return request<SurveyAccess>(
    `/validation-projects/${encodeURIComponent(projectId)}/survey`,
    { method: "POST" },
  );
}

export function getValidationSurvey(
  projectId: string,
  signal?: AbortSignal,
): Promise<SurveyAccess> {
  return request<SurveyAccess>(
    `/validation-projects/${encodeURIComponent(projectId)}/survey`,
    { signal },
  );
}

export function getValidationSurveyResults(
  projectId: string,
  signal?: AbortSignal,
): Promise<SurveyResults> {
  return request<SurveyResults>(
    `/validation-projects/${encodeURIComponent(projectId)}/survey-results`,
    { signal },
  );
}

export function getPublicSurvey(
  token: string,
  signal?: AbortSignal,
): Promise<SurveyAccess> {
  return request<SurveyAccess>(`/surveys/${encodeURIComponent(token)}`, { signal });
}

export function submitSurveyResponse(
  token: string,
  body: SurveySubmissionRequest,
): Promise<SurveySubmissionResult> {
  return request<SurveySubmissionResult>(
    `/surveys/${encodeURIComponent(token)}/responses`,
    { method: "POST", body },
  );
}
