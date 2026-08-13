import { describe, expect, it } from "vitest";
import { getStageLabel, stageIndex, STAGE_ORDER } from "../src/lib/stageLabels";

describe("stage label mapping", () => {
  it("maps every known stage to a Chinese label", () => {
    expect(getStageLabel("queued")).toBe("等待启动");
    expect(getStageLabel("evidence_selection")).toBe("本地证据选择");
    expect(getStageLabel("future_forecasting")).toBe("多视角未来预测");
    expect(getStageLabel("forecast_deliberation")).toBe("Agent 交叉质疑");
    expect(getStageLabel("consensus_formation")).toBe("共识与分歧");
    expect(getStageLabel("opportunity_synthesis")).toBe("未来机会聚合");
    expect(getStageLabel("competitor_analysis")).toBe("竞品空白分析");
    expect(getStageLabel("candidate_generation")).toBe("候选产品生成");
    expect(getStageLabel("candidate_review")).toBe("多维盲评");
    expect(getStageLabel("awaiting_product_selection")).toBe("等待人工选择");
    expect(getStageLabel("failed")).toBe("执行失败");
  });

  it("falls back to the raw identifier for unknown stages", () => {
    expect(getStageLabel("some_new_backend_stage")).toBe("some_new_backend_stage");
  });

  it("orders pipeline stages consistently (competitor_analysis included)", () => {
    expect(STAGE_ORDER[0]?.key).toBe("queued");
    expect(stageIndex("queued")).toBe(0);
    expect(stageIndex("competitor_analysis")).toBe(6);
    expect(stageIndex("candidate_generation")).toBe(7);
    expect(stageIndex("candidate_review")).toBe(8);
    expect(stageIndex("awaiting_product_selection")).toBe(9);
  });

  it("returns -1 for stages outside the healthy pipeline", () => {
    expect(stageIndex("failed")).toBe(-1);
  });
});
