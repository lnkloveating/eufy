import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createForecastRun } from "../src/lib/api/forecastApi";
import { deriveDegradation } from "../src/features/forecast-run/RunWorkbenchPage";
import type { AgentEvent, ForecastRequest } from "../src/types/api";

const BASE = "http://localhost:8000/api/v1";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const REQUEST: ForecastRequest = {
  question: "预测未来三年美国 eufy Security 的 AI 原生产品机会",
  category: "eufy Security",
  forecast_horizon_years: 3,
  regions: ["United States"],
  target_users: ["Households"],
  price_segment: null,
  constraints: [],
  research_context: {},
  candidate_count: 6,
  strategy_profile: "balanced",
  weights: {
    innovation: 0.25,
    user_value: 0.2,
    business_value: 0.15,
    cost_effectiveness: 0.15,
    feasibility: 0.15,
    eufy_synergy: 0.1,
  },
} as unknown as ForecastRequest;

describe("createForecastRun idempotency", () => {
  it("sends the Idempotency-Key header when a key is supplied", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "forecast-1", status: "pending" }));
    await createForecastRun(REQUEST, "click-key-123456");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/forecast-runs`);
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("click-key-123456");
  });

  it("omits the header when no key is supplied", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "forecast-1", status: "pending" }));
    await createForecastRun(REQUEST);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBeUndefined();
  });
});

function completedEvent(payload: Record<string, unknown>): AgentEvent {
  return {
    id: 1,
    run_id: "forecast-1",
    sequence: 99,
    event_type: "run_completed",
    agent: null,
    message: "done",
    payload,
    created_at: new Date().toISOString(),
  };
}

describe("deriveDegradation", () => {
  it("reports a fully-completed run as not degraded", () => {
    const info = deriveDegradation([completedEvent({ degraded: false, degradation_count: 0 })]);
    expect(info.degraded).toBe(false);
    expect(info.count).toBe(0);
  });

  it("surfaces degradation reasons from the terminal event", () => {
    const info = deriveDegradation([
      completedEvent({
        degraded: true,
        degradation_count: 2,
        degradations: [
          { stage: "competitor_analysis", reason: "竞品分析已降级" },
          { stage: "candidate_review", reason: "缺失评审维度：feasibility" },
        ],
      }),
    ]);
    expect(info.degraded).toBe(true);
    expect(info.count).toBe(2);
    expect(info.reasons.map((item) => item.stage)).toEqual([
      "competitor_analysis",
      "candidate_review",
    ]);
  });

  it("treats a run with no completion event as not degraded", () => {
    expect(deriveDegradation([]).degraded).toBe(false);
  });
});
