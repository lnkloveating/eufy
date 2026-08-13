import clsx from "clsx";
import type { ReactNode } from "react";
import { Check, FileText, Loader2 } from "lucide-react";
import type { AgentEvent, Artifact } from "../../types/api";
import { getAgentLabel, getAgentRole } from "../../lib/agentLabels";
import { formatDurationMs } from "./researchMetrics";

export type AgentStatus = "idle" | "running" | "done";

const COMPLETED_EVENTS = new Set([
  "agent_completed",
  "product_definition_completed",
  "evidence_selected",
]);
const STARTED_EVENTS = new Set(["agent_started", "product_definition_started"]);

/** Live status for a single agent derived from the event stream. */
export function agentStatus(events: AgentEvent[], agent: string): AgentStatus {
  let status: AgentStatus = "idle";
  for (const event of events) {
    if (event.agent !== agent) continue;
    if (STARTED_EVENTS.has(event.event_type)) status = "running";
    if (COMPLETED_EVENTS.has(event.event_type)) status = "done";
  }
  return status;
}

/** Count artifacts produced by an agent + total duration reported. */
function agentArtifacts(artifacts: Artifact[], agent: string): { count: number; durationMs: number } {
  let count = 0;
  let durationMs = 0;
  for (const artifact of artifacts) {
    if (artifact.producer === agent) {
      count += 1;
      if (typeof artifact.duration_ms === "number") durationMs += artifact.duration_ms;
    }
  }
  return { count, durationMs };
}

export interface AgentActivityCardProps {
  agent: string;
  icon: ReactNode;
  status: AgentStatus;
  artifactCount: number;
  durationMs: number;
}

export function AgentActivityCard({
  agent,
  icon,
  status,
  artifactCount,
  durationMs,
}: AgentActivityCardProps) {
  return (
    <div
      className={clsx("activity-card", {
        "is-running": status === "running",
        "is-done": status === "done",
      })}
    >
      <div className="row row-gap-3" style={{ minWidth: 0 }}>
        <span className="agent-avatar">{icon}</span>
        <div className="agent-meta">
          <div className="agent-name">{getAgentLabel(agent)}</div>
          <div className="agent-role">{getAgentRole(agent)}</div>
        </div>
        <span className="agent-state">
          {status === "done" ? (
            <span className="badge badge-completed">
              <Check size={12} aria-hidden="true" /> 完成
            </span>
          ) : status === "running" ? (
            <span className="badge badge-running">
              <Loader2 size={12} className="spin-inline" aria-hidden="true" /> 分析中
            </span>
          ) : (
            <span className="badge badge-pending">待启动</span>
          )}
        </span>
      </div>
      <div className="activity-foot">
        <span className="subtle row row-gap-2" style={{ fontSize: "var(--text-xs)" }}>
          <FileText size={11} aria-hidden="true" />
          {artifactCount > 0 ? `${artifactCount} 份产物` : "尚无产物"}
        </span>
        {status === "done" && durationMs > 0 && (
          <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
            {formatDurationMs(durationMs)}
          </span>
        )}
      </div>
    </div>
  );
}

export interface AgentActivityGridProps {
  agents: { agent: string; icon: ReactNode }[];
  events: AgentEvent[];
  artifacts: Artifact[];
}

/** A grid of parallel-agent activity cards (lens panel / review panel). */
export function AgentActivityGrid({ agents, events, artifacts }: AgentActivityGridProps) {
  return (
    <div className="activity-grid">
      {agents.map(({ agent, icon }) => {
        const info = agentArtifacts(artifacts, agent);
        return (
          <AgentActivityCard
            key={agent}
            agent={agent}
            icon={icon}
            status={agentStatus(events, agent)}
            artifactCount={info.count}
            durationMs={info.durationMs}
          />
        );
      })}
    </div>
  );
}
