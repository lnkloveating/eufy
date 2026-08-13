/**
 * Low-level HTTP client for the eufy FutureLab backend.
 *
 * Responsibilities:
 * - Resolve the API base URL from the Vite environment (never from user input).
 * - Parse JSON responses.
 * - Translate non-2xx responses and network failures into a typed `ApiError`
 *   with a human-readable Chinese message, while preserving the backend detail.
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** Shape of a FastAPI request-validation error entry (422 responses). */
interface FastApiValidationItem {
  loc?: unknown;
  msg?: unknown;
  type?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  /** Parsed, human-readable backend detail (never the raw object). */
  readonly detail: string;
  /** True for network / CORS / timeout failures where there is no HTTP status. */
  readonly isNetworkError: boolean;

  constructor(options: {
    status: number;
    detail: string;
    isNetworkError?: boolean;
  }) {
    super(options.detail);
    this.name = "ApiError";
    this.status = options.status;
    this.detail = options.detail;
    this.isNetworkError = options.isNetworkError ?? false;
  }

  /** The forecast result is not ready yet (run still processing). */
  get isResultNotReady(): boolean {
    return this.status === 409;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

/**
 * FastAPI reports errors as `{ "detail": ... }` where `detail` may be:
 * - a plain string (HTTPException),
 * - an array of validation items (RequestValidationError), or
 * - occasionally a nested object.
 * This normalizes all of those into a single readable string.
 */
export function parseErrorDetail(body: unknown, status: number): string {
  const fallback = `请求失败（HTTP ${status}）`;
  if (body == null || typeof body !== "object") {
    return typeof body === "string" && body.trim() ? body : fallback;
  }

  const detail = (body as { detail?: unknown }).detail;
  if (detail == null) {
    return fallback;
  }
  if (typeof detail === "string") {
    return detail.trim() || fallback;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const validation = item as FastApiValidationItem;
          const loc = Array.isArray(validation.loc)
            ? validation.loc
                .filter((part) => part !== "body")
                .map((part) => String(part))
                .join(".")
            : "";
          const msg = typeof validation.msg === "string" ? validation.msg : "";
          return loc ? `${loc}: ${msg}` : msg;
        }
        return "";
      })
      .filter(Boolean);
    return messages.length ? messages.join("；") : fallback;
  }
  if (typeof detail === "object") {
    const msg = (detail as { msg?: unknown }).msg;
    if (typeof msg === "string" && msg.trim()) return msg;
  }
  return fallback;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

/**
 * Perform a typed JSON request against the backend.
 * Throws `ApiError` on any failure; never returns a non-2xx result.
 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: { Accept: "application/json" },
    signal: options.signal,
  };

  if (options.body !== undefined) {
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    // We intentionally do not log request payloads (may contain no secrets,
    // but keep the console clean and privacy-preserving regardless).
    throw new ApiError({
      status: 0,
      detail: "无法连接后端服务，请确认后端已在 http://localhost:8000 启动。",
      isNetworkError: true,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const raw = await response.text();
  let parsed: unknown = undefined;
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = raw;
    }
  }

  if (!response.ok) {
    throw new ApiError({
      status: response.status,
      detail: parseErrorDetail(parsed, response.status),
    });
  }

  return parsed as T;
}

// Re-export for callers that build absolute URLs (e.g. the SSE EventSource).
export function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}
