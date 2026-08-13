import { useState } from "react";
import { Boxes, ClipboardList, Compass, Database, Layers3, Map as MapIcon, Scale, ShieldCheck, Swords } from "lucide-react";
import type { ForecastResult } from "../../types/api";
import { Tabs, type TabItem } from "../../components/ui/Tabs";
import { AgentInsights } from "./AgentInsights";
import { EvidenceLibrary } from "./EvidenceLibrary";
import { OpportunityAtlas } from "../opportunities/OpportunityAtlas";
import { CandidatesPanel } from "../candidates/CandidatesPanel";
import { KnowledgePlanPanel } from "./KnowledgePlanPanel";
import { CompetitiveAnalysisPanel } from "./CompetitiveAnalysisPanel";
import { DeliberationPanel } from "./DeliberationPanel";
import { ResearchContextPanel } from "./ResearchContextPanel";
import { StrategyImpactPanel } from "./StrategyImpactPanel";
import { NoveltyAuditPanel } from "./NoveltyAuditPanel";

type TabKey = "brief" | "retrieval" | "insights" | "deliberation" | "opportunities" | "competition" | "novelty" | "candidates" | "evidence";

export interface RunResultTabsProps {
  runId: string;
  result: ForecastResult;
}

/** Tabbed result explorer shown once a run completes. */
export function RunResultTabs({ runId, result }: RunResultTabsProps) {
  const [active, setActive] = useState<TabKey>("candidates");

  const items: TabItem[] = [
    {
      key: "brief",
      label: "研究简报",
      icon: <ClipboardList size={15} aria-hidden="true" />,
    },
    {
      key: "deliberation",
      label: "共识与分歧",
      count: result.lens_deliberations.length,
      icon: <Scale size={15} aria-hidden="true" />,
    },
    {
      key: "competition",
      label: "竞品与空白",
      count: result.competitive_analysis?.gaps.length,
      icon: <Swords size={15} aria-hidden="true" />,
    },
    {
      key: "retrieval",
      label: "RAG 检索计划",
      count: result.retrieval_plan?.selected_evidence_ids.length,
      icon: <Layers3 size={15} aria-hidden="true" />,
    },
    {
      key: "candidates",
      label: "产品候选",
      count: result.candidates.length,
      icon: <Boxes size={15} aria-hidden="true" />,
    },
    {
      key: "novelty",
      label: "创新查重",
      count: result.novelty_audit?.assessments.length,
      icon: <ShieldCheck size={15} aria-hidden="true" />,
    },
    {
      key: "opportunities",
      label: "机会图谱",
      count: result.opportunities.length,
      icon: <MapIcon size={15} aria-hidden="true" />,
    },
    {
      key: "insights",
      label: "Agent 洞察",
      count: result.lens_forecasts.length,
      icon: <Compass size={15} aria-hidden="true" />,
    },
    {
      key: "evidence",
      label: "证据库",
      count: result.evidence.length,
      icon: <Database size={15} aria-hidden="true" />,
    },
  ];

  return (
    <div className="stack stack-5">
      <Tabs
        items={items}
        active={active}
        onChange={(key) => setActive(key as TabKey)}
        ariaLabel="预测结果"
      />

      {active === "candidates" && (
        <CandidatesPanel
          runId={runId}
          candidates={result.candidates}
          evidence={result.evidence}
          noveltyAudit={result.novelty_audit}
        />
      )}
      {active === "brief" && (
        <div className="stack stack-5">
          <StrategyImpactPanel result={result} />
          <ResearchContextPanel request={result.run.request} />
        </div>
      )}
      {active === "novelty" && (
        <NoveltyAuditPanel
          baseline={result.current_capability_baseline}
          audit={result.novelty_audit}
          diversityAudit={result.portfolio_diversity_audit}
          candidates={result.candidates}
        />
      )}
      {active === "retrieval" && (
        <KnowledgePlanPanel plan={result.retrieval_plan} evidence={result.evidence} />
      )}
      {active === "opportunities" && (
        <OpportunityAtlas
          opportunities={result.opportunities}
          evidence={result.evidence}
        />
      )}
      {active === "competition" && (
        <CompetitiveAnalysisPanel
          analysis={result.competitive_analysis}
          evidence={result.competitor_evidence}
        />
      )}
      {active === "deliberation" && (
        <DeliberationPanel
          deliberations={result.lens_deliberations}
          consensus={result.forecast_consensus}
        />
      )}
      {active === "insights" && (
        <AgentInsights forecasts={result.lens_forecasts} evidence={result.evidence} />
      )}
      {active === "evidence" && <EvidenceLibrary evidence={result.evidence} />}
    </div>
  );
}
