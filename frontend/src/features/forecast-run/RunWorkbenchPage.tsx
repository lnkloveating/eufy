import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Gauge,
  Radio,
  Swords,
} from "lucide-react";

import type { AgentEvent, Artifact, ForecastResult } from "../../types/api";
import { useRun, useRunArtifacts, useRunResult } from "../../lib/queries";
import { formatDateTime } from "../../lib/formatters";
import { ApiError } from "../../lib/api/client";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { AgentTimeline } from "../../components/AgentTimeline/AgentTimeline";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { Skeleton, SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { RunResultTabs } from "./RunResultTabs";
import { ResearchStageView } from "./ResearchStageView";
import { ResearchLedger } from "./ResearchLedger";
import { LiveResearchCanvas } from "./LiveResearchCanvas";
import { useRunEvents, type ConnectionState } from "./useRunEvents";
import { aggregateArtifactMetrics, formatDurationMs } from "./researchMetrics";

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

/**
 * Read the terminal run_completed event's degraded metadata. A degraded run is
 * still COMPLETED (never FAILED) but must be shown honestly — not as a fully
 * verified analysis.
 */
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
  const run = useRun(runId);
  const status = run.data?.status;
  const isFinished = status === "completed" || status === "failed";

  const { events, connection } = useRunEvents(runId, isFinished);
  const result = useRunResult(runId, status === "completed");
  const artifacts = useRunArtifacts(runId, !isFinished);
  const artifactList = artifacts.data ?? [];

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
  const activeStageKey =
    status === "completed"
      ? "awaiting_product_selection"
      : status === "failed"
        ? deriveStage(events)
        : data.stage;

  return (
    <div className="page">
      <div className="page-header stack stack-4">
        <div className="row between wrap row-gap-3">
          <Link to="/" className="row row-gap-2 muted" style={{ fontSize: "var(--text-sm)" }}>
            <ArrowLeft size={15} aria-hidden="true" />
            返回研究首页
          </Link>
          <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
            {data.id}
          </span>
        </div>

        <div className="row between wrap row-gap-3" style={{ alignItems: "flex-start" }}>
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
          <div className="stack stack-2" style={{ alignItems: "flex-end" }}>
            <StatusBadge status={data.status} />
            <span className="subtle row row-gap-2" style={{ fontSize: "var(--text-xs)" }}>
              <Clock size={12} aria-hidden="true" />
              创建于 {formatDateTime(data.created_at)}
            </span>
          </div>
        </div>
      </div>

      <div className="research-grid">
        <aside className="research-col research-left">
          <ResearchStageView activeStageKey={activeStageKey} failed={status === "failed"} />
        </aside>

        <section className="research-col research-center">
          <ResearchCenter
            runId={data.id}
            status={data.status}
            stage={data.stage}
            error={data.error}
            regions={data.request.regions}
            result={result}
            artifacts={artifactList}
            events={events}
          />
        </section>

        <aside className="research-col research-right">
          <ResearchLedger artifacts={artifactList} events={events} active={!isFinished} />
          <div className="panel">
            <div className="panel-head">
              <span className="panel-title">
                <Activity size={16} aria-hidden="true" /> 实时活动
              </span>
              <ConnectionPill state={connection} />
            </div>
            <div className="panel-body panel-scroll" style={{ maxHeight: 460 }}>
              {events.length === 0 ? (
                <div className="stack stack-3">
                  <SkeletonText lines={4} />
                  <span className="subtle center" style={{ fontSize: "var(--text-xs)" }}>
                    正在等待第一条事件…
                  </span>
                </div>
              ) : (
                <AgentTimeline events={events} />
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

interface ResearchCenterProps {
  runId: string;
  status: "pending" | "running" | "completed" | "failed";
  stage: string;
  error: string | null;
  regions: string[];
  result: ReturnType<typeof useRunResult>;
  artifacts: Artifact[];
  events: AgentEvent[];
}

function ResearchCenter({
  runId,
  status,
  stage,
  error,
  regions,
  result,
  artifacts,
  events,
}: ResearchCenterProps) {
  if (status === "failed") {
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

  return <ResearchReport runId={runId} result={result.data} artifacts={artifacts} events={events} />;
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

function ResearchReport({
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
            <span className="alert-title">研究已降级继续完成，等待人工选择</span>
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
            <span>请在“产品候选”中对比方案，并自由选择任意方向生成标准 ProductSpec。</span>
          </div>
        </div>
      )}

      <RunResultTabs runId={runId} result={result} />
    </div>
  );
}
