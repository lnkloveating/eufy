import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createValidationProject,
  runValidationProject,
  sendBackFinding,
} from "../src/lib/api/forecastApi";

interface Recorded {
  url: string;
  method: string;
  body: string | undefined;
}

let calls: Recorded[];

function fakeResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    text: async () => JSON.stringify(payload),
  } as unknown as Response;
}

beforeEach(() => {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({
        url,
        method: init.method ?? "GET",
        body: init.body as string | undefined,
      });
      return fakeResponse({ ok: true });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("validation API contract", () => {
  it("send-back POSTs to the real /validation-findings/{id}/send-back endpoint", async () => {
    await sendBackFinding("vf-abc123");
    expect(calls).toHaveLength(1);
    expect(calls[0]?.method).toBe("POST");
    expect(calls[0]?.url).toBe(
      "http://localhost:8000/api/v1/validation-findings/vf-abc123/send-back",
    );
  });

  it("create project POSTs to the product-scoped endpoint", async () => {
    await createValidationProject("product-9");
    expect(calls[0]?.method).toBe("POST");
    expect(calls[0]?.url).toBe(
      "http://localhost:8000/api/v1/products/product-9/validation-projects",
    );
  });

  it("run POSTs to the project-scoped run endpoint", async () => {
    await runValidationProject("vproj-1");
    expect(calls[0]?.method).toBe("POST");
    expect(calls[0]?.url).toBe(
      "http://localhost:8000/api/v1/validation-projects/vproj-1/run",
    );
  });

  it("encodes ids so a hostile id cannot break the path", async () => {
    await sendBackFinding("../evil");
    expect(calls[0]?.url).toBe(
      "http://localhost:8000/api/v1/validation-findings/..%2Fevil/send-back",
    );
  });
});
