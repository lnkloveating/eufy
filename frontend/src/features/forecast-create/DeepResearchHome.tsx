import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ForecastOptions, HealthResponse } from "../../types/api";
import { useCreateRun, useForecastOptions, useHealth } from "../../lib/queries";
import { rememberRun } from "../../lib/recent";
import { ApiError } from "../../lib/api/client";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { useToast } from "../../components/ui/Toast";
import { AdvancedSettingsCard } from "./AdvancedSettingsCard";
import { ClarificationDialog } from "./ClarificationDialog";
import { RecentResearchEntry } from "./RecentResearchEntry";
import { ResearchHomeAlerts } from "./ResearchHomeAlerts";
import { ResearchPrompt } from "./ResearchPrompt";
import { ResearchBriefCard } from "./ResearchBriefCard";
import {
  applyClarificationAnswers,
  applyExamplePrompt,
  areWeightsValid,
  briefToRequest,
  createEmptyBrief,
  getMissingClarifications,
  getMissingFields,
  type ClarificationQuestion,
  type ExamplePrompt,
  type ResearchBrief,
} from "./researchBrief";

function ResearchHomeInner({
  options,
  health,
}: {
  options: ForecastOptions;
  health: HealthResponse | undefined;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  const createRun = useCreateRun();

  const [brief, setBrief] = useState<ResearchBrief>(() => createEmptyBrief(options));
  const [phase, setPhase] = useState<"compose" | "brief">("compose");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarificationReviewed, setClarificationReviewed] = useState(false);
  const [clarifyQuestions, setClarifyQuestions] = useState<ClarificationQuestion[]>([]);

  const backendOnline = Boolean(health);
  const llmConfigured = health?.llm_configured ?? false;
  const weightsOk = areWeightsValid(brief.weights);
  const canStart = backendOnline && llmConfigured && weightsOk && !createRun.isPending;

  const patchBrief = (patch: Partial<ResearchBrief>) =>
    setBrief((prev) => ({ ...prev, ...patch }));

  const handleStart = () => {
    const missing = getMissingClarifications(brief, options);
    if (getMissingFields(brief).length > 0 || (!clarificationReviewed && missing.length > 0)) {
      setClarifyQuestions(missing);
      setClarifyOpen(true);
      return;
    }
    setPhase("brief");
  };

  const handleClarifyConfirm = (answers: Partial<Record<ClarificationQuestion["key"], string[]>>) => {
    const next = applyClarificationAnswers(brief, answers);
    setBrief(next);
    if (getMissingFields(next).length > 0) {
      setClarifyQuestions(getMissingClarifications(next, options));
      return;
    }
    setClarificationReviewed(true);
    setClarifyOpen(false);
    setPhase("brief");
  };

  const startResearch = async () => {
    try {
      const run = await createRun.mutateAsync(briefToRequest(brief));
      rememberRun(run.id);
      toast.success("深度研究已启动", "正在进入实时研究工作台");
      navigate(`/runs/${run.id}`);
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "启动研究失败，请稍后重试。";
      toast.error("启动研究失败", detail);
    }
  };

  return (
    <div className="stack stack-6">
      {phase === "compose" ? (
        <>
          <ResearchPrompt
            question={brief.question}
            onQuestionChange={(question) => patchBrief({ question })}
            onPickExample={(example: ExamplePrompt) =>
              setBrief((prev) => applyExamplePrompt(prev, example))
            }
            onStart={handleStart}
            starting={createRun.isPending}
            canStart={canStart}
          />

          <ResearchHomeAlerts backendOnline={backendOnline} llmConfigured={llmConfigured} />

          <RecentResearchEntry />

          <AdvancedSettingsCard
            brief={brief}
            options={options}
            open={showAdvanced}
            onToggle={() => setShowAdvanced((value) => !value)}
            onChange={patchBrief}
          />
        </>
      ) : (
        <>
          <ResearchHomeAlerts backendOnline={backendOnline} llmConfigured={llmConfigured} />

          <RecentResearchEntry />

          <ResearchBriefCard
            brief={brief}
            regionLabel={(region) => region}
            onEdit={() => setPhase("compose")}
            onStart={startResearch}
            starting={createRun.isPending}
            canStart={canStart}
          />
        </>
      )}

      <ClarificationDialog
        open={clarifyOpen}
        questions={clarifyQuestions}
        brief={brief}
        onCancel={() => setClarifyOpen(false)}
        onConfirm={handleClarifyConfirm}
      />
    </div>
  );
}

export function DeepResearchHome() {
  const health = useHealth();
  const options = useForecastOptions();

  return (
    <div className="page">
      {options.isLoading || health.isLoading ? (
        <div className="card card-pad">
          <SkeletonText lines={6} />
        </div>
      ) : options.isError ? (
        <ErrorState
          title="无法加载研究配置"
          error={options.error}
          onRetry={() => options.refetch()}
        />
      ) : options.data ? (
        <ResearchHomeInner options={options.data} health={health.data} />
      ) : null}
    </div>
  );
}
