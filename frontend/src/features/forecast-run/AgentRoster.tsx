import clsx from "clsx";
import {
  Boxes,
  Check,
  ChevronDown,
  Cpu,
  Database,
  Gavel,
  Loader2,
  ShieldQuestion,
  TrendingUp,
  Users,
  Swords,
  Scale,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { AgentEvent } from "../../types/api";
import { getAgentLabel, getAgentRole } from "../../lib/agentLabels";
import { getDefaultExpandedGroups, type CollapsibleGroupState } from "../../lib/collapsible";

type AgentStatus = "idle" | "running" | "done";

interface RosterEntry {
  agent: string;
  icon: ReactNode;
}

interface RosterGroup {
  label: string;
  entries: RosterEntry[];
}

const GROUPS: RosterGroup[] = [
  {
    label: "证据检索",
    entries: [{ agent: "local-evidence-store", icon: <Database size={17} /> }],
  },
  {
    label: "多视角未来预测",
    entries: [
      { agent: "futures-user_trends", icon: <Users size={17} /> },
      { agent: "futures-technology_trends", icon: <Cpu size={17} /> },
      { agent: "futures-security_futures", icon: <ShieldQuestion size={17} /> },
      { agent: "futures-market_futures", icon: <TrendingUp size={17} /> },
    ],
  },
  {
    label: "交叉审核与共识",
    entries: [
      { agent: "deliberator-user_trends", icon: <Users size={17} /> },
      { agent: "deliberator-technology_trends", icon: <Cpu size={17} /> },
      { agent: "deliberator-security_futures", icon: <ShieldQuestion size={17} /> },
      { agent: "deliberator-market_futures", icon: <TrendingUp size={17} /> },
      { agent: "forecast-consensus", icon: <Scale size={17} /> },
    ],
  },
  {
    label: "机会与产品",
    entries: [
      { agent: "opportunity-synthesizer", icon: <Boxes size={17} /> },
      { agent: "competitor-analysis", icon: <Swords size={17} /> },
      { agent: "current-product-auditor", icon: <ShieldQuestion size={17} /> },
      { agent: "product-architect", icon: <Boxes size={17} /> },
      { agent: "candidate-novelty-auditor", icon: <ShieldQuestion size={17} /> },
      { agent: "portfolio-diversity-auditor", icon: <ShieldQuestion size={17} /> },
    ],
  },
  {
    label: "多维盲评委员会",
    entries: [
      { agent: "reviewer-innovation", icon: <Gavel size={17} /> },
      { agent: "reviewer-user_value", icon: <Gavel size={17} /> },
      { agent: "reviewer-business_value", icon: <Gavel size={17} /> },
      { agent: "reviewer-feasibility", icon: <Gavel size={17} /> },
      { agent: "reviewer-eufy_synergy", icon: <Gavel size={17} /> },
    ],
  },
];

const STARTED_EVENTS = new Set(["agent_started", "product_definition_started"]);
const COMPLETED_EVENTS = new Set([
  "agent_completed",
  "product_definition_completed",
  "evidence_selected",
]);

/** Derive each agent's live status from the event stream. */
function computeStatuses(events: AgentEvent[]): Record<string, AgentStatus> {
  const latest: Record<string, AgentStatus> = {};
  for (const event of events) {
    if (!event.agent) continue;
    if (STARTED_EVENTS.has(event.event_type)) latest[event.agent] = "running";
    if (COMPLETED_EVENTS.has(event.event_type)) latest[event.agent] = "done";
  }
  const statuses: Record<string, AgentStatus> = {};
  for (const group of GROUPS) {
    for (const entry of group.entries) {
      statuses[entry.agent] = latest[entry.agent] ?? "idle";
    }
  }
  return statuses;
}

function StatePill({ status }: { status: AgentStatus }) {
  if (status === "done") {
    return (
      <span className="badge badge-completed">
        <Check size={12} aria-hidden="true" />
        完成
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="badge badge-running">
        <Loader2 size={12} className="spin-inline" aria-hidden="true" />
        运行中
      </span>
    );
  }
  return <span className="badge badge-pending">待启动</span>;
}

export interface AgentRosterProps {
  events: AgentEvent[];
}

/** Left-rail roster showing every agent and its live execution state. */
export function AgentRoster({ events }: AgentRosterProps) {
  const statuses = computeStatuses(events);
  const done = Object.values(statuses).filter((s) => s === "done").length;
  const total = Object.values(statuses).length;
  const groupStates = useMemo(
    () =>
      GROUPS.map((group) => {
        const values = group.entries.map((entry) => statuses[entry.agent] ?? "idle");
        let state: CollapsibleGroupState = "idle";
        if (values.some((value) => value === "running")) state = "running";
        else if (values.some((value) => value === "done")) state = "done";
        return { key: group.label, state };
      }),
    [statuses],
  );
  const defaultExpanded = useMemo<Record<string, boolean>>(
    () => getDefaultExpandedGroups(groupStates),
    [groupStates],
  );
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(defaultExpanded);

  const toggleGroup = (label: string) => {
    setExpandedGroups((current) => ({
      ...current,
      [label]: !(current[label] ?? defaultExpanded[label] ?? true),
    }));
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">
          <Cpu size={16} aria-hidden="true" /> 智能体团队
        </span>
        <span className="chip">
          {done}/{total} 完成
        </span>
      </div>
      <div className="panel-body stack stack-2">
        {GROUPS.map((group) => {
          const completedCount = group.entries.filter(
            (entry) => statuses[entry.agent] === "done",
          ).length;
          const runningCount = group.entries.filter(
            (entry) => statuses[entry.agent] === "running",
          ).length;
          const isExpanded = expandedGroups[group.label] ?? defaultExpanded[group.label] ?? true;

          return (
            <div className="agent-group" key={group.label}>
              <button
                type="button"
                className="agent-group-toggle"
                aria-expanded={isExpanded}
                onClick={() => toggleGroup(group.label)}
              >
                <span className="agent-group-heading">
                  <span className="agent-group-label">{group.label}</span>
                  <span className="agent-group-meta">
                    {completedCount}/{group.entries.length}
                    {runningCount > 0 ? ` · 运行中 ${runningCount}` : ""}
                  </span>
                </span>
                <ChevronDown
                  size={15}
                  aria-hidden="true"
                  className={clsx("agent-group-chevron", isExpanded && "is-expanded")}
                />
              </button>

              {isExpanded && (
                <div className="stack stack-2">
                  {group.entries.map((entry) => {
                    const status = statuses[entry.agent] ?? "idle";
                    return (
                      <div
                        key={entry.agent}
                        className={clsx("agent-item", {
                          "is-running": status === "running",
                          "is-done": status === "done",
                        })}
                      >
                        <span className="agent-avatar">{entry.icon}</span>
                        <div className="agent-meta">
                          <div className="agent-name">{getAgentLabel(entry.agent)}</div>
                          <div className="agent-role">{getAgentRole(entry.agent)}</div>
                        </div>
                        <span className="agent-state">
                          <StatePill status={status} />
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
