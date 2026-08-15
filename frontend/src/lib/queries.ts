/** React Query hooks wrapping the forecast API. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import type {
  ForecastOptions,
  ForecastRequest,
  ForecastRunListResponse,
  ForecastResult,
  ForecastRun,
  HealthResponse,
  Artifact,
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
  SendBackResponse,
  SuggestionDismissRequest,
  ValidationEvent,
  ValidationProject,
} from "../types/api";
import { ApiError } from "./api/client";
import {
  applyProductRevision,
  askProductQuestion,
  confirmProduct,
  createForecastRun,
  createSelection,
  createValidationProject,
  dismissDesignIssues,
  dismissSuggestions,
  generateIssueProposal,
  getForecastOptions,
  getForecastResult,
  getForecastRun,
  getHealth,
  getKnowledgeCoverage,
  getLatestValidationProject,
  getProduct,
  getProductQuestions,
  getProductReadiness,
  getProductRevisions,
  getRunArtifacts,
  getRunProductDefinitionState,
  getValidationEvents,
  getValidationProject,
  listForecastRuns,
  runValidationProject,
  sendBackFinding,
} from "./api/forecastApi";

export const queryKeys = {
  health: ["health"] as const,
  forecastOptions: ["forecast-options"] as const,
  recentRuns: (limit: number) => ["forecast-runs", "recent", limit] as const,
  run: (runId: string) => ["forecast-run", runId] as const,
  productDefinitionState: (runId: string) => ["product-definition-state", runId] as const,
  result: (runId: string) => ["forecast-result", runId] as const,
  product: (productId: string) => ["product", productId] as const,
  artifacts: (runId: string) => ["forecast-artifacts", runId] as const,
  coverage: (regions: string[]) => ["knowledge-coverage", ...regions] as const,
  productQuestions: (productId: string) => ["product-questions", productId] as const,
  productRevisions: (productId: string) => ["product-revisions", productId] as const,
  productReadiness: (productId: string) => ["product-readiness", productId] as const,
  latestValidationProject: (productId: string) =>
    ["validation-project", "latest", productId] as const,
  validationProject: (projectId: string) => ["validation-project", projectId] as const,
  validationEvents: (projectId: string) => ["validation-events", projectId] as const,
};

/** Health poll — refreshed periodically so connection status stays live. */
export function useHealth(): UseQueryResult<HealthResponse, ApiError> {
  return useQuery<HealthResponse, ApiError>({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 20_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
}

export function useForecastOptions(): UseQueryResult<ForecastOptions, ApiError> {
  return useQuery<ForecastOptions, ApiError>({
    queryKey: queryKeys.forecastOptions,
    queryFn: ({ signal }) => getForecastOptions(signal),
    staleTime: 5 * 60_000,
    retry: 1,
  });
}

export function useKnowledgeCoverage(
  regions: string[],
): UseQueryResult<KnowledgeCoverage, ApiError> {
  return useQuery<KnowledgeCoverage, ApiError>({
    queryKey: queryKeys.coverage(regions),
    queryFn: ({ signal }) => getKnowledgeCoverage(regions, signal),
    enabled: regions.length > 0,
    staleTime: 5 * 60_000,
  });
}

export interface CreateRunVariables {
  request: ForecastRequest;
  /** Client-supplied key so a double-click / retry creates at most one run. */
  idempotencyKey?: string;
}

export function useCreateRun() {
  return useMutation<ForecastRun, ApiError, CreateRunVariables>({
    mutationFn: ({ request, idempotencyKey }) =>
      createForecastRun(request, idempotencyKey),
  });
}

export function useRecentRuns(
  limit = 3,
): UseQueryResult<ForecastRunListResponse, ApiError> {
  return useQuery<ForecastRunListResponse, ApiError>({
    queryKey: queryKeys.recentRuns(limit),
    queryFn: ({ signal }) => listForecastRuns(limit, signal),
    staleTime: 30_000,
    retry: 1,
  });
}

const ACTIVE_STATUSES = new Set(["pending", "running"]);

/**
 * Poll a run while it is pending/running (every 2s — the task-polling fallback
 * required by the spec), and stop once it completes or fails.
 */
export function useRun(
  runId: string | undefined,
): UseQueryResult<ForecastRun, ApiError> {
  return useQuery<ForecastRun, ApiError>({
    queryKey: queryKeys.run(runId ?? "unknown"),
    queryFn: ({ signal }) => getForecastRun(runId as string, signal),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_STATUSES.has(status) ? 2000 : false;
    },
    // A 404 is a real "not found" — do not hammer it.
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

const ACTIVE_PRODUCT_DEFINITION_STATUSES = new Set(["researching", "generating"]);

export function useRunProductDefinitionState(
  runId: string | undefined,
): UseQueryResult<RunProductDefinitionState, ApiError> {
  return useQuery<RunProductDefinitionState, ApiError>({
    queryKey: queryKeys.productDefinitionState(runId ?? "unknown"),
    queryFn: ({ signal }) => getRunProductDefinitionState(runId as string, signal),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_PRODUCT_DEFINITION_STATUSES.has(status) ? 1500 : false;
    },
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

/**
 * Fetch the full result. Only enable once the run has completed to avoid the
 * backend's 409 "still processing" response.
 */
export function useRunResult(
  runId: string | undefined,
  enabled: boolean,
): UseQueryResult<ForecastResult, ApiError> {
  return useQuery<ForecastResult, ApiError>({
    queryKey: queryKeys.result(runId ?? "unknown"),
    queryFn: ({ signal }) => getForecastResult(runId as string, signal),
    enabled: Boolean(runId) && enabled,
    staleTime: 60_000,
    // If we ever race the completion flag, a 409 will resolve shortly.
    retry: (failureCount, error) => error.isResultNotReady && failureCount < 3,
    retryDelay: 1500,
  });
}

export function useRunArtifacts(
  runId: string | undefined,
  active: boolean,
): UseQueryResult<Artifact[], ApiError> {
  return useQuery<Artifact[], ApiError>({
    queryKey: queryKeys.artifacts(runId ?? "unknown"),
    queryFn: ({ signal }) => getRunArtifacts(runId as string, signal),
    enabled: Boolean(runId),
    refetchInterval: active ? 1500 : false,
    retry: 1,
  });
}

export function useCreateSelection(runId: string) {
  const queryClient = useQueryClient();
  return useMutation<ProductSpec, ApiError, ProductSelectionRequest>({
    mutationFn: (selection) => createSelection(runId, selection),
    onMutate: (selection) => {
      queryClient.setQueryData<RunProductDefinitionState>(
        queryKeys.productDefinitionState(runId),
        {
          run_id: runId,
          status: "generating",
          product_id: null,
          candidate_id: selection.candidate_id,
          error: null,
        },
      );
    },
    onSuccess: (product) => {
      queryClient.setQueryData(queryKeys.product(product.id), product);
      queryClient.setQueryData<RunProductDefinitionState>(
        queryKeys.productDefinitionState(runId),
        {
          run_id: runId,
          status: "ready",
          product_id: product.id,
          candidate_id: product.source_candidate_id,
          error: null,
        },
      );
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.productDefinitionState(runId) });
    },
  });
}

export function useProduct(
  productId: string | undefined,
): UseQueryResult<ProductSpec, ApiError> {
  return useQuery<ProductSpec, ApiError>({
    queryKey: queryKeys.product(productId ?? "unknown"),
    queryFn: ({ signal }) => getProduct(productId as string, signal),
    enabled: Boolean(productId),
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

/* ---------- Product Definition Workbench ---------- */

export function useProductQuestions(
  productId: string | undefined,
): UseQueryResult<ProductQuestionRecord[], ApiError> {
  return useQuery<ProductQuestionRecord[], ApiError>({
    queryKey: queryKeys.productQuestions(productId ?? "unknown"),
    queryFn: ({ signal }) => getProductQuestions(productId as string, signal),
    enabled: Boolean(productId),
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

export function useProductRevisions(
  productId: string | undefined,
): UseQueryResult<ProductRevision[], ApiError> {
  return useQuery<ProductRevision[], ApiError>({
    queryKey: queryKeys.productRevisions(productId ?? "unknown"),
    queryFn: ({ signal }) => getProductRevisions(productId as string, signal),
    enabled: Boolean(productId),
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

export function useProductReadiness(
  productId: string | undefined,
): UseQueryResult<ProductDefinitionReadiness, ApiError> {
  return useQuery<ProductDefinitionReadiness, ApiError>({
    queryKey: queryKeys.productReadiness(productId ?? "unknown"),
    queryFn: ({ signal }) => getProductReadiness(productId as string, signal),
    enabled: Boolean(productId),
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

/** Refresh product, questions, revisions and readiness after a workbench change. */
function useInvalidateWorkbench(productId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.product(productId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.productQuestions(productId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.productRevisions(productId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.productReadiness(productId) });
  };
}

export function useAskProductQuestion(productId: string) {
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductQuestionRecord, ApiError, ProductQuestionRequest>({
    mutationFn: (body) => askProductQuestion(productId, body),
    onSuccess: invalidate,
  });
}

export function useApplyProductRevision(productId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductSpec, ApiError, ProductRevisionRequest>({
    mutationFn: (body) => applyProductRevision(productId, body),
    onSuccess: (product) => {
      queryClient.setQueryData(queryKeys.product(product.id), product);
      invalidate();
    },
  });
}

export function useDismissSuggestions(productId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductDefinitionReadiness, ApiError, SuggestionDismissRequest>({
    mutationFn: (body) => dismissSuggestions(productId, body),
    onSuccess: (readiness) => {
      queryClient.setQueryData(queryKeys.productReadiness(productId), readiness);
      invalidate();
    },
  });
}

export function useGenerateIssueProposal(productId: string) {
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductQuestionRecord, ApiError, string>({
    mutationFn: (questionId) => generateIssueProposal(productId, questionId),
    onSuccess: invalidate,
  });
}

export function useDismissDesignIssues(productId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductDefinitionReadiness, ApiError, IssueDismissRequest>({
    mutationFn: (body) => dismissDesignIssues(productId, body),
    onSuccess: (readiness) => {
      queryClient.setQueryData(queryKeys.productReadiness(productId), readiness);
      invalidate();
    },
  });
}

export function useConfirmProduct(productId: string) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateWorkbench(productId);
  return useMutation<ProductSpec, ApiError, void>({
    mutationFn: () => confirmProduct(productId),
    onSuccess: (product) => {
      queryClient.setQueryData(queryKeys.product(product.id), product);
      invalidate();
    },
  });
}

/* ---------- Pre-validation lab ---------- */

const ACTIVE_VALIDATION_STATUSES = new Set(["running"]);

/**
 * Fetch the latest validation project for a product. A 404 means "no project
 * yet" and is surfaced (not retried) so the page can auto-create one.
 */
export function useLatestValidationProject(
  productId: string | undefined,
): UseQueryResult<ValidationProject, ApiError> {
  return useQuery<ValidationProject, ApiError>({
    queryKey: queryKeys.latestValidationProject(productId ?? "unknown"),
    queryFn: ({ signal }) => getLatestValidationProject(productId as string, signal),
    enabled: Boolean(productId),
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_VALIDATION_STATUSES.has(status) ? 1500 : false;
    },
  });
}

/** Poll a specific project while it is running; stop once terminal. */
export function useValidationProject(
  projectId: string | undefined,
): UseQueryResult<ValidationProject, ApiError> {
  return useQuery<ValidationProject, ApiError>({
    queryKey: queryKeys.validationProject(projectId ?? "unknown"),
    queryFn: ({ signal }) => getValidationProject(projectId as string, signal),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ACTIVE_VALIDATION_STATUSES.has(status) ? 1500 : false;
    },
    retry: (failureCount, error) => !error.isNotFound && failureCount < 2,
  });
}

/** Bounded polling of the validation activity stream while the run is active. */
export function useValidationEvents(
  projectId: string | undefined,
  active: boolean,
): UseQueryResult<ValidationEvent[], ApiError> {
  return useQuery<ValidationEvent[], ApiError>({
    queryKey: queryKeys.validationEvents(projectId ?? "unknown"),
    queryFn: ({ signal }) => getValidationEvents(projectId as string, 0, signal),
    enabled: Boolean(projectId),
    refetchInterval: active ? 1500 : false,
    retry: 1,
  });
}

export function useCreateValidationProject(productId: string) {
  const queryClient = useQueryClient();
  return useMutation<ValidationProject, ApiError, void>({
    mutationFn: () => createValidationProject(productId),
    onSuccess: (project) => {
      queryClient.setQueryData(queryKeys.latestValidationProject(productId), project);
      queryClient.setQueryData(queryKeys.validationProject(project.id), project);
    },
  });
}

export function useRunValidationProject(productId: string, projectId: string) {
  const queryClient = useQueryClient();
  return useMutation<ValidationProject, ApiError, void>({
    mutationFn: () => runValidationProject(projectId),
    onSuccess: (project) => {
      queryClient.setQueryData(queryKeys.validationProject(project.id), project);
      queryClient.setQueryData(queryKeys.latestValidationProject(productId), project);
      void queryClient.invalidateQueries({ queryKey: queryKeys.validationEvents(project.id) });
    },
  });
}

export function useSendBackFinding(productId: string, projectId: string) {
  const queryClient = useQueryClient();
  return useMutation<SendBackResponse, ApiError, string>({
    mutationFn: (findingId) => sendBackFinding(findingId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.validationProject(projectId) });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.latestValidationProject(productId),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.productQuestions(productId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.productReadiness(productId) });
    },
  });
}
