import { describe, expect, it } from "vitest";

import { getProductDefinitionNavigation } from "../src/lib/productDefinitionNavigation";
import type { RunProductDefinitionState } from "../src/types/api";

function state(
  status: RunProductDefinitionState["status"],
  productId: string | null = null,
): RunProductDefinitionState {
  return {
    run_id: "forecast-current",
    status,
    product_id: productId,
    candidate_id: null,
    error: null,
  };
}

describe("run-scoped product definition navigation", () => {
  it("keeps research and generation states on the current run status page", () => {
    for (const status of ["researching", "awaiting_selection", "generating", "failed"] as const) {
      expect(getProductDefinitionNavigation("forecast-current", state(status)).path).toBe(
        "/runs/forecast-current/product-definition",
      );
    }
  });

  it("opens a product only when the current run reports it ready", () => {
    expect(
      getProductDefinitionNavigation("forecast-current", state("ready", "product-current")).path,
    ).toBe("/products/product-current");
  });

  it("never opens a ready product belonging to another run", () => {
    const stale = state("ready", "product-old");
    stale.run_id = "forecast-old";

    expect(getProductDefinitionNavigation("forecast-current", stale).path).toBe(
      "/runs/forecast-current/product-definition",
    );
  });
});
