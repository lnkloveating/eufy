/**
 * Friendly Chinese labels for agents, forecasting lenses and score dimensions.
 * Every lookup falls back to the raw backend identifier so unknown agents still
 * render meaningfully.
 */

import type { ScoreDimension } from "../types/api";

interface AgentDescriptor {
  label: string;
  role: string;
}

const AGENT_LABELS: Record<string, AgentDescriptor> = {
  "local-evidence-store": { label: "本地证据库", role: "证据检索" },
  "futures-user_trends": { label: "用户趋势", role: "未来预测视角" },
  "futures-technology_trends": { label: "技术趋势", role: "未来预测视角" },
  "futures-security_futures": { label: "安防未来", role: "未来预测视角" },
  "futures-market_futures": { label: "市场未来", role: "未来预测视角" },
  "deliberator-user_trends": { label: "用户趋势审议", role: "交叉审核" },
  "deliberator-technology_trends": { label: "技术趋势审议", role: "交叉审核" },
  "deliberator-security_futures": { label: "安防未来审议", role: "交叉审核" },
  "deliberator-market_futures": { label: "市场未来审议", role: "交叉审核" },
  "deliberation-panel": { label: "交叉审核委员会", role: "Deliberation Panel" },
  "forecast-consensus": { label: "共识裁决 Agent", role: "Consensus Judge" },
  "opportunity-synthesizer": { label: "机会聚合器", role: "Opportunity Synthesizer" },
  "local-competitor-store": { label: "本地竞品资料库", role: "Competitor Evidence" },
  "competitor-analysis": { label: "竞品分析师", role: "Competitive Intelligence" },
  "product-architect": { label: "产品架构师", role: "Product Architect" },
  "reviewer-innovation": { label: "创新性评审", role: "盲评 Reviewer" },
  "reviewer-user_value": { label: "用户价值评审", role: "盲评 Reviewer" },
  "reviewer-business_value": { label: "商业价值评审", role: "盲评 Reviewer" },
  "reviewer-feasibility": { label: "可行性评审", role: "盲评 Reviewer" },
  "reviewer-eufy_synergy": { label: "eufy 协同性评审", role: "盲评 Reviewer" },
  "product-definition": { label: "产品定义 Agent", role: "Product Definition" },
  "blind-review-panel": { label: "盲评委员会", role: "Review Panel" },
  "futures-panel": { label: "未来预测委员会", role: "Futures Panel" },
};

export function getAgentLabel(agent: string | null | undefined): string {
  if (!agent) return "系统编排";
  return AGENT_LABELS[agent]?.label ?? agent;
}

export function getAgentRole(agent: string | null | undefined): string {
  if (!agent) return "Orchestrator";
  return AGENT_LABELS[agent]?.role ?? "Agent";
}

/** The four forecasting lenses in canonical order (matches backend). */
export const LENS_LABELS: Record<string, string> = {
  user_trends: "用户趋势",
  technology_trends: "技术趋势",
  security_futures: "安防未来",
  market_futures: "市场未来",
};

export function getLensLabel(lens: string): string {
  return LENS_LABELS[lens] ?? lens;
}

/** The five scoring dimensions with their Chinese names. */
export const DIMENSION_LABELS: Record<ScoreDimension, string> = {
  innovation: "创新性",
  user_value: "用户价值",
  business_value: "商业价值",
  feasibility: "可行性",
  eufy_synergy: "eufy 协同性",
};

export function getDimensionLabel(dimension: string): string {
  return (DIMENSION_LABELS as Record<string, string>)[dimension] ?? dimension;
}
