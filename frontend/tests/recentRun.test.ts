import { afterEach, describe, expect, it, vi } from "vitest";

import { getRecentRun, rememberRun } from "../src/lib/recent";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("recent run storage", () => {
  it("removes the legacy global product pointer when a run becomes current", () => {
    const values = new Map<string, string>([
      ["eufy-futurelab.recent-product", "product-old"],
    ]);
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    });

    rememberRun("forecast-new");

    expect(getRecentRun()).toBe("forecast-new");
    expect(values.has("eufy-futurelab.recent-product")).toBe(false);
  });
});
