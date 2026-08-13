import clsx from "clsx";
import type { AgentEvent } from "../../types/api";
import { getAgentLabel } from "../../lib/agentLabels";
import { formatClock } from "../../lib/formatters";

export interface AgentTimelineProps {
  events: AgentEvent[];
  /** Newest first (default) reads best for a live activity feed. */
  newestFirst?: boolean;
}

const DONE_EVENTS = new Set([
  "run_completed",
  "agent_completed",
  "reviews_completed",
  "opportunities_created",
  "candidates_created",
  "evidence_selected",
  "product_definition_completed",
]);
const START_EVENTS = new Set([
  "run_queued",
  "agent_started",
  "product_definition_started",
]);

function dotClass(eventType: string): string {
  if (eventType === "run_failed") return "tl-fail";
  if (DONE_EVENTS.has(eventType)) return "tl-done";
  if (START_EVENTS.has(eventType)) return "tl-start";
  return "";
}

/** Vertical activity / trace feed of agent events (deduped upstream). */
export function AgentTimeline({ events, newestFirst = true }: AgentTimelineProps) {
  const ordered = newestFirst ? [...events].reverse() : events;

  return (
    <div className="timeline">
      {ordered.map((event) => (
        <div className="tl-item" key={event.sequence}>
          <div className="tl-rail">
            <span className={clsx("tl-dot", dotClass(event.event_type))} />
            <span className="tl-line" />
          </div>
          <div className="tl-body">
            <div className="tl-head">
              <span className="tl-agent">{getAgentLabel(event.agent)}</span>
              <span className="tl-time">{formatClock(event.created_at)}</span>
            </div>
            <div className="tl-msg">{event.message}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
