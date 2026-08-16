/** Mapping between backend `stage` identifiers and Chinese pipeline labels. */

export interface StageDescriptor {
  key: string;
  label: string;
  /** Short helper shown under the pipeline node. */
  hint: string;
}

/** Ordered pipeline stages for a healthy run (excludes the `failed` stage). */
export const STAGE_ORDER: StageDescriptor[] = [
  { key: "queued", label: "等待启动", hint: "任务已创建，准备编排智能体" },
  { key: "evidence_selection", label: "本地证据选择", hint: "从本地证据库检索相关证据" },
  { key: "future_forecasting", label: "多视角未来预测", hint: "四个视角智能体并行分析" },
  { key: "forecast_deliberation", label: "智能体交叉质疑", hint: "四个视角相互审核并修正观点" },
  { key: "consensus_formation", label: "共识与分歧", hint: "裁决共识并保留少数意见" },
  { key: "opportunity_synthesis", label: "未来机会聚合", hint: "合并去重形成机会图谱" },
  { key: "competitor_analysis", label: "竞品空白分析", hint: "对照竞品能力，识别可验证空白" },
  { key: "current_capability_audit", label: "当前能力基线", hint: "识别 eufy 今天已经具备的产品能力" },
  { key: "candidate_generation", label: "候选产品生成", hint: "生成差异化产品候选" },
  { key: "novelty_audit", label: "创新查重门槛", hint: "淘汰现有功能重组并定向重生" },
  { key: "portfolio_diversity_audit", label: "候选组合去重", hint: "两两审计底层机制并替换重复方向" },
  { key: "candidate_review", label: "多维盲评", hint: "六个维度独立盲评打分" },
  {
    key: "awaiting_product_selection",
    label: "等待人工选择",
    hint: "由用户自由选择候选方向",
  },
];

const STAGE_LABELS: Record<string, string> = {
  ...Object.fromEntries(STAGE_ORDER.map((stage) => [stage.key, stage.label])),
  failed: "执行失败",
};

/** Resolve a stage identifier to its Chinese label, falling back to the raw id. */
export function getStageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

/** Index of a stage within the healthy pipeline (−1 if not part of it). */
export function stageIndex(stage: string): number {
  return STAGE_ORDER.findIndex((item) => item.key === stage);
}
