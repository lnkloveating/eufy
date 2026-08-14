import { useRef, useState } from "react";
import { AlertTriangle, ChevronRight, History } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import type { ForecastOptions, HealthResponse } from "../../types/api";
import { useCreateRun, useForecastOptions, useHealth } from "../../lib/queries";
import { getRecentRun, rememberRun } from "../../lib/recent";
import { ApiError } from "../../lib/api/client";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { useToast } from "../../components/ui/Toast";
import { ResearchPrompt } from "./ResearchPrompt";
import { ResearchSetupDialog } from "./ResearchSetupDialog";
import {
  applyExamplePrompt,
  areWeightsValid,
  briefToRequest,
  createEmptyBrief,
  MIN_QUESTION_LENGTH,
  type ExamplePrompt,
  type ResearchBrief,
} from "./researchBrief";
import {
  createEmptySupplementalSources,
  type SupplementalResearchSources,
} from "./supplementalSources";

function HealthAlerts({
  backendOnline,
  llmConfigured,
}: {
  backendOnline: boolean;
  llmConfigured: boolean;
}) {
  return (
    <>
      {!backendOnline && (
        <div className="alert alert-danger" role="alert">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">后端未连接</span>
            <span>请先启动后端服务（默认 `http://localhost:8000`），再开始研究。</span>
          </div>
        </div>
      )}

      {backendOnline && !llmConfigured && (
        <div className="alert alert-warn" role="alert">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">LLM 未配置</span>
            <span>
              后端未检测到 LLM API Key。多 Agent 研究依赖 LLM，请在后端环境变量中配置后再开始。
            </span>
          </div>
        </div>
      )}
    </>
  );
}

function RecentResearchEntry() {
  const recentRun = getRecentRun();

  if (!recentRun) {
    return null;
  }

  return (
    <Link to={`/runs/${recentRun}`} className="recent-entry">
      <span className="row row-gap-3" style={{ minWidth: 0 }}>
        <History size={16} aria-hidden="true" />
        <span className="stack stack-none" style={{ minWidth: 0 }}>
          <span className="strong">继续上次研究</span>
          <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
            {recentRun}
          </span>
        </span>
      </span>
      <ChevronRight size={16} aria-hidden="true" />
    </Link>
  );
}

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
  const [setupOpen, setSetupOpen] = useState(false);
  const [supplementalSources, setSupplementalSources] = useState<SupplementalResearchSources>(
    createEmptySupplementalSources,
  );
  const startingRef = useRef(false);

  const backendOnline = Boolean(health);
  const llmConfigured = health?.llm_configured ?? false;
  const weightsOk = areWeightsValid(brief.weights);
  const canConfigure = brief.question.trim().length >= MIN_QUESTION_LENGTH;
  const canStart = backendOnline && llmConfigured && weightsOk && !createRun.isPending;

  const disabledReason = !backendOnline
    ? "后端未连接，请先启动后端服务"
    : !llmConfigured
      ? "LLM 未配置，请先完成后端模型配置"
      : !weightsOk
        ? "评估权重需要归一化为 100%"
        : undefined;

  const patchBrief = (patch: Partial<ResearchBrief>) =>
    setBrief((prev) => ({ ...prev, ...patch }));

  const startResearch = async () => {
    // Synchronous guard: blocks a rapid double-click before React state (and the
    // disabled button) can react. The Idempotency-Key is a second line of
    // defense so even a retried POST creates at most one run on the backend.
    if (startingRef.current || createRun.isPending) return;
    startingRef.current = true;
    const idempotencyKey = crypto.randomUUID();
    try {
      const run = await createRun.mutateAsync({
        request: briefToRequest(brief),
        idempotencyKey,
      });
      rememberRun(run.id);
      toast.success("深度研究已启动", "正在进入实时研究工作台…");
      navigate(`/runs/${run.id}`);
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "启动研究失败，请稍后重试。";
      toast.error("启动研究失败", detail);
    } finally {
      startingRef.current = false;
    }
  };

  return (
    <div className="stack stack-6">
      <HealthAlerts backendOnline={backendOnline} llmConfigured={llmConfigured} />

      <ResearchPrompt
        question={brief.question}
        onQuestionChange={(question) => patchBrief({ question })}
        onPickExample={(example: ExamplePrompt) =>
          setBrief((prev) => applyExamplePrompt(prev, example))
        }
        onStart={() => setSetupOpen(true)}
        starting={false}
        canStart={canConfigure}
        disabledReason={
          canConfigure ? undefined : `请输入至少 ${MIN_QUESTION_LENGTH} 个字符的研究问题`
        }
      />

      <RecentResearchEntry />

      <ResearchSetupDialog
        open={setupOpen}
        brief={brief}
        options={options}
        supplementalSources={supplementalSources}
        onBriefChange={patchBrief}
        onSupplementalSourcesChange={setSupplementalSources}
        onClose={() => setSetupOpen(false)}
        onStart={startResearch}
        onAutoResearchUnavailable={() =>
          toast.info("自动补充公开资料暂未启用", "当前研究继续使用本地知识快照。")
        }
        starting={createRun.isPending}
        canStart={canStart}
        disabledReason={disabledReason}
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
