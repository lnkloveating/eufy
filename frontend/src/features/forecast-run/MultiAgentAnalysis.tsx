import { useState } from "react";
import { Compass, Map as MapIcon, MessageSquareWarning, Swords } from "lucide-react";

import type { ForecastResult } from "../../types/api";
import { Tabs, type TabItem } from "../../components/ui/Tabs";
import { OpportunityAtlas } from "../opportunities/OpportunityAtlas";
import { AgentInsights } from "./AgentInsights";
import { CompetitiveAnalysisPanel } from "./CompetitiveAnalysisPanel";
import { DeliberationPanel } from "./DeliberationPanel";

type AnalysisTabKey = "deliberation" | "insights" | "opportunities" | "competition";

export function MultiAgentAnalysis({ result }: { result: ForecastResult }) {
  const [active, setActive] = useState<AnalysisTabKey>("deliberation");
  const items: TabItem[] = [
    {
      key: "deliberation",
      label: "质疑与修正",
      count: result.lens_deliberations.length,
      icon: <MessageSquareWarning size={15} aria-hidden="true" />,
    },
    {
      key: "insights",
      label: "Agent 独立判断",
      count: result.lens_forecasts.length,
      icon: <Compass size={15} aria-hidden="true" />,
    },
    {
      key: "opportunities",
      label: "共识机会",
      count: result.opportunities.length,
      icon: <MapIcon size={15} aria-hidden="true" />,
    },
    {
      key: "competition",
      label: "竞品推演",
      count: result.competitive_analysis?.gaps.length,
      icon: <Swords size={15} aria-hidden="true" />,
    },
  ];

  return (
    <div className="stack stack-5">
      <div className="card card-pad stack stack-2">
        <span className="eyebrow">Multi-Agent Analysis · 多 Agent 分析记录</span>
        <strong>查看各 Agent 的结构化判断、相互质疑、观点修正与最终共识</strong>
        <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
          这里展示的是后端保存的 Agent 研究产物与审核结论，不生成或伪造隐藏思维过程。
        </span>
      </div>

      <Tabs
        items={items}
        active={active}
        onChange={(key) => setActive(key as AnalysisTabKey)}
        ariaLabel="多 Agent 分析"
      />

      {active === "deliberation" && (
        <DeliberationPanel
          deliberations={result.lens_deliberations}
          consensus={result.forecast_consensus}
        />
      )}
      {active === "insights" && (
        <AgentInsights forecasts={result.lens_forecasts} evidence={result.evidence} />
      )}
      {active === "opportunities" && (
        <OpportunityAtlas opportunities={result.opportunities} evidence={result.evidence} />
      )}
      {active === "competition" && (
        <CompetitiveAnalysisPanel
          analysis={result.competitive_analysis}
          evidence={result.competitor_evidence}
        />
      )}
    </div>
  );
}
