import { describe, expect, it } from "vitest";

import {
  briefToRequest,
  createEmptyBrief,
} from "../src/features/forecast-create/researchBrief";
import {
  createEmptySupplementalSources,
  isHttpUrl,
} from "../src/features/forecast-create/supplementalSources";

describe("supplemental source drafts", () => {
  it("starts disabled and empty", () => {
    expect(createEmptySupplementalSources()).toEqual({
      autoPublicResearch: false,
      enterpriseSources: [],
      focusSources: [],
    });
  });

  it("accepts only HTTP(S) URLs", () => {
    expect(isHttpUrl("https://example.com/paper")).toBe(true);
    expect(isHttpUrl("http://example.com/video")).toBe(true);
    expect(isHttpUrl("file:///private/report.pdf")).toBe(false);
    expect(isHttpUrl("not a url")).toBe(false);
  });

  it("does not add preview source fields to ForecastRequest", () => {
    const brief = createEmptyBrief();
    brief.question = "未来三年美国独栋家庭有哪些安防机会？";
    brief.regions = ["United States"];
    brief.target_users = ["独栋住宅家庭"];
    const request = briefToRequest(brief);
    expect(request).not.toHaveProperty("supplementalSources");
    expect(request).not.toHaveProperty("enterpriseSources");
    expect(request).not.toHaveProperty("focusSources");
    expect(request).not.toHaveProperty("autoPublicResearch");
  });
});
