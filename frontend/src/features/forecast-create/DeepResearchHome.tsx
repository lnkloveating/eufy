import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Database,
  History,
  Layers3,
  Radar,
  Settings2,
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
import { AdvancedResearchSettings } from "./AdvancedResearchSettings";
import { ClarificationDialog } from "./ClarificationDialog";
import { ResearchBriefCard } from "./ResearchBriefCard";
import {
  applyClarificationAnswers,
  applyExamplePrompt,
  areWeightsValid,
  briefToRequest,
  createEmptyBrief,
  getBriefCompleteness,
  getMissingClarifications,
  getMissingFields,
  type ClarificationQuestion,
  type ExamplePrompt,
  type ResearchBrief,
} from "./researchBrief";

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
  const [phase, setPhase] = useState<"compose" | "brief">("compose");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarificationReviewed, setClarificationReviewed] = useState(false);
  const [clarifyQuestions, setClarifyQuestions] = useState<ClarificationQuestion[]>([]);

  const backendOnline = Boolean(health);
  const llmConfigured = health?.llm_configured ?? false;
  const weightsOk = areWeightsValid(brief.weights);
  const canStart = backendOnline && llmConfigured && weightsOk && !createRun.isPending;

  const disabledReason = !backendOnline
    ? "后端未连接，请先启动后端服务（默认 http://localhost:8000）"
    : !llmConfigured
      ? "LLM 未配置，请在后端环境变量中配置 API Key（前端永不接触密钥）"
      : !weightsOk
        ? "评估权重需在高级设置中归一化为 100%"
        : undefined;

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
            disabledReason={disabledReason}
          />

          <div className="card">
            <button
              type="button"
              className="advanced-toggle"
              aria-expanded={showAdvanced}
              onClick={() => setShowAdvanced((value) => !value)}
            >
                <span className="row row-gap-3">
                <Settings2 size={17} aria-hidden="true" />
                <span className="stack" style={{ gap: 0 }}>
                  <span className="strong">高级研究设置</span>
                  <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                    地区、目标用户、预测周期、价格、约束、候选数量与评估权重
                  </span>
                </span>
                </span>
              <span className="row row-gap-2">
                <span className="chip chip-accent">Brief {getBriefCompleteness(brief)}%</span>
                <ChevronDown
                  size={18}
                  aria-hidden="true"
                  style={{
                    transition: "transform 160ms",
                    transform: showAdvanced ? "rotate(180deg)" : "none",
                  }}
                />
              </span>
            </button>
            {showAdvanced && (
              <div className="card-pad" style={{ borderTop: "1px solid var(--line)" }}>
                <AdvancedResearchSettings brief={brief} options={options} onChange={patchBrief} />
              </div>
            )}
          </div>
        </>
      ) : (
        <ResearchBriefCard
          brief={brief}
          regionLabel={(region) => region}
          onEdit={() => setPhase("compose")}
          onStart={startResearch}
          starting={createRun.isPending}
          canStart={canStart}
        />
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
