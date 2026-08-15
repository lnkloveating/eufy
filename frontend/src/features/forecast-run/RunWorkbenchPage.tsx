import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
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

import type {
  AgentEvent,
  Artifact,
  ForecastRequest,
  ForecastResult,
  RunStatus,
} from "../../types/api";
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
import { Dialog } from "../../components/ui/Dialog";
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

type WorkspaceTabKey = "overview" | "process" | "analysis" | "evidence" | "ledger";

const WORKSPACE_TAB_KEYS = new Set<WorkspaceTabKey>([
  "overview",
  "process",
  "analysis",
  "evidence",
  "ledger",
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
  const [proposalDetailsOpen, setProposalDetailsOpen] = useState(false);

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
    {
      key: "ledger",
      label: "研究台账",
      icon: <Gauge size={15} aria-hidden="true" />,
    },
  ];

  return (
    <div className="page">
      <div className="stack stack-5">
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
              <div className="row row-gap-2 wrap">
                <span className="chip chip-outline">{data.request.target_users.join("、")}</span>
                <span className="chip chip-outline">{data.request.price_segment ?? "未限定"}</span>
                {data.request.constraints.map((constraint) => (
                  <span className="chip chip-accent" key={constraint}>
                    {constraint}
                  </span>
                ))}
              </div>
            </div>

            <div className="stack stack-2 run-hero-meta">
              <StatusBadge status={data.status} />
              <Button
                variant="secondary"
                size="sm"
                iconStart={<ScrollText size={14} aria-hidden="true" />}
                onClick={() => setProposalDetailsOpen(true)}
              >
                查看提案细节
              </Button>
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
          <div className="stack stack-5">
            <ResearchContextPanel request={data.request} />
            {data.status === "completed" && result.data ? (
              null
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
          <div className="stack stack-5">
            <RunEvidenceWorkspace
              status={data.status}
              error={data.error}
              result={result}
              artifacts={artifactList}
            />
          </div>
        )}

        {workspaceTab === "ledger" && (
          <div className="stack stack-5">
            <ResearchLedger artifacts={artifactList} events={events} active={!isFinished} />
          </div>
        )}

        <ProposalDetailsDialog
          open={proposalDetailsOpen}
          onClose={() => setProposalDetailsOpen(false)}
          request={data.request}
        />

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

function isEvidenceRelatedFailure(error: string | null): boolean {
  if (!error) return false;

  const normalized = error.toLowerCase();
  return (
    normalized.includes("insufficient_evidence") ||
    normalized.includes("evidence insufficient") ||
    normalized.includes("evidence bundle") ||
    normalized.includes("????")
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

function ProposalDetailsDialog({
  open,
  onClose,
  request,
}: {
  open: boolean;
  onClose: () => void;
  request: ForecastRequest;
}) {
  const contextItems: { label: string; value: string }[] = [
    { label: "住房类型", value: request.research_context.housing_types.join("、") || "未填写" },
    {
      label: "家庭成员",
      value: request.research_context.household_members.join("、") || "未填写",
    },
    {
      label: "安全场景",
      value: request.research_context.security_scenarios.join("、") || "未填写",
    },
    {
      label: "现有设备",
      value: request.research_context.current_devices.join("、") || "未填写",
    },
    {
      label: "痛点",
      value: request.research_context.pain_points.join("、") || "未填写",
    },
    {
      label: "允许传感器",
      value: request.research_context.allowed_sensors.join("、") || "未填写",
    },
    {
      label: "隐私偏好",
      value: request.research_context.privacy_preferences.join("、") || "未填写",
    },
    {
      label: "安装约束",
      value: request.research_context.installation_constraints.join("、") || "未填写",
    },
    {
      label: "连接约束",
      value: request.research_context.connectivity_constraints.join("、") || "未填写",
    },
    {
      label: "商业偏好",
      value: request.research_context.business_preferences.join("、") || "未填写",
    },
    {
      label: "期望结果",
      value: request.research_context.desired_outcomes.join("、") || "未填写",
    },
    {
      label: "验证优先级",
      value: request.research_context.validation_priorities.join("、") || "未填写",
    },
    {
      label: "创新姿态",
      value: request.research_context.innovation_posture ?? "未填写",
    },
  ];
  const weightItems = Object.entries(request.weights);

  return (
    <Dialog
      open={open}
      title="完整提案详情"
      onClose={onClose}
      size="xl"
    >
      <div className="stack stack-4">
        <div className="card card-pad stack stack-3">
          <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
            <span className="eyebrow">Research Brief · 输入追溯</span>
            <span className="chip chip-outline">{request.category}</span>
          </div>
          <span className="opp-section-label">提案摘要</span>
          <strong style={{ fontSize: "var(--text-lg)", lineHeight: 1.35 }}>
            {request.question}
          </strong>
          <div className="metagrid">
            <MetaItem label="预测周期" value={`未来 ${request.forecast_horizon_years} 年`} />
            <MetaItem label="地区" value={request.regions.join("、")} />
            <MetaItem label="目标用户" value={request.target_users.join("、")} />
            <MetaItem label="价格带" value={request.price_segment ?? "未限定"} />
            <MetaItem label="候选数量" value={`${request.candidate_count} 个`} />
            <MetaItem label="策略档位" value={request.strategy_profile} />
          </div>
          {request.constraints.length > 0 ? (
            <div className="row wrap row-gap-2">
              {request.constraints.map((constraint) => (
                <span className="chip chip-accent" key={constraint}>
                  {constraint}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="card card-pad stack stack-3">
          <span className="opp-section-label">研究上下文</span>
          <div className="metagrid">
            {contextItems.map((item) => (
              <MetaItem key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
        </div>

        <div className="card card-pad stack stack-3">
          <span className="opp-section-label">策略权重</span>
          <div className="metagrid">
            {weightItems.map(([key, value]) => (
              <MetaItem key={key} label={key} value={`${Math.round(value * 100)}%`} />
            ))}
          </div>
        </div>
      </div>
    </Dialog>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span className="meta-label">{label}</span>
      <span className="meta-value">{value}</span>
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
    if (artifacts.length > 0 && isEvidenceRelatedFailure(error)) {
      return (
        <div className="stack stack-5">
          <ResearchFailurePanel error={error} />
          <IntermediateArtifacts
            artifacts={artifacts}
            defaultEvidenceBundleExpanded
          />
        </div>
      );
    }

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

