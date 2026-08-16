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
      label: "智能体独立判断",
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
      <Tabs
        items={items}
        active={active}
        onChange={(key) => setActive(key as AnalysisTabKey)}
        ariaLabel="多智能体分析"
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
