import { describe, expect, it } from "vitest";
import { ApiError, parseErrorDetail } from "../src/lib/api/client";

describe("parseErrorDetail", () => {
  it("returns a plain string detail unchanged", () => {
    expect(parseErrorDetail({ detail: "forecast is currently running" }, 409)).toBe(
      "forecast is currently running",
    );
  });

  it("joins FastAPI validation arrays into a readable message", () => {
    const body = {
      detail: [
        { loc: ["body", "question"], msg: "String should have at least 12 characters", type: "value_error" },
        { loc: ["body", "regions"], msg: "List should have at least 1 item", type: "value_error" },
      ],
    };
    expect(parseErrorDetail(body, 422)).toBe(
      "question: String should have at least 12 characters；regions: List should have at least 1 item",
    );
  });

  it("handles a nested object detail with a msg field", () => {
    expect(parseErrorDetail({ detail: { msg: "candidate not found" } }, 404)).toBe(
      "candidate not found",
    );
  });

  it("falls back to a generic message when detail is missing", () => {
    expect(parseErrorDetail({}, 500)).toBe("请求失败（HTTP 500）");
    expect(parseErrorDetail(null, 503)).toBe("请求失败（HTTP 503）");
  });

  it("accepts a raw string body", () => {
    expect(parseErrorDetail("boom", 400)).toBe("boom");
  });
});

describe("ApiError", () => {
  it("flags 409 as result-not-ready", () => {
    const error = new ApiError({ status: 409, detail: "forecast is currently candidate_review" });
    expect(error.isResultNotReady).toBe(true);
    expect(error.isNotFound).toBe(false);
  });

  it("flags 404 as not-found", () => {
    const error = new ApiError({ status: 404, detail: "forecast run not found" });
    expect(error.isNotFound).toBe(true);
    expect(error.isResultNotReady).toBe(false);
  });

  it("carries the network-error flag", () => {
    const error = new ApiError({ status: 0, detail: "无法连接后端服务", isNetworkError: true });
    expect(error.isNetworkError).toBe(true);
    expect(error.message).toBe("无法连接后端服务");
  });
});
