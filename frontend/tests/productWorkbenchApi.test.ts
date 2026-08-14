import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyProductRevision,
  askProductQuestion,
  confirmProduct,
  dismissDesignIssues,
  dismissSuggestions,
  generateIssueProposal,
  getProductQuestions,
  getProductReadiness,
} from "../src/lib/api/forecastApi";
import { ApiError } from "../src/lib/api/client";

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

describe("askProductQuestion", () => {
  it("POSTs a real question and idempotency key to the product questions endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ question: {}, answer: {} }));
    await askProductQuestion("product-1", {
      question: "断网后还能工作吗？",
      idempotency_key: "abcdefgh",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/questions`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      question: "断网后还能工作吗？",
      idempotency_key: "abcdefgh",
    });
  });
});

describe("applyProductRevision", () => {
  it("POSTs only the accepted decisions to the revisions endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "product-1", version: "1.1" }));
    await applyProductRevision("product-1", {
      decisions: [{ suggestion_id: "sc-1", disposition: "apply" }],
      idempotency_key: "revkey-01",
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/revisions`);
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body.decisions).toEqual([{ suggestion_id: "sc-1", disposition: "apply" }]);
  });
});

describe("dismissSuggestions", () => {
  it("POSTs the dismissed suggestion ids", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ready: false, blocking_items: [] }));
    await dismissSuggestions("product-1", { suggestion_ids: ["sc-1", "sc-2"] });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/suggestions/dismiss`);
    expect(JSON.parse(init.body as string)).toEqual({ suggestion_ids: ["sc-1", "sc-2"] });
  });
});

describe("generateIssueProposal", () => {
  it("POSTs to the per-question proposal endpoint without a body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ question: {}, answer: {} }));
    await generateIssueProposal("product-1", "pq-1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/questions/pq-1/proposal`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });
});

describe("dismissDesignIssues", () => {
  it("POSTs the dismissed issue ids", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ready: true, blocking_items: [] }));
    await dismissDesignIssues("product-1", { issue_ids: ["di-1"] });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/issues/dismiss`);
    expect(JSON.parse(init.body as string)).toEqual({ issue_ids: ["di-1"] });
  });
});

describe("confirmProduct", () => {
  it("POSTs to the confirm endpoint without a body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "product-1", definition_status: "validation_ready" }));
    await confirmProduct("product-1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/products/product-1/confirm`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("surfaces a 409 readiness failure as an ApiError", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "还有 2 项阻塞项待处理" }, 409));
    await expect(confirmProduct("product-1")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("read endpoints", () => {
  it("GETs product questions and readiness", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await getProductQuestions("product-1");
    expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toBe(
      `${BASE}/products/product-1/questions`,
    );

    fetchMock.mockResolvedValue(jsonResponse({ ready: true }));
    await getProductReadiness("product-1");
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[0]).toBe(
      `${BASE}/products/product-1/readiness`,
    );
  });
});
