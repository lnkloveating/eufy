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
  ForecastResult,
  ForecastRun,
  HealthResponse,
  Artifact,
  KnowledgeCoverage,
  ProductSelectionRequest,
  ProductSpec,
} from "../types/api";
import { ApiError } from "./api/client";
import {
  createForecastRun,
  createSelection,
  getForecastOptions,
  getForecastResult,
  getForecastRun,
  getHealth,
  getKnowledgeCoverage,
  getProduct,
  getRunArtifacts,
} from "./api/forecastApi";

export const queryKeys = {
  health: ["health"] as const,
  forecastOptions: ["forecast-options"] as const,
  run: (runId: string) => ["forecast-run", runId] as const,
  result: (runId: string) => ["forecast-result", runId] as const,
  product: (productId: string) => ["product", productId] as const,
  artifacts: (runId: string) => ["forecast-artifacts", runId] as const,
  coverage: (regions: string[]) => ["knowledge-coverage", ...regions] as const,
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

export function useCreateRun() {
  return useMutation<ForecastRun, ApiError, ForecastRequest>({
    mutationFn: (request) => createForecastRun(request),
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
    onSuccess: (product) => {
      queryClient.setQueryData(queryKeys.product(product.id), product);
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
