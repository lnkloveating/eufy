import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Clock,
  Cpu,
  Database,
  Gauge,
  Layers3,
  LayoutDashboard,
  Radio,
  ScrollText,
  Swords,
} from "lucide-react";

import type { AgentEvent, Artifact, ForecastResult, RunStatus } from "../../types/api";
import { useRun, useRunArtifacts, useRunResult } from "../../lib/queries";
import { formatDateTime } from "../../lib/formatters";
import { ApiError } from "../../lib/api/client";
import { rememberRun } from "../../lib/recent";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { AgentTimeline } from "../../components/AgentTimeline/AgentTimeline";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { Skeleton, SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { Tabs, type TabItem } from "../../components/ui/Tabs";
import { MultiAgentAnalysis } from "./MultiAgentAnalysis";
import { ResearchStageView } from "./ResearchStageView";
import { ResearchLedger } from "./ResearchLedger";
import { LiveResearchCanvas } from "./LiveResearchCanvas";
import { AgentRoster } from "./AgentRoster";
import { EvidenceLibrary } from "./EvidenceLibrary";
import { IntermediateArtifacts } from "./IntermediateArtifacts";
import { ResearchContextPanel } from "./ResearchContextPanel";
import { useRunEvents, type ConnectionState } from "./useRunEvents";
import {
  aggregateArtifactMetrics,
  deriveLedgerCounts,
  formatDurationMs,
} from "./researchMetrics";

type WorkspaceTabKey = "overview" | "process" | "analysis" | "evidence";

const WORKSPACE_TAB_KEYS = new Set<WorkspaceTabKey>([
  "overview",
  "process",
  "analysis",
  "evidence",
]);

export function resolveWorkspaceTab(
  requested: string | null,
  status: RunStatus | undefined,
): WorkspaceTabKey {
  if (requested && WORKSPACE_TAB_KEYS.has(requested as WorkspaceTabKey)) {
    return requested as WorkspaceTabKey;
  }
  if (requested === "results") return "analysis";
  return status === "completed" ? "analysis" : "process";
}

function deriveStage(events: AgentEvent[]): string {
  let stage = "queued";
  for (const event of events) {
    const agent = event.agent ?? "";
    if (event.event_type === "evidence_selected") stage = "evidence_selection";
    else if (event.event_type === "agent_started" && agent.startsWith("futures-")) {
      stage = "future_forecasting";
    } else if (event.event_type === "agent_started" && agent.startsWith("deliberator-")) {
      stage = "forecast_deliberation";
    } else if (event.event_type === "agent_started" && agent === "forecast-consensus") {
      stage = "consensus_formation";
    } else if (event.event_type === "agent_started" && agent === "opportunity-synthesizer") {
      stage = "opportunity_synthesis";
    } else if (event.event_type === "agent_started" && agent === "competitor-analysis") {
      stage = "competitor_analysis";
    } else if (event.event_type === "agent_started" && agent === "current-product-auditor") {
      stage = "current_capability_audit";
    } else if (event.event_type === "agent_started" && agent === "candidate-novelty-auditor") {
      stage = "novelty_audit";
    } else if (event.event_type === "agent_started" && agent === "portfolio-diversity-auditor") {
      stage = "portfolio_diversity_audit";
    } else if (event.event_type === "agent_started" && agent === "product-architect") {
      stage = "candidate_generation";
    } else if (
      event.event_type === "novelty_audit_started" ||
      event.event_type === "novelty_gate_failed" ||
      event.event_type === "novelty_rescue_started" ||
      event.event_type === "novelty_gate_degraded" ||
      event.event_type === "novelty_audit_completed"
    ) {
      stage = "novelty_audit";
    } else if (
      event.event_type === "portfolio_diversity_audit_started" ||
      event.event_type === "portfolio_duplicate_found" ||
      event.event_type === "portfolio_diversity_degraded" ||
      event.event_type === "portfolio_diversity_audit_completed"
    ) {
      stage = "portfolio_diversity_audit";
    } else if (event.event_type === "agent_started" && agent.startsWith("reviewer-")) {
      stage = "candidate_review";
    }
  }
  return stage;
}

const CONNECTION_META: Record<
  ConnectionState,
  { label: string; className: string; live?: boolean }
> = {
  connecting: { label: "连接中", className: "conn-connecting" },
  live: { label: "实时", className: "conn-live", live: true },
  reconnecting: { label: "重连中（轮询兜底）", className: "conn-reconnecting" },
  closed: { label: "已结束", className: "conn-closed" },
};

function ConnectionPill({ state }: { state: ConnectionState }) {
  const meta = CONNECTION_META[state];
  return (
    <span className={`conn-pill ${meta.className}`}>
      {meta.live ? <span className="dot" /> : <Radio size={11} aria-hidden="true" />}
      {meta.label}
    </span>
  );
}

export interface DegradationInfo {
  degraded: boolean;
  count: number;
  reasons: { stage: string; reason: string }[];
}

export function deriveDegradation(events: AgentEvent[]): DegradationInfo {
  const completed = events.find((event) => event.event_type === "run_completed");
  const payload = completed?.payload as
    | {
        degraded?: boolean;
        degradation_count?: number;
        degradations?: { stage: string; reason: string }[];
      }
    | undefined;
  if (payload?.degraded) {
    const reasons = Array.isArray(payload.degradations) ? payload.degradations : [];
    return {
      degraded: true,
      count: payload.degradation_count ?? reasons.length,
      reasons,
    };
  }
  return { degraded: false, count: 0, reasons: [] };
}

function completedAgentCount(events: AgentEvent[]): number {
  const done = new Set<string>();
  for (const event of events) {
    if (!event.agent) continue;
    if (
      event.event_type === "agent_completed" ||
      event.event_type === "product_definition_completed" ||
      event.event_type === "evidence_selected"
    ) {
      done.add(event.agent);
    }
  }
  return done.size;
}

export function RunWorkbenchPage() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const processStageRef = useRef<HTMLDivElement | null>(null);
  const [processTimelineHeight, setProcessTimelineHeight] = useState<number | null>(null);

  useEffect(() => {
    if (runId) rememberRun(runId);
  }, [runId]);
  const run = useRun(runId);
  const runData = run.data;
  const status = run.data?.status;
  const workspaceTab = resolveWorkspaceTab(searchParams.get("tab"), status);
  const selectWorkspaceTab = (tab: WorkspaceTabKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    setSearchParams(next, { replace: true });
  };
  const isFinished = status === "completed" || status === "failed";

  const { events, connection } = useRunEvents(runId, isFinished);
  const result = useRunResult(runId, status === "completed");
  const artifacts = useRunArtifacts(runId, !isFinished);
  const artifactList = artifacts.data ?? [];
  const activeStageKey =
    status === "completed"
      ? "awaiting_product_selection"
      : status === "failed"
        ? deriveStage(events)
        : runData?.stage ?? "queued";

  useEffect(() => {
    if (workspaceTab !== "process") return;
    const element = processStageRef.current;
    if (!element) return;

    const updateHeight = () => {
      setProcessTimelineHeight(element.getBoundingClientRect().height);
    };

    updateHeight();

    const observer = new ResizeObserver(() => {
      updateHeight();
    });
    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [workspaceTab, activeStageKey, status, events.length]);

  if (run.isLoading && !run.data) {
    return (
      <div className="page">
        <Skeleton width="40%" height={30} radius={8} />
        <div style={{ height: 20 }} />
        <div className="research-grid">
          <div className="card card-pad">
            <SkeletonText lines={8} />
          </div>
          <div className="card card-pad">
            <SkeletonText lines={10} />
          </div>
          <div className="card card-pad">
            <SkeletonText lines={8} />
          </div>
        </div>
      </div>
    );
  }

  if (run.isError || !run.data) {
    const notFound = run.error instanceof ApiError && run.error.isNotFound;
    return (
      <div className="page">
        {notFound ? (
          <EmptyState
            icon={<AlertTriangle size={26} aria-hidden="true" />}
            title="研究任务不存在"
            description={`未找到任务 ${runId}，它可能尚未创建或已被清理。`}
            action={
              <Link to="/">
                <Button variant="primary">返回研究首页</Button>
              </Link>
            }
          />
        ) : (
          <ErrorState
            title="无法加载任务"
            error={run.error}
            onRetry={() => run.refetch()}
            action={
              <Link to="/">
                <Button variant="ghost">返回首页</Button>
              </Link>
            }
          />
        )}
      </div>
    );
  }

  const data = run.data;
  const ledgerCounts = deriveLedgerCounts(artifactList);

  const workspaceTabs: TabItem[] = [
    {
      key: "overview",
      label: "概览",
      icon: <LayoutDashboard size={15} aria-hidden="true" />,
    },
    {
      key: "process",
      label: "研究过程",
      count: events.length,
      icon: <Activity size={15} aria-hidden="true" />,
    },
    {
      key: "analysis",
      label: "多 Agent 分析",
      count:
        data.status === "completed"
          ? (result.data?.lens_deliberations.length ?? 0)
          : undefined,
      icon: <Layers3 size={15} aria-hidden="true" />,
    },
    {
      key: "evidence",
      label: "研究证据",
      count:
        data.status === "completed"
          ? (result.data?.evidence.length ?? ledgerCounts.evidenceCount)
          : ledgerCounts.evidenceCount,
      icon: <Database size={15} aria-hidden="true" />,
    },
  ];

  return (
    <div className="page">
      <div className="stack stack-5">
        <Link to="/" className="row row-gap-2 muted run-back-link">
          <ArrowLeft size={15} aria-hidden="true" />
          返回研究首页
        </Link>

        <section className="card card-pad run-hero">
          <div className="run-hero-top">
            <div className="stack stack-3" style={{ minWidth: 0, flex: 1 }}>
              <h1 className="page-title" style={{ fontSize: "var(--text-2xl)" }}>
                {data.request.question}
              </h1>
              <div className="row row-gap-2 wrap">
                <span className="chip chip-accent">{data.request.category}</span>
                <span className="chip">未来 {data.request.forecast_horizon_years} 年</span>
                <span className="chip">{data.request.candidate_count} 个候选</span>
                {data.request.regions.map((region) => (
                  <span className="chip chip-outline" key={region}>
                    {region}
                  </span>
                ))}
              </div>
            </div>

            <div className="stack stack-2 run-hero-meta">
              <StatusBadge status={data.status} />
              <span className="subtle row row-gap-2" style={{ fontSize: "var(--text-xs)" }}>
                <Clock size={12} aria-hidden="true" />
                创建于 {formatDateTime(data.created_at)}
              </span>
              <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
                {data.id}
              </span>
            </div>
          </div>

          <Tabs
            items={workspaceTabs}
            active={workspaceTab}
            onChange={(key) => selectWorkspaceTab(key as WorkspaceTabKey)}
            ariaLabel="研究工作台"
          />
        </section>

        {workspaceTab === "overview" && (
          <div className="run-overview-layout">
            <div className="stack stack-5">
              {data.status === "completed" && result.data ? (
                <>
                  <RunCompletionSnapshot
                    runId={data.id}
                    result={result.data}
                    artifacts={artifactList}
                    events={events}
                  />
                  <ResearchContextPanel request={data.request} />
                </>
              ) : (
                <ResearchCenter
                  status={data.status}
                  stage={data.stage}
                  error={data.error}
                  regions={data.request.regions}
                  result={result}
                  artifacts={artifactList}
                  events={events}
                />
              )}
            </div>

            <div className="run-side-stack">
              <ResearchLedger artifacts={artifactList} events={events} active={!isFinished} />
            </div>
          </div>
        )}

        {workspaceTab === "process" && (
          <div className="stack stack-5">
            <div className="run-process-layout">
              <div className="process-left-stack" ref={processStageRef}>
                <ResearchStageView activeStageKey={activeStageKey} failed={status === "failed"} />
              </div>

              <div className="process-right-stack">
                <TimelinePanel
                  events={events}
                  connection={connection}
                  targetHeight={processTimelineHeight}
                />
              </div>
            </div>

            <AgentRoster events={events} />
          </div>
        )}

        {workspaceTab === "analysis" && (
          <RunAnalysisWorkspace
            status={data.status}
            error={data.error}
            result={result}
            artifacts={artifactList}
            events={events}
          />
        )}

        {workspaceTab === "evidence" && (
          <div className="run-evidence-layout">
            <div className="stack stack-5">
              <ResearchContextPanel request={data.request} />
            </div>

            <div className="stack stack-5">
              <RunEvidenceWorkspace
                status={data.status}
                error={data.error}
                result={result}
                artifacts={artifactList}
              />
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

function TimelinePanel({
  events,
  connection,
  targetHeight,
}: {
  events: AgentEvent[];
  connection: ConnectionState;
  targetHeight?: number | null;
}) {
  const [showHistory, setShowHistory] = useState(false);
  const recentCount = 10;
  const ordered = [...events].reverse();
  const recentEvents = ordered.slice(0, recentCount);
  const olderEvents = ordered.slice(recentCount);

  return (
    <div
      className="panel process-timeline-panel"
      style={targetHeight ? { height: `${targetHeight}px` } : undefined}
    >
      <div className="panel-head">
        <span className="panel-title">
          <Activity size={16} aria-hidden="true" /> 实时活动
        </span>
        <ConnectionPill state={connection} />
      </div>
      <div className="panel-body panel-scroll process-timeline-body">
        {events.length === 0 ? (
          <div className="stack stack-3">
            <SkeletonText lines={4} />
            <span className="subtle center" style={{ fontSize: "var(--text-xs)" }}>
              正在等待第一条事件…
            </span>
          </div>
        ) : (
          <div className="stack stack-4">
            <AgentTimeline events={recentEvents} newestFirst={false} />

            {olderEvents.length > 0 && (
              <div className="timeline-history">
                <button
                  type="button"
                  className="timeline-history-toggle"
                  aria-expanded={showHistory}
                  onClick={() => setShowHistory((value) => !value)}
                >
                  <span className="timeline-history-label">
                    更早活动记录
                    <span className="timeline-history-count">{olderEvents.length} 条</span>
                  </span>
                  <ChevronDown
                    size={15}
                    aria-hidden="true"
                    className={`timeline-history-chevron ${showHistory ? "is-expanded" : ""}`}
                  />
                </button>

                {showHistory && <AgentTimeline events={olderEvents} newestFirst={false} />}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResearchFailurePanel({ error }: { error: string | null }) {
  return (
    <div className="card card-pad">
      <div className="alert alert-danger" role="alert">
        <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
        <div className="alert-body">
          <span className="alert-title">研究任务执行失败</span>
          <span>{error || "未知错误，请返回重新发起研究。"}</span>
        </div>
      </div>
      <div className="row row-gap-3" style={{ marginTop: "var(--space-4)" }}>
        <Link to="/">
          <Button variant="primary">重新发起研究</Button>
        </Link>
      </div>
    </div>
  );
}

interface ResearchCenterProps {
  status: RunStatus;
  stage: string;
  error: string | null;
  regions: string[];
  result: ReturnType<typeof useRunResult>;
  artifacts: Artifact[];
  events: AgentEvent[];
}

function ResearchCenter({
  status,
  stage,
  error,
  regions,
  result,
  artifacts,
  events,
}: ResearchCenterProps) {
  if (status === "failed") {
    return <ResearchFailurePanel error={error} />;
  }

  if (status !== "completed") {
    return (
      <LiveResearchCanvas stage={stage} regions={regions} events={events} artifacts={artifacts} />
    );
  }

  if (result.isLoading) {
    return (
      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">正在载入研究报告…</span>
        <SkeletonText lines={6} />
      </div>
    );
  }

  if (result.isError || !result.data) {
    return (
      <div className="card card-pad">
        <ErrorState title="无法载入研究报告" error={result.error} onRetry={() => result.refetch()} />
      </div>
    );
  }

  return <MultiAgentResearchReport result={result.data} artifacts={artifacts} events={events} />;
}

function SummaryStat({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="summary-stat">
      <span className="summary-stat-label">
        {icon}
        {label}
      </span>
      <span className="summary-stat-value">{value}</span>
    </div>
  );
}

function RunCompletionSnapshot({
  runId,
  result,
  artifacts,
  events,
}: {
  runId: string;
  result: ForecastResult;
  artifacts: Artifact[];
  events: AgentEvent[];
}) {
  const metrics = aggregateArtifactMetrics(artifacts);
  const degradation = deriveDegradation(events);

  return (
    <div className="stack stack-5">
      <div className="card card-pad research-summary">
        <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
          <span className="eyebrow">Research Workspace · 结果摘要</span>
          <span className={`badge ${degradation.degraded ? "badge-degraded" : "badge-completed"}`}>
            <CheckCircle2 size={12} aria-hidden="true" />
            {degradation.degraded ? "已降级完成" : "研究完成"}
          </span>
        </div>
        <div className="summary-grid">
          <SummaryStat
            icon={<Database size={12} aria-hidden="true" />}
            label="证据"
            value={`${result.evidence.length} 条`}
          />
          <SummaryStat
            icon={<Swords size={12} aria-hidden="true" />}
            label="竞品资料"
            value={`${result.competitor_evidence.length} 条`}
          />
          <SummaryStat
            icon={<Cpu size={12} aria-hidden="true" />}
            label="完成 Agent"
            value={`${completedAgentCount(events)} 个`}
          />
          <SummaryStat
            icon={<Gauge size={12} aria-hidden="true" />}
            label="总 Token"
            value={metrics.totalTokens.toLocaleString()}
          />
          <SummaryStat
            icon={<Clock size={12} aria-hidden="true" />}
            label="研究耗时"
            value={formatDurationMs(metrics.totalDurationMs)}
          />
          <SummaryStat
            icon={<ScrollText size={12} aria-hidden="true" />}
            label="产品候选"
            value={`${result.candidates.length} 个`}
          />
        </div>
      </div>

      {degradation.degraded ? (
        <div className="alert alert-warn" role="status">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">研究已降级继续完成</span>
            <span>
              当前结果可用，但包含 {degradation.count} 个降级环节。建议先查看“多 Agent 分析”和研究证据，再进入产品定义选择候选。
            </span>
          </div>
        </div>
      ) : (
        <div className="alert alert-success" role="status">
          <CheckCircle2 size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">研究完成，等待人工选择</span>
            <span>Agent 分析已保留在实时研究中，候选产品已经转移到独立的“产品定义”页面。</span>
          </div>
        </div>
      )}

      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">下一步</span>
        <strong>进入产品定义，对比并选择候选产品</strong>
        <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
          实时研究保留完整分析过程；产品定义负责候选比较、人工选择和最终 ProductSpec。
        </span>
        <div>
          <Link to={`/runs/${encodeURIComponent(runId)}/product-definition`}>
            <Button variant="primary">进入产品定义并选择</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

function RunEvidenceWorkspace({
  status,
  error,
  result,
  artifacts,
}: {
  status: RunStatus;
  error: string | null;
  result: ReturnType<typeof useRunResult>;
  artifacts: Artifact[];
}) {
  if (status === "failed") {
    return <ResearchFailurePanel error={error} />;
  }

  if (status === "completed") {
    if (result.isLoading) {
      return (
        <div className="card card-pad stack stack-3">
          <span className="opp-section-label">正在载入研究证据…</span>
          <SkeletonText lines={6} />
        </div>
      );
    }

    if (result.isError || !result.data) {
      return (
        <div className="card card-pad">
          <ErrorState title="无法载入研究证据" error={result.error} onRetry={() => result.refetch()} />
        </div>
      );
    }

    return <EvidenceLibrary evidence={result.data.evidence} />;
  }

  if (artifacts.length > 0) {
    return (
      <div className="stack stack-5">
        <div className="card card-pad stack stack-3">
          <span className="opp-section-label">研究证据正在累积</span>
          <strong>当前展示的是已经产出的中间研究产物</strong>
          <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
            完成后，这里会自动切换成完整的证据库视图，方便你按证据逐条审阅。
          </span>
        </div>
        <IntermediateArtifacts artifacts={artifacts} />
      </div>
    );
  }

  return (
    <div className="card card-pad stack stack-3">
      <span className="opp-section-label">研究证据</span>
      <strong>证据还在准备中</strong>
      <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
        当前还没有可展示的证据或中间产物，等第一批检索结果出来后会显示在这里。
      </span>
    </div>
  );
}

function RunAnalysisWorkspace({
  status,
  error,
  result,
  artifacts,
  events,
}: {
  status: RunStatus;
  error: string | null;
  result: ReturnType<typeof useRunResult>;
  artifacts: Artifact[];
  events: AgentEvent[];
}) {
  if (status === "failed") {
    return <ResearchFailurePanel error={error} />;
  }

  if (status !== "completed") {
    return (
      <div className="card card-pad stack stack-4 run-empty-state">
        <span className="opp-section-label">多 Agent 分析</span>
        <strong>结构化分析仍在生成中</strong>
        <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
          各 Agent 的独立判断、交叉质疑和观点修正会在相应阶段完成后写入研究产物。
        </span>
        {artifacts.length > 0 && <IntermediateArtifacts artifacts={artifacts} />}
      </div>
    );
  }

  if (result.isLoading) {
    return (
      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">正在载入多 Agent 分析…</span>
        <SkeletonText lines={6} />
      </div>
    );
  }

  if (result.isError || !result.data) {
    return (
      <div className="card card-pad">
        <ErrorState title="无法载入多 Agent 分析" error={result.error} onRetry={() => result.refetch()} />
      </div>
    );
  }

  return <MultiAgentResearchReport result={result.data} artifacts={artifacts} events={events} />;
}

function MultiAgentResearchReport({
  result,
  artifacts,
  events,
}: {
  result: ForecastResult;
  artifacts: Artifact[];
  events: AgentEvent[];
}) {
  const metrics = aggregateArtifactMetrics(artifacts);
  const degradation = deriveDegradation(events);
  return (
    <div className="stack stack-5">
      <div className="card card-pad research-summary">
        <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
          <span className="eyebrow">Research Report · 研究总览</span>
          <span className={`badge ${degradation.degraded ? "badge-degraded" : "badge-completed"}`}>
            <CheckCircle2 size={12} aria-hidden="true" />
            {degradation.degraded ? "已降级完成" : "研究完成"}
          </span>
        </div>
        <div className="summary-grid">
          <SummaryStat
            icon={<Database size={12} aria-hidden="true" />}
            label="证据"
            value={`${result.evidence.length} 条`}
          />
          <SummaryStat
            icon={<Swords size={12} aria-hidden="true" />}
            label="竞品资料"
            value={`${result.competitor_evidence.length} 条`}
          />
          <SummaryStat
            icon={<Cpu size={12} aria-hidden="true" />}
            label="完成 Agent"
            value={`${completedAgentCount(events)} 个`}
          />
          <SummaryStat
            icon={<Gauge size={12} aria-hidden="true" />}
            label="总 Token"
            value={metrics.totalTokens.toLocaleString()}
          />
          <SummaryStat
            icon={<Clock size={12} aria-hidden="true" />}
            label="研究耗时"
            value={formatDurationMs(metrics.totalDurationMs)}
          />
          {degradation.degraded && (
            <SummaryStat
              icon={<AlertTriangle size={12} aria-hidden="true" />}
              label="降级环节"
              value={`${degradation.count} 项`}
            />
          )}
        </div>
      </div>

      {degradation.degraded ? (
        <div className="alert alert-warn" role="status">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">研究已降级继续完成</span>
            <span>
              以下环节因模型限制或个别 Agent 失败而降级，其余分析已正常完成。结果并非“完整验证”，
              请结合降级说明查看：
            </span>
            {degradation.reasons.length > 0 && (
              <ul className="degraded-reasons">
                {degradation.reasons.map((item, index) => (
                  <li key={`${item.stage}-${index}`}>
                    <span className="chip chip-outline">{item.stage}</span> {item.reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : (
        <div className="alert alert-success" role="status">
          <CheckCircle2 size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">研究完成，等待人工选择</span>
            <span>以下为完整多 Agent 分析记录；候选比较与选择请进入左侧“产品定义”。</span>
          </div>
        </div>
      )}

      <MultiAgentAnalysis result={result} />
    </div>
  );
}
