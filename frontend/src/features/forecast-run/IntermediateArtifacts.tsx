import { Boxes, CheckCircle2, Database, Loader2, Map as MapIcon, Swords } from "lucide-react";
import type {
  Artifact,
  EvidenceRecord,
  LensForecast,
  ProductCandidate,
  RetrievalPlan,
  CompetitiveAnalysis,
  CompetitorRecord,
  ForecastConsensus,
  LensDeliberation,
} from "../../types/api";
import { AgentInsights } from "./AgentInsights";
import { KnowledgePlanPanel } from "./KnowledgePlanPanel";
import { CompetitiveAnalysisPanel } from "./CompetitiveAnalysisPanel";
import { DeliberationPanel } from "./DeliberationPanel";

function artifactPayload<T>(artifacts: Artifact[], kind: string): T | null {
  const artifact = [...artifacts].reverse().find((item) => item.kind === kind);
  return artifact ? (artifact.payload as T) : null;
}

export function IntermediateArtifacts({ artifacts }: { artifacts: Artifact[] }) {
  const plan = artifactPayload<RetrievalPlan>(artifacts, "retrieval_plan");
  const evidence = artifactPayload<EvidenceRecord[]>(artifacts, "evidence") ?? [];
  const forecasts = artifacts
    .filter((item) => item.kind.startsWith("lens_forecast:"))
    .map((item) => item.payload as LensForecast);
  const opportunities = artifactPayload<unknown[]>(artifacts, "opportunities") ?? [];
  const candidates = artifactPayload<ProductCandidate[]>(artifacts, "raw_candidates") ?? [];
  const competitorEvidence = artifactPayload<CompetitorRecord[]>(artifacts, "competitor_evidence") ?? [];
  const competition = artifactPayload<CompetitiveAnalysis>(artifacts, "competitive_analysis");
  const deliberations = artifactPayload<LensDeliberation[]>(artifacts, "lens_deliberations") ?? [];
  const consensus = artifactPayload<ForecastConsensus>(artifacts, "forecast_consensus");

  if (artifacts.length === 0) {
    return (
      <div className="card card-pad row row-gap-3">
        <Loader2 size={18} className="spin-inline" />
        <span className="muted">正在生成第一份可审计中间产物…</span>
      </div>
    );
  }

  return (
    <div className="stack stack-5">
      <div className="row wrap row-gap-2">
        <span className="chip"><Database size={12} /> {evidence.length} 条入选证据</span>
        <span className="chip"><CheckCircle2 size={12} /> {forecasts.length}/4 份趋势预测</span>
        <span className="chip"><MapIcon size={12} /> {opportunities.length} 个机会</span>
        <span className="chip"><Swords size={12} /> {competition?.gaps.length ?? 0} 个竞争空白</span>
        <span className="chip"><Boxes size={12} /> {candidates.length} 个候选</span>
      </div>
      {plan && <KnowledgePlanPanel plan={plan} evidence={evidence} />}
      {forecasts.length > 0 && <AgentInsights forecasts={forecasts} evidence={evidence} />}
      {(deliberations.length > 0 || consensus) && (
        <DeliberationPanel deliberations={deliberations} consensus={consensus} />
      )}
      {competition && (
        <CompetitiveAnalysisPanel analysis={competition} evidence={competitorEvidence} />
      )}
    </div>
  );
}
