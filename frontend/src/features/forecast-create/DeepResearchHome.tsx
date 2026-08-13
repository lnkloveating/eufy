import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ChevronRight,
  Database,
  History,
  Layers3,
  Radar,
  ShieldCheck,
  Swords,
} from "lucide-react";

import type { ForecastOptions, HealthResponse } from "../../types/api";
import { useCreateRun, useForecastOptions, useHealth } from "../../lib/queries";
import { rememberRun, getRecentRun } from "../../lib/recent";
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

function StatusStrip({ health }: { health: HealthResponse | undefined }) {
  const online = Boolean(health);
  return (
    <div className="hero-health">
      <div className="hero-stat">
        <span className="hero-stat-label">后端连接</span>
        <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
          <span className={`dot ${online ? "dot-ok" : "dot-off"}`} style={{ width: 8, height: 8 }} />
          {online ? "在线" : "离线"}
        </span>
      </div>
      <div className="hero-stat">
        <span className="hero-stat-label">LLM 模型</span>
        <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
          <span
            className={`dot ${health?.llm_configured ? "dot-ok" : "dot-warn"}`}
            style={{ width: 8, height: 8 }}
          />
          {health?.llm_configured ? health.llm_model : "未配置"}
        </span>
      </div>
      <div className="hero-stat">
        <span className="hero-stat-label">
          <Database size={11} aria-hidden="true" /> 本地知识
        </span>
        <span className="hero-stat-value">{health?.local_evidence_count ?? "—"} 条</span>
      </div>
      <div className="hero-stat">
        <span className="hero-stat-label">
          <Layers3 size={11} aria-hidden="true" /> 知识分层
        </span>
        <span className="hero-stat-value">
          {health ? Object.keys(health.knowledge_layers).length : "—"} 层
        </span>
      </div>
      <div className="hero-stat">
        <span className="hero-stat-label">
          <Swords size={11} aria-hidden="true" /> 竞品资料
        </span>
        <span className="hero-stat-value">{health?.competitor_evidence_count ?? "—"} 条</span>
      </div>
    </div>
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
  const recentRun = getRecentRun();

  const [brief, setBrief] = useState<ResearchBrief>(() => createEmptyBrief(options));
  const [setupOpen, setSetupOpen] = useState(false);
  const [supplementalSources, setSupplementalSources] = useState<SupplementalResearchSources>(
    createEmptySupplementalSources,
  );

  const backendOnline = Boolean(health);
  const llmConfigured = health?.llm_configured ?? false;
  const weightsOk = areWeightsValid(brief.weights);
  const canConfigure = brief.question.trim().length >= MIN_QUESTION_LENGTH;
  const canStart = backendOnline && llmConfigured && weightsOk && !createRun.isPending;

  const disabledReason = !backendOnline
    ? "后端未连接，请先启动后端服务（默认 http://localhost:8000）"
    : !llmConfigured
      ? "LLM 未配置，请在后端环境变量中配置 API Key（前端永不接触密钥）"
      : !weightsOk
        ? "评估权重需归一化为 100%"
        : undefined;

  const patchBrief = (patch: Partial<ResearchBrief>) =>
    setBrief((prev) => ({ ...prev, ...patch }));

  const startResearch = async () => {
    try {
      const run = await createRun.mutateAsync(briefToRequest(brief));
      rememberRun(run.id);
      toast.success("深度研究已启动", "正在进入实时研究工作台…");
      navigate(`/runs/${run.id}`);
    } catch (error) {
      const detail =
        error instanceof ApiError ? error.detail : "启动研究失败，请稍后重试。";
      toast.error("启动研究失败", detail);
    }
  };

  return (
    <div className="stack stack-6">
      {!backendOnline && (
        <div className="alert alert-danger" role="alert">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">后端未连接</span>
            <span>请先启动后端服务（默认 http://localhost:8000），再开始研究。</span>
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
              前端不会保存或读取任何 API Key。
            </span>
          </div>
        </div>
      )}

      {recentRun && (
        <Link to={`/runs/${recentRun}`} className="recent-entry">
          <span className="row row-gap-3" style={{ minWidth: 0 }}>
            <History size={16} aria-hidden="true" />
            <span className="stack" style={{ gap: 0, minWidth: 0 }}>
              <span className="strong">继续上次研究</span>
              <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
                {recentRun}
              </span>
            </span>
          </span>
          <ChevronRight size={16} aria-hidden="true" />
        </Link>
      )}

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

/** Deep Research home: large research question + clarification + brief. */
export function DeepResearchHome() {
  const health = useHealth();
  const options = useForecastOptions();

  return (
    <div className="page">
      <div className="hero" style={{ marginBottom: "var(--space-8)" }}>
        <div className="row row-gap-3" style={{ marginBottom: "var(--space-2)" }}>
          <Radar size={20} style={{ color: "var(--accent)" }} aria-hidden="true" />
          <span className="eyebrow" style={{ color: "#8fb9c4" }}>
            AI-Native Product Research Workbench
          </span>
        </div>
        <h1>eufy FutureLab</h1>
        <p className="hero-sub">
          像 Deep Research 一样发起一次多 Agent 产品研究 —— 从一个未来产品问题，到可验证的标准 ProductSpec。
        </p>
        <div className="hero-note">
          <ShieldCheck size={18} style={{ color: "var(--accent)", flexShrink: 0 }} aria-hidden="true" />
          同一套研究工作流会根据问题、地区、用户与约束生成不同的未来产品组合 —— 产品不是预设的，而是由多个 Agent 基于地区化 RAG 与竞品分析动态预测生成。
        </div>
        <StatusStrip health={health.data} />
      </div>

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
